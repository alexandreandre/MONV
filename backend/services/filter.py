"""
Couche 0 — Filtre de scope (modèle cheap / rapide).

Décide en amont si la requête utilisateur est dans le périmètre
de MONV (prospection B2B) ou totalement hors-scope.
Retourne un booléen ``in_scope`` + optionnellement un message de rejet.

Politique sur erreur LLM / JSON : ``FILTER_LLM_ERROR_POLICY`` dans ``config`` —
en production, préférer ``heuristic_then_closed`` ou ``fail_closed`` pour éviter
fail-open (spam / coût).
"""

from __future__ import annotations

from pydantic import BaseModel

from config import settings
from utils.filter_heuristic import heuristic_in_scope
from utils.pipeline_log import plog

FILTER_SYSTEM_PROMPT = """\
Tu es le pré-filtre de MONV, un outil de recherche d'entreprises en France.

Ta SEULE mission : décider si la requête de l'utilisateur est liée
à la recherche d'entreprises OU à l'utilisation de l'outil MONV.

IN-SCOPE (réponds true) — la requête parle de :
- Entreprises, sociétés, PME, startups, ETI
- Prospection, clients, prospects, leads
- Prestataires, fournisseurs, sous-traitants, partenaires
- Dirigeants, PDG, gérants, contacts professionnels
- Secteurs d'activité, codes NAF, SIREN, SIRET
- Villes/régions de France EN CONTEXTE d'entreprises
- L'outil MONV : crédits, fonctionnement, export
- Salutations basiques : "Bonjour", "Salut", "Merci"

HORS-SCOPE (réponds false) — la requête demande :
- Écrire du contenu créatif (poèmes, histoires, blagues)
- Culture générale (capitales, dates historiques, sciences)
- Aide au codage / programmation
- Résumé ou traduction de textes
- Conseils personnels, recettes, météo
- Toute tâche qui n'a AUCUN rapport avec les entreprises

Exemples IN-SCOPE :
"Trouve-moi des PME du BTP à Lyon" → true
"Je cherche un comptable" → true
"Bonjour" → true
"Comment marche MONV ?" → true

Exemples HORS-SCOPE :
"Écris-moi un poème" → false
"Quelle est la capitale du Japon ?" → false
"Aide-moi à coder en Python" → false
"Raconte-moi une blague" → false
"Résume ce texte" → false
"Traduis en anglais" → false
"Quel temps fait-il ?" → false

Réponds UNIQUEMENT avec un JSON valide :
{"in_scope": true}  ou  {"in_scope": false}
"""


class FilterResult(BaseModel):
    in_scope: bool


def in_scope_after_filter_llm_error(user_message: str) -> bool:
    """Décision ``in_scope`` si l'appel LLM du filtre a échoué (tests / doc)."""
    pol = (settings.FILTER_LLM_ERROR_POLICY or "fail_open").strip().lower()
    if pol == "fail_closed":
        return False
    if pol == "heuristic_then_closed":
        return heuristic_in_scope(user_message)
    return True


async def run_filter(user_message: str, *, agent_id: str = "prospection") -> FilterResult:
    """Filtre rapide : la requête est-elle dans le scope de MONV ?"""
    from services.agent_config import resolve_llm_for_block
    from utils.filter_heuristic import skip_filter_llm_if_heuristic_strong
    from utils.llm import llm_json_call

    if getattr(settings, "FILTER_HEURISTIC_SHORT_CIRCUIT", True):
        if skip_filter_llm_if_heuristic_strong(user_message):
            plog("filter_short_circuit_heuristic", agent_id=agent_id)
            return FilterResult(in_scope=True)

    cfg = await resolve_llm_for_block(
        agent_id,
        "filter",
        default_model=settings.FILTER_MODEL,
        default_system=FILTER_SYSTEM_PROMPT,
        default_max_tokens=32,
        default_temperature=0.0,
    )
    try:
        result = await llm_json_call(
            model=cfg.model,
            system=cfg.system_prompt,
            messages=[{"role": "user", "content": user_message}],
            max_tokens=cfg.max_tokens,
            temperature=cfg.temperature,
            usage_stage="filter",
        )
        if not isinstance(result, dict):
            raise ValueError("filter_json_not_object")
        return FilterResult(in_scope=bool(result.get("in_scope", False)))
    except Exception as exc:
        plog(
            "filter_llm_error",
            error=repr(exc),
            policy=settings.FILTER_LLM_ERROR_POLICY,
            heuristic_allow=heuristic_in_scope(user_message),
        )
        return FilterResult(in_scope=in_scope_after_filter_llm_error(user_message))
