#!/usr/bin/env python3
"""
Benchmark complet du pipeline MONV.
Teste chaque couche (Filter, Guard, Orchestrator, API Engine) sur un panel large de requêtes.
Produit un rapport JSON + résumé console.

Usage :
    cd backend
    source venv/bin/activate
    python benchmark_pipeline.py
"""

import asyncio
import json
import time
import sys
import traceback
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from services.filter import run_filter
from services.guard import run_guard
from services.orchestrator import run_orchestrator
from services.api_engine import execute_plan
from services.sirene import patch_sirene_calls_from_guard_entities

# ═══════════════════════════════════════════════════════════════════════
# PANEL DE REQUÊTES — 45 requêtes couvrant tous les cas d'usage
# ═══════════════════════════════════════════════════════════════════════

QUERIES = [
    # ── CAT 1 : Prospection B2B classique (secteur + zone) ─────────
    {"id": "B2B-01", "query": "Trouve-moi des PME du BTP à Lyon", "category": "b2b_standard",
     "expect_scope": True, "expect_results": True, "expect_clarification": False},
    {"id": "B2B-02", "query": "Je cherche des ESN en Île-de-France", "category": "b2b_standard",
     "expect_scope": True, "expect_results": True, "expect_clarification": False},
    {"id": "B2B-03", "query": "Entreprises de transport à Marseille", "category": "b2b_standard",
     "expect_scope": True, "expect_results": True, "expect_clarification": False},
    {"id": "B2B-04", "query": "Cabinets comptables à Paris", "category": "b2b_standard",
     "expect_scope": True, "expect_results": True, "expect_clarification": False},
    {"id": "B2B-05", "query": "Agences de communication à Bordeaux", "category": "b2b_standard",
     "expect_scope": True, "expect_results": True, "expect_clarification": False},
    {"id": "B2B-06", "query": "Entreprises informatiques en Auvergne-Rhône-Alpes", "category": "b2b_standard",
     "expect_scope": True, "expect_results": True, "expect_clarification": False},
    {"id": "B2B-07", "query": "Sociétés d'ingénierie à Toulouse", "category": "b2b_standard",
     "expect_scope": True, "expect_results": True, "expect_clarification": False},
    {"id": "B2B-08", "query": "Industries alimentaires en Bretagne", "category": "b2b_standard",
     "expect_scope": True, "expect_results": True, "expect_clarification": False},

    # ── CAT 2 : Recherche de prestataires / fournisseurs ───────────
    {"id": "PREST-01", "query": "Je cherche un prestataire informatique à Paris", "category": "prestataire",
     "expect_scope": True, "expect_results": True, "expect_clarification": False},
    {"id": "PREST-02", "query": "Trouve-moi un cabinet d'avocats spécialisé en droit des affaires à Lyon", "category": "prestataire",
     "expect_scope": True, "expect_results": True, "expect_clarification": False},
    {"id": "PREST-03", "query": "Je cherche un expert-comptable pour ma startup à Nantes", "category": "prestataire",
     "expect_scope": True, "expect_results": True, "expect_clarification": False},
    {"id": "PREST-04", "query": "Fournisseurs d'emballage en Île-de-France", "category": "prestataire",
     "expect_scope": True, "expect_results": True, "expect_clarification": False},
    {"id": "PREST-05", "query": "Sous-traitants en électronique dans le Sud-Est", "category": "prestataire",
     "expect_scope": True, "expect_results": True, "expect_clarification": False},

    # ── CAT 3 : Niches / Google Places ─────────────────────────────
    {"id": "NICHE-01", "query": "Boutiques de padel en PACA", "category": "niche",
     "expect_scope": True, "expect_results": True, "expect_clarification": False},
    {"id": "NICHE-02", "query": "Restaurants japonais à Bordeaux", "category": "niche",
     "expect_scope": True, "expect_results": True, "expect_clarification": False},
    {"id": "NICHE-03", "query": "Salles de crossfit à Toulouse", "category": "niche",
     "expect_scope": True, "expect_results": True, "expect_clarification": False},
    {"id": "NICHE-04", "query": "Espaces de coworking à Nantes", "category": "niche",
     "expect_scope": True, "expect_results": True, "expect_clarification": False},
    {"id": "NICHE-05", "query": "Salons de coiffure à Strasbourg", "category": "niche",
     "expect_scope": True, "expect_results": True, "expect_clarification": False},
    {"id": "NICHE-06", "query": "Escape games à Paris", "category": "niche",
     "expect_scope": True, "expect_results": True, "expect_clarification": False},
    {"id": "NICHE-07", "query": "Boulangeries artisanales à Montpellier", "category": "niche",
     "expect_scope": True, "expect_results": True, "expect_clarification": False},

    # ── CAT 4 : Dirigeants ─────────────────────────────────────────
    {"id": "DIR-01", "query": "Donne-moi les dirigeants de SAS dans le 75", "category": "dirigeants",
     "expect_scope": True, "expect_results": True, "expect_clarification": False},
    {"id": "DIR-02", "query": "Je cherche les PDG d'entreprises tech à Lyon", "category": "dirigeants",
     "expect_scope": True, "expect_results": True, "expect_clarification": False},
    {"id": "DIR-03", "query": "Gérants de SARL dans la restauration à Marseille", "category": "dirigeants",
     "expect_scope": True, "expect_results": True, "expect_clarification": False},

    # ── CAT 5 : Taille / filtres avancés ───────────────────────────
    {"id": "TAILLE-01", "query": "Startups tech créées après 2020 à Paris", "category": "taille",
     "expect_scope": True, "expect_results": True, "expect_clarification": False},
    {"id": "TAILLE-02", "query": "PME de plus de 50 salariés dans l'industrie en IDF", "category": "taille",
     "expect_scope": True, "expect_results": True, "expect_clarification": False},
    {"id": "TAILLE-03", "query": "ETI dans la finance à Paris", "category": "taille",
     "expect_scope": True, "expect_results": True, "expect_clarification": False},
    {"id": "TAILLE-04", "query": "Grandes entreprises de plus de 500 salariés à Lyon", "category": "taille",
     "expect_scope": True, "expect_results": True, "expect_clarification": False},
    {"id": "TAILLE-05", "query": "Entreprises avec un CA supérieur à 10 millions dans le commerce", "category": "taille",
     "expect_scope": True, "expect_results": True, "expect_clarification": False},

    # ── CAT 6 : Requêtes vagues (devraient demander clarification) ─
    {"id": "VAGUE-01", "query": "Je cherche des entreprises", "category": "vague",
     "expect_scope": True, "expect_results": False, "expect_clarification": True},
    {"id": "VAGUE-02", "query": "Trouve-moi des clients", "category": "vague",
     "expect_scope": True, "expect_results": False, "expect_clarification": True},
    {"id": "VAGUE-03", "query": "Je veux prospecter", "category": "vague",
     "expect_scope": True, "expect_results": False, "expect_clarification": True},

    # ── CAT 7 : Hors scope (devrait être filtré) ──────────────────
    {"id": "OOS-01", "query": "Écris-moi un poème sur la mer", "category": "hors_scope",
     "expect_scope": False, "expect_results": False, "expect_clarification": False},
    {"id": "OOS-02", "query": "Quelle est la capitale du Japon ?", "category": "hors_scope",
     "expect_scope": False, "expect_results": False, "expect_clarification": False},
    {"id": "OOS-03", "query": "Aide-moi à coder en Python", "category": "hors_scope",
     "expect_scope": False, "expect_results": False, "expect_clarification": False},
    {"id": "OOS-04", "query": "Raconte-moi une blague", "category": "hors_scope",
     "expect_scope": False, "expect_results": False, "expect_clarification": False},
    {"id": "OOS-05", "query": "Résume ce texte : les oiseaux volent haut", "category": "hors_scope",
     "expect_scope": False, "expect_results": False, "expect_clarification": False},

    # ── CAT 8 : Edge cases / salutations / questions outil ─────────
    {"id": "EDGE-01", "query": "Bonjour", "category": "edge",
     "expect_scope": True, "expect_results": False, "expect_clarification": True},
    {"id": "EDGE-02", "query": "Comment fonctionne MONV ?", "category": "edge",
     "expect_scope": True, "expect_results": False, "expect_clarification": True},
    {"id": "EDGE-03", "query": "Merci beaucoup !", "category": "edge",
     "expect_scope": True, "expect_results": False, "expect_clarification": True},

    # ── CAT 9 : Géographies spécifiques (départements, régions) ────
    {"id": "GEO-01", "query": "Entreprises BTP dans le Nord", "category": "geo",
     "expect_scope": True, "expect_results": True, "expect_clarification": False},
    {"id": "GEO-02", "query": "Sociétés de conseil dans les Hauts-de-Seine", "category": "geo",
     "expect_scope": True, "expect_results": True, "expect_clarification": False},
    {"id": "GEO-03", "query": "Industries en Occitanie", "category": "geo",
     "expect_scope": True, "expect_results": True, "expect_clarification": False},
    {"id": "GEO-04", "query": "Commerces dans le 13", "category": "geo",
     "expect_scope": True, "expect_results": True, "expect_clarification": False},
    {"id": "GEO-05", "query": "PME tech à Nice", "category": "geo",
     "expect_scope": True, "expect_results": True, "expect_clarification": False},

    # ── CAT 10 : Formulations naturelles complexes ────────────────
    {"id": "NAT-01", "query": "Quels sont mes concurrents en restauration rapide à Nantes ?", "category": "naturel",
     "expect_scope": True, "expect_results": True, "expect_clarification": False},
    {"id": "NAT-02", "query": "J'ai une startup SaaS et je cherche des prospects PME dans l'industrie", "category": "naturel",
     "expect_scope": True, "expect_results": True, "expect_clarification": False},
    {"id": "NAT-03", "query": "Je veux lancer une campagne de prospection sur les pharmacies en PACA", "category": "naturel",
     "expect_scope": True, "expect_results": True, "expect_clarification": False},
]


# ═══════════════════════════════════════════════════════════════════════
# BENCHMARK ENGINE
# ═══════════════════════════════════════════════════════════════════════

class BenchmarkResult:
    def __init__(self, query_def: dict):
        self.id = query_def["id"]
        self.query = query_def["query"]
        self.category = query_def["category"]
        self.expect_scope = query_def["expect_scope"]
        self.expect_results = query_def["expect_results"]
        self.expect_clarification = query_def["expect_clarification"]

        self.filter_ok = None
        self.filter_in_scope = None
        self.filter_time_ms = 0

        self.guard_ok = None
        self.guard_intent = None
        self.guard_entities = None
        self.guard_clarification = None
        self.guard_missing = None
        self.guard_confidence = None
        self.guard_time_ms = 0

        self.orch_ok = None
        self.orch_plan = None
        self.orch_api_calls_count = 0
        self.orch_sources = []
        self.orch_credits = 0
        self.orch_clarification = None
        self.orch_time_ms = 0

        self.engine_ok = None
        self.engine_total = 0
        self.engine_time_ms = 0

        self.total_time_ms = 0
        self.errors = []
        self.verdict = "UNKNOWN"

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "query": self.query,
            "category": self.category,
            "verdict": self.verdict,
            "total_time_ms": self.total_time_ms,
            "filter": {
                "ok": self.filter_ok,
                "in_scope": self.filter_in_scope,
                "time_ms": self.filter_time_ms,
            },
            "guard": {
                "ok": self.guard_ok,
                "intent": self.guard_intent,
                "confidence": self.guard_confidence,
                "clarification": self.guard_clarification,
                "missing": self.guard_missing,
                "entities": self.guard_entities,
                "time_ms": self.guard_time_ms,
            },
            "orchestrator": {
                "ok": self.orch_ok,
                "api_calls_count": self.orch_api_calls_count,
                "sources": self.orch_sources,
                "credits": self.orch_credits,
                "clarification": self.orch_clarification,
                "time_ms": self.orch_time_ms,
            },
            "engine": {
                "ok": self.engine_ok,
                "total_results": self.engine_total,
                "time_ms": self.engine_time_ms,
            },
            "errors": self.errors,
            "expectations": {
                "scope": self.expect_scope,
                "results": self.expect_results,
                "clarification": self.expect_clarification,
            },
        }


async def benchmark_one(q: dict) -> BenchmarkResult:
    r = BenchmarkResult(q)
    start_all = time.monotonic()

    # ── Couche 0 : Filter ──
    try:
        t0 = time.monotonic()
        filt = await run_filter(q["query"])
        r.filter_time_ms = round((time.monotonic() - t0) * 1000)
        r.filter_in_scope = filt.in_scope
        r.filter_ok = (filt.in_scope == q["expect_scope"])
    except Exception as e:
        r.filter_ok = False
        r.errors.append(f"FILTER: {e}")
        r.filter_time_ms = round((time.monotonic() - t0) * 1000)

    if not r.filter_in_scope:
        r.total_time_ms = round((time.monotonic() - start_all) * 1000)
        r.verdict = "PASS" if r.filter_ok else "FAIL_FILTER"
        return r

    # ── Couche 1 : Guard ──
    try:
        t0 = time.monotonic()
        guard = await run_guard(q["query"])
        r.guard_time_ms = round((time.monotonic() - t0) * 1000)
        r.guard_intent = guard.intent
        r.guard_confidence = guard.confidence
        r.guard_clarification = guard.clarification_needed
        r.guard_missing = guard.missing_criteria
        r.guard_entities = guard.entities.model_dump()
        r.guard_ok = True
    except Exception as e:
        r.guard_ok = False
        r.errors.append(f"GUARD: {e}")
        r.guard_time_ms = round((time.monotonic() - t0) * 1000)
        r.total_time_ms = round((time.monotonic() - start_all) * 1000)
        r.verdict = "FAIL_GUARD"
        return r

    if guard.intent in ("hors_scope", "salutation", "meta_question"):
        r.total_time_ms = round((time.monotonic() - start_all) * 1000)
        r.verdict = "PASS" if not q["expect_results"] else "FAIL_GUARD_OOS"
        return r

    # Garde-fou : secteur + zone explicites, secteur non ambigu → skip clarification
    e = guard.entities
    has_secteur = bool(e.secteur or e.code_naf or e.mots_cles)
    has_zone = bool(e.localisation or e.departement or e.region)
    if (
        guard.clarification_needed
        and has_secteur
        and has_zone
        and not getattr(guard, "sector_ambiguous", False)
    ):
        guard.clarification_needed = False
        guard.missing_criteria = []
        r.guard_clarification = False

    if guard.clarification_needed:
        r.total_time_ms = round((time.monotonic() - start_all) * 1000)
        if q["expect_clarification"]:
            r.verdict = "PASS"
        elif q["expect_results"]:
            r.verdict = "FAIL_UNEXPECTED_CLARIFICATION"
        else:
            r.verdict = "PASS"
        return r

    # ── Couche 2 : Orchestrator ──
    try:
        t0 = time.monotonic()
        plan = await run_orchestrator(guard)
        r.orch_time_ms = round((time.monotonic() - t0) * 1000)
        r.orch_ok = True
        r.orch_api_calls_count = len(plan.api_calls)
        r.orch_sources = list({c.source for c in plan.api_calls})
        r.orch_credits = plan.estimated_credits
        r.orch_clarification = plan.clarification_needed
    except Exception as e:
        r.orch_ok = False
        r.errors.append(f"ORCH: {e}")
        r.orch_time_ms = round((time.monotonic() - t0) * 1000)
        r.total_time_ms = round((time.monotonic() - start_all) * 1000)
        r.verdict = "FAIL_ORCHESTRATOR"
        return r

    if plan.clarification_needed:
        r.total_time_ms = round((time.monotonic() - start_all) * 1000)
        r.verdict = "PASS" if q["expect_clarification"] else "FAIL_ORCH_CLARIFICATION"
        return r

    # ── Couche 3 : API Engine ──
    try:
        t0 = time.monotonic()
        patch_sirene_calls_from_guard_entities(plan, guard.entities)
        results = await execute_plan(plan)
        r.engine_time_ms = round((time.monotonic() - t0) * 1000)
        r.engine_ok = True
        r.engine_total = results.total
    except Exception as e:
        r.engine_ok = False
        r.errors.append(f"ENGINE: {traceback.format_exc()[-500:]}")
        r.engine_time_ms = round((time.monotonic() - t0) * 1000)
        r.total_time_ms = round((time.monotonic() - start_all) * 1000)
        r.verdict = "FAIL_ENGINE"
        return r

    r.total_time_ms = round((time.monotonic() - start_all) * 1000)

    if q["expect_results"] and results.total == 0:
        r.verdict = "FAIL_NO_RESULTS"
    elif q["expect_results"] and results.total > 0:
        r.verdict = "PASS"
    elif not q["expect_results"] and results.total > 0:
        r.verdict = "WARN_UNEXPECTED_RESULTS"
    else:
        r.verdict = "PASS"

    return r


async def run_benchmark():
    print("=" * 70)
    print("  BENCHMARK PIPELINE MONV")
    print(f"  {len(QUERIES)} requêtes — {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)
    print()

    results: list[BenchmarkResult] = []

    for i, q in enumerate(QUERIES, 1):
        print(f"[{i:2d}/{len(QUERIES)}] {q['id']:12s} | {q['query'][:55]:55s} ", end="", flush=True)
        try:
            r = await benchmark_one(q)
        except Exception as e:
            r = BenchmarkResult(q)
            r.verdict = "CRASH"
            r.errors.append(str(e))
        results.append(r)

        icon = {"PASS": "✅", "FAIL_FILTER": "❌", "FAIL_GUARD": "❌",
                "FAIL_GUARD_OOS": "❌", "FAIL_UNEXPECTED_CLARIFICATION": "⚠️",
                "FAIL_ORCHESTRATOR": "❌", "FAIL_ORCH_CLARIFICATION": "⚠️",
                "FAIL_ENGINE": "❌", "FAIL_NO_RESULTS": "🔴",
                "WARN_UNEXPECTED_RESULTS": "⚠️", "CRASH": "💥"}.get(r.verdict, "❓")

        print(f"{icon} {r.verdict:30s} | {r.engine_total:3d} résultats | {r.total_time_ms:5d}ms")

    # ── Rapport ──
    print()
    print("=" * 70)
    print("  RÉSUMÉ DU BENCHMARK")
    print("=" * 70)

    categories = {}
    for r in results:
        cat = r.category
        if cat not in categories:
            categories[cat] = {"pass": 0, "fail": 0, "warn": 0, "total": 0}
        categories[cat]["total"] += 1
        if r.verdict == "PASS":
            categories[cat]["pass"] += 1
        elif r.verdict.startswith("WARN"):
            categories[cat]["warn"] += 1
        else:
            categories[cat]["fail"] += 1

    total_pass = sum(c["pass"] for c in categories.values())
    total_fail = sum(c["fail"] for c in categories.values())
    total_warn = sum(c["warn"] for c in categories.values())
    total_all = len(results)

    print(f"\n  GLOBAL : {total_pass}/{total_all} PASS | {total_fail} FAIL | {total_warn} WARN")
    print(f"  Score  : {total_pass/total_all*100:.1f}%\n")

    for cat, stats in sorted(categories.items()):
        bar = f"{'█' * stats['pass']}{'░' * stats['fail']}{'▒' * stats['warn']}"
        print(f"  {cat:25s} {stats['pass']}/{stats['total']} {bar}")

    # Détail des échecs
    failures = [r for r in results if r.verdict.startswith("FAIL")]
    if failures:
        print(f"\n  ── ÉCHECS DÉTAILLÉS ({len(failures)}) ──")
        for r in failures:
            print(f"\n  {r.id} [{r.category}] → {r.verdict}")
            print(f"    Query: {r.query}")
            if r.guard_intent:
                print(f"    Guard intent: {r.guard_intent}, confidence: {r.guard_confidence}")
            if r.guard_entities:
                ents = {k: v for k, v in r.guard_entities.items() if v}
                if ents:
                    print(f"    Entities: {json.dumps(ents, ensure_ascii=False)}")
            if r.orch_sources:
                print(f"    Orch sources: {r.orch_sources}, calls: {r.orch_api_calls_count}")
            if r.errors:
                print(f"    Errors: {'; '.join(r.errors)}")

    # Warnings
    warnings = [r for r in results if r.verdict.startswith("WARN")]
    if warnings:
        print(f"\n  ── WARNINGS ({len(warnings)}) ──")
        for r in warnings:
            print(f"    {r.id}: {r.verdict} — {r.query[:60]}")

    # Temps
    avg_ms = sum(r.total_time_ms for r in results) / len(results) if results else 0
    max_r = max(results, key=lambda x: x.total_time_ms) if results else None
    print(f"\n  ── PERFORMANCE ──")
    print(f"  Temps moyen : {avg_ms:.0f}ms")
    if max_r:
        print(f"  Plus lent   : {max_r.id} ({max_r.total_time_ms}ms)")
    print(f"  Temps total : {sum(r.total_time_ms for r in results)/1000:.1f}s")

    # Sauvegarder le rapport JSON
    report = {
        "timestamp": datetime.now().isoformat(),
        "total_queries": total_all,
        "pass": total_pass,
        "fail": total_fail,
        "warn": total_warn,
        "score_pct": round(total_pass / total_all * 100, 1),
        "categories": categories,
        "results": [r.to_dict() for r in results],
    }

    report_path = Path(__file__).parent / "benchmark_report.json"
    with open(report_path, "w") as f:
        json.dump(report, f, ensure_ascii=False, indent=2, default=str)
    print(f"\n  Rapport sauvegardé : {report_path}")

    return report


if __name__ == "__main__":
    report = asyncio.run(run_benchmark())
