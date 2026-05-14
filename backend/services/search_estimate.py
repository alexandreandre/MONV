"""
Estimation d'un plan de recherche sans exécuter SIRENE / Pappers / Places.

Aligné sur le plan produit (aperçu crédits / appels) : garde + orchestrateur + patches
identiques au chat avant ``execute_plan``.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from supabase import Client

from models.db import messages_recent_for_llm
from models.schemas import GUARD_INTENTS_STATIC_REPLY, GuardResult
from services.filter import FilterResult, run_filter
from services.guard import run_guard
from services.modes import Mode, normalize_mode
from services.orchestrator import maybe_clamp_prospection_after_plan_patches, run_orchestrator
from services.plan_google_places import (
    augment_google_places_boutique_and_club_queries,
    augment_google_places_regional_variant,
)
from services.sirene import patch_sirene_calls_from_guard_entities
from services.clarification_gate import (
    should_skip_orchestrator_clarification_qcm,
    should_unlock_guard_after_qcm,
)
from models.entities import Message


async def estimate_search_execution(
    *,
    user_message: str,
    mode: Mode,
    history: list[dict],
    recent_db: list[Message],
    recent_for_gates: list[Message],
    agent_id: str,
    skip_filter_llm: bool = False,
) -> dict[str, Any]:
    """
    Retourne un dict sérialisable (réponse ``POST /api/search/estimate``).

    ``recent_db`` : fenêtre récente telle qu'en base **avant** le message courant
    (qualification rachat / sous-traitant, skip filtre si QCM).

    ``recent_for_gates`` : ``recent_db`` + message utilisateur courant **synthétique**
    en dernière position (même logique que ``user_message_follows_assistant_qcm``).
    """
    active_mode: Mode = normalize_mode(mode)

    if skip_filter_llm:
        filter_result = FilterResult(in_scope=True)
    else:
        filter_result = await run_filter(user_message, agent_id=agent_id)
    if not filter_result.in_scope:
        return {
            "in_scope": False,
            "clarification_needed": False,
            "clarification_source": None,
            "orchestrator_clarification_needed": False,
            "guard_static_intent": None,
            "estimated_credits": None,
            "description": None,
            "api_calls": [],
            "columns": [],
            "intent": None,
            "missing_criteria": [],
        }

    guard_result: GuardResult = await run_guard(user_message, history, agent_id=agent_id)

    if should_unlock_guard_after_qcm(guard_result, recent_for_gates, mode=active_mode):
        guard_result = guard_result.model_copy(
            update={"clarification_needed": False, "missing_criteria": []}
        )

    e = guard_result.entities
    has_secteur = bool(e.secteur or e.code_naf or e.mots_cles)
    has_zone = bool(e.localisation or e.departement or e.region)
    if guard_result.clarification_needed and has_secteur and has_zone:
        if not getattr(guard_result, "sector_ambiguous", False):
            guard_result = guard_result.model_copy(
                update={"clarification_needed": False, "missing_criteria": []}
            )

    if active_mode in ("sous_traitant", "rachat") and not guard_result.clarification_needed:
        has_qcm_in_history = any(m.message_type == "qcm" for m in recent_db)
        if not has_qcm_in_history:
            base_missing: list[str] = []
            if not has_zone:
                base_missing.append("zone_geo")
            if active_mode == "sous_traitant":
                guard_result = guard_result.model_copy(
                    update={
                        "missing_criteria": base_missing + ["capacite", "type_mission"],
                        "clarification_needed": True,
                    }
                )
            else:
                guard_result = guard_result.model_copy(
                    update={
                        "missing_criteria": base_missing
                        + ["budget_acquisition", "profil_cible", "type_reprise"],
                        "clarification_needed": True,
                    }
                )

    if guard_result.intent in GUARD_INTENTS_STATIC_REPLY:
        return {
            "in_scope": True,
            "clarification_needed": False,
            "clarification_source": None,
            "orchestrator_clarification_needed": False,
            "guard_static_intent": guard_result.intent,
            "estimated_credits": None,
            "description": None,
            "api_calls": [],
            "columns": [],
            "intent": guard_result.intent,
            "missing_criteria": [],
        }

    if guard_result.clarification_needed:
        return {
            "in_scope": True,
            "clarification_needed": True,
            "clarification_source": "guard",
            "orchestrator_clarification_needed": False,
            "guard_static_intent": None,
            "estimated_credits": None,
            "description": None,
            "api_calls": [],
            "columns": [],
            "intent": guard_result.intent,
            "missing_criteria": list(guard_result.missing_criteria or []),
        }

    plan = await run_orchestrator(guard_result, mode=active_mode)

    if should_skip_orchestrator_clarification_qcm(
        plan_clarification_needed=plan.clarification_needed,
        guard_result=guard_result,
        recent_messages=recent_for_gates,
        mode=active_mode,
    ):
        plan = plan.model_copy(update={"clarification_needed": False, "clarification_question": None})

    if plan.clarification_needed:
        return {
            "in_scope": True,
            "clarification_needed": True,
            "clarification_source": "orchestrator",
            "orchestrator_clarification_needed": True,
            "guard_static_intent": None,
            "estimated_credits": plan.estimated_credits,
            "description": plan.description,
            "api_calls": [],
            "columns": list(plan.columns or []),
            "intent": guard_result.intent,
            "missing_criteria": list(guard_result.missing_criteria or []),
        }

    augment_google_places_regional_variant(plan, guard_result.entities)
    augment_google_places_boutique_and_club_queries(plan, user_message)
    patch_sirene_calls_from_guard_entities(plan, guard_result.entities)
    maybe_clamp_prospection_after_plan_patches(plan, active_mode, guard_result)

    return {
        "in_scope": True,
        "clarification_needed": False,
        "clarification_source": None,
        "orchestrator_clarification_needed": False,
        "guard_static_intent": None,
        "estimated_credits": plan.estimated_credits,
        "description": plan.description,
        "api_calls": [c.model_dump(mode="json") for c in plan.api_calls],
        "columns": list(plan.columns or []),
        "intent": guard_result.intent,
        "missing_criteria": [],
    }


_GUARD_LLM_FETCH = 28
_GUARD_LLM_MAX_MESSAGES = 16


def _compact_messages_for_guard_llm(messages: list[Message]) -> list[Message]:
    """Réduit les tours anciens en conservant le bloc à partir du dernier message QCM."""
    if len(messages) <= _GUARD_LLM_MAX_MESSAGES:
        return messages
    last_qcm_i: int | None = None
    for i in range(len(messages) - 1, -1, -1):
        m = messages[i]
        if m.role == "assistant" and m.message_type == "qcm":
            last_qcm_i = i
            break
    if last_qcm_i is None:
        return messages[-_GUARD_LLM_MAX_MESSAGES:]
    tail = messages[last_qcm_i:]
    if len(tail) >= _GUARD_LLM_MAX_MESSAGES:
        return tail[-_GUARD_LLM_MAX_MESSAGES:]
    need = _GUARD_LLM_MAX_MESSAGES - len(tail)
    start = max(0, last_qcm_i - need)
    prefix = messages[start:last_qcm_i]
    out = prefix + tail
    if len(out) > _GUARD_LLM_MAX_MESSAGES:
        return out[-_GUARD_LLM_MAX_MESSAGES:]
    return out


async def build_estimate_context(
    supabase: Client,
    *,
    conversation_id: str,
    pending_user_message: str,
) -> tuple[list[dict], list[Message], list[Message], bool]:
    """
    Charge l'historique Guard et les messages récents comme le chat (sans persister le message).

    La conversation doit déjà avoir été résolue et autorisée pour l'utilisateur (routeur).

    Retourne ``(history, recent_db, recent_for_gates, skip_filter_llm)``.
    """
    recent_db = await messages_recent_for_llm(supabase, conversation_id, 24)
    skip_filter_llm = any(m.message_type == "qcm" for m in recent_db)

    msgs = await messages_recent_for_llm(supabase, conversation_id, _GUARD_LLM_FETCH)
    msgs = _compact_messages_for_guard_llm(msgs)
    history: list[dict] = []
    for m in msgs:
        if m.role in ("user", "assistant"):
            history.append({"role": m.role, "content": m.content})
    history.append({"role": "user", "content": pending_user_message})

    pending = Message(
        id="estimate-pending",
        conversation_id=conversation_id,
        role="user",
        content=pending_user_message,
        message_type="text",
        metadata_json=None,
        created_at=datetime.now(timezone.utc),
    )
    recent_for_gates = list(recent_db) + [pending]
    return history, recent_db, recent_for_gates, skip_filter_llm
