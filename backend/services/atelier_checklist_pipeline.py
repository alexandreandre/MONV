"""
Pipeline multi-étapes pour la checklist Atelier (régénération).

Ordre : squelette (titres / phases) → détail des actions (lots parallèles) →
soit **chemin rapide** (brouillon déjà dense → petit appel « pièges » seulement),
soit étape QA complète → coercion Pydantic.

Pourquoi c'était lent : l'étape QA demandait au modèle de **réémettre toute** la checklist
(75–110+ items, max_tokens 14k), soit souvent la plus longue partie du pipeline alors que
le brouillon post-détail est déjà exploitable.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any

from config import settings
from models.schemas import AgentSynthesis, AtelierChecklist, ChecklistItem, ProjectBrief
from services.agent_config import resolve_llm_for_block
from services.atelier_coerce import coerce_checklist_from_llm_dict, merge_atelier_checklist_detail_chunks
from utils.llm import llm_json_call
from utils.pipeline_log import plog

# Sections par appel « détail » (équilibre tokens / parallélisme)
_DETAIL_CHUNK_SIZE = 4

# Brouillon suffisamment fourni → pas d'étape QA « full JSON » (très coûteuse en latence).
_FAST_PATH_MIN_SECTIONS = 10
_FAST_PATH_MIN_ITEMS = 42
_FAST_PATH_MIN_PITFALLS = 6

_OUTLINE_SYSTEM = """\
Tu es l'agent « Architecte de parcours » de l'Atelier MONV.

MISSION : produire uniquement le SQUELETTE chronologique de la checklist (titres de
sections / étapes), SANS les cases à cocher ni les guides détaillés.

Entrée : JSON utilisateur avec pitch, réponses QCM, brief, synthèse (sans checklist),
segments de recherche.

Règles :
- Français, factuel, sans emoji.
- Ordre strict : du premier geste immédiat jusqu'au pilotage en régime de croisière.
- **Minimum 14 sections**, viser **18 à 26** si le projet est multi-canaux (ex. physique +
  livraison + digital réglementé).
- Chaque section : `title` explicite (ex. « Semaine 1 — Démarrer proprement — 7 jours »,
  « Étape 3 — Business plan — Mois 2-3 »), `subtitle` optionnel (durée, mois, fenêtre).
- `bloc_chrono` ∈ demarrage | preparation | execution | lancement | pilotage
- `id` : identifiants uniques **s01**, **s02**, … **s26** (ascii, sans trous dans la série).
- `headline_draft` : objectif utilisateur en une ligne (≤ 140 car.).
- `lede_draft` : ligne contexte chrono (ex. « À faire cette semaine ») ou null.
- Pas de saut de ligne littéral dans les chaînes JSON.

Réponds UNIQUEMENT avec un objet JSON strict :
{
  "headline_draft": "...",
  "lede_draft": "... ou null",
  "outline_sections": [
    {"id": "s01", "title": "...", "subtitle": "... ou null", "bloc_chrono": "demarrage"}
  ]
}
"""


_DETAIL_SYSTEM = """\
Tu es l'agent « Rédacteur opérationnel » de l'Atelier MONV.

MISSION : pour les sections listées dans `sections_a_remplir` uniquement, produire les
**items** de checklist (actions vérifiables) en conservant les `id`, `title`, `subtitle`
fournis (tu peux corriger une coquille minime sur title, sans changer le sens).

Contexte global (pitch, brief, etc.) est fourni pour aligner le contenu.

Règles items :
- **Minimum 4 items** par section, viser **5 à 12** selon la densité de l'étape.
- Chaque item : `label` ≤ 140 caractères, impératif ou résultat mesurable ; `guide` :
  **2 à 4 phrases** (comment, critère « fait », piège fréquent). Pas de jargon creux.
- Pas de numérotation « 1. » dans les labels.
- Français, sans emoji ; pas de saut de ligne littéral dans les chaînes JSON.

Réponds UNIQUEMENT avec :
{ "sections": [ { "id", "title", "subtitle", "items": [ { "label", "guide" } ] } ] }
"""


_QA_SYSTEM = """\
Tu es l'agent « Audit complétude & cohérence » de l'Atelier MONV.

Tu reçois une checklist JSON (headline, lede, sections avec items, éventuellement
pitfalls vides ou incomplets).

MISSION :
1. **Couverture** : juridique, finance, offre/marché, opérations, recrutement, lancement,
   pilotage récurrent — adapte au secteur du brief. Ajoute des **sections** ou **items**
   manquants si des trous bloquants existent (sans doublons évidents).
2. **Cohérence chronologique** : pas d'étape absurde avant son prérequis ; réordonne les
   `sections` si nécessaire (liste ordonnée finale).
3. **Quantité** : vise **au moins 75 items** au total hors pièges (110+ si restauration +
   livraison + e-commerce ou équivalent complexe).
4. **Pièges** : `pitfalls_title` + **10 à 14** entrées `{label, guide}` sectorielles,
   percutantes.
5. Conserve le style existant ; améliore plutôt qu'effacer.

Contraintes finales :
- `headline` et `lede` : forts, clairs, alignés au brief.
- label ≤ 140 car. ; guides 2 à 4 phrases ; pas de saut de ligne littéral dans les chaînes.

Réponds UNIQUEMENT avec :
{"checklist": { "headline", "lede", "sections": [ { "title", "subtitle", "items": [ { "label", "guide" } ] } ], "pitfalls_title", "pitfalls": [ { "label", "guide" } ] }}

**Efficacité** : le brouillon d'entrée contient déjà sections et items — **conserve** ce qui
est pertinent ; complète les trous, réordonne si besoin, enrichis surtout les pièges.
Évite de tout réécrire mot pour mot si ce n'est pas nécessaire.
"""


_PITFALLS_ONLY_SYSTEM = """\
Tu es l'Atelier MONV. Tu reçois un résumé de projet et les titres des sections d'une checklist
déjà rédigée (les actions détaillées existent côté serveur).

MISSION : produire **uniquement** les pièges à éviter pour ce secteur / ce contexte.

Réponds UNIQUEMENT avec un objet JSON strict :
{"pitfalls_title": "...", "pitfalls": [ {"label": "...", "guide": "..." }, ... ]}

- pitfalls_title : une ligne percutante (≤ 90 car.).
- pitfalls : **8 à 12** entrées ; label ≤ 120 car. ; guide **1 à 2 phrases** (piège + comment l'éviter).
- Français, factuel, sans emoji ; pas de saut de ligne littéral dans les chaînes.
"""


_MONOLITH_FALLBACK_SYSTEM = """\
Tu es l'Atelier MONV. Tu reçois le pitch, les réponses QCM, le brief structuré, un extrait
de la synthèse existante (sans checklist) et les libellés des segments de recherche entreprises.
MISSION : produire une NOUVELLE checklist opérationnelle complète (JSON uniquement).

Règles :
- Français, factuel, sans emoji ni ton marketing creux.
- `headline` : objectif utilisateur en une ligne ; `lede` : une ligne chrono ou contexte si pertinent.
- `sections` : minimum 14 sections, viser 18 à 26 si multi-canaux ; ordre chronologique.
- Chaque section : `title`, `subtitle` optionnel, `items` minimum 4 par section (viser 5 à 12) ;
  chaque item `{ "label", "guide" }` avec label ≤ 140 car. et guide 2 à 4 phrases.
- `pitfalls_title` et `pitfalls` : 10 à 14 pièges avec guides courts.
- Vise au moins 75 items au total hors pièges (110+ si restauration + livraison + e-commerce).
- Guillemets doubles JSON ; pas de saut de ligne littéral dans les chaînes.

Réponds UNIQUEMENT avec :
{"checklist": { "headline", "lede", "sections": [ { "title", "subtitle", "items": [ { "label", "guide" } ] } ], "pitfalls_title", "pitfalls": [ { "label", "guide" } ] }}
"""


def _atelier_model() -> str:
    m = (settings.ATELIER_BUSINESS_MODEL or "").strip()
    return m or settings.ORCHESTRATOR_MODEL


def _base_user_payload(
    pitch: str,
    answers: str,
    brief: ProjectBrief,
    synthesis: AgentSynthesis,
    segment_labels: list[str],
) -> dict[str, Any]:
    syn_ctx = {
        "forces": (synthesis.forces or [])[:8],
        "risques": (synthesis.risques or [])[:8],
        "prochaines_etapes": (synthesis.prochaines_etapes or [])[:12],
        "kpis": (synthesis.kpis or [])[:8],
        "budget_estimatif": synthesis.budget_estimatif,
        "ordres_grandeur": (synthesis.ordres_grandeur or [])[:12],
        "conseil_semaine": synthesis.conseil_semaine,
    }
    return {
        "pitch": pitch.strip(),
        "reponses_qcm": (answers or "").strip(),
        "brief": brief.model_dump(),
        "synthese_sans_checklist": syn_ctx,
        "segments_recherche": [str(x).strip() for x in segment_labels if str(x).strip()][
            :12
        ],
    }


def _parse_outline(raw: dict[str, Any]) -> tuple[list[dict[str, Any]], str, str | None] | None:
    secs = raw.get("outline_sections")
    if not isinstance(secs, list) or len(secs) < 14:
        return None
    outline: list[dict[str, Any]] = []
    for s in secs[:30]:
        if not isinstance(s, dict):
            continue
        sid = str(s.get("id") or "").strip()
        title = str(s.get("title") or "").strip()
        if not sid or not title:
            continue
        st = s.get("subtitle")
        subtitle = str(st).strip() if st is not None else ""
        outline.append(
            {
                "id": sid[:12],
                "title": title[:220],
                "subtitle": subtitle[:200] if subtitle else None,
                "bloc_chrono": str(s.get("bloc_chrono") or "").strip()[:32] or None,
            }
        )
    if len(outline) < 14:
        return None
    hd = str(raw.get("headline_draft") or "").strip()[:220]
    ld_raw = raw.get("lede_draft")
    lede = str(ld_raw).strip()[:360] if ld_raw not in (None, "", False) else None
    return outline, hd, lede


async def _call_outline(model: str, payload: dict[str, Any]) -> dict[str, Any]:
    m = (model or "").strip() or _atelier_model()
    cfg = await resolve_llm_for_block(
        "atelier",
        "checklist_outline",
        default_model=m,
        default_system=_OUTLINE_SYSTEM,
        default_max_tokens=4096,
        default_temperature=0.22,
    )
    return await llm_json_call(
        model=cfg.model,
        system=cfg.system_prompt,
        messages=[{"role": "user", "content": json.dumps(payload, ensure_ascii=False)}],
        max_tokens=cfg.max_tokens,
        temperature=cfg.temperature,
        json_mode=True,
        allow_json_repair=True,
        repair_model=settings.FILTER_MODEL,
    )


async def _call_detail_chunk(
    model: str,
    payload_base: dict[str, Any],
    chunk: list[dict[str, Any]],
) -> dict[str, Any]:
    m = (model or "").strip() or _atelier_model()
    cfg = await resolve_llm_for_block(
        "atelier",
        "checklist_detail",
        default_model=m,
        default_system=_DETAIL_SYSTEM,
        default_max_tokens=8192,
        default_temperature=0.22,
    )
    body = {
        **payload_base,
        "sections_a_remplir": chunk,
    }
    return await llm_json_call(
        model=cfg.model,
        system=cfg.system_prompt,
        messages=[{"role": "user", "content": json.dumps(body, ensure_ascii=False)}],
        max_tokens=cfg.max_tokens,
        temperature=cfg.temperature,
        json_mode=True,
        allow_json_repair=True,
        repair_model=settings.FILTER_MODEL,
    )


async def _call_qa(model: str, draft_checklist: dict[str, Any], payload_base: dict[str, Any]) -> dict[str, Any]:
    m = (model or "").strip() or _atelier_model()
    cfg = await resolve_llm_for_block(
        "atelier",
        "checklist_qa",
        default_model=m,
        default_system=_QA_SYSTEM,
        default_max_tokens=11000,
        default_temperature=0.18,
    )
    body = {
        "brief_et_contexte": {
            "pitch": payload_base.get("pitch"),
            "brief": payload_base.get("brief"),
            "segments_recherche": payload_base.get("segments_recherche"),
        },
        "checklist_brouillon": draft_checklist,
    }
    return await llm_json_call(
        model=cfg.model,
        system=cfg.system_prompt,
        messages=[{"role": "user", "content": json.dumps(body, ensure_ascii=False)}],
        max_tokens=cfg.max_tokens,
        temperature=cfg.temperature,
        json_mode=True,
        allow_json_repair=True,
        repair_model=settings.FILTER_MODEL,
    )


def _pitfalls_model() -> str:
    f = (settings.FILTER_MODEL or "").strip()
    return f or _atelier_model()


def _pitfalls_from_llm(raw: dict[str, Any]) -> tuple[str | None, list[ChecklistItem]]:
    title = str(raw.get("pitfalls_title") or "").strip()[:120] or None
    out: list[ChecklistItem] = []
    for it in (raw.get("pitfalls") or [])[:14]:
        if not isinstance(it, dict):
            continue
        lab = str(it.get("label") or "").strip()
        if not lab:
            continue
        guide = str(it.get("guide") or "").strip()
        out.append(ChecklistItem(label=lab[:420], guide=guide[:2600]))
    return title, out


async def _call_pitfalls_only(model: str, context: dict[str, Any]) -> dict[str, Any]:
    return await llm_json_call(
        model=model,
        system=_PITFALLS_ONLY_SYSTEM,
        messages=[{"role": "user", "content": json.dumps(context, ensure_ascii=False)}],
        max_tokens=2800,
        temperature=0.2,
        json_mode=True,
        allow_json_repair=True,
        repair_model=settings.FILTER_MODEL,
    )


async def _call_monolith(model: str, payload: dict[str, Any]) -> dict[str, Any]:
    return await llm_json_call(
        model=model,
        system=_MONOLITH_FALLBACK_SYSTEM,
        messages=[{"role": "user", "content": json.dumps(payload, ensure_ascii=False)}],
        max_tokens=12000,
        temperature=0.22,
        json_mode=True,
        allow_json_repair=True,
        repair_model=settings.FILTER_MODEL,
    )


async def generate_checklist_multi_stage(
    pitch: str,
    answers: str,
    brief: ProjectBrief,
    synthesis: AgentSynthesis,
    segment_labels: list[str],
) -> AtelierChecklist | None:
    """Squelette → détails (parallèle) → chemin rapide (brouillon + pièges légers) ou QA complète."""
    model = _atelier_model()
    payload = _base_user_payload(pitch, answers, brief, synthesis, segment_labels)

    try:
        raw_outline = await _call_outline(model, payload)
        if not isinstance(raw_outline, dict):
            raise ValueError("outline_non_dict")
        parsed = _parse_outline(raw_outline)
        if not parsed:
            raise ValueError("outline_invalide")
        outline, headline_draft, lede_draft = parsed

        plog(
            "atelier_checklist_pipeline",
            stage="outline",
            sections=len(outline),
        )

        chunks: list[list[dict[str, Any]]] = [
            outline[i : i + _DETAIL_CHUNK_SIZE]
            for i in range(0, len(outline), _DETAIL_CHUNK_SIZE)
        ]
        detail_tasks = [_call_detail_chunk(model, payload, ch) for ch in chunks]
        chunk_raws = await asyncio.gather(*detail_tasks, return_exceptions=True)

        detail_dicts: list[dict[str, Any]] = []
        for i, r in enumerate(chunk_raws):
            if isinstance(r, Exception):
                plog(
                    "atelier_checklist_pipeline",
                    stage="detail_chunk_error",
                    chunk_index=i,
                    error=str(r)[:300],
                )
                raise r
            if isinstance(r, dict):
                detail_dicts.append(r)

        merged_sections = merge_atelier_checklist_detail_chunks(outline, detail_dicts)
        draft = {
            "headline": headline_draft,
            "lede": lede_draft,
            "sections": merged_sections,
            "pitfalls_title": None,
            "pitfalls": [],
        }

        items_merged = sum(len(s.get("items") or []) for s in merged_sections)
        plog(
            "atelier_checklist_pipeline",
            stage="detail_merged",
            sections=len(merged_sections),
            items_total=items_merged,
        )

        cl_draft = coerce_checklist_from_llm_dict({"checklist": draft})
        items_coerced = (
            sum(len(s.items) for s in cl_draft.sections) if cl_draft else 0
        )
        if (
            cl_draft
            and len(cl_draft.sections) >= _FAST_PATH_MIN_SECTIONS
            and items_coerced >= _FAST_PATH_MIN_ITEMS
        ):
            cl_out = cl_draft
            if len(cl_out.pitfalls) < _FAST_PATH_MIN_PITFALLS:
                brief = payload.get("brief") or {}
                pit_ctx: dict[str, Any] = {
                    "pitch": payload.get("pitch"),
                    "secteur": brief.get("secteur"),
                    "nom_projet": brief.get("nom"),
                    "synthese_sans_checklist": payload.get("synthese_sans_checklist"),
                    "checklist_resume": {
                        "headline": cl_out.headline,
                        "lede": cl_out.lede,
                        "sections_titles": [s.title for s in cl_out.sections[:28]],
                    },
                }
                try:
                    pit_raw = await _call_pitfalls_only(_pitfalls_model(), pit_ctx)
                    if isinstance(pit_raw, dict):
                        pt, pitems = _pitfalls_from_llm(pit_raw)
                        if pitems:
                            cl_out = cl_out.model_copy(
                                update={
                                    "pitfalls_title": pt
                                    or cl_out.pitfalls_title
                                    or "Pièges à éviter",
                                    "pitfalls": pitems,
                                }
                            )
                except Exception as pit_exc:
                    plog(
                        "atelier_checklist_pipeline",
                        stage="pitfalls_only_error",
                        error=str(pit_exc)[:300],
                    )
            plog(
                "atelier_checklist_pipeline",
                stage="fast_path_ok",
                sections=len(cl_out.sections),
                items_total=items_coerced,
                pitfalls=len(cl_out.pitfalls),
                items_merged_raw=items_merged,
            )
            return cl_out

        qa_raw = await _call_qa(model, draft, payload)
        if not isinstance(qa_raw, dict):
            raise ValueError("qa_non_dict")

        cl = coerce_checklist_from_llm_dict(qa_raw)
        if cl is None:
            raise ValueError("qa_coerce_none")

        plog(
            "atelier_checklist_pipeline",
            stage="qa_ok",
            sections=len(cl.sections),
            items_total=sum(len(s.items) for s in cl.sections),
            pitfalls=len(cl.pitfalls),
        )
        return cl

    except Exception as exc:
        plog(
            "atelier_checklist_pipeline_fallback",
            error=str(exc)[:400],
        )
        try:
            raw = await _call_monolith(model, payload)
            if isinstance(raw, dict):
                return coerce_checklist_from_llm_dict(raw)
        except Exception as exc2:
            plog("atelier_checklist_monolith_error", error=str(exc2)[:400])
        return None
