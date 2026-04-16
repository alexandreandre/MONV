#!/usr/bin/env python3
"""
Benchmark de PERTINENCE du filtre relevance.py.

Exécute le pipeline complet (Guard → Orchestrator → API Engine → Relevance)
sur un panel de requêtes couvrant les 4 modes, puis demande au LLM évaluateur
de noter chaque résultat. Produit un rapport d'analyse détaillé.

Usage :
    cd backend
    python benchmark_relevance.py
"""

import asyncio
import json
import time
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from config import settings
from services.filter import run_filter
from services.guard import run_guard
from services.orchestrator import run_orchestrator
from services.api_engine import execute_plan
from services.relevance import filter_results_by_relevance
from services.sirene import patch_sirene_calls_from_guard_entities
from utils.llm import llm_json_call

# ═══════════════════════════════════════════════════════════════════════
# PANEL — 16 requêtes × 4 modes, couvrant niches, secteurs larges, etc.
# ═══════════════════════════════════════════════════════════════════════

QUERIES = [
    # ── Mode prospection ──────────────────────────────────────────
    {"id": "P-01", "query": "Boutiques de padel à Marseille", "mode": "prospection",
     "target": "commerces/clubs spécifiquement liés au padel"},
    {"id": "P-02", "query": "Restaurants japonais à Bordeaux", "mode": "prospection",
     "target": "restaurants de cuisine japonaise uniquement"},
    {"id": "P-03", "query": "ESN en Île-de-France", "mode": "prospection",
     "target": "entreprises de services numériques / SSII"},
    {"id": "P-04", "query": "Hôtels 3 étoiles à Nice", "mode": "prospection",
     "target": "hôtels de catégorie 3 étoiles, pas 4-5 étoiles ni auberges"},
    {"id": "P-05", "query": "Salles de crossfit à Lyon", "mode": "prospection",
     "target": "salles dédiées au crossfit, pas fitness générique"},
    {"id": "P-06", "query": "PME du BTP à Toulouse", "mode": "prospection",
     "target": "entreprises du bâtiment et travaux publics"},
    {"id": "P-07", "query": "Pharmacies à Strasbourg", "mode": "prospection",
     "target": "pharmacies d'officine"},
    {"id": "P-08", "query": "Boulangeries artisanales à Montpellier", "mode": "prospection",
     "target": "boulangeries, pas pâtisseries industrielles ni grandes surfaces"},

    # ── Mode sous_traitant ────────────────────────────────────────
    {"id": "S-01", "query": "Imprimeur 3D en PACA", "mode": "sous_traitant",
     "target": "prestataires d'impression 3D / fabrication additive"},
    {"id": "S-02", "query": "Sous-traitant usinage mécanique dans le Nord", "mode": "sous_traitant",
     "target": "ateliers d'usinage / mécanique de précision"},
    {"id": "S-03", "query": "Agence web à Nantes", "mode": "sous_traitant",
     "target": "agences de développement web / digital"},
    {"id": "S-04", "query": "Cabinet comptable à Paris", "mode": "sous_traitant",
     "target": "cabinets d'expertise comptable"},

    # ── Mode client ───────────────────────────────────────────────
    {"id": "C-01", "query": "Cliniques vétérinaires en Bretagne", "mode": "benchmark",
     "target": "cabinets et cliniques vétérinaires"},
    {"id": "C-02", "query": "Concessions automobiles à Lyon", "mode": "benchmark",
     "target": "concessionnaires / vendeurs automobiles"},

    # ── Mode rachat ───────────────────────────────────────────────
    {"id": "R-01", "query": "Entreprises de nettoyage industriel en IDF", "mode": "rachat",
     "target": "sociétés de nettoyage / propreté industrielle"},
    {"id": "R-02", "query": "Garages automobiles à Marseille", "mode": "rachat",
     "target": "garages / ateliers de réparation automobile"},
]

# ═══════════════════════════════════════════════════════════════════════
# ÉVALUATEUR LLM — note chaque résultat de 0 à 10
# ═══════════════════════════════════════════════════════════════════════

EVAL_SYSTEM = """Tu es un évaluateur de pertinence. On te donne une requête utilisateur, \
une description de la cible attendue, et une liste de résultats d'entreprises.

Pour CHAQUE résultat, donne un score de pertinence 0-10 :
- 0-2 : hors sujet, rien à voir
- 3-4 : même secteur large mais pas la cible
- 5-6 : lien plausible mais pas idéal
- 7-8 : bon résultat, correspond bien
- 9-10 : parfait, exactement la cible

Réponds UNIQUEMENT en JSON : {"evals":[{"id":<int>,"s":<int>,"r":"<raison courte>"}]}"""


async def eval_results(query: str, target: str, rows: list[dict]) -> list[dict]:
    """Demande au LLM évaluateur de noter chaque résultat."""
    if not rows:
        return []
    content = json.dumps({
        "requete": query, "cible_attendue": target, "resultats": rows
    }, ensure_ascii=False)
    try:
        raw = await llm_json_call(
            model="anthropic/claude-3.5-haiku",
            system=EVAL_SYSTEM,
            messages=[{"role": "user", "content": content}],
            max_tokens=4096,
            temperature=0.0,
        )
        return raw.get("evals", [])
    except Exception as e:
        print(f"    ⚠ Eval error: {e}")
        return []


# ═══════════════════════════════════════════════════════════════════════
# BENCHMARK ENGINE
# ═══════════════════════════════════════════════════════════════════════

async def run_one(q: dict) -> dict:
    result = {
        "id": q["id"], "query": q["query"], "mode": q["mode"], "target": q["target"],
        "raw_count": 0, "filtered_count": 0, "relevance_stats": {},
        "eval_scores": [], "avg_score_raw": 0, "avg_score_filtered": 0,
        "precision_at_10": 0, "time_ms": 0, "error": None,
    }

    t0 = time.monotonic()
    try:
        # Filter
        filt = await run_filter(q["query"])
        if not filt.in_scope:
            result["error"] = "out_of_scope"
            return result

        # Guard
        guard = await run_guard(q["query"])
        if guard.intent in ("hors_scope", "salutation", "meta_question"):
            result["error"] = f"intent={guard.intent}"
            return result
        e = guard.entities
        if guard.clarification_needed and (e.secteur or e.code_naf or e.mots_cles) and (e.localisation or e.departement or e.region):
            guard.clarification_needed = False
        if guard.clarification_needed:
            result["error"] = "clarification_needed"
            return result

        # Orchestrator
        plan = await run_orchestrator(guard, mode=q["mode"])
        if plan.clarification_needed:
            result["error"] = "orch_clarification"
            return result

        # API Engine
        patch_sirene_calls_from_guard_entities(plan, guard.entities)
        search_results = await execute_plan(plan)
        result["raw_count"] = search_results.total
        raw_results = list(search_results.results)

        # Relevance filter
        filtered, rel_stats = await filter_results_by_relevance(
            search_results.results,
            user_query=q["query"],
            guard_result=guard,
            mode=q["mode"],
        )
        result["filtered_count"] = len(filtered)
        result["relevance_stats"] = rel_stats

        # Évaluation : on évalue les 20 premiers filtrés
        eval_rows = []
        for i, r in enumerate(filtered[:20]):
            eval_rows.append({
                "id": i, "nom": r.nom or "",
                "activite": r.libelle_activite or "",
                "ape": r.activite_principale or "",
                "ville": r.ville or "",
            })

        evals = await eval_results(q["query"], q["target"], eval_rows)
        eval_map = {e["id"]: e for e in evals if isinstance(e, dict) and "id" in e and "s" in e}

        scores_filtered = []
        for i in range(min(20, len(filtered))):
            ev = eval_map.get(i, {})
            s = ev.get("s", -1)
            reason = ev.get("r", "")
            scores_filtered.append({
                "nom": filtered[i].nom,
                "activite": filtered[i].libelle_activite,
                "score": s,
                "reason": reason,
            })
        result["eval_scores"] = scores_filtered

        valid_scores = [x["score"] for x in scores_filtered if x["score"] >= 0]
        if valid_scores:
            result["avg_score_filtered"] = round(sum(valid_scores) / len(valid_scores), 1)
            result["precision_at_10"] = round(
                sum(1 for s in valid_scores[:10] if s >= 5) / min(10, len(valid_scores)) * 100, 1
            )

    except Exception as e:
        result["error"] = str(e)[:300]
    finally:
        result["time_ms"] = round((time.monotonic() - t0) * 1000)

    return result


async def run_benchmark():
    print("=" * 72)
    print("  BENCHMARK PERTINENCE — FILTRE RELEVANCE")
    print(f"  {len(QUERIES)} requêtes — {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  Seuil filtre : score >= 4/10")
    print(f"  Modèle filtre : {settings.RELEVANCE_FILTER_MODEL}")
    print("=" * 72)

    all_results = []
    for i, q in enumerate(QUERIES, 1):
        print(f"\n[{i:2d}/{len(QUERIES)}] {q['id']:5s} | {q['query'][:50]:50s} | mode={q['mode']}")
        r = await run_one(q)
        all_results.append(r)

        if r["error"]:
            print(f"    ❌ Error: {r['error']}")
        else:
            print(f"    Brut: {r['raw_count']:4d} → Filtré: {r['filtered_count']:4d} | "
                  f"Score moyen: {r['avg_score_filtered']}/10 | P@10: {r['precision_at_10']}%")

            # Montrer les résultats évalués
            for j, ev in enumerate(r["eval_scores"][:10]):
                icon = "✅" if ev["score"] >= 7 else "🟡" if ev["score"] >= 4 else "❌"
                print(f"      {icon} [{ev['score']:2d}] {ev['nom'][:40]:40s} | {ev['activite'][:35] if ev['activite'] else 'N/A':35s} | {ev['reason'][:30]}")

    # ── Résumé global ──────────────────────────────────────────────
    print("\n" + "=" * 72)
    print("  RÉSUMÉ GLOBAL")
    print("=" * 72)

    valid = [r for r in all_results if not r["error"]]
    if valid:
        avg_raw = sum(r["raw_count"] for r in valid) / len(valid)
        avg_filtered = sum(r["filtered_count"] for r in valid) / len(valid)
        avg_score = sum(r["avg_score_filtered"] for r in valid) / len(valid)
        avg_p10 = sum(r["precision_at_10"] for r in valid) / len(valid)
        avg_time = sum(r["time_ms"] for r in valid) / len(valid)

        print(f"  Requêtes réussies : {len(valid)}/{len(all_results)}")
        print(f"  Résultats bruts moyen : {avg_raw:.0f}")
        print(f"  Résultats filtrés moyen : {avg_filtered:.0f}")
        print(f"  Taux de filtrage moyen : {(1 - avg_filtered/max(avg_raw,1))*100:.0f}%")
        print(f"  Score pertinence moyen : {avg_score:.1f}/10")
        print(f"  Precision@10 moyenne : {avg_p10:.0f}%")
        print(f"  Temps moyen : {avg_time:.0f}ms")

        # Par mode
        for mode in ("prospection", "sous_traitant", "benchmark", "rachat"):
            mode_rs = [r for r in valid if r["mode"] == mode]
            if mode_rs:
                ms = sum(r["avg_score_filtered"] for r in mode_rs) / len(mode_rs)
                mp = sum(r["precision_at_10"] for r in mode_rs) / len(mode_rs)
                mf = sum(r["filtered_count"] for r in mode_rs) / len(mode_rs)
                print(f"    {mode:15s} : score={ms:.1f}/10, P@10={mp:.0f}%, filtré={mf:.0f} moy")

    # Mauvais résultats (score < 4 dans les 10 premiers)
    print(f"\n  ── FAUX POSITIFS (score < 4 dans top 10 filtré) ──")
    fp_count = 0
    for r in valid:
        for ev in r["eval_scores"][:10]:
            if 0 <= ev["score"] < 4:
                fp_count += 1
                print(f"    {r['id']} | {ev['nom'][:35]:35s} | score={ev['score']} | {ev['reason'][:40]}")
    if fp_count == 0:
        print("    Aucun faux positif !")
    else:
        print(f"    Total : {fp_count} faux positifs")

    # Sauvegarder
    report = {
        "timestamp": datetime.now().isoformat(),
        "model": settings.RELEVANCE_FILTER_MODEL,
        "threshold": 4,
        "results": all_results,
    }
    report_path = Path(__file__).parent / "benchmark_relevance_report.json"
    with open(report_path, "w") as f:
        json.dump(report, f, ensure_ascii=False, indent=2, default=str)
    print(f"\n  Rapport : {report_path}")

    return report


if __name__ == "__main__":
    asyncio.run(run_benchmark())
