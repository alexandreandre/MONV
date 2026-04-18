"""
Couche 1b — Conversationalist (même modèle moyen que le Guard).

Génère des QCM (questions à choix multiples) structurés pour aider
l'utilisateur à préciser sa recherche en quelques clics.

Appelé quand le Guard détecte ``clarification_needed=True``.
"""

from __future__ import annotations

import json
from models.schemas import GuardResult, QcmQuestion, QcmOption
from services.modes import normalize_mode
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

CRITÈRE SPÉCIAL :
- "secteur_confirmation" : ne génère PAS cette question ici — elle est insérée séparément en tête de QCM quand le Guard l'exige.

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

MODE SOUS-TRAITANT — questions spécifiques à privilégier :

Capacité requise (id: "capacite") :
- 1 à 5 personnes (artisan / micro-structure)
- 5 à 20 personnes (PME spécialisée)
- 20 personnes et plus (structure établie)
- Peu importe

Type de mission (id: "type_mission") :
- Mission ponctuelle
- Partenariat régulier / récurrent
- Sous-traitance en cascade
- Peu importe

Certification / label requis (id: "certification") :
- RGE (travaux énergie)
- QUALIBAT (BTP)
- ISO 9001 (qualité)
- Aucune exigence particulière

Ancienneté minimum (id: "anciennete") :
- +2 ans
- +5 ans
- +10 ans
- Peu importe

MODE RACHAT — questions spécifiques à privilégier :

Budget d'acquisition (id: "budget_acquisition") :
- Moins de 500k€
- 500k€ — 2M€
- 2M€ — 10M€
- Plus de 10M€
- Non défini pour l'instant

Profil de cible (id: "profil_cible") :
- Entreprise saine et rentable
- Entreprise en difficulté (retournement)
- Transmission familiale / départ retraite
- Peu importe

Type de reprise (id: "type_reprise") :
- Reprise totale avec les salariés
- Rachat de fonds de commerce uniquement
- Prise de participation minoritaire
- Peu importe
"""

SECTOR_CONFIRMATION_SYSTEM = """\
Tu génères UNE seule question à choix unique pour lever une ambiguïté sectorielle B2B en France.
L'utilisateur a utilisé un terme qui peut désigner plusieurs activités d'entreprises différentes.

Réponds UNIQUEMENT avec un JSON valide :
{
    "question": "Phrase courte en français (ex. préciser le type d'activité recherchée)",
    "options": [
        {"id": "identifiant_snake_unique", "label": "Libellé concret, émoji optionnel", "free_text": false},
        ... 3 ou 4 interprétations métier distinctes ...
        {"id": "autre", "label": "✏️ Autre (précisez)", "free_text": true}
    ]
}

Contraintes :
- 3 à 4 options métier concrètes + exactement une option "Autre" en dernier avec free_text=true
- Toutes les autres options : free_text=false
- Choix unique implicite (pas de champ multiple)
- Textes en français
"""


def _build_context(
    guard_result: GuardResult,
    missing_override: list[str] | None = None,
    *,
    skip_infer_missing: bool = False,
) -> str:
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

    if missing_override is not None:
        missing = list(missing_override)
    else:
        missing = list(guard_result.missing_criteria or [])
    if not missing and not skip_infer_missing:
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


def _fallback_sector_confirmation_question(guard_result: GuardResult) -> QcmQuestion:
    term = (
        (guard_result.entities.secteur or "").strip()
        or (guard_result.entities.mots_cles[0] if guard_result.entities.mots_cles else "")
        or "ce secteur"
    )
    return QcmQuestion(
        id="secteur_confirmation",
        question=f"« {term} » peut correspondre à plusieurs activités. Laquelle vises-tu ?",
        options=[
            QcmOption(id="services_conseil", label="Services aux entreprises / conseil", free_text=False),
            QcmOption(id="commerce_distribution", label="Commerce / distribution / retail", free_text=False),
            QcmOption(id="artisanat_industrie_btp", label="Artisanat / industrie / BTP", free_text=False),
            QcmOption(id="sante_sport_loisirs", label="Santé / sport / loisirs / bien-être", free_text=False),
            QcmOption(id="autre", label="✏️ Autre (précisez)", free_text=True),
        ],
        multiple=False,
    )


async def _generate_sector_confirmation_question(
    guard_result: GuardResult,
) -> QcmQuestion:
    base_m = list(guard_result.missing_criteria or [])
    skip_one = len(base_m) == 1 and base_m[0] == "secteur_confirmation"
    ctx = _build_context(
        guard_result,
        missing_override=base_m,
        skip_infer_missing=skip_one,
    )
    ambiguous_term = (
        (guard_result.entities.secteur or "").strip()
        or (guard_result.entities.mots_cles[0] if guard_result.entities.mots_cles else "")
        or "le secteur mentionné"
    )
    user_block = f"Terme ambigu à clarifier : « {ambiguous_term} »\n\n{ctx}"
    try:
        raw = await llm_json_call(
            model=settings.GUARD_MODEL,
            system=SECTOR_CONFIRMATION_SYSTEM,
            messages=[{"role": "user", "content": user_block}],
            max_tokens=512,
            temperature=0.2,
        )
        qtext = str(raw.get("question", "")).strip()
        opts_raw = raw.get("options", [])
        if not qtext or not isinstance(opts_raw, list) or len(opts_raw) < 2:
            return _fallback_sector_confirmation_question(guard_result)
        wrapped = {
            "intro": "",
            "questions": [
                {
                    "id": "secteur_confirmation",
                    "question": qtext,
                    "options": opts_raw,
                    "multiple": False,
                }
            ],
        }
        _, questions = _parse_questions(wrapped)
        if not questions:
            return _fallback_sector_confirmation_question(guard_result)
        q0 = questions[0]
        q0 = QcmQuestion(
            id="secteur_confirmation",
            question=q0.question,
            options=q0.options,
            multiple=False,
        )
        return q0
    except Exception:
        return _fallback_sector_confirmation_question(guard_result)


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
    "capacite": QcmQuestion(
        id="capacite",
        question="Quelle capacité requise ?",
        options=[
            QcmOption(id="micro", label="1 à 5 personnes (artisan / micro-structure)"),
            QcmOption(id="pme_specialisee", label="5 à 20 personnes (PME spécialisée)"),
            QcmOption(id="structure_etablie", label="20 personnes et plus (structure établie)"),
            QcmOption(id="any", label="Peu importe"),
        ],
        multiple=False,
    ),
    "budget_acquisition": QcmQuestion(
        id="budget_acquisition",
        question="Quel est ton budget d'acquisition ?",
        options=[
            QcmOption(id="moins_500k", label="Moins de 500k€"),
            QcmOption(id="500k_2m", label="500k€ — 2M€"),
            QcmOption(id="2m_10m", label="2M€ — 10M€"),
            QcmOption(id="plus_10m", label="Plus de 10M€"),
            QcmOption(id="non_defini", label="Non défini pour l'instant"),
        ],
        multiple=False,
    ),
    "profil_cible": QcmQuestion(
        id="profil_cible",
        question="Quel profil de cible tu recherches ?",
        options=[
            QcmOption(id="saine", label="Entreprise saine et rentable"),
            QcmOption(id="difficulte", label="Entreprise en difficulté (retournement)"),
            QcmOption(id="transmission", label="Transmission familiale / départ retraite"),
            QcmOption(id="peu_importe", label="Peu importe"),
        ],
        multiple=False,
    ),
    "type_reprise": QcmQuestion(
        id="type_reprise",
        question="Quel type de reprise tu envisages ?",
        options=[
            QcmOption(id="totale", label="Reprise totale avec les salariés"),
            QcmOption(id="fonds", label="Rachat de fonds de commerce uniquement"),
            QcmOption(id="participation", label="Prise de participation minoritaire"),
            QcmOption(id="peu_importe", label="Peu importe"),
        ],
        multiple=False,
    ),
}


def _swap_taille_for_capacite_sous_traitant(
    questions: list[QcmQuestion],
    mode: str,
    guard_result: GuardResult,
) -> list[QcmQuestion]:
    """En mode sous-traitant, remplace la question taille par capacité si pertinent."""
    if normalize_mode(mode) != "sous_traitant":
        return questions
    missing = list(guard_result.missing_criteria or [])
    if "taille" not in missing and "capacite" not in missing:
        return questions
    capacite_q = _FALLBACK_QUESTIONS["capacite"]
    return [capacite_q if q.id == "taille" else q for q in questions]


def _apply_rachat_qualification_qcm(
    questions: list[QcmQuestion],
    mode: str,
    guard_result: GuardResult,
) -> list[QcmQuestion]:
    """Mode rachat : remplace le lot LLM par les 3 questions de qualification si prévues et absentes."""
    if normalize_mode(mode) != "rachat":
        return questions
    missing = guard_result.missing_criteria or []
    if "budget_acquisition" not in missing:
        return questions
    if any(q.id == "budget_acquisition" for q in questions):
        return questions
    triple = [
        _FALLBACK_QUESTIONS["budget_acquisition"],
        _FALLBACK_QUESTIONS["profil_cible"],
        _FALLBACK_QUESTIONS["type_reprise"],
    ]
    if questions and questions[0].id == "secteur_confirmation":
        return [questions[0]] + triple
    return triple


async def generate_qcm(
    guard_result: GuardResult,
    conversation_history: list[dict] | None = None,
    mode: str = "prospection",
) -> tuple[str, list[QcmQuestion]]:
    """Génère un QCM structuré pour les critères manquants."""

    raw_missing = list(guard_result.missing_criteria or [])
    sector_q: QcmQuestion | None = None
    if "secteur_confirmation" in raw_missing:
        sector_q = await _generate_sector_confirmation_question(guard_result)

    missing_main = [m for m in raw_missing if m != "secteur_confirmation"]
    has_sector_confirm = "secteur_confirmation" in raw_missing
    skip_infer = has_sector_confirm and len(missing_main) == 0

    if has_sector_confirm:
        context = _build_context(
            guard_result,
            missing_override=missing_main,
            skip_infer_missing=skip_infer,
        )
    else:
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
        if sector_q:
            questions = [sector_q] + questions
        questions = _swap_taille_for_capacite_sous_traitant(questions, mode, guard_result)
        questions = _apply_rachat_qualification_qcm(questions, mode, guard_result)
        if questions:
            return intro, questions
    except Exception:
        pass

    missing = guard_result.missing_criteria or _infer_missing(guard_result)
    missing_fb = [m for m in missing if m != "secteur_confirmation"]
    fallback_qs: list[QcmQuestion] = []
    for m in missing_fb:
        key = m
        if normalize_mode(mode) == "sous_traitant" and m == "taille":
            key = "capacite"
        fq = _FALLBACK_QUESTIONS.get(key)
        if fq is not None:
            fallback_qs.append(fq)
    merged = ([sector_q] if sector_q else []) + fallback_qs
    merged = _apply_rachat_qualification_qcm(merged, mode, guard_result)
    if merged:
        return "Pour affiner ta recherche :", merged
    return "Pour affiner ta recherche :", list(_FALLBACK_QUESTIONS.values())[:2]
