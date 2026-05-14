"""
Post-filtrage de pertinence des lignes de résultats (couche LLM).

Utilisé après `execute_plan` : compacte chaque fiche, envoie des lots au modèle
qui attribue un score de pertinence 0-10, puis on coupe au seuil **calculé**
(mots-clés / géo / volume, mode, part Google Maps ; voir ``_compute_threshold``).
Les lignes jamais notées par le LLM (id manquant, lot incomplet) reçoivent 0 : \
elles ne passent pas le seuil. Si toutes les lignes sont exclues, repli sur la liste brute.

Taille des lots : 50 lignes par appel LLM (réduit le nombre d'appels vs 40 historique
pour un panel max ~150 lignes ; qualité : même barème 0–10, légèrement plus de fiches
par prompt — surveiller les réponses JSON incomplètes via logs ``relevance_batch_*``).
"""


from __future__ import annotations

import asyncio
import json
from typing import Any, Literal

from config import settings
from models.schemas import CompanyResult, GuardEntity, GuardResult
from services.modes import MODE_LABELS, Mode
from utils.observability_counters import increment_counter
from utils.pipeline_log import plog

_BATCH_SIZE = 50
_MAX_STR = 180
_BASE_THRESHOLD = 5
_NICHE_THRESHOLD = 6
# Prospection « large » (sans niche mots-clés + géo / volume) : garder plus de lignes utiles
_BASE_THRESHOLD_PROSPECTION = 4
# Niche + panel dominé par Google Places : faux positifs fréquents → couper plus haut
_PLACES_NICHE_THRESHOLD = 7
# Sentinelle : en attente de note LLM (ne doit pas passer le filtre telle quelle)
_UNSCORED = -1


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
         recherchée (sans ambiguïté avec la requête).
  7-8  = TRÈS BON — l'activité correspond bien et la localisation est correcte, \
         même sans confirmation parfaite dans le nom.
  5-6  = INCERTAIN — la fiche pourrait encore être la bonne catégorie (nom neutre, \
         libellé générique du bon métier) sans contradiction. Ce n'est PAS \
         « incertain » si le nom ou l'activité affiche clairement une AUTRE spécialité \
         (autre sport, autre cuisine, autre corps de métier, autre filière) : dans ce \
         cas c'est 0-3, pas 5-6.
  3-4  = FAIBLE — même grand secteur MAIS activité réelle visiblement différente. \
         Exemples : une grande surface sport pour une boutique spécialisée, \
         un restaurant d'une autre cuisine pour une cuisine ciblée, \
         un hôtel 5 étoiles pour une recherche 3 étoiles.
  1-2  = HORS SUJET — secteur vaguement lié ou localisation complètement différente.
  0    = AUCUN rapport avec la recherche.

RÈGLES D'ÉVALUATION :

1. SPÉCIFICITÉ D'ABORD. Quand la requête cible une NICHE (sport ou loisir précis, \
   filière technique, type de commerce ou de restauration détaillé…), les acteurs \
   GÉNÉRALISTES du même grand secteur = 3-4 max. Une autre spécialité explicite \
   dans le nom = 0-3 (voir règle 2bis).

2. LOCALISATION. Vérifie ville ET département. Si la requête cible une ville \
   et l'entreprise est hors zone → retire fortement. Si la requête cible une région \
   large (PACA, IDF), le département ou la région affichée peut suffire.

2bis. TYPE D'ENTITÉ vs INTENTION. Si la requête vise un commerce, un cabinet, \
   un atelier, un producteur ou un prestataire précis, et que la fiche est une \
   association, ligue, fédération, club scolaire ou structure collective sans lien \
   direct avec l'offre recherchée → 0-2 (pas « même secteur »).

2ter. SPÉCIALITÉ DIVERGENTE. Toute mention explicite dans le nom ou le libellé \
   d'une activité différente de celle demandée (autre discipline sportive, autre \
   métier du bâtiment, autre filière industrielle…) → 0-2.

2quater. SPORTS / SALLES GÉNÉRALISTES. Si la requête cible une **niche sportive ou loisir** \
   précise (nom ou mots-clés dans l'intent), une salle de sport, club omnisports, \
   association syndicale ou fédération **sans** lien explicite avec cette niche dans \
   le nom ni le libellé → 0-2 (même ville correcte).

3. NOM > CODE APE. Le code APE couvre un secteur entier (ex. activités sportives). \
   Le NOM et le libellé d'activité révèlent la vraie spécialité. \
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

7. SEUIL D'APPLICATION. Le bloc utilisateur JSON contient **seuil_application** (entier). \
   Une fiche sera conservée si et seulement si sa note **s** ≥ seuil_application. \
   Ce seuil est calculé côté serveur (mode d'usage, niche mots-clés/géo/volume, \
   part des résultats Google Maps) : ne « gonfle » pas artificiellement les scores ; \
   le barème 0-10 reste absolu, le seuil encode la politique métier.

Réponds UNIQUEMENT en JSON valide :
{"scores":[{"id":<int>,"s":<int 0-10>}]}
Exactement une entrée par fiche, mêmes "id"."""


def _guard_entities_payload(entities: GuardEntity) -> dict[str, Any]:
    d = entities.model_dump()
    return {k: v for k, v in d.items() if v}


def _places_heavy_for_niche(results: list[CompanyResult] | None, n_results: int) -> bool:
    """True si une part significative des lignes porte une URL Maps (découverte locale)."""
    if not results or n_results < 8:
        return False
    with_maps = sum(1 for r in results if (r.google_maps_url or "").strip())
    if with_maps < 5:
        return False
    ratio = with_maps / max(n_results, 1)
    return with_maps >= 10 or ratio >= 0.28


def _compute_threshold(
    guard_result: GuardResult,
    n_results: int,
    *,
    mode: Mode = "prospection",
    results: list[CompanyResult] | None = None,
) -> int:
    """Seuil dynamique : mots-clés / géo / volume, puis mode et niche + Places."""
    e = guard_result.entities
    has_keywords = bool(e.mots_cles)
    # Ville, département ou région extraits du guard comptent comme ancrage géo
    # (ex. « dans le 13 » souvent modélisé en departement sans localisation).
    has_geo = bool(e.localisation or e.departement or e.region)
    has_sector = bool(e.secteur)

    if has_keywords and has_geo:
        t = _NICHE_THRESHOLD
    elif has_keywords and n_results > 200:
        t = _NICHE_THRESHOLD
    elif has_geo and has_sector and n_results > 300:
        t = _BASE_THRESHOLD + 1
    else:
        t = _BASE_THRESHOLD

    niche_kw = (has_keywords and has_geo) or (has_keywords and n_results > 200)

    # Prospection large B2B : plus tolérant ; structuré géo+secteur+volume sans mots-clés : pas de +1 dur
    if mode == "prospection":
        if t == _BASE_THRESHOLD:
            t = _BASE_THRESHOLD_PROSPECTION
        elif (
            t == _BASE_THRESHOLD + 1
            and has_geo
            and has_sector
            and n_results > 300
            and not has_keywords
        ):
            t = _BASE_THRESHOLD

    if niche_kw and _places_heavy_for_niche(results, n_results):
        t = max(t, _PLACES_NICHE_THRESHOLD)

    return max(0, min(10, t))


async def _score_batch(
    *,
    user_query: str,
    guard_result: GuardResult,
    mode: Mode,
    threshold: int,
    rows_payload: list[dict[str, Any]],
    agent_id: str,
    block_id: str,
) -> dict[int, int]:
    """Un appel LLM : retourne id -> score (0-10)."""
    from services.agent_config import resolve_llm_for_block
    from utils.llm import llm_json_call

    mode_label = MODE_LABELS.get(mode, mode)
    user_content = json.dumps(
        {
            "requete_utilisateur": user_query,
            "intent": guard_result.intent,
            "entites": _guard_entities_payload(guard_result.entities),
            "mode": mode_label,
            "seuil_application": threshold,
            "fiches": rows_payload,
        },
        ensure_ascii=False,
    )
    cfg = await resolve_llm_for_block(
        agent_id,
        block_id,
        default_model=settings.RELEVANCE_FILTER_MODEL,
        default_system=RELEVANCE_SYSTEM_PROMPT,
        default_max_tokens=2048,
        default_temperature=0.0,
    )
    raw = await llm_json_call(
        model=cfg.model,
        system=cfg.system_prompt,
        messages=[{"role": "user", "content": user_content}],
        max_tokens=cfg.max_tokens,
        temperature=cfg.temperature,
        usage_stage="relevance",
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


RelevanceFlag = Literal["ok", "warning", "excluded"]


def relevance_flag_for_score(score_0_10: int, threshold: int) -> RelevanceFlag:
    """Classe une note 0–10 par rapport au seuil (affichage Atelier / chat)."""
    if score_0_10 >= threshold:
        return "ok"
    if score_0_10 == threshold - 1 and threshold >= 1:
        return "warning"
    return "excluded"


def relevance_reason_excluded_fr(score_0_10: int, threshold: int) -> str | None:
    if score_0_10 >= threshold:
        return None
    return (
        f"Pertinence {score_0_10}/10 sous le seuil MONV ({threshold}/10) ; "
        "ligne masquée par défaut dans l’Atelier."
    )


async def compute_relevance_scores(
    results: list[CompanyResult],
    *,
    user_query: str,
    guard_result: GuardResult,
    mode: Mode,
    agent_id: str | None = None,
    block_id: str = "relevance",
) -> tuple[list[int], int, dict[str, Any]]:
    """Calcule une note 0–10 par ligne et le seuil, sans filtrer la liste.

    Retourne (scores par index, seuil, stats partielles). En cas de skip
    (pas de clé API, une seule ligne, liste vide), les scores valent le
    seuil de base pour ne pas bloquer l'affichage.
    """
    stats: dict[str, Any] = {
        "relevance_skipped": False,
        "relevance_before": len(results),
        "relevance_threshold": _BASE_THRESHOLD,
    }
    n = len(results)

    if not settings.OPENROUTER_API_KEY:
        stats["relevance_skipped"] = True
        stats["relevance_skip_reason"] = "no_openrouter_key"
        t = _BASE_THRESHOLD
        stats["relevance_avg_score"] = float(t)
        return [t] * n, t, stats

    if n <= 0:
        stats["relevance_skipped"] = True
        stats["relevance_skip_reason"] = "empty"
        return [], _BASE_THRESHOLD, stats

    if n == 1:
        stats["relevance_skipped"] = True
        stats["relevance_skip_reason"] = "single_row"
        t = _BASE_THRESHOLD
        stats["relevance_avg_score"] = float(t)
        return [t] * n, t, stats

    threshold = _compute_threshold(guard_result, n, mode=mode, results=results)
    stats["relevance_threshold"] = threshold

    if (
        mode == "prospection"
        and 2 <= n <= 6
        and not (guard_result.entities.mots_cles or [])
        and not _places_heavy_for_niche(results, n)
    ):
        stats["relevance_skipped"] = True
        stats["relevance_skip_reason"] = "small_structured_panel"
        pass_score = max(threshold, 6)
        stats["relevance_avg_score"] = float(pass_score)
        return [pass_score] * n, threshold, stats

    scores = [_UNSCORED] * n

    batches: list[tuple[int, int, list[int]]] = []
    for start in range(0, n, _BATCH_SIZE):
        end = min(start + _BATCH_SIZE, n)
        batches.append((start, end, list(range(start, end))))

    aid = (agent_id or str(mode)).strip()

    async def _process_batch(start: int, end: int, batch_indices: list[int]) -> dict[int, int]:
        payload = [row_for_relevance_check(i, results[i]) for i in batch_indices]
        try:
            return await _score_batch(
                user_query=user_query,
                guard_result=guard_result,
                mode=mode,
                threshold=threshold,
                rows_payload=payload,
                agent_id=aid,
                block_id=block_id,
            )
        except Exception as e:
            plog("relevance_batch_error", batch_start=start, batch_end=end, error=repr(e))
            return {}

    sem = asyncio.Semaphore(5)

    async def _bounded(s: int, e: int, bi: list[int]) -> dict[int, int]:
        async with sem:
            return await _process_batch(s, e, bi)

    all_decisions = await asyncio.gather(*[_bounded(s, e, bi) for s, e, bi in batches])

    unscored_after_llm = 0
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

    for i in range(n):
        if scores[i] < 0:
            scores[i] = 0
            unscored_after_llm += 1
    if unscored_after_llm:
        stats["relevance_unscored_default_zero"] = unscored_after_llm

    assigned_scores = [s for i, s in enumerate(scores) if i < n]
    distribution: dict[str, int] = {}
    for s in assigned_scores:
        bucket = f"{s}"
        distribution[bucket] = distribution.get(bucket, 0) + 1

    stats["relevance_score_distribution"] = distribution
    stats["relevance_avg_score"] = round(sum(assigned_scores) / max(len(assigned_scores), 1), 1)
    return scores, threshold, stats


async def filter_results_by_relevance(
    results: list[CompanyResult],
    *,
    user_query: str,
    guard_result: GuardResult,
    mode: Mode,
    agent_id: str | None = None,
    relevance_block_id: str = "relevance",
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

    n = len(results)
    if n <= 0:
        stats["relevance_skipped"] = True
        stats["relevance_skip_reason"] = "empty"
        return results, stats

    scores, threshold, partial = await compute_relevance_scores(
        results,
        user_query=user_query,
        guard_result=guard_result,
        mode=mode,
        agent_id=agent_id,
        block_id=relevance_block_id,
    )
    stats.update(partial)

    if stats.get("relevance_skipped"):
        return results, stats

    scored_pairs = [
        (scores[i], i, r) for i, r in enumerate(results) if scores[i] >= threshold
    ]
    scored_pairs.sort(key=lambda t: (-t[0], t[1]))
    filtered = [r for _, _, r in scored_pairs]
    removed = n - len(filtered)

    if removed == n and n > 0:
        plog("relevance_fallback_all_rejected", n=n)
        increment_counter("relevance_fallback_all_rejected", 1)
        filtered = list(results)
        removed = 0
        stats["relevance_fallback_unfiltered"] = True

    stats["relevance_after"] = len(filtered)
    stats["relevance_removed"] = removed
    stats["relevance_threshold"] = threshold

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
