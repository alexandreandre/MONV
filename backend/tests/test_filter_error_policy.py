"""Politique filtre sur erreur LLM + rate limit chat."""

from __future__ import annotations

import os

os.environ.setdefault("SKIP_DB_VERIFY_ON_STARTUP", "true")
os.environ.setdefault("SUPABASE_URL", "https://placeholder.supabase.co")
os.environ.setdefault("SUPABASE_SERVICE_KEY", "placeholder-service-key")
if not (os.environ.get("OPENROUTER_API_KEY") or "").strip():
    os.environ["OPENROUTER_API_KEY"] = "test-placeholder-openrouter-key"

import pytest

from config import settings
from services.sliding_rate_limit import check_sliding_window, reset_sliding_window
from utils.filter_heuristic import heuristic_in_scope


@pytest.fixture(autouse=True)
def _reset_rate_limit():
    reset_sliding_window()
    yield
    reset_sliding_window()


def test_heuristic_rejects_obvious_off_topic():
    assert heuristic_in_scope("Écris-moi un poème sur la mer") is False
    assert heuristic_in_scope("Aide-moi à coder en Python") is False


def test_heuristic_accepts_greeting():
    assert heuristic_in_scope("Bonjour !") is True


def test_heuristic_accepts_b2b_keywords():
    assert heuristic_in_scope("Trouve des PME du BTP à Lyon") is True


def test_error_policy_fail_closed(monkeypatch):
    monkeypatch.setattr(settings, "FILTER_LLM_ERROR_POLICY", "fail_closed")
    from services.filter import in_scope_after_filter_llm_error

    assert in_scope_after_filter_llm_error("n'importe quoi") is False


def test_error_policy_heuristic_then_closed(monkeypatch):
    monkeypatch.setattr(settings, "FILTER_LLM_ERROR_POLICY", "heuristic_then_closed")
    from services.filter import in_scope_after_filter_llm_error

    assert in_scope_after_filter_llm_error("poème sur l'automne") is False
    assert in_scope_after_filter_llm_error("Je cherche des ESN à Paris") is True


def test_error_policy_fail_open_default(monkeypatch):
    monkeypatch.setattr(settings, "FILTER_LLM_ERROR_POLICY", "fail_open")
    from services.filter import in_scope_after_filter_llm_error

    assert in_scope_after_filter_llm_error("n'importe quoi") is True


def test_skip_llm_heuristic_greeting():
    from utils.filter_heuristic import skip_filter_llm_if_heuristic_strong

    assert skip_filter_llm_if_heuristic_strong("Bonjour !") is True


def test_skip_llm_heuristic_long_b2b():
    from utils.filter_heuristic import skip_filter_llm_if_heuristic_strong

    msg = (
        "Je cherche des entreprises du secteur du bâtiment en région parisienne "
        "avec plus de vingt salariés pour une prospection commerciale"
    )
    assert skip_filter_llm_if_heuristic_strong(msg) is True


def test_skip_llm_heuristic_siren_digits():
    from utils.filter_heuristic import skip_filter_llm_if_heuristic_strong

    assert skip_filter_llm_if_heuristic_strong("Fiche entreprise SIREN 552032534") is True


def test_skip_llm_heuristic_not_short_ambiguous():
    from utils.filter_heuristic import skip_filter_llm_if_heuristic_strong

    assert skip_filter_llm_if_heuristic_strong("ok") is False
    assert skip_filter_llm_if_heuristic_strong("Python") is False
    reset_sliding_window("u1")
    assert check_sliding_window("u1", max_events=3, window_s=60.0) is True
    assert check_sliding_window("u1", max_events=3, window_s=60.0) is True
    assert check_sliding_window("u1", max_events=3, window_s=60.0) is True
    assert check_sliding_window("u1", max_events=3, window_s=60.0) is False
