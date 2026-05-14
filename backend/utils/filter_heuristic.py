"""
Second seuil léger si le filtre scope LLM échoue (voir ``FILTER_LLM_ERROR_POLICY``).

Sans dépendance applicative : importable dans les tests sans Supabase.
"""

from __future__ import annotations

import re

_OUT_SCOPE_HINTS: tuple[str, ...] = (
    "poème",
    "poem",
    "blague",
    "raconte-moi",
    "raconte moi",
    "écris-moi",
    "écris moi",
    "code python",
    "aide-moi à coder",
    "traduis ",
    "résume ",
    "resume ",
    "capitale du",
    "capitale de",
    "météo",
    "meteo",
    "recette de",
    "recipe for",
)

_IN_SCOPE_HINTS: tuple[str, ...] = (
    "entreprise",
    "société",
    "societe",
    "siren",
    "siret",
    " naf",
    "naf ",
    "code naf",
    "pme",
    "eti",
    " esn",
    "esn ",
    " btp",
    "btp ",
    "prospect",
    "client",
    "fournisseur",
    "prestataire",
    "sous-traitant",
    "sous traitant",
    "partenaire",
    "dirigeant",
    "pdg",
    " gérant",
    "gerant",
    "cherche",
    "trouve",
    "trouve-moi",
    "liste ",
    "recherche",
    "secteur",
    "effectif",
    "département",
    "departement",
    " région",
    "region ",
    " monv",
    "crédit",
    "credit",
    "export",
    "sirene",
    "insee",
)

_GREETING_ONLY = re.compile(
    r"^(bonjour|salut|coucou|hello|hi|hey|merci|thanks|thank you|bonsoir)"
    r"[\s!.?]*$",
    re.IGNORECASE,
)


def skip_filter_llm_if_heuristic_strong(user_message: str) -> bool:
    """
    Si True, on peut éviter l'appel LLM du filtre scope : signal fort in-scope uniquement.

    Conservateur : en cas de doute, renvoie False (on garde le LLM).
    """
    s = (user_message or "").strip()
    if not s or len(s) > 8000:
        return False
    if not heuristic_in_scope(s):
        return False
    if _GREETING_ONLY.match(s):
        return True
    if len(s) >= 48:
        return True
    low = s.lower()
    if re.search(r"\b\d{9}\b", s) or re.search(r"\b\d{14}\b", s):
        return True
    if "code naf" in low or "siret" in low or "siren" in low:
        return True
    if (
        "trouve-moi" in low
        or "trouve moi" in low
        or "je cherche" in low
    ):
        return True
    return False


def heuristic_in_scope(user_message: str) -> bool:
    """
    Heuristique conservatrice : préfère rejeter l'ambigu.

    Utilisée quand ``FILTER_LLM_ERROR_POLICY=heuristic_then_closed``.
    """
    s = (user_message or "").strip().lower()
    if not s or len(s) > 8000:
        return False
    for bad in _OUT_SCOPE_HINTS:
        if bad in s:
            return False
    if _GREETING_ONLY.match(s):
        return True
    for good in _IN_SCOPE_HINTS:
        if good in s:
            return True
    return False
