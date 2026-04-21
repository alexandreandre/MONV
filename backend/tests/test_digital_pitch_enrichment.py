"""Enrichissement « pitch digital » — détection requête + mock LLM."""

from __future__ import annotations

import asyncio
import os
from unittest.mock import AsyncMock, patch

os.environ.setdefault("SKIP_DB_VERIFY_ON_STARTUP", "true")
os.environ.setdefault("SUPABASE_URL", "https://placeholder.supabase.co")
os.environ.setdefault("SUPABASE_SERVICE_KEY", "placeholder-service-key")

from config import settings  # noqa: E402
from models.schemas import CompanyResult, GuardEntity, GuardResult  # noqa: E402
from services import digital_pitch_enrichment as dpe  # noqa: E402
from services.digital_pitch_enrichment import (  # noqa: E402
    DIGITAL_PITCH_RESULT_COLUMNS,
    enrich_results_for_digital_service_pitch,
    user_query_suggests_digital_service_pitch,
)


def test_user_query_detects_web_pitch_phrases():
    q = (
        "Je cherche des boutiques de padel et clubs de padel pour leur proposer "
        "la création ou la refonte d'un site web, Marseille/PACA"
    )
    assert user_query_suggests_digital_service_pitch(q) is True
    assert user_query_suggests_digital_service_pitch("PME BTP Lyon") is False
    assert user_query_suggests_digital_service_pitch("x") is False


def test_infer_columns_prospection_prefers_pitch_panel():
    from routers.search import _infer_columns

    rows = [
        CompanyResult(
            siren="123456789",
            nom="Test",
            synthese_site_web="Hypothèse.",
            opportunite_prestation_web="Moyenne - test.",
        )
    ]
    cols = _infer_columns("recherche_entreprise", {}, rows, mode="prospection")
    assert cols == DIGITAL_PITCH_RESULT_COLUMNS


def test_enrich_fills_fields():
    rows = [
        CompanyResult(siren="111111111", nom="Club A", ville="Marseille", site_web="https://a.fr"),
        CompanyResult(siren="222222222", nom="Shop B", ville="Aix-en-Provence"),
    ]
    guard = GuardResult(
        intent="recherche_entreprise",
        entities=GuardEntity(mots_cles=["padel"]),
        confidence=0.9,
    )

    async def fake_llm(*args, **kwargs):
        return {
            "lignes": [
                {"id": 0, "type": "Club", "analyse": "Site probablement simple.", "opportunite": "Moyenne - test."},
                {"id": 1, "type": "Boutique", "analyse": "E-commerce.", "opportunite": "Faible - déjà outillé."},
            ]
        }

    async def run():
        with patch.object(settings, "OPENROUTER_API_KEY", "k"):
            with patch.object(dpe, "llm_json_call", new_callable=AsyncMock, side_effect=fake_llm):
                return await enrich_results_for_digital_service_pitch(
                    rows,
                    user_query="proposer une refonte de site web aux clubs",
                    guard_result=guard,
                    mode="prospection",
                )

    assert asyncio.run(run()) is True
    assert rows[0].type_etablissement_prospect == "Club"
    assert rows[0].synthese_site_web
    assert rows[1].opportunite_prestation_web.startswith("Faible")


def test_enrich_skipped_non_prospection():
    rows = [CompanyResult(siren="1", nom="X")]

    async def run():
        with patch.object(settings, "OPENROUTER_API_KEY", "k"):
            return await enrich_results_for_digital_service_pitch(
                rows,
                user_query="refonte site pour les pros",
                guard_result=GuardResult(
                    intent="recherche_entreprise",
                    entities=GuardEntity(),
                    confidence=1.0,
                ),
                mode="benchmark",
            )

    assert asyncio.run(run()) is False
