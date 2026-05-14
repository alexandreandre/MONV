"""
Échantillonnage des durées du pipeline chat (filtre → pitch) pour p50/p95 côté admin.

Peut inclure des totaux tokens LLM cumulés par requête : ``llm_prompt_tokens``,
``llm_completion_tokens``, ``llm_total_tokens``, ``llm_calls`` (voir ``utils.llm`` +
``routers.chat``).

Anneau mémoire process-local : utile en dev et sur un worker unique ; pour du multi-worker,
exporter vers Prometheus / OTel plutôt que s'appuyer sur cet agrégat seul.
"""

from __future__ import annotations

import threading
import time
from collections import deque
from typing import Any

from config import settings
from utils.pipeline_log import plog

_lock = threading.Lock()
_samples: deque[dict[str, Any]] = deque()


def _percentile(sorted_vals: list[float], p: float) -> float | None:
    if not sorted_vals:
        return None
    if len(sorted_vals) == 1:
        return sorted_vals[0]
    k = (len(sorted_vals) - 1) * (p / 100.0)
    f = int(k)
    c = min(f + 1, len(sorted_vals) - 1)
    if f == c:
        return sorted_vals[f]
    return sorted_vals[f] + (sorted_vals[c] - sorted_vals[f]) * (k - f)


def record_chat_pipeline_sample(mode: str, stages_ms: dict[str, float | None]) -> None:
    """Enregistre un échantillon (durées en millisecondes, clés optionnelles absentes ou None)."""
    max_n = max(50, int(getattr(settings, "PIPELINE_TIMING_MAX_SAMPLES", 500) or 500))
    row: dict[str, Any] = {
        "ts": time.time(),
        "mode": mode,
    }
    for k, v in stages_ms.items():
        if v is not None and isinstance(v, (int, float)):
            row[k] = round(float(v), 2)

    with _lock:
        _samples.append(row)
        while len(_samples) > max_n:
            _samples.popleft()

    if getattr(settings, "PIPELINE_DEBUG", False):
        plog("pipeline_timing_sample", mode=mode, stages_ms={k: v for k, v in row.items() if k not in ("ts", "mode")})


def get_pipeline_timing_summary() -> dict[str, Any]:
    """Résumé p50/p95/moyenne par étape + derniers échantillons."""
    max_n = max(50, int(getattr(settings, "PIPELINE_TIMING_MAX_SAMPLES", 500) or 500))
    with _lock:
        rows = list(_samples)[-max_n:]

    if not rows:
        return {"sample_count": 0, "by_stage": {}, "recent": []}

    numeric_keys: set[str] = set()
    for r in rows:
        for k, v in r.items():
            if k not in ("ts", "mode") and isinstance(v, (int, float)):
                numeric_keys.add(k)

    by_stage: dict[str, dict[str, float | int | None]] = {}
    for key in sorted(numeric_keys):
        vals = sorted(float(r[key]) for r in rows if key in r and isinstance(r[key], (int, float)))
        if not vals:
            continue
        by_stage[key] = {
            "n": len(vals),
            "avg_ms": round(sum(vals) / len(vals), 2),
            "p50_ms": round(_percentile(vals, 50) or 0, 2),
            "p95_ms": round(_percentile(vals, 95) or 0, 2),
        }

    recent = rows[-20:]
    return {
        "sample_count": len(rows),
        "by_stage": by_stage,
        "recent": recent,
    }


def reset_pipeline_timing_samples() -> None:
    """Tests / admin : vide l'anneau."""
    with _lock:
        _samples.clear()
