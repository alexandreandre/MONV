"""Détecteur lexical + second passage ambiguïté sectorielle (Guard)."""

from __future__ import annotations

import asyncio
import importlib
import sys
import types
from types import SimpleNamespace

import pytest

from config import settings
from services import guard_ambiguity as ga


def _minimal_guard_json(**overrides: object) -> dict:
    base: dict = {
        "intent": "recherche_entreprise",
        "confidence": 0.5,
        "context_hints": [],
        "entities": {
            "localisation": "Marseille",
            "departement": None,
            "region": None,
            "secteur": None,
            "code_naf": None,
            "taille_min": None,
            "taille_max": None,
            "ca_min": None,
            "ca_max": None,
            "date_creation_apres": None,
            "date_creation_avant": None,
            "mots_cles": ["padel"],
            "forme_juridique": None,
        },
        "clarification_needed": False,
        "missing_criteria": [],
        "clarification_question": None,
        "sector_ambiguous": False,
        "sector_confirmed": None,
    }
    base.update(overrides)
    return base


def _stub_agent_config_module(fake_resolve):
    m = types.ModuleType("services.agent_config")
    m.resolve_llm_for_block = fake_resolve
    return m


def _stub_llm_module(fake_llm_json):
    m = types.ModuleType("utils.llm")
    m.llm_json_call = fake_llm_json
    return m


def _reload_guard_with_stub(monkeypatch, fake_resolve, fake_llm_json) -> None:
    """Évite de charger OpenAI / supabase lors des tests d’intégration Guard."""
    monkeypatch.setitem(sys.modules, "utils.llm", _stub_llm_module(fake_llm_json))
    monkeypatch.setitem(sys.modules, "services.agent_config", _stub_agent_config_module(fake_resolve))
    if "services.guard" in sys.modules:
        importlib.reload(sys.modules["services.guard"])
    else:
        importlib.import_module("services.guard")


def test_message_triggers_padel():
    assert ga.message_triggers_sector_ambiguity_check("Clubs de padel à Marseille") is True


def test_message_triggers_long_substring():
    assert ga.message_triggers_sector_ambiguity_check("Agence de communication à Lyon") is True


def test_message_triggers_comptable_negative():
    assert ga.message_triggers_sector_ambiguity_check("Cabinet comptable à Rennes") is False


def test_message_triggers_disabled_via_settings(monkeypatch):
    monkeypatch.setattr(settings, "GUARD_SECTOR_AMBIGUITY_SECOND_PASS", False)
    try:
        assert ga.message_triggers_sector_ambiguity_check("padel partout") is False
    finally:
        monkeypatch.setattr(settings, "GUARD_SECTOR_AMBIGUITY_SECOND_PASS", True)


def test_run_guard_single_llm_when_no_lexical_trigger(monkeypatch):
    calls: list[int] = []

    async def fake_resolve(
        agent_id: str,
        block_id: str,
        *,
        default_model: str,
        default_system: str,
        default_max_tokens: int,
        default_temperature: float,
        default_top_p: float = 1.0,
    ) -> SimpleNamespace:
        return SimpleNamespace(
            model="stub",
            system_prompt=default_system,
            max_tokens=default_max_tokens,
            temperature=default_temperature,
            top_p=default_top_p,
        )

    async def fake_llm_json(**kwargs: object) -> dict:
        calls.append(1)
        return _minimal_guard_json(
            mots_cles=["comptabilité"],
            entities={
                "localisation": "Lille",
                "departement": None,
                "region": None,
                "secteur": None,
                "code_naf": None,
                "taille_min": None,
                "taille_max": None,
                "ca_min": None,
                "ca_max": None,
                "date_creation_apres": None,
                "date_creation_avant": None,
                "mots_cles": ["comptabilité"],
                "forme_juridique": None,
            },
        )

    _reload_guard_with_stub(monkeypatch, fake_resolve, fake_llm_json)

    from services.guard import run_guard

    async def _run() -> None:
        g = await run_guard("Expert-comptable à Lille", conversation_history=None)
        assert len(calls) == 1
        assert g.sector_ambiguous is False

    asyncio.run(_run())


def test_run_guard_second_llm_overrides_sector_ambiguous(monkeypatch):
    calls: list[int] = []

    async def fake_resolve(
        agent_id: str,
        block_id: str,
        *,
        default_model: str,
        default_system: str,
        default_max_tokens: int,
        default_temperature: float,
        default_top_p: float = 1.0,
    ) -> SimpleNamespace:
        return SimpleNamespace(
            model="stub",
            system_prompt=default_system,
            max_tokens=default_max_tokens,
            temperature=default_temperature,
            top_p=default_top_p,
        )

    async def fake_llm_json(**kwargs: object) -> dict:
        calls.append(1)
        if len(calls) == 1:
            return _minimal_guard_json()
        return {"sector_ambiguous": True}

    _reload_guard_with_stub(monkeypatch, fake_resolve, fake_llm_json)

    from services.guard import run_guard

    async def _run() -> None:
        g = await run_guard("Clubs de padel à Marseille", conversation_history=None)
        assert len(calls) == 2
        assert g.sector_ambiguous is True
        assert "secteur_confirmation" in g.missing_criteria

    asyncio.run(_run())


def test_run_guard_second_pass_skipped_when_setting_off(monkeypatch):
    monkeypatch.setattr(settings, "GUARD_SECTOR_AMBIGUITY_SECOND_PASS", False)
    calls: list[int] = []

    async def fake_resolve(
        agent_id: str,
        block_id: str,
        *,
        default_model: str,
        default_system: str,
        default_max_tokens: int,
        default_temperature: float,
        default_top_p: float = 1.0,
    ) -> SimpleNamespace:
        return SimpleNamespace(
            model="stub",
            system_prompt=default_system,
            max_tokens=default_max_tokens,
            temperature=default_temperature,
            top_p=default_top_p,
        )

    async def fake_llm_json(**kwargs: object) -> dict:
        calls.append(1)
        return _minimal_guard_json()

    _reload_guard_with_stub(monkeypatch, fake_resolve, fake_llm_json)

    from services.guard import run_guard

    async def _run() -> None:
        g = await run_guard("Clubs de padel à Marseille", conversation_history=None)
        assert len(calls) == 1
        assert g.sector_ambiguous is False

    try:
        asyncio.run(_run())
    finally:
        monkeypatch.setattr(settings, "GUARD_SECTOR_AMBIGUITY_SECOND_PASS", True)
