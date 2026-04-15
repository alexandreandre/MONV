"""Politique crédits : comptes listés dans UNLIMITED_CREDITS_EMAILS ne sont pas débités à l'export."""

from __future__ import annotations

from config import settings
from models.entities import User
from models.schemas import UserOut

# Solde affiché / suffisant pour les contrôles UI (export autorisé sans débit réel)
UNLIMITED_CREDITS_DISPLAY = 9_999_999


def _unlimited_email_set() -> set[str]:
    raw = (settings.UNLIMITED_CREDITS_EMAILS or "").strip()
    if not raw:
        return set()
    return {e.strip().lower() for e in raw.split(",") if e.strip()}


def user_has_unlimited_credits(user: User) -> bool:
    return user.email.strip().lower() in _unlimited_email_set()


def credits_for_api(user: User) -> int:
    if user_has_unlimited_credits(user):
        return UNLIMITED_CREDITS_DISPLAY
    return user.credits


def user_to_user_out(user: User) -> UserOut:
    return UserOut(
        id=user.id,
        email=user.email,
        name=user.name,
        credits=credits_for_api(user),
        credits_unlimited=user_has_unlimited_credits(user),
        created_at=user.created_at,
    )
