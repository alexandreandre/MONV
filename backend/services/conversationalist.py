"""
Couche 1b — Conversationalist (même modèle moyen que le Guard).

Génère des QCM (questions à choix multiples) structurés pour aider
l'utilisateur à préciser sa recherche en quelques clics.

Appelé quand le Guard détecte ``clarification_needed=True``.
"""

from __future__ import annotations

import json
from models.schemas import GuardResult, QcmQuestion, QcmOption
from utils.llm import llm_json_call
from config import settings

QCM_SYSTEM_PROMPT = """\
Tu es l'assistant conversationnel de MONV, un outil de recherche d'entreprises en France.
MONV permet de trouver des clients, prestataires, fournisseurs, partenaires ou concurrents.

L'utilisateur a posé une question mais il manque des informations pour lancer
la recherche. Tu dois générer des QUESTIONS À CHOIX MULTIPLES (QCM) pour
compléter les critères manquants.

CRITÈRES MANQUANTS POSSIBLES :
- "secteur" : secteur d'activité / type d'entreprise
- "zone_geo" : zone géographique (ville, département, région)
- "taille" : taille d'entreprise (nombre de salariés)
- "ca" : chiffre d'affaires
- "type_resultat" : ce que cherche l'utilisateur (entreprises, dirigeants, contacts)
- "date_creation" : ancienneté des entreprises

RÈGLES STRICTES :
1. Génère UNIQUEMENT les questions pour les critères qui MANQUENT (fournis dans "missing")
2. Chaque question a 4-6 options pertinentes + TOUJOURS une option "Autre" avec free_text=true
3. Les options doivent être concrètes et utiles pour la prospection B2B
4. Adapte les options au contexte de la requête utilisateur
5. Maximum 3 questions à la fois
6. "multiple": true UNIQUEMENT si ça a du sens (ex: plusieurs secteurs)

Réponds UNIQUEMENT avec un JSON valide :
{
    "intro": "Phrase d'intro courte et chaleureuse (1 ligne)",
    "questions": [
        {
            "id": "secteur",
            "question": "Quel secteur d'activité ?",
            "options": [
                {"id": "btp", "label": "BTP / Construction", "free_text": false},
                {"id": "tech", "label": "Tech / Informatique", "free_text": false},
                {"id": "autre", "label": "Autre", "free_text": true}
            ],
            "multiple": false
        }
    ]
}

EXEMPLES D'OPTIONS PAR CRITÈRE :

Secteur (adapter selon contexte) :
- BTP / Construction, Tech / Informatique, Commerce / Distribution,
  Industrie / Manufacture, Santé / Pharma, Finance / Assurance,
  Immobilier, Restauration / Hôtellerie, Conseil / Services,
  Transport / Logistique

Zone géographique :
- Paris / Île-de-France, Lyon / Auvergne-Rhône-Alpes,
  Marseille / PACA, Toulouse / Occitanie, Nantes / Pays de la Loire,
  Bordeaux / Nouvelle-Aquitaine, France entière

Taille :
- TPE (1-9 salariés), PME (10-249 salariés),
  ETI (250-4999 salariés), Grand groupe (5000+),
  Peu importe

Chiffre d'affaires :
- Moins de 500K€, 500K€ - 2M€, 2M€ - 10M€,
  10M€ - 50M€, Plus de 50M€, Peu importe
"""


def _build_context(guard_result: GuardResult) -> str:
    parts = [f"Requête utilisateur : « {guard_result.original_query} »"]
    parts.append(f"Intent : {guard_result.intent}")

    e = guard_result.entities
    found = []
    if e.secteur:
        found.append(f"secteur={e.secteur}")
    if e.localisation:
        found.append(f"ville={e.localisation}")
    if e.departement:
        found.append(f"département={e.departement}")
    if e.region:
        found.append(f"région={e.region}")
    if e.code_naf:
        found.append(f"code_naf={e.code_naf}")
    if e.taille_min or e.taille_max:
        found.append(f"effectif={e.taille_min or '?'}-{e.taille_max or '?'}")
    if e.ca_min or e.ca_max:
        found.append(f"CA={e.ca_min or '?'}-{e.ca_max or '?'}€")
    if e.mots_cles:
        found.append(f"mots-clés={', '.join(e.mots_cles)}")

    if found:
        parts.append(f"Déjà détecté : {', '.join(found)}")

    missing = guard_result.missing_criteria
    if not missing:
        missing = _infer_missing(guard_result)
    parts.append(f"Critères manquants : {json.dumps(missing)}")

    return "\n".join(parts)


def _infer_missing(guard_result: GuardResult) -> list[str]:
    """Déduit les critères manquants si le Guard ne les a pas spécifiés."""
    e = guard_result.entities
    missing = []
    has_secteur = bool(e.secteur or e.code_naf or e.mots_cles)
    has_zone = bool(e.localisation or e.departement or e.region)
    if not has_secteur:
        missing.append("secteur")
    if not has_zone:
        missing.append("zone_geo")
    return missing[:3]


def _parse_questions(raw: dict) -> tuple[str, list[QcmQuestion]]:
    intro = raw.get("intro", "Pour affiner ta recherche :")
    questions: list[QcmQuestion] = []

    for q in raw.get("questions", []):
        options = []
        has_autre = False
        for o in q.get("options", []):
            opt = QcmOption(
                id=str(o.get("id", "")),
                label=str(o.get("label", "")),
                free_text=bool(o.get("free_text", False)),
            )
            if opt.free_text:
                has_autre = True
            options.append(opt)

        if not has_autre:
            options.append(QcmOption(id="autre", label="Autre", free_text=True))

        questions.append(QcmQuestion(
            id=str(q.get("id", "")),
            question=str(q.get("question", "")),
            options=options,
            multiple=bool(q.get("multiple", False)),
        ))

    return intro, questions


_FALLBACK_QUESTIONS: dict[str, QcmQuestion] = {
    "secteur": QcmQuestion(
        id="secteur",
        question="Quel secteur d'activité t'intéresse ?",
        options=[
            QcmOption(id="btp", label="BTP / Construction"),
            QcmOption(id="tech", label="Tech / Informatique"),
            QcmOption(id="commerce", label="Commerce / Distribution"),
            QcmOption(id="industrie", label="Industrie / Manufacture"),
            QcmOption(id="conseil", label="Conseil / Services"),
            QcmOption(id="autre", label="Autre", free_text=True),
        ],
        multiple=False,
    ),
    "zone_geo": QcmQuestion(
        id="zone_geo",
        question="Quelle zone géographique ?",
        options=[
            QcmOption(id="idf", label="Paris / Île-de-France"),
            QcmOption(id="aura", label="Lyon / Auvergne-Rhône-Alpes"),
            QcmOption(id="paca", label="Marseille / PACA"),
            QcmOption(id="occitanie", label="Toulouse / Occitanie"),
            QcmOption(id="france", label="France entière"),
            QcmOption(id="autre", label="Autre", free_text=True),
        ],
        multiple=False,
    ),
    "taille": QcmQuestion(
        id="taille",
        question="Quelle taille d'entreprise ?",
        options=[
            QcmOption(id="tpe", label="TPE (1-9 salariés)"),
            QcmOption(id="pme", label="PME (10-249 salariés)"),
            QcmOption(id="eti", label="ETI (250-4999 salariés)"),
            QcmOption(id="ge", label="Grand groupe (5000+)"),
            QcmOption(id="any", label="Peu importe"),
        ],
        multiple=False,
    ),
}


async def generate_qcm(
    guard_result: GuardResult,
    conversation_history: list[dict] | None = None,
) -> tuple[str, list[QcmQuestion]]:
    """Génère un QCM structuré pour les critères manquants."""

    context = _build_context(guard_result)

    messages: list[dict] = []
    if conversation_history:
        messages.extend(conversation_history)
    messages.append({"role": "user", "content": context})

    try:
        raw = await llm_json_call(
            model=settings.GUARD_MODEL,
            system=QCM_SYSTEM_PROMPT,
            messages=messages,
            max_tokens=1024,
            temperature=0.3,
        )
        intro, questions = _parse_questions(raw)
        if questions:
            return intro, questions
    except Exception:
        pass

    missing = guard_result.missing_criteria or _infer_missing(guard_result)
    fallback_qs = [_FALLBACK_QUESTIONS[m] for m in missing if m in _FALLBACK_QUESTIONS]
    return "Pour affiner ta recherche :", fallback_qs or list(_FALLBACK_QUESTIONS.values())[:2]
