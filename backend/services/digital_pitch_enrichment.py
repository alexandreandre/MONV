"""
Enrichissement des lignes de résultats lorsque l'utilisateur exprime une intention
de prospection « offre digitale / site web » à destination des établissements listés.

Exécuté **après** la pertinence (relevance) : la liste est déjà filtrée ; ce module
**n'en retire aucune ligne**, il ajoute des champs sur les premières lignes uniquement
(voir ``DIGITAL_PITCH_ENRICH_MAX_ROWS``, aligné sur le cap d'aperçu chat).

Déclenché par des formulations variées (refonte site / site vitrine, création web,
proposition commerciale web…), via ``user_query_suggests_digital_service_pitch``.

Plafond LLM ``max_tokens`` par défaut : 1536 (JSON court par lot ; limite le coût
vs 4096 historique — si troncature, relever légèrement ou réduire la verbosité du prompt).
"""

from __future__ import annotations

import asyncio
import json
import re
from typing import Any

from config import settings
from models.schemas import CompanyResult, GuardResult
from services.agent_config import resolve_llm_for_block
from services.modes import Mode
from utils.llm import llm_json_call
from utils.pipeline_log import plog

# Colonnes d'aperçu / export quand l'enrichissement a été appliqué (ordre produit).
DIGITAL_PITCH_RESULT_COLUMNS: list[str] = [
    "nom",
    "type_etablissement_prospect",
    "ville",
    "site_web",
    "synthese_site_web",
    "opportunite_prestation_web",
    "signaux",
]

# Lignes max enrichies par LLM (lots) — même ordre de grandeur que l'aperçu JSON chat.
DIGITAL_PITCH_ENRICH_MAX_ROWS = 20
_BATCH = 12


def prioritize_google_maps_discoveries(results: list[CompanyResult]) -> None:
    """Met en tête les fiches issues de Google Maps (URL Maps), sans perdre le reste."""
    with_maps = [r for r in results if (r.google_maps_url or "").strip()]
    rest = [r for r in results if not (r.google_maps_url or "").strip()]
    if not with_maps or len(with_maps) == len(results):
        return
    results[:] = with_maps + rest


_DIGITAL_SERVICE_PITCH_RE = re.compile(
    r"(?:"
    # Proposition / offre → cible web ou digitale
    r"propos(?:er|ition).{0,140}(?:site|web|internet|refonte|réfonte|cr[ée]ation|digit|vitrine)"
    # Site / refonte … puis « propos » (ordre inverse courant)
    r"|(?:site\s*web|site\s*vitrine|vitrine\s*web|vitrine\s*en\s*ligne|refonte|réfonte|"
    r"cr[ée]ation|cr[ée]er).{0,120}propos"
    # Refonte / modernisation … → site, vitrine, présence web (ex. « refonte site vitrine »)
    r"|(?:refonte|réfonte|modernis(?:er|ation)|refaire|relancer|"
    r"r[ée]nov(?:er|ation)|nouveau|nouvelle).{0,65}"
    r"(?:site|web|internet|pr[ée]sence|vitrine|page\s*web|e-?commerce|boutique\s*en\s*ligne)"
    # Développement / mise en ligne
    r"|(?:d[ée]veloppement|d[ée]velopper|mise\s*en\s*ligne).{0,65}(?:site|web|application|vitrine)"
    # Prestation / besoin orienté site (évite « vitrine » seule hors contexte web)
    r"|(?:pr[ée]station|offre|besoin|accompagnement).{0,45}"
    r"(?:site\s*web|site\s*vitrine|refonte|cr[ée]ation|web|digit|internet)"
    r")",
    re.IGNORECASE | re.DOTALL,
)


def user_query_suggests_digital_service_pitch(user_message: str) -> bool:
    q = (user_message or "").strip()
    if len(q) < 12:
        return False
    return bool(_DIGITAL_SERVICE_PITCH_RE.search(q))


SYSTEM = """\
Tu aides un commercial B2B français qui prospecte des **entreprises locales** pour
lui proposer une **prestation web** (site, refonte, e-commerce, réservation en ligne).

Tu reçois pour chaque fiche : nom, ville, URL éventuelle, libellé d'activité court.
Tu n'as **pas** visité les sites : tu déduis une **hypothèse raisonnable** à partir
de ces seuls indices (nom de domaine, mots-clés « store », « club », « franchise »,
« urban », « réseau », etc.).

Pour chaque fiche, renvoie :
- **type** : exactement l'un de : « Club », « Boutique », « Franchise / siège national », « Autre »
- **analyse** : 1 à 2 phrases en français, ton professionnel, sans emoji
- **opportunite** : exactement un niveau parmi
  « Très faible », « Faible », « Moyenne », « Forte », « Très forte »
  suivi de « - » et d'une brève justification (ex. « Très faible - enseigne pilotée au niveau national »).

Règles générales :
- Franchise ou grand réseau national (indices dans le nom) → « Franchise / siège national »
  et opportunité **Très faible** ou **Faible** selon le cas.
- Boutique / magasin spécialisé → type « Boutique » si cohérent, sinon « Autre ».
- Association sportive locale / club → « Club » si cohérent.
- Absence d'URL ou URL Facebook / Instagram seulement → opportunité souvent **Forte** ou **Très forte**
  pour un site dédié (à nuancer si c'est une franchise).
- URL en http:// ou nom suggérant site vieillissant → opportunité souvent **Forte** ou **Très forte**.

Réponds UNIQUEMENT en JSON :
{"lignes":[{"id":<int>,"type":"...","analyse":"...","opportunite":"..."}]}
Une entrée par id fourni, mêmes id."""


def _row_payload(global_idx: int, r: CompanyResult) -> dict[str, Any]:
    d: dict[str, Any] = {"id": global_idx, "nom": (r.nom or "")[:200]}
    if r.ville:
        d["ville"] = str(r.ville)[:80]
    if r.site_web:
        d["url"] = str(r.site_web)[:200]
    if r.libelle_activite:
        d["activite"] = str(r.libelle_activite)[:160]
    return d


async def _call_batch(
    *,
    user_query: str,
    guard: GuardResult,
    rows: list[dict[str, Any]],
    agent_id: str = "prospection",
) -> dict[int, dict[str, str]]:
    payload = {
        "requete_utilisateur": user_query[:800],
        "indices": [h for h in (guard.context_hints or []) if isinstance(h, str)][:5],
        "fiches": rows,
    }
    model = (settings.DIGITAL_PITCH_ENRICH_MODEL or "").strip() or settings.RELEVANCE_FILTER_MODEL
    cfg = await resolve_llm_for_block(
        agent_id,
        "digital_pitch",
        default_model=model,
        default_system=SYSTEM,
        default_max_tokens=1536,
        default_temperature=0.2,
    )
    raw = await llm_json_call(
        model=cfg.model,
        system=cfg.system_prompt,
        messages=[{"role": "user", "content": json.dumps(payload, ensure_ascii=False)}],
        max_tokens=cfg.max_tokens,
        temperature=cfg.temperature,
        usage_stage="digital_pitch",
    )
    out: dict[int, dict[str, str]] = {}
    for item in raw.get("lignes") or []:
        if not isinstance(item, dict):
            continue
        try:
            i = int(item["id"])
        except (KeyError, TypeError, ValueError):
            continue
        typ = str(item.get("type") or "").strip()
        ana = str(item.get("analyse") or "").strip()
        opp = str(item.get("opportunite") or "").strip()
        if typ or ana or opp:
            out[i] = {"type": typ, "analyse": ana, "opportunite": opp}
    return out


async def enrich_results_for_digital_service_pitch(
    results: list[CompanyResult],
    *,
    user_query: str,
    guard_result: GuardResult,
    mode: Mode,
    agent_id: str = "prospection",
) -> bool:
    """
    Remplit type / synthèse / opportunité sur les premières lignes.
    Retourne True si au moins une ligne a été enrichie.
    """
    if mode != "prospection":
        return False
    if not settings.OPENROUTER_API_KEY:
        return False
    if not user_query_suggests_digital_service_pitch(user_query):
        return False
    n = min(len(results), DIGITAL_PITCH_ENRICH_MAX_ROWS)
    if n <= 0:
        return False

    batches: list[list[int]] = []
    for start in range(0, n, _BATCH):
        batches.append(list(range(start, min(start + _BATCH, n))))

    async def _one_batch(indices: list[int]) -> dict[int, dict[str, str]]:
        payload = [_row_payload(i, results[i]) for i in indices]
        try:
            return await _call_batch(user_query=user_query, guard=guard_result, rows=payload, agent_id=agent_id)
        except Exception as e:
            plog("digital_pitch_batch_error", error=repr(e))
            return {}

    merged: dict[int, dict[str, str]] = {}
    for part in await asyncio.gather(*[_one_batch(bi) for bi in batches]):
        merged.update(part)

    touched = 0
    for i in range(n):
        row = merged.get(i)
        if not row:
            continue
        r = results[i]
        if row.get("type"):
            r.type_etablissement_prospect = row["type"][:80]
        if row.get("analyse"):
            r.synthese_site_web = row["analyse"][:600]
        if row.get("opportunite"):
            r.opportunite_prestation_web = row["opportunite"][:400]
        touched += 1

    if touched:
        plog("digital_pitch_enrich_done", rows=n, touched=touched)
    return touched > 0
