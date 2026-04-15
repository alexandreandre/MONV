"""
Logs de diagnostic pour le pipeline chat → guard → orchestrateur → APIs.

Active avec PIPELINE_DEBUG=true dans ``backend/.env``, puis redémarre uvicorn.

Les messages sont écrits sur **stderr** avec flush immédiat : ils s’affichent dans le
même terminal que uvicorn même quand la config logging d’uvicorn ignore les loggers
d’application.
"""

from __future__ import annotations

import json
import os
import sys
from typing import Any

from config import settings

_banner_shown = False


def configure_pipeline_logging() -> None:
    """Bannière une fois au démarrage pour confirmer que le mode debug pipeline est actif."""
    global _banner_shown
    if _banner_shown:
        return
    _banner_shown = True
    if not getattr(settings, "PIPELINE_DEBUG", False):
        return
    print(
        "[MONV.pipeline] PIPELINE_DEBUG activé — traces sur stderr | "
        f"cwd={os.getcwd()} | indique si .env est bien chargé depuis ce dossier",
        file=sys.stderr,
        flush=True,
    )


def _short(value: Any, max_len: int = 500) -> str:
    try:
        s = json.dumps(value, ensure_ascii=False, default=str)
    except TypeError:
        s = repr(value)
    if len(s) <= max_len:
        return s
    return s[: max_len - 1] + "…"


def plog(msg: str, **kwargs: Any) -> None:
    """Affiche une ligne sur stderr si ``settings.PIPELINE_DEBUG`` est vrai."""
    if not getattr(settings, "PIPELINE_DEBUG", False):
        return
    if kwargs:
        parts = [msg, "|"]
        for k in sorted(kwargs.keys()):
            v = kwargs[k]
            if isinstance(v, (dict, list)):
                parts.append(f"{k}={_short(v)}")
            else:
                parts.append(f"{k}={v!r}")
        msg = " ".join(parts)
    print(f"[MONV.pipeline] {msg}", file=sys.stderr, flush=True)
