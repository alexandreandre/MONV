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
    BusinessCanvas,
    BusinessDossier,
    FlowMap,
    GuardResult,
    ProjectBrief,
    QcmQuestion,
    SegmentBrief,
    SegmentResult,
)
from services.atelier_constants import ATELIER_MODE_LABEL
from services.atelier_coerce import coerce_dossier
from services.atelier_mutations import atelier_dossier_rollup_fields, merge_atelier_cross_segment_tags
from services.atelier_heuristics import (
    heuristic_atelier_conversation_title,
    heuristic_atelier_project_folder_name,
)
from services.atelier_qcm import (
    _FALLBACK_ATELIER_QUESTIONS,
    finalize_atelier_qcm as _finalize_atelier_qcm,
    parse_qcm_raw as _parse_qcm_raw,
)
from services.api_engine import _dedup_key, execute_plan
from services.guard import run_guard
from services.orchestrator import run_orchestrator
from services.modes import normalize_mode, Mode
from services.relevance import (
    compute_relevance_scores,
    relevance_flag_for_score,
    relevance_reason_excluded_fr,
)
from services.sirene import patch_sirene_calls_from_guard_entities
from utils.llm import llm_call, llm_json_call
from utils.pipeline_log import plog

# Limite de lignes sérialisées par segment (metadata + search_history).
_ATELIER_PREVIEW_MAX_ROWS = 400


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
Tu es l'Atelier MONV : tu aides un porteur de projet à structurer son idée AVANT
de générer un dossier (business model, schéma de flux, listes d'entreprises réelles).
Tu reçois un pitch libre (parfois déjà très détaillé).

RÈGLE D'OR — NOMBRE DE QUESTIONS = FONCTION DU MANQUE RÉEL :
- Avant chaque question, vérifie si l'axe est DÉJÀ couvert par le pitch (même implicitement).
  Si oui : ne pose PAS cette question (ex. ne redemande pas la ville si elle est nommée ;
  ne redemande pas service sur place + livraison + e-commerce si les trois sont déjà annoncés).
- Zéro question est un résultat VALIDE et SOUHAITABLE lorsque le pitch est déjà assez riche
  pour produire un dossier et des recherches d'entreprises pertinentes. Dans ce cas :
  "questions": [] et l'intro confirme que tu enchaînes sur le dossier.
- Le volume de questions n'est PAS fixe : 0 si rien d'utile à débloquer, jusqu'à 8 si le pitch
  est très vague ou lacunaire sur plusieurs axes indépendants.

ANTI-PATTERN (à éviter) :
- Ne pose PAS un questionnaire « start-up générique » (B2B/B2C + abonnement/SaaS +
  budget minuscule) si le pitch décrit déjà un métier concret (restauration, retail,
  artisanat, santé, logistique, import, etc.).
- Ne recycle pas des questions « coaching » (budget global, expérience du fondateur, délai
  d'ouverture, positionnement haut de gamme ou non) si le pitch y a déjà répondu ou si la
  réponse est déductible sans ambiguïté pour la suite du dossier.
- Les options doivent être ANCRÉES dans le pitch (noms de canaux, formats, zones,
  types de clientèle que l'utilisateur a évoqués ou qui sont évidents pour ce métier).
- Ne demande pas « Administration » si le projet ne concerne manifestement pas le public.

AXES D'ANALYSE (interne — ne pas les lister à l'utilisateur) :
- cible : qui paie / qui consomme (B2C, B2B, pros, mixte, événementiel…)
- modele_revenus : ticket resto, vente à emporter/livraison, e-commerce, abonnement
  box, licence, commission, services, mixte omnicanal…
- localisation : lieu d'implantation ET, si vente à distance : zone de livraison /
  expédition (ville, métropole, région, France, UE)
- conformite / risques : alcools, santé, transport denrées, import/douanes, données,
  marchés réglementés — UNE question courte si le pitch l'implique ou si ça change
  la chaîne de valeur
- canaux : acquisition, distribution, partenaires prescripteurs
- budget : fourchette réaliste pour CE type d'activité (un restaurant haut de gamme
  ou un local commercial ≠ un SaaS solo)
- ambition : taille d'équipe / surface / volume à 2-3 ans

NOMBRE DE QUESTIONS (guide, pas un quota obligatoire) :
- Pitch très flou ou < ~40 mots : jusqu'à 8 questions au total, les plus discriminantes d'abord.
- Pitch moyen : seulement les axes encore ambigus pour le dossier (souvent 1 à 4 questions).
- Pitch déjà dense (ex. offre + zone + canaux + modèle économique déjà posés) : 0 à 2 questions
  ultra ciblées sur le seul angle qui bloque encore (ex. périmètre exact d'une livraison locale
  si « local » est flou ; licence / import si l'alcool est central et non cadré).
- Pitch complet sur tous les axes utiles au dossier et aux recherches : "questions": [].

ORDRE DES QUESTIONS (respecte cet ordre quand il y en a plusieurs) :
1) cible / priorité marché
2) modèle de revenus ou répartition des sources (multiple=true si mix fort)
3) localisation physique + périmètre livraison / vente en ligne si pertinent
4) canaux ou dépendances clés (go-to-market) si encore flou
5) conformité / import / opérations critiques si le secteur le impose
6) budget de lancement
7) ambition de taille

IDs PRÉFÉRÉS (snake_case) : "cible", "modele_revenus", "localisation", "canaux",
"conformite", "budget", "ambition". Autres ids explicites acceptés si le pitch impose
un angle unique (ex. "import_sake", "positionnement_prix").

FORMAT DES QUESTIONS :
- Tutoiement, une intention par question, libellés concrets.
- 4 à 6 options contextualisées + option "Autre" avec free_text=true (sauf doublon).
- "multiple": true pour "canaux" ou "modele_revenus" quand l'utilisateur peut cocher
  plusieurs sources ou canaux pertinents.

CHAMP "intro" (OBLIGATION) — deux paragraphes séparés par le littéral \\n\\n :
1) Paragraphe 1 : TA LECTURE du pitch (2 à 4 phrases). Reformule promesse, format
   (sur place / livraison / web…), différenciation ou niche, zone déjà mentionnée.
   Montre que tu as compris le MÉTIER, pas seulement « un projet d'entreprise ».
2) Paragraphe 2 : une phrase courte qui enchaîne vers le QCM (ex. ce que tu veux
   verrouiller pour le dossier et les recherches).

Si "questions" est vide : paragraphe 2 peut être « Je peux enchaîner sur le dossier. »

Réponds UNIQUEMENT avec un JSON strict :
{
  "intro": "Paragraphe lecture du pitch...\\n\\nPhrase de transition vers le QCM.",
  "questions": [
    {
      "id": "cible",
      "question": "Libellé métier contextualisé",
      "options": [
        {"id": "exemple", "label": "Option ancrée dans le pitch", "free_text": false},
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
    """Génère un QCM adapté au pitch (0 à 8 questions selon le manque réel).

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
            temperature=0.22,
        )
        intro, questions = _parse_qcm_raw(raw)
        return _finalize_atelier_qcm(intro, questions)
    except Exception as exc:
        plog("atelier_qcm_fallback", error=str(exc)[:300])
    return (
        "Je résume : tu montes un projet entrepreneurial et il me manque encore "
        "quelques points pour caler le dossier et les recherches d'entreprises.\n\n"
        "Réponds aux questions ci-dessous (une réponse par bloc).",
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
      "pourquoi": "1 phrase utile au porteur",
      "out_of_scope": false,
      "out_of_scope_note": null
    }
  ],
  "alertes_structurelles": ["..."],
  "hypotheses_a_valider": ["..."],
  "jalons_creation": [
    "Semaine 1 — cadrage & arbitrages",
    "Étude de marché & offre",
    "Business plan & financement",
    "Juridique & conformité",
    "Local / production / outils",
    "Recrutement & organisation",
    "Lancement & acquisition clients",
    "Pilotage & optimisation"
  ]
}

Règles :
- 4 à 12 entrées dans `acteurs_cles` selon la complexité réelle (pas toujours 3).
- 3 à 5 objets dans `segments_recherche` (jamais « atelier » ni « client » comme mode).
- Les noms dans `de`/`vers` doivent correspondre EXACTEMENT à des `nom` de `acteurs_cles`.
- `jalons_creation` : obligatoire, 10 à 20 entrées, chacune ≤ 72 caractères, sans doublons,
  couvrant de « démarrage immédiat » jusqu'à « pilotage / croisière » selon le projet.

PÉRIMÈTRE PIPELINE MONV (obligatoire) :
- Chaque segment qui doit lancer une recherche d'entreprises françaises doit cibler des
  **personnes morales ou établissements identifiables en France** (SIRENE, Pappers,
  Google Places). Interdit comme cible d'appel pipeline : producteurs ou cibles
  exclusivement à l'étranger sans implant française ; **particuliers / consommateurs
  finaux** comme « segment à lister » (non couvert par les annuaires) ; listes de
  « clientèle » générique sans angle B2B entreprise.
- Si une cible est pertinente stratégiquement mais **non cherchable** par ce pipeline,
  mets `"out_of_scope": true`, une `out_of_scope_note` courte (recherche web,
  panels, enquête terrain…) et ne prévois pas de requête MONV pour ce point.
- Pour import / distribution alimentaire ou boissons : favoriser grossistes,
  importateurs **français** (NAF 46.x), distributeurs B2B, prescripteurs entreprises —
  pas les concurrents directs « restaurants » comme proxy d'une clientèle.
"""


_ATELIER_DOSSIER_FILL_SYSTEM = """\
Tu es l'Atelier MONV : tu transformes un PLAN STRATÉGIQUE (JSON) + pitch + QCM
en DOSSIER LIVRABLE pour l'interface utilisateur.

Sortie : UN SEUL objet JSON (pas de markdown, pas de commentaires hors JSON).

FORMAT JSON (critique) :
- Guillemets doubles ; pas de saut de ligne littéral dans les chaînes (remplace par virgules ou points) ;
  `detail` des arcs ≤ 200 car.
- Objet complet et **terminé** (toutes accolades fermées).
- **Priorité tokens** : canvas et flux restent compacts ; la **checklist** doit être très fournie
  (c'est le guide opérationnel principal du porteur).

Contraintes rédactionnelles :
- Tout en FRANÇAIS, factuel, sans emoji ni ton marketing creux.
- Canvas : puces 5-12 mots, orientées action / test / décision.
- `brief.nom` : 1-3 mots ; `brief.tagline` ≤ 80 caractères.
- `brief.cible` : "B2C", "B2B", "B2B2C", "Administrations" ou "Les deux".
- `brief.budget` : phrase complète en français (ex. « 80 k€ – 200 k€ dont fonds de roulement 6 mois »).
- `brief.budget_min_eur` / `brief.budget_max_eur` : entiers optionnels cohérents avec la phrase.
- `brief.budget_hypotheses` : 1 à 4 puces courtes (loyer, stock, équipement, FR…).

SEGMENTS (pipeline MONV — clé du produit) :
- 3 à 5 segments ; `mode` ∈ "prospection", "sous_traitant", "rachat" uniquement.
- "rachat" seulement si le plan ou le pitch parle de reprise / acquisition.
- Chaque `query` : phrase naturelle en français pour le Guard MONV, avec ZONE géo,
  **sans termes génériques type « importateur » seul** : précise le produit, le canal
  B2B et la zone (ex. « Grossistes en boissons alcoolisées spécialisés commerce de gros
  Rhône-Alpes »). Pour commerce de gros boissons / import : privilégier codes APE 46.34Z,
  46.39A, 46.39B lorsque c'est pertinent (mentionner dans la requête ou les mots-clés).
- Hors périmètre annuaires FR : `"out_of_scope": true`, `out_of_scope_note` explicite,
  `query` peut être vide ; pas d'icône inventée hors liste.
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

Canvas : chaque liste **3 à 5** éléments (puces courtes uniquement).

Synthèse :
- forces / risques : 3 à 5 points concrets ; prochaines_etapes : **6 à 10** micro-étapes alignées sur le début de la checklist ;
  kpis : 3 à 5 indicateurs mesurables ; budget_estimatif si pertinent.
- ordres_grandeur : 4 à 10 puces ultra courtes (chiffres, fourchettes, %, pas de phrases longues) :
  investissement global, mix financement indicatif, CA / marge / seuil de rentabilité si pertinent,
  BFR ou trésorerie si pertinent — style note de cadrage pro.
- conseil_semaine : UNE action concrète immédiate (rendez-vous, livrable, contact) sur 1 à 3 phrases max.

CHECKLIST — **guide A à Z « comme une recette »** (le cœur du livrable ; **très dense**, adapté au pitch + plan) :
- Lis le plan stratégique : champ `jalons_creation` (s'il manque, déduis-le du pitch). **Chaque jalon majeur**
  doit devenir au moins une `section` OU être regroupé en phases avec plusieurs sections.
- `headline` : objectif utilisateur en une ligne (ex. « Ouvrir … à … »).
- `lede` : une ligne chrono (ex. « À faire cette semaine » ou « Mois 1 à 4 — préparation ») si pertinent.
- `sections` : **minimum 14 sections**, viser **18 à 26** pour un projet multi-canaux (ex. restau + livraison + e-commerce réglementé).
  Ordre **chronologique** du premier geste jusqu'au pilotage en « régime de croisière ».
- Chaque section :
  - `title` : libellé explicite, style atelier (ex. « Semaine 1 — Démarrer proprement — 7 jours »,
    « Étape 3 — Business plan — Mois 2-3 », « Phase exécution — Travaux & MEP »). Inclure durée ou mois quand c'est clair.
  - `subtitle` : optionnel (ex. « Mois 1 », « 2-4 semaines »).
  - `items` : **minimum 4 items par section**, viser **5 à 12** selon l'étape ; chaque item = action **vérifiable**
    (comme une case à cocher), formulation impérative ou résultat attendu, **sans numérotation dans le texte**.
- Chaque item : `{ "label": "...", "guide": "..." }` avec
  - `label` : une ligne, ≤ 140 caractères, concret (livrable, rendez-vous, document, seuil chiffré…).
  - `guide` : **2 à 4 phrases** utiles (comment faire, où trouver, piège fréquent, critère de « fait »). Pas de jargon creux.
- Couvre **tout le cycle** : cadrage & arbitrages, étude marché / offre, BP & financement, juridique & conformité
  (inclure sujets spécifiques au secteur : alcool, hygiene, métrologie, données perso, etc. si pertinents),
  local / équipements / supply chain si pertinent, recrutement, opérations multi-canaux (ex. sur place + livraison + e-commerce),
  marketing & lancement, ouverture, puis **pilotage récurrent** (tableaux de bord, rituels, revues).
- `pitfalls_title` : ex. « Les 10 pièges à éviter (à relire tous les 3 mois) ».
- `pitfalls` : **10 à 14** objets `{label, guide}` — erreurs classiques du secteur / modèle, guides courts mais percutants.
- **Total global** : vise **≥ 110 items** checklist (hors pièges) pour un projet riche comme restauration + livraison + vente en ligne ;
  si le projet est plus simple, reste au-dessus de **75 items** quand même.
- Noms propres géographiques ou dispositifs : seulement si plausibles pour la zone du brief (ex. métropole citée).

Structure JSON exacte attendue :
{
  "brief": { "nom", "tagline", "secteur", "localisation", "cible", "budget", "budget_min_eur", "budget_max_eur", "budget_hypotheses", "modele_revenus", "ambition" },
  "canvas": { "proposition_valeur", "segments_clients", "canaux", "relation_client", "sources_revenus", "ressources_cles", "activites_cles", "partenaires_cles", "structure_couts" },
  "flows": {
    "diagram_title", "layout", "flow_insight",
    "acteurs": [...],
    "flux_valeur": [...],
    "flux_financiers": [...],
    "flux_information": [...]
  },
  "segments": [ { "key", "label", "description", "mode", "query", "icon", "out_of_scope", "out_of_scope_note" } ],
  "synthesis": {
    "forces", "risques", "prochaines_etapes", "kpis", "budget_estimatif",
    "ordres_grandeur", "conseil_semaine",
    "checklist": {
      "headline", "lede", "sections": [ { "title", "subtitle", "items": [ { "label", "guide" } ] } ],
      "pitfalls_title", "pitfalls": [ { "label", "guide" } ]
    }
  }
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
        + "\n\n--- CONSIGNE FINALE ---\n"
        "Le champ `synthesis.checklist` est la priorité absolue du JSON : feuille de route A à Z, "
        "très détaillée, en suivant `jalons_creation` du plan (chaque jalon = une ou plusieurs sections). "
        "Respecte les minimums indiqués dans le prompt système (nombre de sections, d'items, pièges). "
        "Canvas et flux : rester concis pour laisser de la place à la checklist."
    )
    raw = await llm_json_call(
        model=model,
        system=_ATELIER_DOSSIER_FILL_SYSTEM,
        messages=[{"role": "user", "content": user_fill}],
        max_tokens=16384,
        temperature=0.2,
        json_mode=True,
        allow_json_repair=True,
        repair_model=settings.FILTER_MODEL,
    )
    return raw


# ─── Couche 3 : exécution des segments via le pipeline MONV ──────────────────


async def run_segment_search(segment: SegmentBrief) -> SegmentResult:
    """Exécute un segment en REUTILISANT le pipeline MONV standard.

    Guard → Orchestrator → API Engine. La pertinence LLM est **calculée et exposée**
    sur chaque ligne (`relevance_score`, `relevance_flag`, `reason_excluded`) sans
    retirer silencieusement les résultats : l'UI masque les `excluded` par défaut."""
    mode: Mode = normalize_mode(segment.mode)
    if segment.out_of_scope:
        note = segment.out_of_scope_note or (
            "Segment hors périmètre des annuaires d'entreprises françaises MONV ; "
            "compléter par recherche web ou enquête terrain."
        )
        return SegmentResult(
            key=segment.key,
            label=segment.label,
            description=segment.description,
            mode=mode,
            icon=segment.icon,
            query=segment.query or "",
            total=0,
            credits_required=0,
            columns=[],
            preview=[],
            map_points=[],
            error=None,
            out_of_scope=True,
            out_of_scope_note=note,
            total_relevant=0,
            relevance_threshold=None,
        )
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
        results = await execute_plan(plan, mode=mode)
        n = len(results.results)
        scores: list[int] = []
        threshold = 5
        if n > 0:
            scores, threshold, rel_stats = await compute_relevance_scores(
                results.results,
                user_query=segment.query,
                guard_result=guard_result,
                mode=mode,
            )
            plog(
                "atelier_segment_relevance",
                key=segment.key,
                skipped=rel_stats.get("relevance_skipped"),
                threshold=threshold,
                avg=rel_stats.get("relevance_avg_score"),
            )
        preview: list[dict[str, Any]] = []
        preview_cap = min(_ATELIER_PREVIEW_MAX_ROWS, n)
        for i in range(preview_cap):
            r = results.results[i]
            sc = scores[i] if i < len(scores) else threshold
            flg = relevance_flag_for_score(sc, threshold)
            d = r.model_dump()
            d["_dedup_key"] = _dedup_key(r)
            d["relevance_score"] = round(sc / 10.0, 3)
            d["relevance_flag"] = flg
            d["reason_excluded"] = relevance_reason_excluded_fr(sc, threshold)
            d["segments"] = [segment.key]
            preview.append(d)

        total_rel = 0
        if n > 0 and scores:
            total_rel = sum(
                1
                for i in range(n)
                if relevance_flag_for_score(scores[i], threshold) in ("ok", "warning")
            )

        plog(
            "atelier_segment_done",
            key=segment.key,
            total=results.total,
            credits=results.credits_required,
            preview_rows=len(preview),
            total_relevant=total_rel,
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
            preview=preview,
            map_points=map_points,
            total_relevant=total_rel,
            relevance_threshold=threshold if n > 0 else None,
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


_ATELIER_CANVAS_REFRESH_SYSTEM = """\
Tu es l'Atelier MONV. Tu reçois le pitch, les réponses QCM, le brief structuré à jour et le Business Model Canvas actuel (JSON).
Réécris le canvas pour qu'il soit aligné avec le brief : 9 cases, 3 à 6 puces par case (puces courtes en français, factuel, sans emoji).

Réponds par UN SEUL objet JSON strict :
{"canvas": { "proposition_valeur": [], "segments_clients": [], "canaux": [], "relation_client": [], "sources_revenus": [], "ressources_cles": [], "activites_cles": [], "partenaires_cles": [], "structure_couts": [] }}
Guillemets doubles ; pas de markdown hors JSON ; pas de saut de ligne dans les chaînes.
"""


_ATELIER_FLOWS_REFRESH_SYSTEM = """\
Tu es l'Atelier MONV. Tu reçois le pitch, les réponses QCM, le brief, la liste des clés de segments autorisées, et la cartographie des flux actuelle (JSON).
Produis UN SEUL objet JSON strict :
{"flows": { "diagram_title": null, "layout": "radial|horizontal|vertical", "flow_insight": "", "acteurs": [], "flux_valeur": [], "flux_financiers": [], "flux_information": [] }}

Règles : mêmes contraintes que le dossier Atelier (acteurs avec segment_key seulement si la clé est dans la liste autorisée ; arcs entre libellés d'acteurs existants).
Français, factuel, pas de markdown hors JSON.
"""


async def regenerate_atelier_canvas_llm(
    pitch: str,
    answers: str,
    brief: ProjectBrief,
    current_canvas: BusinessCanvas,
) -> BusinessCanvas:
    from services.atelier_coerce import coerce_canvas_from_llm_dict

    model = _atelier_business_model()
    payload = {
        "pitch": pitch.strip(),
        "reponses_qcm": (answers or "").strip(),
        "brief": brief.model_dump(),
        "canvas_actuel": current_canvas.model_dump(),
    }
    raw = await llm_json_call(
        model=model,
        system=_ATELIER_CANVAS_REFRESH_SYSTEM,
        messages=[{"role": "user", "content": json.dumps(payload, ensure_ascii=False)}],
        max_tokens=4096,
        temperature=0.2,
        json_mode=True,
        allow_json_repair=True,
        repair_model=settings.FILTER_MODEL,
    )
    if not isinstance(raw, dict):
        return current_canvas
    return coerce_canvas_from_llm_dict(raw)


async def regenerate_atelier_flows_llm(
    pitch: str,
    answers: str,
    brief: ProjectBrief,
    segment_keys: list[str],
    current_flows: FlowMap,
) -> FlowMap:
    from services.atelier_coerce import coerce_flows_from_llm_dict

    model = _atelier_business_model()
    keys = [str(k).strip().lower()[:40] for k in segment_keys if str(k).strip()]
    payload = {
        "pitch": pitch.strip(),
        "reponses_qcm": (answers or "").strip(),
        "brief": brief.model_dump(),
        "cles_segments_autorisees": keys,
        "flows_actuels": current_flows.model_dump(),
    }
    raw = await llm_json_call(
        model=model,
        system=_ATELIER_FLOWS_REFRESH_SYSTEM,
        messages=[{"role": "user", "content": json.dumps(payload, ensure_ascii=False)}],
        max_tokens=4096,
        temperature=0.2,
        json_mode=True,
        allow_json_repair=True,
        repair_model=settings.FILTER_MODEL,
    )
    if not isinstance(raw, dict):
        return current_flows
    return coerce_flows_from_llm_dict(raw, set(keys))


__all__ = [
    "ATELIER_MODE_LABEL",
    "build_brief_metadata",
    "coerce_dossier",
    "dossier_metadata_json",
    "generate_atelier_qcm",
    "generate_dossier_skeleton",
    "regenerate_atelier_canvas_llm",
    "regenerate_atelier_flows_llm",
    "run_segment_search",
    "run_segment_searches",
]
