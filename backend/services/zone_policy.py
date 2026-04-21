"""
Politique de zone géographique pour le Guard / le chat.

Toute recherche d'entreprises ou de dirigeants doit disposer d'une zone
explicitement posée par l'utilisateur (ville, département, région, ou périmètre
national clair). Sinon on force ``zone_geo`` dans les critères manquants.
"""

from __future__ import annotations

import re
import unicodedata

from models.schemas import GuardEntity

_SEARCH_INTENTS = frozenset({"recherche_entreprise", "recherche_dirigeant"})

# Formulations explicites d'un périmètre national / France entière (message utilisateur).
_NATIONAL_SCOPE_RE = re.compile(
    r"(?:"
    r"france\s+enti[eè]re|toute\s+la\s+france|partout\s+en\s+france|"
    r"tout\s+le\s+territoire\s+(?:fran[cç]ais|national)?|"
    r"[eé]chelle\s+nationale|nationalement|"
    r"au\s+niveau\s+national|sans\s+limite\s+g[eé]ographique|"
    r"pas\s+de\s+limite\s+g[eé]ographique|"
    r"ensemble\s+du\s+territoire|"
    r"h[eé]xagone|m[eé]tropole\s+fran[cç]aise"
    r")",
    re.IGNORECASE,
)

# « … en France » comme cible géographique (pas « entreprise française » seul).
_EN_FRANCE_GEO_RE = re.compile(
    r"(?:^|\s)(?:en|sur|dans|à)\s+la\s+france(?:\s|$|[,\.!?])",
    re.IGNORECASE,
)


def _fold(s: str) -> str:
    return "".join(
        c
        for c in unicodedata.normalize("NFD", (s or "").lower())
        if unicodedata.category(c) != "Mn"
    )


def _blank(v: str | None) -> bool:
    return v is None or not str(v).strip()


def entity_has_resolved_geography(e: GuardEntity) -> bool:
    """True si une zone exploitable est présente dans les entités."""
    return not (_blank(e.localisation) and _blank(e.departement) and _blank(e.region))


def apply_natural_scope_from_user_message(user_message: str, e: GuardEntity) -> None:
    """
    Si le message affirme un périmètre national explicite, renseigne ``region``
    pour éviter un QCM zone inutile.
    """
    if entity_has_resolved_geography(e):
        return
    raw = user_message or ""
    if _NATIONAL_SCOPE_RE.search(raw) or _EN_FRANCE_GEO_RE.search(raw):
        e.region = "France (périmètre national)"


def corroborate_zone_entities(user_message: str, e: GuardEntity) -> None:
    """
    Retire localisation / département / région si elles ne sont pas soutenues
    par le texte utilisateur (réduit les inférences erronées du modèle).
    """
    msg = _fold(user_message or "")

    def _token_supported(token: str) -> bool:
        t = _fold(token.strip())
        if len(t) < 3:
            return t in msg
        if t in msg:
            return True
        parts = [p for p in re.split(r"[\s,/-]+", t) if len(p) >= 3]
        return any(p in msg for p in parts)

    if not _blank(e.localisation) and not _token_supported(str(e.localisation)):
        e.localisation = None
    if not _blank(e.departement) and not _token_supported(str(e.departement)):
        e.departement = None
    if not _blank(e.region) and not _token_supported(str(e.region)):
        e.region = None


def post_process_guard_geography(
    user_message: str,
    intent: str,
    entities: GuardEntity,
    missing_final: list[str],
    clarification_needed_final: bool,
) -> bool:
    """
    Après extraction LLM : corrige les zones, applique le scope national textuel,
    puis impose ``zone_geo`` si la recherche cible des établissements/dirigeants
    sans zone résolue. Modifie ``missing_final`` en place.

    Retourne ``clarification_needed`` mis à jour.
    """
    if intent not in _SEARCH_INTENTS:
        return clarification_needed_final

    corroborate_zone_entities(user_message, entities)
    apply_natural_scope_from_user_message(user_message, entities)

    if entity_has_resolved_geography(entities):
        return clarification_needed_final

    if "zone_geo" not in missing_final:
        missing_final.append("zone_geo")
    return True
