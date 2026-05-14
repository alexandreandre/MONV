"""
Cache mémoire process-local pour réponses SIRENE / Google Places (recherches read-only).

TTL court par défaut : réduit la charge sur les API publiques lors de requêtes répétées
ou de plans multi-appels identiques. Désactivable via ``CONNECTOR_CACHE_ENABLED``.
"""

from __future__ import annotations

import hashlib
import json
import threading
import time
from collections import OrderedDict
from typing import Any

from config import settings
from models.schemas import CompanyResult


_lock = threading.Lock()
_lru: OrderedDict[str, tuple[float, list[dict[str, Any]]]] = OrderedDict()


def _cache_key(prefix: str, params: dict[str, Any]) -> str:
    raw = json.dumps(params, sort_keys=True, default=str)
    h = hashlib.sha256(raw.encode()).hexdigest()[:20]
    return f"{prefix}:{h}"


def _max_keys() -> int:
    return max(32, int(getattr(settings, "CONNECTOR_CACHE_MAX_KEYS", 256) or 256))


def _ttl_s() -> float:
    return float(getattr(settings, "CONNECTOR_CACHE_TTL_S", 300.0) or 300.0)


def connector_cache_enabled() -> bool:
    return bool(getattr(settings, "CONNECTOR_CACHE_ENABLED", True))


def connector_cache_get(prefix: str, params: dict[str, Any]) -> list[CompanyResult] | None:
    if not connector_cache_enabled():
        return None
    key = _cache_key(prefix, params)
    now = time.monotonic()
    with _lock:
        item = _lru.get(key)
        if item is None:
            return None
        expires_at, payload = item
        if expires_at < now:
            del _lru[key]
            return None
        _lru.move_to_end(key)
    out: list[CompanyResult] = []
    for d in payload:
        try:
            out.append(CompanyResult.model_validate(d))
        except Exception:
            return None
    return out


def connector_cache_set(prefix: str, params: dict[str, Any], results: list[CompanyResult]) -> None:
    if not connector_cache_enabled():
        return
    key = _cache_key(prefix, params)
    payload = [r.model_dump(mode="json") for r in results]
    expires_at = time.monotonic() + _ttl_s()
    max_keys = _max_keys()
    with _lock:
        _lru[key] = (expires_at, payload)
        _lru.move_to_end(key)
        while len(_lru) > max_keys:
            _lru.popitem(last=False)


def connector_cache_stats() -> dict[str, Any]:
    with _lock:
        n = len(_lru)
    return {
        "enabled": connector_cache_enabled(),
        "entries": n,
        "ttl_s": _ttl_s(),
        "max_keys": _max_keys(),
    }


def connector_cache_clear() -> None:
    with _lock:
        _lru.clear()
