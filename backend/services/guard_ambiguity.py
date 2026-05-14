"""
Second passage Guard — ambiguïté sectorielle (prompt long).

Invoqué uniquement si ``message_triggers_sector_ambiguity_check`` est vrai
(lexique dérivé de la liste du prompt), pour éviter d’empiler ~12k tokens
sur la majorité des requêtes.
"""

from __future__ import annotations

import re
import unicodedata
from pathlib import Path

from config import settings

_PROMPT_PATH = Path(__file__).with_name("_guard_sector_ambiguity_prompt.txt")
GUARD_SECTOR_AMBIGUITY_SYSTEM_PROMPT = _PROMPT_PATH.read_text(encoding="utf-8")

# Sous-chaînes : termes extraits du prompt (guillemets en tête de puce) de longueur >= _SUBSTR_MIN
_SUBSTR_MIN_LEN = 9


def _fold_accents(s: str) -> str:
    nfkd = unicodedata.normalize("NFD", s)
    return "".join(c for c in nfkd if unicodedata.category(c) != "Mn").lower()


def _extract_quoted_lemmas(prompt_text: str) -> list[str]:
    pat = re.compile(r'^- "([^"]+)"', re.MULTILINE)
    out: list[str] = []
    for q in pat.findall(prompt_text):
        for part in re.split(r"\s*/\s*", q):
            p = part.strip().lower()
            if p:
                out.append(_fold_accents(p))
    return out


def _build_trigger_sets(prompt_text: str) -> tuple[frozenset[str], frozenset[str]]:
    lemmas = sorted(set(_extract_quoted_lemmas(prompt_text)), key=lambda x: (-len(x), x))
    substr = frozenset(t for t in lemmas if len(t) >= _SUBSTR_MIN_LEN)
    short = frozenset(t for t in lemmas if len(t) < _SUBSTR_MIN_LEN)
    # « ia » / « vr » souvent seuls en message
    extra = frozenset(
        _fold_accents(x)
        for x in (
            "ia",
            "vr",
            "peche",
            "cafe",
            "e-commerce",
            "e commerce",
            "garde enfant",
        )
    )
    short |= {e for e in extra if len(e) < _SUBSTR_MIN_LEN}
    substr |= {e for e in extra if len(e) >= _SUBSTR_MIN_LEN}
    return substr, short


_SUBSTR_TRIGGERS, _SHORT_TRIGGERS = _build_trigger_sets(GUARD_SECTOR_AMBIGUITY_SYSTEM_PROMPT)


def message_triggers_sector_ambiguity_check(user_message: str) -> bool:
    """True si le message contient un lexème « à risque » (second passage utile)."""
    if not settings.GUARD_SECTOR_AMBIGUITY_SECOND_PASS:
        return False
    raw = (user_message or "").strip()
    if len(raw) < 2:
        return False
    folded = _fold_accents(raw)
    for sub in _SUBSTR_TRIGGERS:
        if sub in folded:
            return True
    tokens = set(re.findall(r"[\w'-]+", folded, flags=re.UNICODE))
    for w in _SHORT_TRIGGERS:
        if len(w) >= 5:
            if w in folded:
                return True
        elif w in tokens:
            return True
    return False


def _parse_bool_llm(value: object, default: bool = False) -> bool:
    if value is True:
        return True
    if value is False:
        return False
    if isinstance(value, str):
        return value.strip().lower() in ("true", "1", "yes", "oui")
    return default


async def run_guard_sector_ambiguity(
    user_message: str,
    *,
    agent_id: str = "prospection",
    block_id: str = "guard_sector_ambiguity",
) -> bool:
    """Appel LLM ciblé : uniquement ``sector_ambiguous`` (JSON minimal)."""
    from services.agent_config import resolve_llm_for_block
    from utils.llm import llm_json_call

    cfg = await resolve_llm_for_block(
        agent_id,
        block_id,
        default_model=settings.GUARD_MODEL,
        default_system=GUARD_SECTOR_AMBIGUITY_SYSTEM_PROMPT,
        default_max_tokens=128,
        default_temperature=0.0,
    )
    out = await llm_json_call(
        model=cfg.model,
        system=cfg.system_prompt,
        messages=[{"role": "user", "content": user_message}],
        max_tokens=cfg.max_tokens,
        temperature=cfg.temperature,
        json_mode=True,
        usage_stage="guard_sector_ambiguity",
    )
    return _parse_bool_llm(out.get("sector_ambiguous"), False)
