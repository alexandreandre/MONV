"""
Service « Atelier » — agent de niveau supérieur aux 4 modes.

Ce service orchestre une expérience guidée multi-étapes pour un porteur de
projet : à partir d'un pitch libre + un QCM court, il produit un dossier
structuré contenant :

  - un brief de projet (nom, tagline, secteur, cible, budget, modèle revenus)
  - un Business Model Canvas (9 cases)
  - une cartographie des flux (valeur, financier, information)
  - plusieurs tableaux d'entreprises réelles, *chacun* calculé via le
    pipeline MONV existant (Guard → Orchestrator → API Engine) avec le
    mode approprié (prospection / sous_traitant / rachat)
  - une synthèse (forces, risques, étapes, KPIs)

L'Atelier NE remplace PAS les modes — il les orchestre. Le mode
conversationnel « atelier » n'est qu'un label de persistence sur la
conversation : il ne modifie pas le pipeline des 4 modes classiques.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any

from config import settings
from models.schemas import (
    AgentSynthesis,
    BusinessCanvas,
    BusinessDossier,
    FlowEdge,
    FlowMap,
    GuardResult,
    ProjectBrief,
    QcmOption,
    QcmQuestion,
    SegmentBrief,
    SegmentResult,
)
from services.api_engine import execute_plan
from services.guard import run_guard
from services.orchestrator import run_orchestrator
from services.modes import normalize_mode, Mode
from services.sirene import patch_sirene_calls_from_guard_entities
from utils.llm import llm_json_call
from utils.pipeline_log import plog


ATELIER_MODE_LABEL = "atelier"


# ─── Couche 1 : QCM de clarification ─────────────────────────────────────────
#
# On REUTILISE volontairement le type `QcmQuestion` / `QcmOption` déjà utilisé
# par le conversationaliste, afin que le composant `QcmCard` côté frontend
# fonctionne sans modification. Seul le PROMPT diffère — on pose des questions
# business plutôt que des questions de filtres de recherche.

_ATELIER_QCM_SYSTEM = """\
Tu es l'Atelier MONV, un agent qui accompagne un porteur de projet dans la
conception de son entreprise. Tu reçois son pitch initial. Tu dois générer un
QCM court (3 à 4 questions) pour obtenir les informations stratégiques qui
manquent, afin de produire un dossier de création complet :

Informations possibles à éclaircir (ne demande QUE celles qui manquent
clairement dans le pitch) :
- "cible" : B2B, B2C, B2B2C, Administrations, Les deux
- "localisation" : ville / département / région de départ
- "modele_revenus" : ventes directes, abonnement, commission, freemium,
  licence, services récurrents, publicité, marketplace, mixte
- "budget" : fourchette de lancement (moins de 20k€, 20-80k€, 80-250k€,
  250k-1M€, plus de 1M€)
- "ambition" : solo / très petite équipe / PME (10-50) / scale-up (50+)
- "canaux" : en ligne, boutique physique, B2B direct, distribution,
  partenaires prescripteurs

Règles :
- 3 à 4 questions maximum (courtes, actionnables)
- 4 à 6 options pertinentes par question + TOUJOURS "Autre" avec free_text=true
- "multiple": true uniquement pour "canaux" ou si un choix combiné a du sens
- Les options sont rédigées en français, concrètes, jamais génériques
- Si le pitch couvre déjà clairement un critère, NE LE REDEMANDE PAS

Réponds UNIQUEMENT avec un JSON strict :
{
  "intro": "Phrase d'accroche courte (1 ligne, tutoiement)",
  "questions": [
    {
      "id": "cible",
      "question": "À qui s'adresse ton offre principalement ?",
      "options": [
        {"id": "b2c", "label": "Particuliers (B2C)", "free_text": false},
        ...
        {"id": "autre", "label": "Autre", "free_text": true}
      ],
      "multiple": false
    }
  ]
}
"""


_FALLBACK_ATELIER_QUESTIONS: list[QcmQuestion] = [
    QcmQuestion(
        id="cible",
        question="À qui s'adresse ton offre principalement ?",
        options=[
            QcmOption(id="b2c", label="Particuliers (B2C)"),
            QcmOption(id="b2b", label="Entreprises (B2B)"),
            QcmOption(id="b2b2c", label="Les deux (B2B2C)"),
            QcmOption(id="admin", label="Administrations / Collectivités"),
            QcmOption(id="autre", label="Autre", free_text=True),
        ],
        multiple=False,
    ),
    QcmQuestion(
        id="modele_revenus",
        question="Quel modèle de revenus envisages-tu ?",
        options=[
            QcmOption(id="vente", label="Ventes directes"),
            QcmOption(id="abo", label="Abonnement / récurrent"),
            QcmOption(id="commission", label="Commission / place de marché"),
            QcmOption(id="service", label="Services / prestations"),
            QcmOption(id="licence", label="Licence / SaaS"),
            QcmOption(id="autre", label="Autre", free_text=True),
        ],
        multiple=False,
    ),
    QcmQuestion(
        id="budget",
        question="Quelle enveloppe prévois-tu pour le lancement ?",
        options=[
            QcmOption(id="lt20k", label="Moins de 20 k€"),
            QcmOption(id="20_80k", label="20 k€ – 80 k€"),
            QcmOption(id="80_250k", label="80 k€ – 250 k€"),
            QcmOption(id="250k_1m", label="250 k€ – 1 M€"),
            QcmOption(id="gt1m", label="Plus de 1 M€"),
            QcmOption(id="autre", label="Autre", free_text=True),
        ],
        multiple=False,
    ),
    QcmQuestion(
        id="ambition",
        question="Quelle taille vises-tu à 2-3 ans ?",
        options=[
            QcmOption(id="solo", label="Solo / indépendant"),
            QcmOption(id="tpe", label="Très petite équipe (2-9)"),
            QcmOption(id="pme", label="PME (10-50)"),
            QcmOption(id="scale", label="Scale-up (50+)"),
            QcmOption(id="autre", label="Autre", free_text=True),
        ],
        multiple=False,
    ),
]


def _parse_qcm_raw(raw: dict) -> tuple[str, list[QcmQuestion]]:
    intro = raw.get("intro", "Affinons ton projet en quelques questions :")
    questions: list[QcmQuestion] = []
    for q in raw.get("questions", []) or []:
        options: list[QcmOption] = []
        has_autre = False
        for o in q.get("options", []) or []:
            opt = QcmOption(
                id=str(o.get("id", "") or ""),
                label=str(o.get("label", "") or ""),
                free_text=bool(o.get("free_text", False)),
            )
            if opt.free_text:
                has_autre = True
            options.append(opt)
        if not has_autre:
            options.append(QcmOption(id="autre", label="Autre", free_text=True))
        questions.append(QcmQuestion(
            id=str(q.get("id", "") or ""),
            question=str(q.get("question", "") or ""),
            options=options,
            multiple=bool(q.get("multiple", False)),
        ))
    return intro, questions


async def generate_atelier_qcm(pitch: str) -> tuple[str, list[QcmQuestion]]:
    """Génère les 3-4 questions qui permettront de structurer le projet.

    Fallback silencieux sur un QCM standard si le LLM est indisponible."""
    try:
        raw = await llm_json_call(
            model=settings.GUARD_MODEL,
            system=_ATELIER_QCM_SYSTEM,
            messages=[{"role": "user", "content": f"Pitch projet :\n{pitch}"}],
            max_tokens=1024,
            temperature=0.4,
        )
        intro, questions = _parse_qcm_raw(raw)
        if questions:
            return intro, questions
    except Exception as exc:
        plog("atelier_qcm_fallback", error=str(exc)[:300])
    return (
        "Affinons ton projet en 4 questions :",
        list(_FALLBACK_ATELIER_QUESTIONS),
    )


# ─── Couche 2 : génération du dossier complet ───────────────────────────────

_ATELIER_DOSSIER_SYSTEM = """\
Tu es l'Atelier MONV, un copilote business qui aide un porteur de projet à
structurer la création de son entreprise. Tu reçois :
  - un pitch initial en langage naturel
  - un ensemble de réponses à un court QCM (format libre)

Ta mission : produire un DOSSIER structuré qui servira de point de départ
concret à la création. Le dossier alimente directement des composants UI —
aucune phrase de conversation, aucun markdown, UNIQUEMENT du JSON valide.

Contraintes rédactionnelles :
- Tout le texte est en FRANÇAIS, factuel, concret, pas d'emoji
- Les bullets du canvas sont courts (5-12 mots) et orientés action
- Le `nom` du projet est une proposition courte (1-3 mots), pas une phrase
- Le `tagline` tient en une ligne (80 caractères max)
- `cible` est l'un de : "B2C", "B2B", "B2B2C", "Administrations", "Les deux"
- `budget` est une fourchette en euros, ex: "20 k€ – 80 k€"
- `ambition` décrit la taille visée à 2-3 ans

Pour les SEGMENTS de recherche d'entreprises (CLE DU DISPOSITIF) :
- Tu dois proposer entre 3 et 5 segments qui seront chacun exécutés par le
  pipeline MONV (recherche d'entreprises réelles via SIRENE / Google Places /
  Pappers).
- Chaque segment a un `mode` parmi : "prospection", "sous_traitant", "rachat"
  (JAMAIS "atelier" ni "client").
- Utilise "sous_traitant" pour : fournisseurs, prestataires, comptable,
  avocat, agence web, expert-comptable, logistique, etc.
- Utilise "prospection" pour : clients B2B cibles, concurrents directs,
  acteurs du marché, partenaires prescripteurs.
- Utilise "rachat" pour : cibles d'acquisition potentielles (UNIQUEMENT si le
  porteur évoque une stratégie de reprise/fusion, sinon ignore ce segment).
- Le `query` de chaque segment est une requête NATURELLE en français qui
  sera passée au Guard MONV (ex: "Je cherche des fournisseurs de poissons
  frais et sakés japonais à Lyon pour un restaurant").
- Le `query` doit inclure la ZONE GÉOGRAPHIQUE issue du pitch (ville, dept
  ou région) — sans zone, la recherche est dégradée.
- `key` est un identifiant court ASCII (fournisseurs, clients_b2b,
  concurrents, prestataires, cibles_rachat).
- `icon` est l'un de : "truck", "target", "users", "briefcase", "landmark",
  "building", "factory", "megaphone", "scale", "calculator".

Format de réponse OBLIGATOIRE (JSON strict) :
{
  "brief": {
    "nom": "...",
    "tagline": "...",
    "secteur": "...",
    "localisation": "...",
    "cible": "B2C|B2B|B2B2C|Administrations|Les deux",
    "budget": "...",
    "modele_revenus": "...",
    "ambition": "..."
  },
  "canvas": {
    "proposition_valeur": ["..."],
    "segments_clients": ["..."],
    "canaux": ["..."],
    "relation_client": ["..."],
    "sources_revenus": ["..."],
    "ressources_cles": ["..."],
    "activites_cles": ["..."],
    "partenaires_cles": ["..."],
    "structure_couts": ["..."]
  },
  "flows": {
    "acteurs": ["Client final", "Entreprise", "Fournisseur principal", ...],
    "flux_valeur": [{"origine": "Fournisseur principal", "destination": "Entreprise", "label": "Matières premières"}, ...],
    "flux_financiers": [{"origine": "Client final", "destination": "Entreprise", "label": "Paiement"}, ...],
    "flux_information": [{"origine": "Entreprise", "destination": "Client final", "label": "Facture / reçu"}, ...]
  },
  "segments": [
    {
      "key": "fournisseurs",
      "label": "Fournisseurs clés",
      "description": "Identifier des fournisseurs ou sous-traitants locaux pour les matières principales.",
      "mode": "sous_traitant",
      "query": "Je cherche des fournisseurs de ... à ...",
      "icon": "truck"
    }
  ],
  "synthesis": {
    "forces": ["..."],
    "risques": ["..."],
    "prochaines_etapes": ["..."],
    "kpis": ["..."],
    "budget_estimatif": "..."
  }
}

Règles :
- Chaque liste du canvas a entre 3 et 6 éléments
- `flux_*` ont entre 2 et 6 arcs chacun
- `synthesis.forces` / `risques` : 3 à 5 éléments concrets chacun
- `synthesis.prochaines_etapes` : 4 à 7 étapes ordonnées et actionnables
- `synthesis.kpis` : 3 à 5 indicateurs mesurables
"""


async def generate_dossier_skeleton(
    pitch: str,
    answers: str,
) -> dict[str, Any]:
    """Appelle le LLM de niveau orchestrateur pour produire le squelette JSON
    du dossier (brief + canvas + flows + segments + synthesis).

    Les segments NE sont PAS encore exécutés : ils seront lancés ensuite via
    `run_segment_searches` qui appelle le pipeline MONV classique.
    """
    user_payload = (
        "Pitch initial :\n"
        f"{pitch.strip()}\n\n"
        "Réponses de clarification :\n"
        f"{(answers or '').strip()}\n"
    )
    raw = await llm_json_call(
        model=settings.ORCHESTRATOR_MODEL,
        system=_ATELIER_DOSSIER_SYSTEM,
        messages=[{"role": "user", "content": user_payload}],
        max_tokens=3072,
        temperature=0.2,
    )
    return raw


def coerce_dossier(raw: dict[str, Any]) -> tuple[
    ProjectBrief, BusinessCanvas, FlowMap, list[SegmentBrief], AgentSynthesis
]:
    """Valide et nettoie la réponse LLM pour la rendre sûre à consommer.

    Toute clé manquante est remplacée par un défaut silencieux : l'Atelier
    doit toujours produire *quelque chose*, même si le LLM a été bavard.
    """
    b = raw.get("brief") or {}
    brief = ProjectBrief(
        nom=str(b.get("nom") or "Mon projet").strip()[:60] or "Mon projet",
        tagline=str(b.get("tagline") or "").strip()[:140],
        secteur=str(b.get("secteur") or "").strip()[:140],
        localisation=str(b.get("localisation") or "").strip()[:140],
        cible=str(b.get("cible") or "B2C").strip(),
        budget=str(b.get("budget") or "").strip()[:80],
        modele_revenus=str(b.get("modele_revenus") or "").strip()[:140],
        ambition=str(b.get("ambition") or "").strip()[:140],
    )

    c = raw.get("canvas") or {}
    def _lst(key: str) -> list[str]:
        v = c.get(key) or []
        return [str(x).strip() for x in v if str(x).strip()][:6]
    canvas = BusinessCanvas(
        proposition_valeur=_lst("proposition_valeur"),
        segments_clients=_lst("segments_clients"),
        canaux=_lst("canaux"),
        relation_client=_lst("relation_client"),
        sources_revenus=_lst("sources_revenus"),
        ressources_cles=_lst("ressources_cles"),
        activites_cles=_lst("activites_cles"),
        partenaires_cles=_lst("partenaires_cles"),
        structure_couts=_lst("structure_couts"),
    )

    f = raw.get("flows") or {}
    def _edges(key: str) -> list[FlowEdge]:
        out: list[FlowEdge] = []
        for e in (f.get(key) or []):
            if not isinstance(e, dict):
                continue
            o = str(e.get("origine") or e.get("from") or "").strip()
            d = str(e.get("destination") or e.get("to") or "").strip()
            lbl = str(e.get("label") or "").strip()
            if o and d:
                out.append(FlowEdge(origine=o[:60], destination=d[:60], label=lbl[:80]))
        return out[:6]
    flows = FlowMap(
        acteurs=[str(x).strip()[:60] for x in (f.get("acteurs") or []) if str(x).strip()][:8],
        flux_valeur=_edges("flux_valeur"),
        flux_financiers=_edges("flux_financiers"),
        flux_information=_edges("flux_information"),
    )

    segments_raw = raw.get("segments") or []
    segments: list[SegmentBrief] = []
    seen_keys: set[str] = set()
    _allowed_modes: set[str] = {"prospection", "sous_traitant", "rachat"}
    for s in segments_raw:
        if not isinstance(s, dict):
            continue
        mode = str(s.get("mode") or "prospection").strip()
        if mode not in _allowed_modes:
            mode = "prospection"
        key = str(s.get("key") or "").strip().lower()[:40] or f"segment_{len(segments)+1}"
        if key in seen_keys:
            continue
        seen_keys.add(key)
        query = str(s.get("query") or "").strip()
        if not query:
            continue
        segments.append(SegmentBrief(
            key=key,
            label=str(s.get("label") or key.replace("_", " ").title())[:80],
            description=str(s.get("description") or "").strip()[:240],
            mode=mode,
            query=query[:400],
            icon=str(s.get("icon") or "building").strip()[:32],
        ))
        if len(segments) >= 5:
            break

    syn = raw.get("synthesis") or {}
    def _lst2(key: str, lim: int = 6) -> list[str]:
        v = syn.get(key) or []
        return [str(x).strip() for x in v if str(x).strip()][:lim]
    synthesis = AgentSynthesis(
        forces=_lst2("forces"),
        risques=_lst2("risques"),
        prochaines_etapes=_lst2("prochaines_etapes", 7),
        kpis=_lst2("kpis"),
        budget_estimatif=(str(syn.get("budget_estimatif") or "").strip()[:140] or None),
    )

    return brief, canvas, flows, segments, synthesis


# ─── Couche 3 : exécution des segments via le pipeline MONV ──────────────────

async def run_segment_search(segment: SegmentBrief) -> SegmentResult:
    """Exécute un segment en REUTILISANT le pipeline MONV standard.

    Guard → Orchestrator → API Engine, mais SANS le filtre de relevance ni le
    filtre de scope (couche 0) : l'Atelier n'a pas besoin de ces garde-fous
    car la requête est générée par l'Atelier lui-même et déjà cadrée."""
    mode: Mode = normalize_mode(segment.mode)
    try:
        guard_result: GuardResult = await run_guard(segment.query)
        plog(
            "atelier_segment_guard",
            key=segment.key,
            intent=guard_result.intent,
            entities=guard_result.entities.model_dump(),
        )
        plan = await run_orchestrator(guard_result, mode=mode)
        patch_sirene_calls_from_guard_entities(plan, guard_result.entities)
        results = await execute_plan(plan)
        plog(
            "atelier_segment_done",
            key=segment.key,
            total=results.total,
            credits=results.credits_required,
        )

        map_points = [
            {
                "nom": r.nom,
                "latitude": r.latitude,
                "longitude": r.longitude,
                "adresse": r.adresse,
                "code_postal": r.code_postal,
                "ville": r.ville,
                "libelle_activite": r.libelle_activite,
                "telephone": r.telephone,
                "site_web": r.site_web,
                "lien_annuaire": r.lien_annuaire,
                "signaux": [s.model_dump() for s in r.signaux] if r.signaux else [],
            }
            for r in results.results
            if r.latitude is not None and r.longitude is not None
        ]

        return SegmentResult(
            key=segment.key,
            label=segment.label,
            description=segment.description,
            mode=mode,
            icon=segment.icon,
            query=segment.query,
            total=results.total,
            credits_required=results.credits_required,
            columns=results.columns,
            preview=[r.model_dump() for r in results.results[:10]],
            map_points=map_points,
        )
    except Exception as exc:
        plog("atelier_segment_error", key=segment.key, error=str(exc)[:300])
        return SegmentResult(
            key=segment.key,
            label=segment.label,
            description=segment.description,
            mode=mode,
            icon=segment.icon,
            query=segment.query,
            total=0,
            credits_required=0,
            columns=[],
            preview=[],
            map_points=[],
            error="Recherche indisponible — réessaie plus tard.",
        )


async def run_segment_searches(
    segments: list[SegmentBrief],
) -> list[SegmentResult]:
    """Exécute tous les segments en parallèle (asyncio.gather).

    Les exceptions d'un segment ne contaminent pas les autres : chacun est
    résilient via `run_segment_search`.
    """
    if not segments:
        return []
    coros = [run_segment_search(s) for s in segments]
    return await asyncio.gather(*coros)


# ─── Helpers d'assemblage ─────────────────────────────────────────────────────

def dossier_metadata_json(dossier: BusinessDossier) -> str:
    """Sérialise un dossier pour `Message.metadata_json`.

    `mode="atelier"` est ajouté pour que le frontend sache qu'il doit
    afficher le composant `BusinessDossier` plutôt que `ResultsTable`.
    """
    payload: dict[str, Any] = dossier.model_dump()
    payload["mode"] = ATELIER_MODE_LABEL
    return json.dumps(payload, ensure_ascii=False, default=str)


def build_brief_metadata(pitch: str) -> str:
    """Metadonnées attachées au message d'ouverture (type agent_brief)."""
    return json.dumps(
        {"pitch": pitch, "mode": ATELIER_MODE_LABEL},
        ensure_ascii=False,
    )


__all__ = [
    "ATELIER_MODE_LABEL",
    "build_brief_metadata",
    "coerce_dossier",
    "dossier_metadata_json",
    "generate_atelier_qcm",
    "generate_dossier_skeleton",
    "run_segment_search",
    "run_segment_searches",
]
