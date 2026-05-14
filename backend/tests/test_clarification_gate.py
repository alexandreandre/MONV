"""Règles anti double-QCM (Guard / Orchestrateur après réponse à un QCM)."""

from datetime import datetime, timezone

from models.entities import Message
from models.schemas import GuardEntity, GuardResult
from services.clarification_gate import (
    guard_entities_complete_for_search,
    should_skip_orchestrator_clarification_qcm,
    should_suppress_orchestrator_clarification_after_guard_flow,
    should_unlock_guard_after_qcm,
    user_message_follows_assistant_qcm,
)


def _msg(role: str, message_type: str = "text") -> Message:
    return Message(
        id="m",
        conversation_id="c",
        role=role,
        content="x",
        message_type=message_type,
        metadata_json=None,
        created_at=datetime.now(timezone.utc),
    )


def test_user_follows_assistant_qcm_true():
    seq = [_msg("assistant", "qcm"), _msg("user")]
    assert user_message_follows_assistant_qcm(seq) is True


def test_user_follows_assistant_qcm_false_when_prev_not_qcm():
    seq = [_msg("assistant", "text"), _msg("user")]
    assert user_message_follows_assistant_qcm(seq) is False


def test_guard_entities_complete_requires_zone_and_sector():
    g = GuardResult(
        intent="recherche_entreprise",
        entities=GuardEntity(secteur="BTP", departement="69"),
        confidence=0.9,
        sector_ambiguous=False,
    )
    assert guard_entities_complete_for_search(g) is True

    g2 = GuardResult(
        intent="recherche_entreprise",
        entities=GuardEntity(secteur="BTP"),
        confidence=0.9,
        sector_ambiguous=False,
    )
    assert guard_entities_complete_for_search(g2) is False


def test_guard_entities_complete_ambiguous_without_confirmation():
    g = GuardResult(
        intent="recherche_entreprise",
        entities=GuardEntity(secteur="padel", region="PACA"),
        confidence=0.9,
        sector_ambiguous=True,
        sector_confirmed=None,
    )
    assert guard_entities_complete_for_search(g) is False

    g2 = g.model_copy(update={"sector_confirmed": "padel club"})
    assert guard_entities_complete_for_search(g2) is True


def test_unlock_guard_only_prospection_benchmark():
    seq = [_msg("assistant", "qcm"), _msg("user")]
    g = GuardResult(
        intent="recherche_entreprise",
        entities=GuardEntity(secteur="x", departement="75"),
        confidence=0.9,
        clarification_needed=True,
        missing_criteria=["zone_geo"],
        sector_ambiguous=False,
    )
    assert should_unlock_guard_after_qcm(g, seq, mode="prospection") is True
    assert should_unlock_guard_after_qcm(g, seq, mode="rachat") is False


def test_skip_orchestrator_qcm_rachat_when_missing_criteria():
    seq = [_msg("assistant", "qcm"), _msg("user")]
    g = GuardResult(
        intent="recherche_entreprise",
        entities=GuardEntity(secteur="x", departement="75"),
        confidence=0.9,
        missing_criteria=["budget_acquisition"],
        sector_ambiguous=False,
    )
    assert (
        should_skip_orchestrator_clarification_qcm(
            plan_clarification_needed=True,
            guard_result=g,
            recent_messages=seq,
            mode="rachat",
        )
        is False
    )

    g2 = g.model_copy(update={"missing_criteria": []})
    assert (
        should_skip_orchestrator_clarification_qcm(
            plan_clarification_needed=True,
            guard_result=g2,
            recent_messages=seq,
            mode="rachat",
        )
        is True
    )


def test_suppress_orchestrator_clarification_when_guard_clear_after_qcm():
    """Guard sans clarification résiduelle + user après QCM → pas de second QCM orchestrateur."""
    seq = [_msg("assistant", "qcm"), _msg("user")]
    g = GuardResult(
        intent="recherche_entreprise",
        entities=GuardEntity(secteur="BTP", departement="69"),
        confidence=0.9,
        clarification_needed=False,
        missing_criteria=[],
        sector_ambiguous=False,
    )
    assert should_suppress_orchestrator_clarification_after_guard_flow(
        plan_clarification_needed=True,
        guard_result=g,
        recent_messages=seq,
        mode="prospection",
    ) is True


def test_suppress_orchestrator_false_when_guard_still_needs_clarification():
    seq = [_msg("assistant", "qcm"), _msg("user")]
    g = GuardResult(
        intent="recherche_entreprise",
        entities=GuardEntity(secteur="BTP", departement="69"),
        confidence=0.9,
        clarification_needed=True,
        missing_criteria=["zone_geo"],
        sector_ambiguous=False,
    )
    assert should_suppress_orchestrator_clarification_after_guard_flow(
        plan_clarification_needed=True,
        guard_result=g,
        recent_messages=seq,
        mode="prospection",
    ) is False
