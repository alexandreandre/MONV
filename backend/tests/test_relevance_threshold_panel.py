"""Panel seuil relevance — voir benchmark_relevance_panel.py (≥30 cas)."""

from __future__ import annotations

import os

os.environ.setdefault("SKIP_DB_VERIFY_ON_STARTUP", "true")
os.environ.setdefault("SUPABASE_URL", "https://placeholder.supabase.co")
os.environ.setdefault("SUPABASE_SERVICE_KEY", "placeholder-service-key")

import sys
import types

if "services.agent_config" not in sys.modules:
    _stub_ac = types.ModuleType("services.agent_config")

    async def _fake_resolve_llm_block(
        agent_id: str,
        block_id: str,
        *,
        default_model: str,
        default_system: str,
        default_max_tokens: int,
        default_temperature: float,
        default_top_p: float = 1.0,
    ):
        return types.SimpleNamespace(
            model=default_model,
            system_prompt=default_system,
            max_tokens=default_max_tokens,
            temperature=default_temperature,
            top_p=default_top_p,
        )

    _stub_ac.resolve_llm_for_block = _fake_resolve_llm_block
    sys.modules["services.agent_config"] = _stub_ac

import pytest

from benchmark_relevance_panel import THRESHOLD_CASES
from services.relevance import _compute_threshold


@pytest.mark.parametrize("case", THRESHOLD_CASES, ids=[c["id"] for c in THRESHOLD_CASES])
def test_compute_threshold_panel(case):
    got = _compute_threshold(
        case["guard"],
        case["n"],
        mode=case.get("mode", "prospection"),
        results=case.get("results"),
    )
    assert got == case["expected"], case["id"]
