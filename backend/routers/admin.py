"""
API Super Admin — graphes agents, versions, tests, logs.

Préfixe : ``/api/admin``. Accès réservé aux emails listés dans ``ADMIN_EMAILS``.
"""

from __future__ import annotations

import asyncio
import json
import time
from datetime import datetime, timedelta, timezone
from typing import Any, AsyncIterator

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from supabase import Client

from config import settings
from models.admin_schemas import (
    AdminMeOut,
    AdminSettingsOut,
    AgentGraphOut,
    AgentSummaryOut,
    AgentTestRequest,
    AgentTestResponse,
    AgentVersionCreate,
    AgentVersionOut,
)
from models.db import (
    agent_run_get,
    agent_run_insert,
    agent_run_step_insert,
    agent_run_steps_list,
    agent_run_update,
    agent_runs_list,
    agent_version_active_get,
    agent_version_deactivate_all,
    agent_version_get,
    agent_version_insert,
    agent_versions_list,
    agent_version_next_number,
    agent_version_update,
    agent_runs_count_errors_since,
    agent_runs_count_since,
    get_supabase,
)
from models.entities import User, gen_uuid
from routers.auth import get_current_user
from services.agent_config import invalidate_agent_config_cache
from services.agent_registry import AGENT_IDS, MODE_LABELS, get_agent_graph_definition
from services.filter import run_filter
from services.guard import run_guard
from services.modes import normalize_mode
from services.orchestrator import maybe_clamp_prospection_after_plan_patches, run_orchestrator
from utils.admin_policy import user_is_admin
from utils.pipeline_timing import get_pipeline_timing_summary
from utils.connector_cache import connector_cache_stats
from utils.observability_counters import get_counters

router = APIRouter(prefix="/api/admin", tags=["admin"])


async def require_admin(
    user: User = Depends(get_current_user),
) -> User:
    if not user_is_admin(user):
        raise HTTPException(403, "Accès administrateur refusé")
    return user


def _version_row_to_out(row: dict[str, Any]) -> AgentVersionOut:
    return AgentVersionOut(
        id=str(row["id"]),
        agent_id=str(row["agent_id"]),
        version_number=int(row["version_number"]),
        label=str(row.get("label") or ""),
        overrides_json=row.get("overrides_json") or {},
        created_by=str(row["created_by"]) if row.get("created_by") else None,
        created_at=row["created_at"],
        is_active=bool(row.get("is_active")),
        parent_version_id=str(row["parent_version_id"]) if row.get("parent_version_id") else None,
    )


def _merge_graph_effective(graph: dict[str, Any], overrides: dict[str, Any]) -> dict[str, Any]:
    out = json.loads(json.dumps(graph))
    for node in out.get("nodes", []):
        nid = node.get("id")
        if not nid:
            continue
        ov = overrides.get(nid) if isinstance(overrides, dict) else None
        if not isinstance(ov, dict):
            node["effective"] = None
            continue
        eff: dict[str, Any] = {"enabled": ov.get("enabled", True)}
        if ov.get("model"):
            eff["model"] = ov["model"]
        if ov.get("system_prompt"):
            eff["system_prompt_preview"] = (ov["system_prompt"][:280] + "…") if len(str(ov["system_prompt"])) > 280 else ov["system_prompt"]
        for k in ("temperature", "max_tokens", "top_p"):
            if k in ov and ov[k] is not None:
                eff[k] = ov[k]
        node["effective"] = eff
    return out


@router.get("/pipeline-timing")
async def admin_pipeline_timing(user: User = Depends(require_admin)) -> dict[str, Any]:
    """p50/p95 par étape du pipeline chat (anneau mémoire process)."""
    del user
    return get_pipeline_timing_summary()


@router.get("/connector-cache")
async def admin_connector_cache(user: User = Depends(require_admin)) -> dict[str, Any]:
    """Statistiques du cache SIRENE / Google Places (process-local)."""
    del user
    return connector_cache_stats()


@router.get("/observability-counters")
async def admin_observability_counters(user: User = Depends(require_admin)) -> dict[str, Any]:
    """Compteurs process-local (signaux rares du pipeline, ex. repli pertinence)."""
    del user
    return {"counters": get_counters()}


@router.get("/me", response_model=AdminMeOut)
async def admin_me(user: User = Depends(require_admin)) -> AdminMeOut:
    return AdminMeOut(email=user.email)


@router.get("/agents", response_model=list[AgentSummaryOut])
async def list_agents(
    user: User = Depends(require_admin),
    supabase: Client = Depends(get_supabase),
):
    del user
    since_24h = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()
    since_7d = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
    out: list[AgentSummaryOut] = []
    for aid in AGENT_IDS:
        label = "Atelier création d'entreprise" if aid == "atelier" else MODE_LABELS.get(aid, aid)  # type: ignore[arg-type]
        active_row = None
        try:
            active_row = await agent_version_active_get(supabase, aid)
        except Exception:
            active_row = None
        active_version_id = str(active_row["id"]) if active_row else None
        active_vn = int(active_row["version_number"]) if active_row else None
        last_mod = active_row["created_at"] if active_row else None
        primary = settings.ORCHESTRATOR_MODEL
        if aid == "atelier":
            primary = (settings.ATELIER_BUSINESS_MODEL or settings.ORCHESTRATOR_MODEL).strip() or settings.ORCHESTRATOR_MODEL
        err_ct = 0
        runs_ct = 0
        try:
            err_ct = await agent_runs_count_errors_since(supabase, aid, since_24h)
            runs_ct = await agent_runs_count_since(supabase, aid, since_7d)
        except Exception:
            pass
        out.append(
            AgentSummaryOut(
                agent_id=aid,
                label=label,
                active_version_id=active_version_id,
                active_version_number=active_vn,
                last_modified_at=last_mod,
                primary_model=primary,
                errors_24h=err_ct,
                runs_7d=runs_ct,
            )
        )
    return out


@router.get("/agents/{agent_id}/graph", response_model=AgentGraphOut)
async def get_agent_graph(
    agent_id: str,
    user: User = Depends(require_admin),
    supabase: Client = Depends(get_supabase),
):
    del user
    if agent_id not in AGENT_IDS:
        raise HTTPException(404, "Agent inconnu")
    base = get_agent_graph_definition(agent_id)
    active = None
    overrides: dict[str, Any] = {}
    try:
        row = await agent_version_active_get(supabase, agent_id)
        if row:
            active = _version_row_to_out(row)
            overrides = row.get("overrides_json") or {}
            if not isinstance(overrides, dict):
                overrides = {}
    except Exception:
        active = None
    merged_graph = _merge_graph_effective(base["graph"], overrides)
    label = base["label"]
    return AgentGraphOut(
        agent_id=agent_id,
        label=label,
        graph=merged_graph,
        active_version=active,
    )


@router.get("/agents/{agent_id}/versions", response_model=list[AgentVersionOut])
async def list_versions(
    agent_id: str,
    user: User = Depends(require_admin),
    supabase: Client = Depends(get_supabase),
):
    del user
    if agent_id not in AGENT_IDS:
        raise HTTPException(404, "Agent inconnu")
    try:
        rows = await agent_versions_list(supabase, agent_id, limit=200)
    except Exception as e:
        raise HTTPException(503, f"Base admin non disponible : {e}") from e
    return [_version_row_to_out(r) for r in rows]


@router.get("/agents/{agent_id}/versions/{version_id}", response_model=AgentVersionOut)
async def get_version(
    agent_id: str,
    version_id: str,
    user: User = Depends(require_admin),
    supabase: Client = Depends(get_supabase),
):
    del user
    row = await agent_version_get(supabase, version_id)
    if not row or str(row["agent_id"]) != agent_id:
        raise HTTPException(404, "Version introuvable")
    return _version_row_to_out(row)


@router.post("/agents/{agent_id}/versions", response_model=AgentVersionOut)
async def create_version(
    agent_id: str,
    body: AgentVersionCreate,
    user: User = Depends(require_admin),
    supabase: Client = Depends(get_supabase),
):
    if agent_id not in AGENT_IDS:
        raise HTTPException(404, "Agent inconnu")
    vn = await agent_version_next_number(supabase, agent_id)
    row = {
        "id": gen_uuid(),
        "agent_id": agent_id,
        "version_number": vn,
        "label": (body.label or f"v{vn}")[:500],
        "overrides_json": body.overrides or {},
        "created_by": user.id,
        "is_active": False,
    }
    try:
        ins = await agent_version_insert(supabase, row)
    except Exception as e:
        raise HTTPException(
            503,
            "Table agent_versions absente ou erreur SQL. Exécutez la migration 004_admin_agents.sql.",
        ) from e
    return _version_row_to_out(ins)


@router.post("/agents/{agent_id}/versions/{version_id}/publish", response_model=AgentVersionOut)
async def publish_version(
    agent_id: str,
    version_id: str,
    user: User = Depends(require_admin),
    supabase: Client = Depends(get_supabase),
):
    del user
    row = await agent_version_get(supabase, version_id)
    if not row or str(row["agent_id"]) != agent_id:
        raise HTTPException(404, "Version introuvable")
    await agent_version_deactivate_all(supabase, agent_id)
    await agent_version_update(supabase, version_id, {"is_active": True})
    invalidate_agent_config_cache(agent_id)
    row2 = await agent_version_get(supabase, version_id)
    return _version_row_to_out(row2 or row)


@router.post("/agents/{agent_id}/versions/{version_id}/rollback", response_model=AgentVersionOut)
async def rollback_version(
    agent_id: str,
    version_id: str,
    user: User = Depends(require_admin),
    supabase: Client = Depends(get_supabase),
):
    old = await agent_version_get(supabase, version_id)
    if not old or str(old["agent_id"]) != agent_id:
        raise HTTPException(404, "Version introuvable")
    vn = await agent_version_next_number(supabase, agent_id)
    new_row = {
        "id": gen_uuid(),
        "agent_id": agent_id,
        "version_number": vn,
        "label": f"Rollback depuis v{old['version_number']}",
        "overrides_json": old.get("overrides_json") or {},
        "created_by": user.id,
        "is_active": False,
        "parent_version_id": str(old["id"]),
    }
    ins = await agent_version_insert(supabase, new_row)
    await agent_version_deactivate_all(supabase, agent_id)
    await agent_version_update(supabase, str(ins["id"]), {"is_active": True})
    invalidate_agent_config_cache(agent_id)
    row2 = await agent_version_get(supabase, str(ins["id"]))
    return _version_row_to_out(row2 or ins)


@router.get("/agents/{agent_id}/diff")
async def diff_versions(
    agent_id: str,
    from_version: str,
    to_version: str,
    user: User = Depends(require_admin),
    supabase: Client = Depends(get_supabase),
):
    del user
    a = await agent_version_get(supabase, from_version)
    b = await agent_version_get(supabase, to_version)
    if not a or not b or str(a["agent_id"]) != agent_id or str(b["agent_id"]) != agent_id:
        raise HTTPException(404, "Version introuvable")
    oa = a.get("overrides_json") or {}
    ob = b.get("overrides_json") or {}
    keys = sorted(set(oa.keys()) | set(ob.keys()))
    blocks: list[dict[str, Any]] = []
    for k in keys:
        blocks.append({"block_id": k, "from": oa.get(k), "to": ob.get(k)})
    return {"agent_id": agent_id, "from_version": from_version, "to_version": to_version, "blocks": blocks}


@router.get("/agents/{agent_id}/export")
async def export_agent(
    agent_id: str,
    user: User = Depends(require_admin),
    supabase: Client = Depends(get_supabase),
):
    del user
    if agent_id not in AGENT_IDS:
        raise HTTPException(404, "Agent inconnu")
    row = None
    try:
        row = await agent_version_active_get(supabase, agent_id)
    except Exception:
        row = None
    graph = get_agent_graph_definition(agent_id)
    return {
        "agent_id": agent_id,
        "label": graph["label"],
        "topology": graph["graph"],
        "active_version": _version_row_to_out(row) if row else None,
    }


@router.post("/agents/{agent_id}/import", response_model=AgentVersionOut)
async def import_agent(
    agent_id: str,
    payload: dict[str, Any],
    user: User = Depends(require_admin),
    supabase: Client = Depends(get_supabase),
):
    if agent_id not in AGENT_IDS:
        raise HTTPException(404, "Agent inconnu")
    active = payload.get("active_version")
    if not isinstance(active, dict):
        raise HTTPException(400, "Clé active_version manquante ou invalide")
    overrides = active.get("overrides_json")
    if not isinstance(overrides, dict):
        overrides = {}
    label = str(active.get("label") or "Import JSON")[:500]
    body = AgentVersionCreate(label=label, overrides=overrides)
    return await create_version(agent_id, body, user, supabase)


@router.get("/settings", response_model=AdminSettingsOut)
async def admin_settings(user: User = Depends(require_admin)):
    del user
    return AdminSettingsOut(
        models={
            "FILTER_MODEL": settings.FILTER_MODEL,
            "GUARD_MODEL": settings.GUARD_MODEL,
            "ORCHESTRATOR_MODEL": settings.ORCHESTRATOR_MODEL,
            "RELEVANCE_FILTER_MODEL": settings.RELEVANCE_FILTER_MODEL,
            "DIGITAL_PITCH_ENRICH_MODEL": settings.DIGITAL_PITCH_ENRICH_MODEL or settings.RELEVANCE_FILTER_MODEL,
            "ATELIER_BUSINESS_MODEL": settings.ATELIER_BUSINESS_MODEL or settings.ORCHESTRATOR_MODEL,
        },
        api_keys_present={
            "OPENROUTER_API_KEY": bool((settings.OPENROUTER_API_KEY or "").strip()),
            "GOOGLE_PLACES_API_KEY": bool((settings.GOOGLE_PLACES_API_KEY or "").strip()),
            "PAPPERS_API_KEY": bool((settings.PAPPERS_API_KEY or "").strip()),
        },
        flags={
            "PIPELINE_DEBUG": settings.PIPELINE_DEBUG,
            "RUN_RECORDING_ENABLED": settings.RUN_RECORDING_ENABLED,
            "DEBUG": settings.DEBUG,
        },
    )


@router.get("/runs")
async def list_runs(
    agent_id: str | None = None,
    limit: int = 50,
    offset: int = 0,
    user: User = Depends(require_admin),
    supabase: Client = Depends(get_supabase),
):
    del user
    try:
        rows = await agent_runs_list(supabase, agent_id=agent_id, limit=min(limit, 200), offset=offset)
    except Exception as e:
        raise HTTPException(503, f"Logs indisponibles : {e}") from e
    return {"items": rows, "limit": limit, "offset": offset}


@router.get("/runs/{run_id}")
async def get_run(
    run_id: str,
    user: User = Depends(require_admin),
    supabase: Client = Depends(get_supabase),
):
    del user
    run = await agent_run_get(supabase, run_id)
    if not run:
        raise HTTPException(404, "Run introuvable")
    steps = await agent_run_steps_list(supabase, run_id)
    return {"run": run, "steps": steps}


async def _record_step(
    supabase: Client,
    run_id: str,
    block_id: str,
    *,
    model_used: str,
    t0: float,
    status: str,
    input_obj: Any = None,
    output_obj: Any = None,
    err: str | None = None,
) -> None:
    t1 = time.perf_counter()
    lat_ms = int((t1 - t0) * 1000)
    row = {
        "id": gen_uuid(),
        "run_id": run_id,
        "block_id": block_id,
        "started_at": datetime.now(timezone.utc).isoformat(),
        "finished_at": datetime.now(timezone.utc).isoformat(),
        "model_used": model_used,
        "tokens_in": 0,
        "tokens_out": 0,
        "cost_usd": 0,
        "latency_ms": lat_ms,
        "status": status,
        "input_json": input_obj,
        "output_json": output_obj,
        "error_message": err,
    }
    try:
        await agent_run_step_insert(supabase, row)
    except Exception:
        pass


@router.post("/agents/{agent_id}/test", response_model=AgentTestResponse)
async def test_agent(
    agent_id: str,
    body: AgentTestRequest,
    user: User = Depends(require_admin),
    supabase: Client = Depends(get_supabase),
):
    if agent_id not in AGENT_IDS:
        raise HTTPException(404, "Agent inconnu")
    run_id = gen_uuid()
    t_run = time.perf_counter()
    steps_out: list[dict[str, Any]] = []
    active_vid = None
    try:
        ar = await agent_version_active_get(supabase, agent_id)
        if ar:
            active_vid = str(ar["id"])
    except Exception:
        pass
    try:
        await agent_run_insert(
            supabase,
            {
                "id": run_id,
                "agent_id": agent_id,
                "version_id": active_vid,
                "user_id": user.id,
                "triggered_from": "admin_test",
                "status": "running",
                "input_json": {"message": body.message},
            },
        )
    except Exception:
        run_id = gen_uuid()

    msg = (body.message or "").strip() or "Je cherche des PME du BTP à Lyon"

    if agent_id == "atelier":
        await agent_run_update(supabase, run_id, {"status": "failed", "finished_at": datetime.now(timezone.utc).isoformat(), "error_message": "Test Atelier non exécuté ici (pipeline long) — utilisez le produit Atelier."})
        return AgentTestResponse(run_id=run_id, status="failed", steps=[])

    mode = normalize_mode(agent_id)
    t0 = time.perf_counter()
    try:
        fr = await run_filter(msg, agent_id=agent_id)
        await _record_step(
            supabase,
            run_id,
            "filter",
            model_used=settings.FILTER_MODEL,
            t0=t0,
            status="completed",
            input_obj={"message": msg},
            output_obj=fr.model_dump(),
        )
        steps_out.append({"block_id": "filter", "status": "completed", "latency_ms": int((time.perf_counter() - t0) * 1000)})
    except Exception as e:
        await _record_step(
            supabase,
            run_id,
            "filter",
            model_used=settings.FILTER_MODEL,
            t0=t0,
            status="failed",
            input_obj={"message": msg},
            err=str(e)[:2000],
        )
        await agent_run_update(
            supabase,
            run_id,
            {
                "status": "failed",
                "finished_at": datetime.now(timezone.utc).isoformat(),
                "error_message": str(e)[:2000],
                "latency_ms": int((time.perf_counter() - t_run) * 1000),
            },
        )
        return AgentTestResponse(run_id=run_id, status="failed", steps=steps_out)

    if not fr.in_scope:
        await agent_run_update(
            supabase,
            run_id,
            {
                "status": "completed",
                "finished_at": datetime.now(timezone.utc).isoformat(),
                "latency_ms": int((time.perf_counter() - t_run) * 1000),
            },
        )
        return AgentTestResponse(run_id=run_id, status="completed", steps=steps_out)

    t0 = time.perf_counter()
    try:
        gr = await run_guard(msg, None, agent_id=agent_id)
        await _record_step(
            supabase,
            run_id,
            "guard",
            model_used=settings.GUARD_MODEL,
            t0=t0,
            status="completed",
            input_obj={"message": msg},
            output_obj={"intent": gr.intent, "clarification_needed": gr.clarification_needed},
        )
        steps_out.append({"block_id": "guard", "status": "completed", "latency_ms": int((time.perf_counter() - t0) * 1000)})
    except Exception as e:
        await _record_step(
            supabase,
            run_id,
            "guard",
            model_used=settings.GUARD_MODEL,
            t0=t0,
            status="failed",
            err=str(e)[:2000],
        )
        await agent_run_update(
            supabase,
            run_id,
            {
                "status": "failed",
                "finished_at": datetime.now(timezone.utc).isoformat(),
                "error_message": str(e)[:2000],
                "latency_ms": int((time.perf_counter() - t_run) * 1000),
            },
        )
        return AgentTestResponse(run_id=run_id, status="failed", steps=steps_out)

    if body.full_pipeline and gr.intent == "recherche_entreprise" and not gr.clarification_needed:
        t0 = time.perf_counter()
        try:
            plan = await run_orchestrator(gr, mode=mode)
            maybe_clamp_prospection_after_plan_patches(plan, mode, gr)
            await _record_step(
                supabase,
                run_id,
                "orchestrator",
                model_used=settings.ORCHESTRATOR_MODEL,
                t0=t0,
                status="completed",
                input_obj={"mode": mode},
                output_obj={"api_calls": [c.model_dump() for c in plan.api_calls], "estimated_credits": plan.estimated_credits},
            )
            steps_out.append({"block_id": "orchestrator", "status": "completed", "latency_ms": int((time.perf_counter() - t0) * 1000)})
        except Exception as e:
            await _record_step(
                supabase,
                run_id,
                "orchestrator",
                model_used=settings.ORCHESTRATOR_MODEL,
                t0=t0,
                status="failed",
                err=str(e)[:2000],
            )
            await agent_run_update(
                supabase,
                run_id,
                {
                    "status": "failed",
                    "finished_at": datetime.now(timezone.utc).isoformat(),
                    "error_message": str(e)[:2000],
                    "latency_ms": int((time.perf_counter() - t_run) * 1000),
                },
            )
            return AgentTestResponse(run_id=run_id, status="failed", steps=steps_out)

    await agent_run_update(
        supabase,
        run_id,
        {
            "status": "completed",
            "finished_at": datetime.now(timezone.utc).isoformat(),
            "latency_ms": int((time.perf_counter() - t_run) * 1000),
        },
    )
    return AgentTestResponse(run_id=run_id, status="completed", steps=steps_out)


@router.get("/runs/{run_id}/stream")
async def stream_run(
    run_id: str,
    user: User = Depends(require_admin),
    supabase: Client = Depends(get_supabase),
):
    del user

    async def gen() -> AsyncIterator[bytes]:
        deadline = time.monotonic() + 120.0
        last_n = -1
        iterations = 0
        while time.monotonic() < deadline and iterations < 400:
            iterations += 1
            run = await agent_run_get(supabase, run_id)
            if not run:
                yield f"data: {json.dumps({'event': 'error', 'detail': 'not_found'})}\n\n".encode()
                return
            steps = await agent_run_steps_list(supabase, run_id)
            if len(steps) != last_n:
                last_n = len(steps)
                yield f"data: {json.dumps({'event': 'steps', 'steps': steps})}\n\n".encode()
            st = str(run.get("status") or "")
            if st in ("completed", "failed"):
                yield f"data: {json.dumps({'event': 'run_completed', 'run': run})}\n\n".encode()
                return
            await asyncio.sleep(0.35)

    return StreamingResponse(gen(), media_type="text/event-stream")
