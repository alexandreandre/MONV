"""Accès admin : liste d'emails autorisés (même pattern que UNLIMITED_CREDITS_EMAILS)."""

from __future__ import annotations

from config import settings
from models.entities import User


def _admin_email_set() -> set[str]:
    raw = (settings.ADMIN_EMAILS or "").strip()
    if not raw:
        return set()
    return {e.strip().lower() for e in raw.split(",") if e.strip()}


def user_is_admin(user: User) -> bool:
    return user.email.strip().lower() in _admin_email_set()
