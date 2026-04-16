"""Tests du post-filtrage de pertinence — mock LLM, sans réseau."""

from __future__ import annotations

import asyncio
import os
from unittest.mock import AsyncMock, patch

os.environ.setdefault("SKIP_DB_VERIFY_ON_STARTUP", "true")
os.environ.setdefault("SUPABASE_URL", "https://placeholder.supabase.co")
os.environ.setdefault("SUPABASE_SERVICE_KEY", "placeholder-service-key")
os.environ.setdefault("OPENROUTER_API_KEY", "test-key-for-relevance")

from config import settings  # noqa: E402
from models.schemas import CompanyResult, GuardEntity, GuardResult  # noqa: E402
from services import relevance as relevance_mod  # noqa: E402
from services.relevance import filter_results_by_relevance, row_for_relevance_check  # noqa: E402


def _guard() -> GuardResult:
    return GuardResult(
        intent="recherche_entreprise",
        entities=GuardEntity(mots_cles=["padel"], secteur=None, localisation="Marseille"),
        confidence=0.9,
        original_query="boutiques padel",
    )


def test_row_for_relevance_check_shape():
    r = CompanyResult(
        siren="123456789",
        nom="Club Test",
        libelle_activite="Enseignement de disciplines sportives",
        ville="Marseille",
    )
    d = row_for_relevance_check(7, r)
    assert d["id"] == 7
    assert d["nom"] == "Club Test"
    assert "libelle_activite" in d


def test_filter_keeps_rows_per_llm_decisions():
    rows = [
        CompanyResult(siren="111111111", nom="Padel Sud", libelle_activite="Club de padel"),
        CompanyResult(siren="222222222", nom="Yoga Zen", libelle_activite="Cours de yoga"),
        CompanyResult(siren="333333333", nom="Smash Padel", libelle_activite="Location terrain padel"),
    ]

    async def fake_llm_json_call(model, system, messages, max_tokens=2048, temperature=0.0):
        payload = (messages[0].get("content") or "") if messages else ""
        if "Yoga Zen" in payload:
            return {
                "decisions": [
                    {"id": 0, "keep": True},
                    {"id": 1, "keep": False},
                    {"id": 2, "keep": True},
                ]
            }
        return {"decisions": []}

    async def run():
        with patch.object(relevance_mod, "llm_json_call", new_callable=AsyncMock, side_effect=fake_llm_json_call):
            return await filter_results_by_relevance(
                rows,
                user_query="boutique padel Marseille",
                guard_result=_guard(),
                mode="prospection",
            )

    out, stats = asyncio.run(run())
    assert len(out) == 2
    assert {r.nom for r in out} == {"Padel Sud", "Smash Padel"}
    assert stats["relevance_removed"] == 1


def test_filter_skipped_without_openrouter_key():
    rows = [
        CompanyResult(siren="111111111", nom="A"),
        CompanyResult(siren="222222222", nom="B"),
    ]

    async def run():
        with patch.object(settings, "OPENROUTER_API_KEY", ""):
            return await filter_results_by_relevance(
                rows,
                user_query="x",
                guard_result=_guard(),
                mode="prospection",
            )

    out, stats = asyncio.run(run())
    assert len(out) == 2
    assert stats["relevance_skipped"] is True


def test_filter_fallback_when_all_rejected():
    rows = [
        CompanyResult(siren="111111111", nom="A"),
        CompanyResult(siren="222222222", nom="B"),
    ]

    async def fake_llm_json_call(*args, **kwargs):
        return {
            "decisions": [
                {"id": 0, "keep": False},
                {"id": 1, "keep": False},
            ]
        }

    async def run():
        with patch.object(relevance_mod, "llm_json_call", new_callable=AsyncMock, side_effect=fake_llm_json_call):
            return await filter_results_by_relevance(
                rows,
                user_query="x",
                guard_result=_guard(),
                mode="prospection",
            )

    out, stats = asyncio.run(run())
    assert len(out) == 2
    assert stats.get("relevance_fallback_unfiltered") is True
    assert stats["relevance_removed"] == 0
