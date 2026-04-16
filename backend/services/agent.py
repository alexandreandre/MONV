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
from utils.llm import llm_call, llm_json_call
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


# Ordre logique d'affichage (funnel) si le modèle mélange les questions.
_ATELIER_QCM_STEP_ORDER: dict[str, int] = {
    "cible": 0,
    "modele_revenus": 1,
    "localisation": 2,
    "budget": 3,
    "canaux": 4,
    "ambition": 5,
}

# Lorsque le pitch couvre déjà tous les axes : une seule étape de validation.
_PITCH_COMPLETE_CONFIRM_Q = QcmQuestion(
    id="validation_dossier",
    question=(
        "Souhaites-tu ajouter une dernière précision avant que je génère "
        "ton dossier complet ?"
    ),
    options=[
        QcmOption(
            id="pret",
            label="Non, génère le dossier à partir de mon pitch",
            free_text=False,
        ),
        QcmOption(
            id="precision",
            label="Oui, j'ai une précision à ajouter",
            free_text=True,
        ),
    ],
    multiple=False,
)


def _sort_atelier_questions(questions: list[QcmQuestion]) -> list[QcmQuestion]:
    def rank(q: QcmQuestion) -> tuple[int, str]:
        return (_ATELIER_QCM_STEP_ORDER.get(q.id, 50), q.id)

    return sorted(questions, key=rank)


def _finalize_atelier_qcm(
    intro: str,
    questions: list[QcmQuestion],
) -> tuple[str, list[QcmQuestion]]:
    """Filtre, déduplique, trie et plafonne le QCM ; complète si zéro question."""
    seen: set[str] = set()
    cleaned: list[QcmQuestion] = []
    for q in questions:
        qid = (q.id or "").strip()
        if not qid or not (q.question or "").strip():
            continue
        if qid in seen:
            continue
        seen.add(qid)
        cleaned.append(q)
    ordered = _sort_atelier_questions(cleaned)[:5]

    if not ordered:
        intro_out = (
            intro.strip()
            or "Ton pitch est déjà très clair — une dernière étape avant le dossier."
        )
        return intro_out, [_PITCH_COMPLETE_CONFIRM_Q]

    intro_out = intro.strip() or "Affinons ton projet :"
    return intro_out, ordered


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

_PITCH_INTENT_PREFIXES: tuple[str, ...] = (
    "je veux créer ",
    "je veux lancer ",
    "je veux monter ",
    "je veux ouvrir ",
    "je souhaite créer ",
    "je souhaite lancer ",
    "je souhaite monter ",
    "je souhaite ouvrir ",
    "j'aimerais créer ",
    "j'aimerais lancer ",
    "j'aimerais monter ",
    "j'aimerais ouvrir ",
    "je compte créer ",
    "je compte lancer ",
    "je compte monter ",
    "je compte ouvrir ",
    "mon projet : ",
    "mon idée : ",
    "idée : ",
)

def _strip_french_pitch_intent(line: str) -> str:
    """Retire les préfixes du type « je veux créer » pour densifier le nom de projet."""
    s = " ".join(line.split())
    while True:
        low = s.lower()
        hit = False
        for p in _PITCH_INTENT_PREFIXES:
            if low.startswith(p):
                s = s[len(p) :].lstrip()
                hit = True
                break
        if not hit:
            break
    return s


def _strip_leading_article_phrase(line: str) -> str:
    """Retire un article en tête (« une boîte » → « boîte ») une seule fois."""
    s = line.strip()
    low = s.lower()
    for art in ("une ", "un ", "des ", "les ", "la ", "le ", "l'", "d'"):
        if low.startswith(art):
            return s[len(art) :].lstrip()
    return s


def _titlecase_project_fr(words: list[str]) -> str:
    """Casse de titre légère pour un nom de projet (particules courtes au milieu)."""
    if not words:
        return ""
    n = len(words)
    out: list[str] = []
    for i, raw in enumerate(words):
        core = raw.strip(".,;:!?").strip()
        if not core:
            continue
        lowc = core.lower()
        if i == 0 or i == n - 1:
            out.append(core[:1].upper() + core[1:].lower())
        elif lowc in _PROJECT_TITLE_SMALL:
            out.append(lowc)
        else:
            out.append(core[:1].upper() + core[1:].lower())
    return " ".join(out)


def heuristic_atelier_conversation_title(pitch: str, max_len: int = 72) -> str:
    """Titre de repli à partir du pitch : première phrase utile, découpe propre aux mots."""
    line = " ".join((pitch or "").split())
    if not line:
        return "Projet Atelier"
    lowered = line.lower()
    for prefix in (
        "bonjour ",
        "salut ",
        "bonsoir ",
        "hello ",
        "coucou ",
    ):
        if lowered.startswith(prefix):
            line = line[len(prefix) :].lstrip()
            lowered = line.lower()
            break
    for sep in (".", "!", "?", "…"):
        pos = line.find(sep)
        if 8 <= pos <= max_len + 24:
            line = line[:pos].strip()
            break
    if len(line) <= max_len:
        return line or "Projet Atelier"
    chunk = line[: max_len + 1]
    if " " in chunk:
        cut = chunk.rsplit(" ", 1)[0].strip()
        if len(cut) >= 8:
            return cut + "…"
    return line[:max_len].rstrip() + "…"


def heuristic_atelier_project_folder_name(pitch: str) -> str:
    """Nom de dossier projet de repli : pitch nettoyé, quelques mots, lieu conservé."""
    line = " ".join((pitch or "").split())
    if not line:
        return "Projet Atelier"
    lowered = line.lower()
    for prefix in (
        "bonjour ",
        "salut ",
        "bonsoir ",
        "hello ",
        "coucou ",
    ):
        if lowered.startswith(prefix):
            line = line[len(prefix) :].lstrip()
            lowered = line.lower()
            break
    line = _strip_french_pitch_intent(line)
    line = _strip_leading_article_phrase(line)
    if not line.strip():
        return "Projet Atelier"
    for sep in (".", "!", "?", "…"):
        pos = line.find(sep)
        if 8 <= pos <= 90:
            line = line[:pos].strip()
            break
    words = line.split()
    if len(words) > 7:
        words = words[:7]
    titled = _titlecase_project_fr(words)
    if not titled:
        return "Projet Atelier"
    out = titled[:80].strip()
    return out or "Projet Atelier"


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
