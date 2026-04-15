"""Accès données via Supabase PostgREST (clé service_role — pas de DATABASE_URL)."""

from __future__ import annotations

import asyncio
import threading
from collections.abc import Callable
from datetime import datetime, timezone
from typing import TypeVar

from supabase import Client, create_client

from config import settings
from gotrue.types import AuthResponse
from models.entities import Conversation, Message, SearchHistory, User

T = TypeVar("T")

_client: Client | None = None

# Le client Supabase utilise httpx synchrone + HTTP/2.
# HTTP/2 multiplexe sur une seule connexion TCP : deux threads
# qui lisent en même temps provoquent « Resource temporarily unavailable ».
# Ce verrou sérialise tous les appels PostgREST.
_sb_lock = threading.Lock()


def get_supabase() -> Client:
    global _client
    url = (settings.SUPABASE_URL or "").strip().strip('"').strip("'")
    key = (settings.SUPABASE_SERVICE_KEY or "").strip().strip('"').strip("'")
    if not url or not key:
        raise RuntimeError(
            "SUPABASE_URL et SUPABASE_SERVICE_KEY sont requis dans .env "
            "(Supabase → Settings → API)."
        )
    if _client is None:
        _client = create_client(url, key)
    return _client


async def sb_run(fn: Callable[[], T]) -> T:
    def _locked() -> T:
        with _sb_lock:
            return fn()
    return await asyncio.to_thread(_locked)


async def verify_connection(client: Client) -> None:
    try:
        await sb_run(lambda: client.table("users").select("id").limit(1).execute())
    except Exception as e:
        raise RuntimeError(
            "Impossible d’atteindre la base via Supabase, ou les tables ne sont pas créées. "
            "Exécute le script SQL `supabase/migrations/001_schema.sql` dans le SQL Editor "
            f"Supabase. Détail : {e}"
        ) from e


async def user_by_id(client: Client, user_id: str) -> User | None:
    def q():
        r = client.table("users").select("*").eq("id", user_id).limit(1).execute()
        return r.data or []

    rows = await sb_run(q)
    return User.from_row(rows[0]) if rows else None


async def user_by_email(client: Client, email: str) -> User | None:
    def q():
        r = client.table("users").select("*").eq("email", email).limit(1).execute()
        return r.data or []

    rows = await sb_run(q)
    return User.from_row(rows[0]) if rows else None


async def user_insert(client: Client, user: User) -> User:
    def q():
        r = client.table("users").insert(user.to_insert_row()).execute()
        return r.data or []

    rows = await sb_run(q)
    return User.from_row(rows[0])


async def user_update_credits(client: Client, user_id: str, credits: int) -> None:
    await sb_run(
        lambda: client.table("users").update({"credits": credits}).eq("id", user_id).execute()
    )


async def user_update_hashed_password(client: Client, user_id: str, hashed_password: str) -> None:
    await sb_run(
        lambda: client.table("users")
        .update({"hashed_password": hashed_password})
        .eq("id", user_id)
        .execute()
    )


async def try_supabase_auth_sign_in(email: str, password: str) -> AuthResponse | None:
    """
    Connexion GoTrue (utilisateurs créés dans Authentication).
    Client jetable pour éviter de mélanger les sessions en mémoire.
    """
    url = (settings.SUPABASE_URL or "").strip().strip('"').strip("'")
    key = (settings.SUPABASE_KEY or "").strip().strip('"').strip("'")
    if not url or not key:
        return None

    def _sign_in():
        ac = create_client(url, key)
        return ac.auth.sign_in_with_password({"email": email, "password": password})

    try:
        return await sb_run(_sign_in)
    except Exception:
        return None


async def conversation_get(client: Client, conv_id: str, user_id: str) -> Conversation | None:
    def q():
        r = (
            client.table("conversations")
            .select("*")
            .eq("id", conv_id)
            .eq("user_id", user_id)
            .limit(1)
            .execute()
        )
        return r.data or []

    rows = await sb_run(q)
    return Conversation.from_row(rows[0]) if rows else None


async def conversation_insert(client: Client, conv: Conversation) -> None:
    await sb_run(lambda: client.table("conversations").insert(conv.to_insert_row()).execute())


async def conversation_touch(client: Client, conv_id: str) -> None:
    now = _iso_now()
    await sb_run(
        lambda: client.table("conversations").update({"updated_at": now}).eq("id", conv_id).execute()
    )


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


async def conversations_list_for_user(client: Client, user_id: str) -> list[Conversation]:
    def q():
        r = (
            client.table("conversations")
            .select("*")
            .eq("user_id", user_id)
            .order("updated_at", desc=True)
            .execute()
        )
        return r.data or []

    rows = await sb_run(q)
    return [Conversation.from_row(x) for x in rows]


async def messages_list_asc(client: Client, conv_id: str) -> list[Message]:
    def q():
        r = (
            client.table("messages")
            .select("*")
            .eq("conversation_id", conv_id)
            .order("created_at", desc=False)
            .execute()
        )
        return r.data or []

    rows = await sb_run(q)
    return [Message.from_row(x) for x in rows]


async def messages_recent_for_llm(client: Client, conv_id: str, limit: int = 10) -> list[Message]:
    def q():
        r = (
            client.table("messages")
            .select("*")
            .eq("conversation_id", conv_id)
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
        )
        return r.data or []

    rows = await sb_run(q)
    return list(reversed([Message.from_row(x) for x in rows]))


async def message_insert(client: Client, msg: Message) -> None:
    await sb_run(lambda: client.table("messages").insert(msg.to_insert_row()).execute())
    await conversation_touch(client, msg.conversation_id)


async def search_history_insert(client: Client, record: SearchHistory) -> SearchHistory:
    def q():
        r = client.table("search_history").insert(record.to_insert_row()).execute()
        return r.data or []

    rows = await sb_run(q)
    return SearchHistory.from_row(rows[0])


async def search_history_list(client: Client, user_id: str, limit: int = 50) -> list[SearchHistory]:
    def q():
        r = (
            client.table("search_history")
            .select("*")
            .eq("user_id", user_id)
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
        )
        return r.data or []

    rows = await sb_run(q)
    return [SearchHistory.from_row(x) for x in rows]


async def search_history_get(
    client: Client, search_id: str, user_id: str
) -> SearchHistory | None:
    def q():
        r = (
            client.table("search_history")
            .select("*")
            .eq("id", search_id)
            .eq("user_id", user_id)
            .limit(1)
            .execute()
        )
        return r.data or []

    rows = await sb_run(q)
    return SearchHistory.from_row(rows[0]) if rows else None


async def search_history_update(client: Client, search_id: str, patch: dict) -> None:
    await sb_run(lambda: client.table("search_history").update(patch).eq("id", search_id).execute())


async def cache_get_row(client: Client, key: str) -> dict | None:
    def q():
        r = client.table("cache").select("*").eq("key", key).limit(1).execute()
        return r.data or []

    rows = await sb_run(q)
    return rows[0] if rows else None


async def cache_delete(client: Client, key: str) -> None:
    await sb_run(lambda: client.table("cache").delete().eq("key", key).execute())


async def cache_update(client: Client, key: str, patch: dict) -> None:
    await sb_run(lambda: client.table("cache").update(patch).eq("key", key).execute())


async def cache_insert(client: Client, row: dict) -> None:
    await sb_run(lambda: client.table("cache").insert(row).execute())
