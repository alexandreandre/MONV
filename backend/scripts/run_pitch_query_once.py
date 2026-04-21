#!/usr/bin/env python3
"""Exécute une recherche complète (guard → orchestrateur → APIs → pertinence → pitch)."""
from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from services.filter import run_filter
from services.guard import run_guard
from services.orchestrator import run_orchestrator
from services.api_engine import execute_plan
from services.relevance import filter_results_by_relevance
from services.digital_pitch_enrichment import (
    DIGITAL_PITCH_RESULT_COLUMNS,
    enrich_results_for_digital_service_pitch,
)
from services.sirene import patch_sirene_calls_from_guard_entities


QUERY = (
    "Je cherche des boutiques de padel et clubs de padel pour leur proposer "
    "la création ou la refonte d'un site web, Marseille/PACA"
)


async def main() -> None:
    f = await run_filter(QUERY)
    if not f.in_scope:
        print("filter out of scope")
        return
    g = await run_guard(QUERY)
    if g.clarification_needed:
        print("clarification_needed", g.missing_criteria)
        return
    plan = await run_orchestrator(g, mode="prospection")
    if plan.clarification_needed:
        print("orch clarification", plan.clarification_question)
        return
    patch_sirene_calls_from_guard_entities(plan, g.entities)
    sr = await execute_plan(plan, mode="prospection")
    print("raw_total", sr.total)
    if sr.total == 0:
        return
    filtered, rel = await filter_results_by_relevance(
        sr.results, user_query=QUERY, guard_result=g, mode="prospection"
    )
    sr.results = filtered
    sr.total = len(filtered)
    print("relevance", {k: rel.get(k) for k in ("relevance_removed", "relevance_threshold", "relevance_avg_score")})
    pitch = await enrich_results_for_digital_service_pitch(
        sr.results, user_query=QUERY, guard_result=g, mode="prospection"
    )
    print("pitch_enriched", pitch, "columns", DIGITAL_PITCH_RESULT_COLUMNS if pitch else sr.columns)
    for i, r in enumerate(sr.results[:22]):
        line = {
            "nom": r.nom,
            "ville": r.ville,
            "site": r.site_web,
            "type": getattr(r, "type_etablissement_prospect", None),
            "opp": (getattr(r, "opportunite_prestation_web", None) or "")[:80],
        }
        print(json.dumps(line, ensure_ascii=False))


if __name__ == "__main__":
    asyncio.run(main())
