"""
Post-filtrage de pertinence des lignes de résultats (couche LLM).

Utilisé après `execute_plan` : compacte chaque fiche, envoie des lots au modèle
qui attribue un score de pertinence 0-10, puis on coupe au seuil.
En cas d'erreur ou de réponse incomplète, on conserve les lignes (défensif).
"""

from __future__ import annotations

import asyncio
import json
from typing import Any

from config import settings
from models.schemas import CompanyResult, GuardEntity, GuardResult
from services.modes import MODE_LABELS, Mode
from utils.llm import llm_json_call
from utils.pipeline_log import plog

_BATCH_SIZE = 40
_MAX_STR = 180
_BASE_THRESHOLD = 5
_NICHE_THRESHOLD = 6


def _clip(s: str | None, n: int = _MAX_STR) -> str | None:
    if s is None:
        return None
    t = s.strip()
    if len(t) <= n:
        return t
    return t[: n - 1] + "…"


def row_for_relevance_check(global_idx: int, r: CompanyResult) -> dict[str, Any]:
    """Représentation compacte d'une ligne pour le LLM."""
    d: dict[str, Any] = {"id": global_idx, "nom": _clip(r.nom) or ""}
    if r.libelle_activite:
        d["activite"] = _clip(r.libelle_activite)
    if r.activite_principale:
        d["ape"] = r.activite_principale
    if r.ville:
        d["ville"] = _clip(r.ville, 60)
    if r.departement:
        d["dept"] = r.departement
    if r.site_web:
        d["web"] = _clip(r.site_web, 100)
    if r.forme_juridique:
        d["forme"] = _clip(r.forme_juridique, 40)
    if r.categorie_entreprise:
        d["cat"] = r.categorie_entreprise
    return d


# ── Prompt de scoring ────────────────────────────────────────────────────

RELEVANCE_SYSTEM_PROMPT = """\
Tu es un expert en filtrage de pertinence pour un moteur de prospection B2B français.

CONTEXTE : un utilisateur recherche des entreprises correspondant à un besoin précis. \
Les API ont renvoyé des résultats bruts, souvent trop larges (même code NAF, même zone). \
Ton rôle : évaluer si chaque entreprise correspond RÉELLEMENT à ce que l'utilisateur cherche.

BARÈME STRICT (0-10) :

  9-10 = PARFAIT — le nom, l'activité ou le site web confirment clairement la spécialité \
         recherchée. Ex : "PADEL SUD" pour "boutique de padel".
  7-8  = TRÈS BON — l'activité correspond bien et la localisation est correcte, \
         même sans confirmation parfaite dans le nom.
  5-6  = INCERTAIN — même secteur, localisation OK, mais impossible de confirmer \
         la spécialité exacte. Acceptable en l'absence de meilleur résultat.
  3-4  = FAIBLE — même grand secteur MAIS activité réelle visiblement différente. \
         Exemples : un Decathlon ou Intersport pour "boutique de padel", \
         un restaurant chinois pour "restaurant japonais", \
         un hôtel 5 étoiles pour "hôtel 3 étoiles".
  1-2  = HORS SUJET — secteur vaguement lié ou localisation complètement différente.
  0    = AUCUN rapport avec la recherche.

RÈGLES D'ÉVALUATION :

1. SPÉCIFICITÉ D'ABORD. Quand la requête cible une NICHE (padel, crossfit, \
   impression 3D, sushi, boulangerie artisanale…), les enseignes GÉNÉRALISTES \
   du même grand secteur = 3-4 max. Un magasin multi-sport n'est PAS une boutique \
   de padel. Un restaurant thaï n'est PAS un restaurant japonais.

2. LOCALISATION. Vérifie ville ET département. Si la requête cible "Marseille" \
   et l'entreprise est à Paris → retire 4-5 points. Si la requête cible une région \
   large (PACA, IDF), le département suffit.

3. NOM > CODE APE. Le code APE couvre un secteur entier (93.12Z = toutes les activités \
   sportives). Le NOM et le libellé d'activité révèlent la vraie spécialité. \
   Fie-toi au nom et à l'activité, pas au code APE seul.

4. QUALIFICATIFS. Si la requête inclut un qualificatif (3 étoiles, artisanal, \
   industriel…), vérifie que l'entreprise le satisfait. "Nettoyage" ≠ "nettoyage \
   industriel". Sans preuve du qualificatif → 5 max.

5. IGNORE le motif business (prospection, rachat…) — évalue uniquement si l'entreprise \
   correspond à la CIBLE décrite.

6. ABSENCE DE PREUVE. Si le seul indice de correspondance est le code APE \
   (nom opaque, pas de libellé d'activité, pas de site web), le score ne doit \
   pas dépasser 5. Le doute ne profite pas : il vaut mieux écarter un résultat \
   douteux que polluer la liste avec un faux positif.

Réponds UNIQUEMENT en JSON valide :
{"scores":[{"id":<int>,"s":<int 0-10>}]}
Exactement une entrée par fiche, mêmes "id"."""


def _guard_entities_payload(entities: GuardEntity) -> dict[str, Any]:
    d = entities.model_dump()
    return {k: v for k, v in d.items() if v}


def _compute_threshold(
    guard_result: GuardResult,
    n_results: int,
) -> int:
    """Seuil dynamique : monte pour les requêtes niches / spécifiques."""
    e = guard_result.entities
    has_keywords = bool(e.mots_cles)
    has_specific_location = bool(e.localisation)
    has_sector = bool(e.secteur)

    if has_keywords and has_specific_location:
        return _NICHE_THRESHOLD
    if has_keywords and n_results > 200:
        return _NICHE_THRESHOLD
    if has_specific_location and has_sector and n_results > 300:
        return _BASE_THRESHOLD + 1
    return _BASE_THRESHOLD


async def _score_batch(
    *,
    user_query: str,
    guard_result: GuardResult,
    mode: Mode,
    rows_payload: list[dict[str, Any]],
) -> dict[int, int]:
    """Un appel LLM : retourne id -> score (0-10)."""
    mode_label = MODE_LABELS.get(mode, mode)
    user_content = json.dumps(
        {
            "requete_utilisateur": user_query,
            "intent": guard_result.intent,
            "entites": _guard_entities_payload(guard_result.entities),
            "mode": mode_label,
            "fiches": rows_payload,
        },
        ensure_ascii=False,
    )
    raw = await llm_json_call(
        model=settings.RELEVANCE_FILTER_MODEL,
        system=RELEVANCE_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_content}],
        max_tokens=2048,
        temperature=0.0,
    )
    out: dict[int, int] = {}
    for item in raw.get("scores") or []:
        if not isinstance(item, dict):
            continue
        try:
            i = int(item["id"])
            score = int(item["s"])
        except (KeyError, TypeError, ValueError):
            continue
        out[i] = max(0, min(10, score))
    return out


async def filter_results_by_relevance(
    results: list[CompanyResult],
    *,
    user_query: str,
    guard_result: GuardResult,
    mode: Mode,
) -> tuple[list[CompanyResult], dict[str, Any]]:
    """
    Retourne (résultats filtrés, stats pour logs / métadonnées).
    """
    stats: dict[str, Any] = {
        "relevance_skipped": False,
        "relevance_before": len(results),
        "relevance_after": len(results),
        "relevance_removed": 0,
    }

    if not settings.OPENROUTER_API_KEY:
        stats["relevance_skipped"] = True
        stats["relevance_skip_reason"] = "no_openrouter_key"
        return results, stats

    n = len(results)
    if n <= 0:
        stats["relevance_skipped"] = True
        stats["relevance_skip_reason"] = "empty"
        return results, stats

    if n == 1:
        stats["relevance_skipped"] = True
        stats["relevance_skip_reason"] = "single_row"
        return results, stats

    threshold = _compute_threshold(guard_result, n)

    scores = [threshold] * n

    batches: list[tuple[int, int, list[int]]] = []
    for start in range(0, n, _BATCH_SIZE):
        end = min(start + _BATCH_SIZE, n)
        batches.append((start, end, list(range(start, end))))

    async def _process_batch(start: int, end: int, batch_indices: list[int]) -> dict[int, int]:
        payload = [row_for_relevance_check(i, results[i]) for i in batch_indices]
        try:
            return await _score_batch(
                user_query=user_query,
                guard_result=guard_result,
                mode=mode,
                rows_payload=payload,
            )
        except Exception as e:
            plog("relevance_batch_error", batch_start=start, batch_end=end, error=repr(e))
            return {}

    sem = asyncio.Semaphore(5)

    async def _bounded(s: int, e: int, bi: list[int]) -> dict[int, int]:
        async with sem:
            return await _process_batch(s, e, bi)

    all_decisions = await asyncio.gather(*[_bounded(s, e, bi) for s, e, bi in batches])

    for (start, end, batch_indices), batch_scores in zip(batches, all_decisions):
        missing = set(batch_indices) - set(batch_scores.keys())
        if missing:
            plog(
                "relevance_batch_incomplete",
                batch_start=start,
                missing_ids=sorted(missing)[:12],
                nb_missing=len(missing),
            )
        for i in batch_indices:
            if i in batch_scores:
                scores[i] = batch_scores[i]

    scored_pairs = [
        (scores[i], i, r) for i, r in enumerate(results) if scores[i] >= threshold
    ]
    scored_pairs.sort(key=lambda t: (-t[0], t[1]))
    filtered = [r for _, _, r in scored_pairs]
    removed = n - len(filtered)

    if removed == n and n > 0:
        plog("relevance_fallback_all_rejected", n=n)
        filtered = list(results)
        removed = 0
        stats["relevance_fallback_unfiltered"] = True

    assigned_scores = [s for i, s in enumerate(scores) if i < n]
    distribution = {}
    for s in assigned_scores:
        bucket = f"{s}"
        distribution[bucket] = distribution.get(bucket, 0) + 1

    stats["relevance_after"] = len(filtered)
    stats["relevance_removed"] = removed
    stats["relevance_threshold"] = threshold
    stats["relevance_score_distribution"] = distribution
    stats["relevance_avg_score"] = round(sum(assigned_scores) / max(len(assigned_scores), 1), 1)

    plog(
        "relevance_filter_done",
        before=n,
        after=len(filtered),
        removed=removed,
        mode=mode,
        threshold=threshold,
        avg_score=stats["relevance_avg_score"],
    )
    return filtered, stats
