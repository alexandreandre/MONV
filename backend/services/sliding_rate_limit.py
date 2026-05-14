"""
Fenêtre glissante en mémoire (processus unique).

Pour plusieurs workers, prévoir un store partagé (Redis) ou un reverse-proxy
rate-limit en amont.
"""

from __future__ import annotations

import time
from collections import defaultdict
from threading import Lock

_lock = Lock()
_buckets: dict[str, list[float]] = defaultdict(list)


def check_sliding_window(key: str, max_events: int, window_s: float) -> bool:
    """
    Enregistre un événement pour ``key`` si la limite n'est pas dépassée.

    Retourne True si l'appel est autorisé, False si rate-limit.
    """
    if max_events <= 0 or window_s <= 0:
        return True
    now = time.monotonic()
    threshold = now - window_s
    with _lock:
        dq = _buckets[key]
        while dq and dq[0] < threshold:
            dq.pop(0)
        if len(dq) >= max_events:
            return False
        dq.append(now)
    return True


def reset_sliding_window(key: str | None = None) -> None:
    """Tests / admin : vide un seau ou tout le cache."""
    with _lock:
        if key is None:
            _buckets.clear()
        else:
            _buckets.pop(key, None)
