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
    BusinessDossier,
    GuardResult,
    QcmQuestion,
    SegmentBrief,
    SegmentResult,
)
from services.atelier_constants import ATELIER_MODE_LABEL
from services.atelier_coerce import coerce_dossier
from services.atelier_heuristics import (
    heuristic_atelier_conversation_title,
    heuristic_atelier_project_folder_name,
)
from services.atelier_qcm import (
    _FALLBACK_ATELIER_QUESTIONS,
    finalize_atelier_qcm as _finalize_atelier_qcm,
    parse_qcm_raw as _parse_qcm_raw,
)
from services.api_engine import execute_plan
from services.guard import run_guard
from services.orchestrator import run_orchestrator
from services.modes import normalize_mode, Mode
from services.sirene import patch_sirene_calls_from_guard_entities
from utils.llm import llm_call, llm_json_call
from utils.pipeline_log import plog


def _atelier_business_model() -> str:
    """Modèle dédié Atelier (plan + dossier). Défaut : orchestrateur."""
    m = (settings.ATELIER_BUSINESS_MODEL or "").strip()
    return m or settings.ORCHESTRATOR_MODEL


# ─── Couche 1 : QCM de clarification ─────────────────────────────────────────
#
# On REUTILISE volontairement le type `QcmQuestion` / `QcmOption` déjà utilisé
# par le conversationaliste, afin que le composant `QcmCard` côté frontend
# fonctionne sans modification. Seul le PROMPT diffère — on pose des questions
# business plutôt que des questions de filtres de recherche.

_ATELIER_QCM_SYSTEM = """\
Tu es l'Atelier MONV, un agent qui accompagne un porteur de projet dans la
conception de son entreprise. Tu reçois son pitch initial (une ou plusieurs
phrases, parfois très détaillé).

MISSION — Avant de rédiger le QCM, raisonne sur la COMPLÉTUDE du pitch par
rapport à ces axes (tu ne les cites pas tels quels à l'utilisateur) :
- cible : à qui vend-on (B2C, B2B, B2B2C, administrations, mixte)
- modele_revenus : comment l'argent est gagné (vente ponctuelle, abonnement,
  pub, commission, marketplace, services, licence/SaaS, mixte…)
- budget : enveloppe ou fourchette de lancement / premier run
- localisation : zone géographique de déploiement ou d'étude (ville, région,
  national) — indispensable pour les recherches d'entreprises réelles
- ambition : taille d'équipe ou de structure visée à 2-3 ans
- canaux : comment l'offre atteint les clients (web, physique, réseau, etc.)

NOMBRE DE QUESTIONS (adapter intelligemment, ne pas « remplir » mécaniquement) :
- Pitch très flou ou < ~40 mots : jusqu'à 5 questions, les plus utiles d'abord.
- Pitch moyen : 2 à 4 questions sur les axes encore ambigus.
- Pitch déjà riche sur la plupart des axes : 1 seule question ciblée sur le
  dernier point critique manquant, OU 2 questions si deux lacunes claires.
- Pitch exceptionnellement complet sur tous les axes ci-dessus : renvoie
  "questions": [] (tableau vide). Ne pose aucune question artificielle.

ORDRE LOGIQUE dans le tableau "questions" (respecte cet ordre quand plusieurs
questions sont nécessaires) :
1) cible client / marché prioritaire
2) modèle de revenus principal
3) localisation / zone d'implantation ou d'étude (si encore floue alors qu'elle
   compte pour le dossier)
4) budget de lancement
5) canaux / go-to-market
6) ambition de taille

FORMAT DES QUESTIONS :
- Utilise de préférence ces ids pour faciliter le traitement : "cible",
  "modele_revenus", "localisation", "budget", "canaux", "ambition". Si un
  sujet spécifique au pitch prime (ex. contrainte réglementaire), un id court
  en snake_case explicite est accepté.
- Chaque question : libellé clair, tutoiement, une seule intention par question.
- 3 à 6 options pertinentes et contextualisées au pitch + TOUJOURS "Autre"
  avec free_text=true (sauf si tu as déjà une option Autre).
- "multiple": true uniquement pour "canaux" ou lorsque plusieurs réponses
  combinées ont du sens (ex. sources de revenus parallèles).

TON DE L'INTRO (champ "intro", une phrase, tutoiement) :
- Plusieurs lacunes : ton chaleureux du type « Super projet ! J'ai quelques
  questions pour mieux cerner ton idée. »
- Peu de lacunes : phrase courte du type « Quelques points à verrouiller pour
  caler ton dossier et les recherches. »
- Aucune question (pitch complet) : « Ton pitch est déjà très clair — je peux
  enchaîner sur le dossier. »

Réponds UNIQUEMENT avec un JSON strict :
{
  "intro": "...",
  "questions": [
    {
      "id": "cible",
      "question": "À qui s'adresse ton offre principalement ?",
      "options": [
        {"id": "b2c", "label": "Particuliers (B2C)", "free_text": false},
        {"id": "autre", "label": "Autre", "free_text": true}
      ],
      "multiple": false
    }
  ]
}
"""


_CONV_TITLE_SYSTEM = """\
Tu nommes une conversation dans une liste latérale (type boîte mail).
À partir du pitch d'un porteur de projet, produis UN libellé court en français.
Contraintes : 4 à 12 mots ; pas de guillemets ni emoji ; ne commence pas par « Atelier » ;
pas de point final ; style titre professionnel et mémorable ; résume l'idée, le secteur
et l'angle principal (zone, cible, différenciation) si le pitch le permet.
Réponds par UNE seule ligne : le titre uniquement, sans préambule.
"""

_PROJECT_FOLDER_NAME_SYSTEM = """\
Tu nommes un PROJET dans une liste de dossiers (sidebar type Notion / ChatGPT).
À partir de la première requête / pitch du porteur, produis UN nom de projet court en français,
comme s'il s'agissait du titre du dossier sur son bureau.

Exemples de bon format (à titre indicatif) :
- Pitch : « Je veux créer une boîte de nuit à Marseille » → Boîte de nuit Marseille
- Pitch : « Food truck de burgers bio à Lille » → Food truck burgers bio Lille

Contraintes strictes :
- 2 à 7 mots ; pas de phrase complète ni de sous-titre ; pas de deux-points ;
- pas de guillemets ni emoji ; pas de point final ;
- ne commence pas par « Atelier », « Projet », « Nouveau », « Idée » ;
- inclure le lieu ou la zone si le pitch en mentionne une (ville, région, pays) ;
- style sobre et lisible (substantifs + lieu), pas de « Je veux » ni formules d'intention.

Réponds par UNE seule ligne : le nom du projet uniquement, sans préambule.
"""


async def suggest_atelier_conversation_title(pitch: str) -> str:
    """Libellé court pour la conversation Atelier (LLM rapide, repli heuristique)."""
    base = heuristic_atelier_conversation_title(pitch)
    if not (settings.OPENROUTER_API_KEY or "").strip():
        return base
    try:
        raw = await llm_call(
            model=settings.FILTER_MODEL,
            system=_CONV_TITLE_SYSTEM,
            messages=[{"role": "user", "content": f"Pitch :\n{pitch.strip()}"}],
            max_tokens=48,
            temperature=0.2,
        )
        title = (raw or "").strip()
        title = title.split("\n", 1)[0].strip()
        for ch in '"\'«»':
            title = title.strip(ch)
        title = " ".join(title.split())
        # Retire un éventuel préfixe redondant
        low = title.lower()
        if low.startswith("atelier — "):
            title = title[10:].strip()
        elif low.startswith("atelier - "):
            title = title[10:].strip()
        if len(title) < 4 or len(title) > 120:
            return base
        if len(title) > 88:
            title = heuristic_atelier_conversation_title(title, max_len=88)
        return title
    except Exception as exc:
        plog("atelier_conv_title_fallback", error=str(exc)[:300])
        return base


async def suggest_atelier_project_folder_name(pitch: str) -> str:
    """Nom court du dossier PROJETS (LLM dédié, repli heuristique)."""
    base = heuristic_atelier_project_folder_name(pitch)
    if not (settings.OPENROUTER_API_KEY or "").strip():
        return base
    try:
        raw = await llm_call(
            model=settings.FILTER_MODEL,
            system=_PROJECT_FOLDER_NAME_SYSTEM,
            messages=[{"role": "user", "content": f"Première requête :\n{pitch.strip()}"}],
            max_tokens=40,
            temperature=0.15,
        )
        name = (raw or "").strip()
        name = name.split("\n", 1)[0].strip()
        for ch in '"\'«»':
            name = name.strip(ch)
        name = " ".join(name.split())
        low = name.lower()
        for _ in range(3):
            low = name.lower()
            if low.startswith("atelier — "):
                name = name[10:].strip()
            elif low.startswith("atelier - "):
                name = name[10:].strip()
            elif low.startswith("atelier "):
                name = name[8:].strip()
            elif low.startswith("projet "):
                name = name[7:].strip()
            elif low.startswith("nouveau "):
                name = name[8:].strip()
            elif low.startswith("idée "):
                name = name[5:].strip()
            else:
                break
        if len(name) < 3 or len(name) > 100:
            return base
        nw = len(name.split())
        if nw > 9:
            return base
        if len(name) > 72:
            name = heuristic_atelier_project_folder_name(name)
        return name
    except Exception as exc:
        plog("atelier_project_name_fallback", error=str(exc)[:300])
        return base


async def generate_atelier_qcm(pitch: str) -> tuple[str, list[QcmQuestion]]:
    """Génère un QCM adapté au pitch (1 à 5 questions, ou validation si complet).

    Fallback silencieux sur un QCM standard si le LLM est indisponible."""
    try:
        pitch_clean = (pitch or "").strip()
        n_words = len(pitch_clean.split())
        raw = await llm_json_call(
            model=settings.GUARD_MODEL,
            system=_ATELIER_QCM_SYSTEM,
            messages=[
                {
                    "role": "user",
                    "content": f"Pitch projet ({n_words} mots) :\n{pitch_clean}",
                }
            ],
            max_tokens=1408,
            temperature=0.35,
        )
        intro, questions = _parse_qcm_raw(raw)
        return _finalize_atelier_qcm(intro, questions)
    except Exception as exc:
        plog("atelier_qcm_fallback", error=str(exc)[:300])
    return (
        "Super projet ! J'ai quelques questions pour mieux cerner ton idée.",
        list(_FALLBACK_ATELIER_QUESTIONS),
    )


# ─── Couche 2 : plan stratégique puis dossier (2 appels, modèle dédié .env) ───

_ATELIER_STRATEGIC_PLAN_SYSTEM = """\
Tu es un stratège senior (création / restructuration d'entreprise, chaîne de valeur,
modèles B2B, B2C, places de marché, SaaS, retail, services, industrie).

Tu reçois le pitch d'un porteur de projet et ses réponses à un QCM court.

MISSION — Produire un PLAN STRATÉGIQUE interne (pas le dossier final). Ce plan
sera la SEULE feuille de route pour un second modèle qui rédigera le JSON livrable.

Exigences d'intelligence :
- Identifie l'ARCHÉTYPE réel du business (ne force pas un schéma « fournisseur →
  nous → client » si ce n'est pas pertinent : marketplace, B2B2C, licence,
  franchise, agence, médiation, infra, abonnement + usage, etc.).
- Décris les INTERMÉDIAIRES, plateformes, régulateurs, prescripteurs, intégrateurs,
  revendeurs, SI tiers, si la valeur le demande.
- Anticipe où la chaîne se CASSE (dépendances, concentration, conformité).
- Propose une TOPOLOGIE de schéma : "radial" (écosystème équilibré), "horizontal"
  (chaîne ou pipeline lisible de gauche à droite), "vertical" (empilement étapes /
  marchés superposés).

FORMAT JSON (critique) :
- Guillemets doubles `"` pour les clés et chaînes ; échapper `\"` dans le texte.
- Aucun saut de ligne à l'intérieur d'une valeur string ; phrases courtes.
- Réponse = un seul objet `{ ... }` valide (pas tronqué).

Réponds UNIQUEMENT avec un JSON strict :
{
  "archetype": "libellé court du modèle économique dominant",
  "resume_chaine_valeur": "3 à 6 phrases factuelles en français",
  "topologie": "radial|horizontal|vertical",
  "justification_topologie": "1 phrase",
  "acteurs_cles": [
    {
      "nom": "libellé unique court pour un nœud du schéma",
      "role_metier": "ex. Prescripteur, Intégrateur, Client payeur, Régulateur",
      "type": "interne|externe|marche|public|plateforme",
      "rattachement_segment": "clé segment MONV ou null si pas de tableau dédié"
    }
  ],
  "flux_valeur": [{"de": "...", "vers": "...", "nature": "...", "priorite": "haute|moyenne|basse"}],
  "flux_financiers": [{"de": "...", "vers": "...", "nature": "...", "priorite": "haute|moyenne|basse"}],
  "flux_information": [{"de": "...", "vers": "...", "nature": "...", "priorite": "haute|moyenne|basse"}],
  "segments_recherche": [
    {
      "key": "identifiant_ascii",
      "intention": "ce qu'on cherche dans la base entreprises",
      "mode_suggere": "prospection|sous_traitant|rachat",
      "pourquoi": "1 phrase utile au porteur"
    }
  ],
  "alertes_structurelles": ["..."],
  "hypotheses_a_valider": ["..."]
}

Règles :
- 4 à 12 entrées dans `acteurs_cles` selon la complexité réelle (pas toujours 3).
- 3 à 5 objets dans `segments_recherche` (jamais « atelier » ni « client » comme mode).
- Les noms dans `de`/`vers` doivent correspondre EXACTEMENT à des `nom` de `acteurs_cles`.
"""


_ATELIER_DOSSIER_FILL_SYSTEM = """\
Tu es l'Atelier MONV : tu transformes un PLAN STRATÉGIQUE (JSON) + pitch + QCM
en DOSSIER LIVRABLE pour l'interface utilisateur.

Sortie : UN SEUL objet JSON (pas de markdown, pas de commentaires hors JSON).

FORMAT JSON (critique) :
- Guillemets doubles ; pas de newline dans les chaînes ; `detail` des arcs ≤ 200 car.
- Objet complet et **terminé** (toutes accolades fermées).

Contraintes rédactionnelles :
- Tout en FRANÇAIS, factuel, sans emoji ni ton marketing creux.
- Canvas : puces 5-12 mots, orientées action / test / décision.
- `brief.nom` : 1-3 mots ; `brief.tagline` ≤ 80 caractères.
- `brief.cible` : "B2C", "B2B", "B2B2C", "Administrations" ou "Les deux".
- `brief.budget` : fourchette en euros lisible (ex. "20 k€ – 80 k€").

SEGMENTS (pipeline MONV — clé du produit) :
- 3 à 5 segments ; `mode` ∈ "prospection", "sous_traitant", "rachat" uniquement.
- "rachat" seulement si le plan ou le pitch parle de reprise / acquisition.
- Chaque `query` : phrase naturelle en français pour le Guard MONV, avec ZONE géo.
- `key` : ascii court ; `icon` ∈ truck, target, users, briefcase, landmark, building,
  factory, megaphone, scale, calculator.

FLOWS — schéma riche et ADAPTÉ au business (interdit de recopier un triangle générique
type « client final / ta structure / fournisseur » si le plan dit autre chose) :
- `flows.diagram_title` : titre court du schéma (ex. « Chaîne B2B2C assurance »).
- `flows.layout` : "radial", "horizontal" ou "vertical" — aligné sur le plan.
- `flows.flow_insight` : UNE phrase qui aide à LIRE le schéma (pas du blabla produit).
- `flows.acteurs` : liste d'objets
  {"label": "...", "segment_key": "clé ou null", "role": "...", "hint": "...", "emphasis": "primary|secondary|null"}
  Les `label` doivent être identiques aux chaînes utilisées dans les arcs.
- Chaque segment dans `segments` doit avoir au moins un acteur avec le même `segment_key`.
- `flux_valeur`, `flux_financiers`, `flux_information` : 2 à 12 arcs chacun si pertinent.
  Chaque arc : {"origine": "...", "destination": "...", "label": "court", "detail": "précision au clic (1-2 phrases)", "pattern": "solid|dashed"}
  Utilise `pattern":"dashed"` pour flux indirects, réglementaires, feedbacks légers.

Canvas : chaque liste 3 à 6 éléments.

Synthèse :
- forces / risques : 3 à 5 points concrets ; prochaines_etapes : 4 à 7 étapes ordonnées ;
  kpis : 3 à 5 indicateurs mesurables ; budget_estimatif si pertinent.

Structure JSON exacte attendue :
{
  "brief": { "nom", "tagline", "secteur", "localisation", "cible", "budget", "modele_revenus", "ambition" },
  "canvas": { "proposition_valeur", "segments_clients", "canaux", "relation_client", "sources_revenus", "ressources_cles", "activites_cles", "partenaires_cles", "structure_couts" },
  "flows": {
    "diagram_title", "layout", "flow_insight",
    "acteurs": [...],
    "flux_valeur": [...],
    "flux_financiers": [...],
    "flux_information": [...]
  },
  "segments": [ { "key", "label", "description", "mode", "query", "icon" } ],
  "synthesis": { "forces", "risques", "prochaines_etapes", "kpis", "budget_estimatif" }
}
"""


async def generate_dossier_skeleton(
    pitch: str,
    answers: str,
) -> dict[str, Any]:
    """Plan stratégique (LLM 1) puis squelette dossier (LLM 2), modèle `ATELIER_BUSINESS_MODEL`."""
    model = _atelier_business_model()
    user_base = (
        "Pitch initial :\n"
        f"{pitch.strip()}\n\n"
        "Réponses de clarification :\n"
        f"{(answers or '').strip()}\n"
    )
    plan: dict[str, Any] = {}
    try:
        plan = await llm_json_call(
            model=model,
            system=_ATELIER_STRATEGIC_PLAN_SYSTEM,
            messages=[{"role": "user", "content": user_base}],
            max_tokens=4096,
            temperature=0.25,
            json_mode=True,
            allow_json_repair=True,
            repair_model=settings.FILTER_MODEL,
        )
        if not isinstance(plan, dict):
            plan = {}
    except Exception as exc:
        plog("atelier_plan_fallback", error=str(exc)[:300])
        plan = {}

    plan_block = json.dumps(plan, ensure_ascii=False, indent=2) if plan else "{}"
    user_fill = (
        user_base
        + "\n\n--- PLAN STRATÉGIQUE (respecte-le fidèlement ; complète seulement les détails manquants) ---\n"
        + plan_block
    )
    raw = await llm_json_call(
        model=model,
        system=_ATELIER_DOSSIER_FILL_SYSTEM,
        messages=[{"role": "user", "content": user_fill}],
        max_tokens=8192,
        temperature=0.2,
        json_mode=True,
        allow_json_repair=True,
        repair_model=settings.FILTER_MODEL,
    )
    return raw


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
