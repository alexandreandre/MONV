"""
Jobs chat asynchrones (spike) : POST démarre une tâche en arrière-plan, GET interroge l'état.

Stockage mémoire process-local — adapté au dev / worker unique. Les jobs expirés sont purgés
à la lecture et à l'enregistrement (TTL ``CHAT_ASYNC_JOB_RESULT_TTL_S``).
"""

from __future__ import annotations

import asyncio
import threading
import time
import traceback
from typing import Any

from config import settings
from models.schemas import ChatRequest

_lock = threading.Lock()
_jobs: dict[str, dict[str, Any]] = {}


def _ttl_s() -> float:
    return float(getattr(settings, "CHAT_ASYNC_JOB_RESULT_TTL_S", 3600.0) or 3600.0)


def _max_jobs() -> int:
    return max(10, int(getattr(settings, "CHAT_ASYNC_JOBS_MAX", 200) or 200))


def _prune_unlocked(now: float) -> None:
    ttl = _ttl_s()
    dead = [k for k, v in _jobs.items() if now - float(v.get("created", now)) > ttl + 60]
    for k in dead:
        _jobs.pop(k, None)
    if len(_jobs) <= _max_jobs():
        return
    # Retire les plus anciens par created
    sorted_ids = sorted(_jobs.keys(), key=lambda x: float(_jobs[x].get("created", 0)))
    while len(_jobs) > _max_jobs() and sorted_ids:
        _jobs.pop(sorted_ids.pop(0), None)


def register_job(job_id: str, *, user_id: str) -> None:
    now = time.time()
    with _lock:
        _prune_unlocked(now)
        _jobs[job_id] = {
            "job_id": job_id,
            "user_id": user_id,
            "status": "pending",
            "created": now,
        }


def set_job(job_id: str, patch: dict[str, Any]) -> None:
    with _lock:
        if job_id not in _jobs:
            return
        _jobs[job_id].update(patch)


def get_job(job_id: str) -> dict[str, Any] | None:
    now = time.time()
    with _lock:
        _prune_unlocked(now)
        row = _jobs.get(job_id)
        if row is None:
            return None
        return dict(row)


def launch_chat_job_task(job_id: str, req: ChatRequest, user_id: str) -> None:
    """Lance ``asyncio.create_task`` sans bloquer la réponse HTTP."""

    req_snapshot = req.model_copy(deep=True)

    async def _runner() -> None:
        set_job(job_id, {"status": "running"})
        try:
            from models.db import get_supabase, user_by_id
            from routers.chat import _process_chat_send_core

            supabase = get_supabase()
            user = await user_by_id(supabase, user_id)
            if user is None:
                set_job(job_id, {"status": "failed", "error": "Utilisateur introuvable"})
                return
            resp = await _process_chat_send_core(req_snapshot, user, supabase)
            set_job(
                job_id,
                {
                    "status": "completed",
                    "conversation_id": resp.conversation_id,
                    "response": resp.model_dump(mode="json"),
                },
            )
        except Exception as e:
            set_job(
                job_id,
                {
                    "status": "failed",
                    "error": str(e),
                    "trace_tail": traceback.format_exc()[-2000:],
                },
            )

    try:
        loop = asyncio.get_running_loop()
        loop.create_task(_runner())
    except RuntimeError:
        set_job(job_id, {"status": "failed", "error": "no_event_loop"})
