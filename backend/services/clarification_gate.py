"""
Évite la double clarification (Guard puis Orchestrateur) après un QCM assistant.

Quand l'utilisateur répond juste après un message assistant de type ``qcm`` et que les
entités extraites par le Guard sont suffisantes pour lancer une recherche (secteur + zone,
secteur non ambigu ou déjà confirmé), on ne renvoie pas un second QCM côté orchestrateur.

En prospection / benchmark, on peut aussi lever un ``clarification_needed`` résiduel du Guard
dans le même cas. En sous-traitant / rachat, on ne modifie pas le Guard ici (qualification
métier via ``missing_criteria``) ; le court-circuit orchestrateur s'applique seulement si
le Guard n'a plus de critères manquants.
"""

from __future__ import annotations

from models.entities import Message
from models.schemas import GuardResult
from services.modes import normalize_mode


def user_message_follows_assistant_qcm(messages: list[Message]) -> bool:
    """
    True si le dernier message est un ``user`` dont le message assistant précédent
    immédiat est un QCM (réponse à une clarification).
    """
    if len(messages) < 2:
        return False
    last = messages[-1]
    if last.role != "user":
        return False
    for m in reversed(messages[:-1]):
        if m.role == "assistant":
            return m.message_type == "qcm"
        if m.role == "user":
            return False
    return False


def guard_entities_complete_for_search(guard: GuardResult) -> bool:
    """
    Secteur (ou NAF / mots-clés) + zone résolue, et pas d'ambiguïté sectorielle non levée.
    """
    e = guard.entities
    has_secteur = bool(e.secteur or e.code_naf or e.mots_cles)
    has_zone = bool(e.localisation or e.departement or e.region)
    if not (has_secteur and has_zone):
        return False
    if getattr(guard, "sector_ambiguous", False):
        confirmed = (guard.sector_confirmed or "").strip()
        if not confirmed:
            return False
    return True


def should_skip_orchestrator_clarification_qcm(
    *,
    plan_clarification_needed: bool,
    guard_result: GuardResult,
    recent_messages: list[Message],
    mode: str,
) -> bool:
    """Court-circuite le QCM orchestrateur après réponse à un QCM si le contexte est stable."""
    if not plan_clarification_needed:
        return False
    if not user_message_follows_assistant_qcm(recent_messages):
        return False
    if normalize_mode(mode) in ("prospection", "benchmark"):
        return guard_entities_complete_for_search(guard_result)
    if guard_result.missing_criteria:
        return False
    return guard_entities_complete_for_search(guard_result)


def should_suppress_orchestrator_clarification_after_guard_flow(
    *,
    plan_clarification_needed: bool,
    guard_result: GuardResult,
    recent_messages: list[Message],
    mode: str,
) -> bool:
    """
    Après réponse à un QCM assistant, si le Guard ne demande plus de clarification
    mais que l'orchestrateur en réclame une (souvent résidu « trop large »), on évite
    un second QCM lorsque les entités sont déjà complètes pour lancer une recherche.
    """
    if not plan_clarification_needed:
        return False
    if normalize_mode(mode) not in ("prospection", "benchmark"):
        return False
    if not user_message_follows_assistant_qcm(recent_messages):
        return False
    if guard_result.clarification_needed:
        return False
    return guard_entities_complete_for_search(guard_result)


def should_unlock_guard_after_qcm(
    guard_result: GuardResult,
    recent_messages: list[Message],
    *,
    mode: str,
) -> bool:
    """
    Lève clarification_needed / missing_criteria du Guard après réponse QCM + entités OK.

    Uniquement prospection / benchmark (pas les modes à QCM de qualification imposée).
    """
    if mode not in ("prospection", "benchmark"):
        return False
    if not user_message_follows_assistant_qcm(recent_messages):
        return False
    return guard_entities_complete_for_search(guard_result)
