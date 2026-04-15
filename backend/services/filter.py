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
(même de loin) à la recherche d'entreprises, quelle que soit la raison :
- Prospection commerciale (chercher des clients)
- Recherche de prestataires / fournisseurs
- Recherche de partenaires commerciaux
- Recherche de sous-traitants
- Recherche de dirigeants / contacts
- Enrichissement de données d'entreprises
- Veille concurrentielle / étude de marché

Exemples IN-SCOPE (réponds true) :
- "Trouve-moi des PME du BTP à Lyon"
- "Je cherche des startups tech"
- "Je cherche un prestataire informatique à Paris"
- "Trouve-moi des fournisseurs de matériaux de construction"
- "Je veux trouver un comptable pour mon entreprise"
- "Donne-moi les dirigeants de SAS dans le 75"
- "Quelles entreprises ont un CA > 1M€ ?"
- "Je cherche un cabinet d'avocats spécialisé en droit des affaires"
- "Trouve-moi des agences de communication à Bordeaux"
- "Je cherche des sous-traitants en électronique"
- "Quels sont mes concurrents en restauration à Nantes ?"
- "Combien de crédits me reste-t-il ?" (question sur l'outil)
- "Comment fonctionne MONV ?" (question sur l'outil)
- "Bonjour" / "Salut" (salutation → in-scope, on accueille l'utilisateur)

Exemples HORS-SCOPE (réponds false) :
- "Écris-moi un poème"
- "Quelle est la capitale du Japon ?"
- "Aide-moi à coder en Python"
- "Résume ce texte"
- "Raconte-moi une blague"

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
