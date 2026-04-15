"""
Couche 0 — Filtre de scope (modèle cheap / rapide).

Décide en amont si la requête utilisateur est dans le périmètre
de MONV (prospection B2B) ou totalement hors-scope.
Retourne un booléen ``in_scope`` + optionnellement un message de rejet.
"""

from __future__ import annotations

from pydantic import BaseModel
from utils.llm import llm_json_call
from config import settings


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


async def run_filter(user_message: str) -> FilterResult:
    """Filtre rapide : la requête est-elle dans le scope de MONV ?"""
    try:
        result = await llm_json_call(
            model=settings.FILTER_MODEL,
            system=FILTER_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_message}],
            max_tokens=32,
            temperature=0.0,
        )
        return FilterResult(in_scope=bool(result.get("in_scope", False)))
    except Exception:
        # En cas d'erreur technique, on laisse passer (fail-open)
        return FilterResult(in_scope=True)
