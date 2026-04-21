"""Panel seuil relevance — voir benchmark_relevance_panel.py (≥30 cas)."""

from __future__ import annotations

import os

os.environ.setdefault("SKIP_DB_VERIFY_ON_STARTUP", "true")
os.environ.setdefault("SUPABASE_URL", "https://placeholder.supabase.co")
os.environ.setdefault("SUPABASE_SERVICE_KEY", "placeholder-service-key")

import pytest

from benchmark_relevance_panel import THRESHOLD_CASES
from services.relevance import _compute_threshold


@pytest.mark.parametrize(
    "case_id,guard,n_res,expected",
    [(c[0], c[1], c[2], c[3]) for c in THRESHOLD_CASES],
    ids=[c[0] for c in THRESHOLD_CASES],
)
def test_compute_threshold_panel(case_id, guard, n_res, expected):
    assert _compute_threshold(guard, n_res) == expected, case_id
