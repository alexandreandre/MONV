"""
Fusion des constantes Python (défaut) avec les overrides Supabase (version active).

Cache court par agent_id pour limiter la charge PostgREST.
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from typing import Any

from config import settings
from models.db import agent_version_active_get, get_supabase

_cache: dict[str, tuple[float, dict[str, Any]]] = {}
_lock = asyncio.Lock()


def invalidate_agent_config_cache(agent_id: str | None = None) -> None:
    if agent_id:
        _cache.pop(agent_id, None)
    else:
        _cache.clear()


async def _fetch_overrides(agent_id: str) -> dict[str, Any]:
    try:
        client = get_supabase()
        row = await agent_version_active_get(client, agent_id)
        if not row:
            return {}
        raw = row.get("overrides_json") or {}
        return raw if isinstance(raw, dict) else {}
    except Exception:
        return {}


async def get_active_overrides(agent_id: str) -> dict[str, Any]:
    ttl = float(settings.AGENT_CONFIG_CACHE_SECONDS or 30.0)
    now = time.monotonic()
    async with _lock:
        hit = _cache.get(agent_id)
        if hit and (now - hit[0]) < ttl:
            return hit[1]
    overrides = await _fetch_overrides(agent_id)
    async with _lock:
        _cache[agent_id] = (now, overrides)
    return overrides


@dataclass
class ResolvedLlmBlock:
    model: str
    system_prompt: str
    max_tokens: int
    temperature: float
    top_p: float


async def resolve_llm_for_block(
    agent_id: str,
    block_id: str,
    *,
    default_model: str,
    default_system: str,
    default_max_tokens: int,
    default_temperature: float,
    default_top_p: float = 1.0,
) -> ResolvedLlmBlock:
    """Applique l'override du bloc s'il existe dans la version active."""
    overrides = await get_active_overrides(agent_id)
    raw = overrides.get(block_id)
    if not isinstance(raw, dict):
        raw = {}
    if raw.get("enabled") is False:
        return ResolvedLlmBlock(
            model=default_model,
            system_prompt=default_system,
            max_tokens=default_max_tokens,
            temperature=default_temperature,
            top_p=default_top_p,
        )

    model = (raw.get("model") or "").strip() or default_model
    sp = raw.get("system_prompt")
    if isinstance(sp, str) and sp.strip():
        system_prompt = sp.strip()
    else:
        system_prompt = default_system

    mt = raw.get("max_tokens")
    try:
        max_tokens = int(mt) if mt is not None else default_max_tokens
    except (TypeError, ValueError):
        max_tokens = default_max_tokens

    t = raw.get("temperature")
    try:
        temperature = float(t) if t is not None else default_temperature
    except (TypeError, ValueError):
        temperature = default_temperature

    tp = raw.get("top_p")
    try:
        top_p = float(tp) if tp is not None else default_top_p
    except (TypeError, ValueError):
        top_p = default_top_p

    return ResolvedLlmBlock(
        model=model,
        system_prompt=system_prompt,
        max_tokens=max(1, max_tokens),
        temperature=max(0.0, min(2.0, temperature)),
        top_p=max(0.0, min(1.0, top_p)),
    )


async def resolve_llm_call_only(
    agent_id: str,
    block_id: str,
    *,
    default_model: str,
    default_max_tokens: int,
    default_temperature: float,
    default_top_p: float = 1.0,
) -> tuple[str, int, float, float]:
    """Pour les appels sans prompt système dédié (ex. llm_call titre)."""
    r = await resolve_llm_for_block(
        agent_id,
        block_id,
        default_model=default_model,
        default_system="",
        default_max_tokens=default_max_tokens,
        default_temperature=default_temperature,
        default_top_p=default_top_p,
    )
    return r.model, r.max_tokens, r.temperature, r.top_p
