"""
Post-filtrage de pertinence des lignes de résultats (couche LLM).

Utilisé après `execute_plan` : compacte chaque fiche, envoie des lots au modèle,
fusionne les décisions. En cas d'erreur ou de réponse incomplète, on conserve
les lignes (comportement défensif), sauf repli global si tout serait supprimé.
"""

from __future__ import annotations

import json
from typing import Any

from config import settings
from models.schemas import CompanyResult, GuardEntity, GuardResult
from services.modes import MODE_LABELS, Mode
from utils.llm import llm_json_call
from utils.pipeline_log import plog

# Lots : assez petit pour rester fiable en JSON, assez grand pour limiter les appels.
_BATCH_SIZE = 32
_MAX_STR = 220


def _clip(s: str | None, n: int = _MAX_STR) -> str | None:
    if s is None:
        return None
    t = s.strip()
    if len(t) <= n:
        return t
    return t[: n - 1] + "…"


def row_for_relevance_check(global_idx: int, r: CompanyResult) -> dict[str, Any]:
    """Représentation compacte et unique d'une ligne pour le LLM (point d'extension unique)."""
    return {
        "id": global_idx,
        "nom": _clip(r.nom) or "",
        "libelle_activite": _clip(r.libelle_activite),
        "activite_principale": r.activite_principale,
        "ville": _clip(r.ville, 80),
        "code_postal": r.code_postal,
        "departement": r.departement,
        "region": _clip(r.region, 40),
        "effectif_label": _clip(r.effectif_label, 60),
        "categorie_entreprise": _clip(r.categorie_entreprise, 40),
        "site_web": _clip(r.site_web, 120),
        "telephone": _clip(r.telephone, 40),
    }


RELEVANCE_SYSTEM_PROMPT = """Tu es un filtre de pertinence pour une prospection B2B en France.

On te donne :
- la requête utilisateur (langage naturel) ;
- l'intent et les critères extraits (JSON) ;
- le mode d'usage (prospection, client, etc.) ;
- une liste de fiches entreprise numérotées (champ "id").

Pour CHAQUE fiche, décide si elle correspond VRAIMENT à l'intention de recherche,
en te basant sur le nom, l'activité libellée, le code APE si présent, la localisation.

Règles :
- Écarte les fiches clairement hors-sujet (ex. yoga / fitness générique quand on
  demande du padel ; hôtel 4–5 étoiles / palace quand on demande explicitement
  hôtel 2 ou 3 étoiles, et inversement).
- Si l'utilisateur impose une niche ou un sous-segment précis, une activité
  voisine générique dans le même grand secteur peut être NON pertinente.
- En cas de doute raisonnable, mets keep=true (mieux une ligne discutable que
  rater une bonne cible).
- Ignore le « pourquoi » business (rachat, prospection…) : seule la CIBLE compte.

Réponds UNIQUEMENT avec un JSON valide de la forme :
{"decisions":[{"id":<entier>,"keep":true|false}]}

La liste "decisions" doit contenir EXACTEMENT une entrée par fiche fournie,
avec les mêmes "id" que dans l'entrée."""


def _guard_entities_payload(entities: GuardEntity) -> dict[str, Any]:
    return entities.model_dump()


async def _score_batch(
    *,
    user_query: str,
    guard_result: GuardResult,
    mode: Mode,
    rows_payload: list[dict[str, Any]],
) -> dict[int, bool]:
    """Un appel LLM : id -> keep."""
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
        max_tokens=1200,
        temperature=0.0,
    )
    out: dict[int, bool] = {}
    for item in raw.get("decisions") or []:
        if not isinstance(item, dict):
            continue
        try:
            i = int(item["id"])
        except (KeyError, TypeError, ValueError):
            continue
        keep = item.get("keep", True)
        out[i] = bool(keep)
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

    Sans clé OpenRouter ou liste vide / très courte : pas d'appel, retour identique.
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

    # Une seule ligne : peu utile et coût évitable
    if n == 1:
        stats["relevance_skipped"] = True
        stats["relevance_skip_reason"] = "single_row"
        return results, stats

    keep_flags = [True] * n

    for start in range(0, n, _BATCH_SIZE):
        end = min(start + _BATCH_SIZE, n)
        batch_indices = list(range(start, end))
        payload = [row_for_relevance_check(i, results[i]) for i in batch_indices]
        expected_ids: set[int] = set(batch_indices)
        try:
            decisions = await _score_batch(
                user_query=user_query,
                guard_result=guard_result,
                mode=mode,
                rows_payload=payload,
            )
        except Exception as e:
            plog(
                "relevance_batch_error",
                batch_start=start,
                batch_end=end,
                error=repr(e),
            )
            continue

        missing = expected_ids - set(decisions.keys())
        if missing:
            plog(
                "relevance_batch_incomplete",
                batch_start=start,
                missing_ids=sorted(missing)[:12],
                nb_missing=len(missing),
            )
        for i in batch_indices:
            # Défaut : conserver si l'id manque ou erreur batch
            keep_flags[i] = decisions.get(i, True)

    filtered = [r for i, r in enumerate(results) if keep_flags[i]]
    removed = n - len(filtered)

    # Repli : éviter une liste vide si le modèle a tout rejeté
    if removed == n and n > 0:
        plog("relevance_fallback_all_rejected", n=n)
        filtered = list(results)
        removed = 0
        stats["relevance_fallback_unfiltered"] = True

    stats["relevance_after"] = len(filtered)
    stats["relevance_removed"] = removed
    plog(
        "relevance_filter_done",
        before=n,
        after=len(filtered),
        removed=removed,
        mode=mode,
    )
    return filtered, stats
