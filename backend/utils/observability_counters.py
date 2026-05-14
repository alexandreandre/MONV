"""
Compteurs process-local pour signaux rares (repli pertinence, etc.).

Consultation : ``GET /api/admin/observability-counters``. Multi-workers : agréger côté proxy ou exporter OTel.
"""

from __future__ import annotations

import threading
from typing import Any

_lock = threading.Lock()
_counters: dict[str, int] = {
    "relevance_fallback_all_rejected": 0,
}


def increment_counter(name: str, delta: int = 1) -> None:
    with _lock:
        _counters[name] = _counters.get(name, 0) + max(0, delta)


def get_counters() -> dict[str, Any]:
    with _lock:
        return dict(_counters)


def reset_counters() -> None:
    """Tests uniquement."""
    with _lock:
        for k in list(_counters.keys()):
            _counters[k] = 0
