"""POST /api/search/estimate — garde-orchestrateur sans connecteurs."""

from __future__ import annotations

import os

os.environ.setdefault("SKIP_DB_VERIFY_ON_STARTUP", "true")
os.environ.setdefault("SUPABASE_URL", "https://placeholder.supabase.co")
os.environ.setdefault("SUPABASE_SERVICE_KEY", "placeholder-service-key")
if not (os.environ.get("OPENROUTER_API_KEY") or "").strip():
    os.environ["OPENROUTER_API_KEY"] = "test-placeholder-openrouter-key"

import asyncio
from unittest.mock import AsyncMock, patch

from models.schemas import GuardEntity, GuardResult
from services.filter import FilterResult
from services.search_estimate import estimate_search_execution


def _minimal_guard() -> GuardResult:
    return GuardResult(
        intent="recherche_entreprise",
        entities=GuardEntity(
            secteur="BTP",
            localisation="Lyon",
        ),
        confidence=0.9,
        clarification_needed=False,
    )


def test_estimate_out_of_scope():
    async def _run():
        with patch("services.search_estimate.run_filter", new_callable=AsyncMock) as rf:
            rf.return_value = FilterResult(in_scope=False)
            return await estimate_search_execution(
                user_message="poème",
                mode="prospection",
                history=[],
                recent_db=[],
                recent_for_gates=[],
                agent_id="prospection",
                skip_filter_llm=False,
            )

    out = asyncio.run(_run())
    assert out["in_scope"] is False
    assert out["api_calls"] == []


def test_estimate_plan_without_connectors():
    from models.schemas import APICall, ExecutionPlan

    plan = ExecutionPlan(
        description="Test",
        estimated_credits=3,
        api_calls=[
            APICall(source="sirene", action="search", params={"q": "x"}),
        ],
        columns=["nom"],
        clarification_needed=False,
    )

    async def _run():
        with (
            patch("services.search_estimate.run_filter", new_callable=AsyncMock) as rf,
            patch("services.search_estimate.run_guard", new_callable=AsyncMock) as rg,
            patch("services.search_estimate.run_orchestrator", new_callable=AsyncMock) as ro,
        ):
            rf.return_value = FilterResult(in_scope=True)
            rg.return_value = _minimal_guard()
            ro.return_value = plan
            return await estimate_search_execution(
                user_message="PME BTP à Lyon",
                mode="prospection",
                history=[{"role": "user", "content": "PME BTP à Lyon"}],
                recent_db=[],
                recent_for_gates=[],
                agent_id="prospection",
            )

    out = asyncio.run(_run())
    assert out["in_scope"] is True
    assert out["clarification_needed"] is False
    assert out["estimated_credits"] == 3
    assert len(out["api_calls"]) == 1
    assert out["api_calls"][0].get("source") == "sirene"
