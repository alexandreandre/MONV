"""Accès données via Supabase PostgREST (clé service_role — pas de DATABASE_URL)."""

from __future__ import annotations

import asyncio
import sys
import threading
from collections.abc import Callable
from datetime import datetime, timezone
from typing import TypeVar
from urllib.parse import urlparse

import httpx
from supabase import Client, create_client

from config import settings
from gotrue.types import AuthResponse
from models.entities import Conversation, Message, ProjectFolder, SearchHistory, User

T = TypeVar("T")

_client: Client | None = None

# Le client Supabase utilise httpx synchrone + HTTP/2.
# HTTP/2 multiplexe sur une seule connexion TCP : deux threads
# qui lisent en même temps provoquent « Resource temporarily unavailable ».
# Ce verrou sérialise tous les appels PostgREST.
_sb_lock = threading.Lock()

# Si la migration `002_modes.sql` n’a pas été appliquée sur le projet Supabase,
# PostgREST renvoie PGRST204 sur insert avec `mode`. On retente sans cette clé.
_mode_column_warned = False


def _missing_mode_column_error(exc: BaseException) -> bool:
    text = str(exc).lower()
    if "mode" not in text:
        return False
    if "pgrst204" in text:
        return True
    if "schema cache" in text and "column" in text:
        return True
    if "could not find" in text and "mode" in text:
        return True
    return False


def _warn_mode_column_once() -> None:
    global _mode_column_warned
    if _mode_column_warned:
        return
    _mode_column_warned = True
    print(
        "[MONV] La colonne SQL `mode` est absente (migration non appliquée). "
        "Les conversations / recherches sont enregistrées sans mode persistant. "
        "Exécutez `backend/supabase/migrations/002_modes.sql` dans le SQL Editor Supabase, "
        "puis rechargez le schéma PostgREST si besoin.",
        file=sys.stderr,
        flush=True,
    )


def _supabase_url_host_problem(url: str) -> str | None:
    """Retourne un message si l’URL Supabase est manifestement invalide (évite erreurs DNS obscures)."""
    parsed = urlparse(url)
    host = (parsed.hostname or "").strip().lower()
    if parsed.scheme != "https":
        return "SUPABASE_URL doit utiliser le schéma https:// (Project URL dans Supabase → Settings → API)."
    if not host:
        return "SUPABASE_URL est incomplet : il manque le nom d’hôte (ex. https://<ref>.supabase.co)."
    if host == "xxxx.supabase.co" or host == "placeholder.supabase.co":
        return (
            "SUPABASE_URL contient encore l’exemple du fichier .env.example : remplacez par la Project URL "
            "réelle de votre projet (https://<project-ref>.supabase.co)."
        )
    return None


def get_supabase() -> Client:
    global _client
    url = (settings.SUPABASE_URL or "").strip().strip('"').strip("'")
    key = (settings.SUPABASE_SERVICE_KEY or "").strip().strip('"').strip("'")
    if not url or not key:
        raise RuntimeError(
            "SUPABASE_URL et SUPABASE_SERVICE_KEY sont requis dans .env "
            "(Supabase → Settings → API)."
        )
    host_hint = _supabase_url_host_problem(url)
    if host_hint:
        raise RuntimeError(host_hint)
    if _client is None:
        _client = create_client(url, key)
    return _client


async def sb_run(fn: Callable[[], T]) -> T:
    def _locked() -> T:
        with _sb_lock:
            return fn()
    return await asyncio.to_thread(_locked)


def _unwrap_connect_error(exc: BaseException) -> BaseException | None:
    cur: BaseException | None = exc
    seen: set[int] = set()
    while cur is not None and id(cur) not in seen:
        seen.add(id(cur))
        if isinstance(cur, httpx.ConnectError):
            return cur
        cur = cur.__cause__
    return None


async def verify_connection(client: Client) -> None:
    try:
        await sb_run(lambda: client.table("users").select("id").limit(1).execute())
    except Exception as e:
        if _unwrap_connect_error(e) is not None:
            raise RuntimeError(
                "Impossible de joindre l’API Supabase (réseau ou DNS). Vérifiez SUPABASE_URL dans "
                "backend/.env : URL https complète du type https://<project-ref>.supabase.co, "
                "connexion Internet, et absence de proxy bloquant. Si les tables manquent, exécutez "
                f"ensuite `supabase/migrations/001_schema.sql` dans le SQL Editor. Détail : {e}"
            ) from e
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
    row = conv.to_insert_row()

    def _insert(payload: dict):
        return client.table("conversations").insert(payload).execute()

    try:
        await sb_run(lambda: _insert(row))
    except Exception as e:
        if "mode" in row and _missing_mode_column_error(e):
            _warn_mode_column_once()
            without = {k: v for k, v in row.items() if k != "mode"}
            await sb_run(lambda: _insert(without))
            return
        raise


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


async def conversation_update_folder(
    client: Client, conversation_id: str, user_id: str, folder_id: str | None
) -> bool:
    """Met à jour `folder_id` si la conversation appartient à l'utilisateur."""
    now = _iso_now()

    def q():
        r = (
            client.table("conversations")
            .update({"folder_id": folder_id, "updated_at": now})
            .eq("id", conversation_id)
            .eq("user_id", user_id)
            .execute()
        )
        return r.data or []

    rows = await sb_run(q)
    return bool(rows)


async def project_folders_list_for_user(client: Client, user_id: str) -> list[ProjectFolder]:
    def q():
        r = (
            client.table("project_folders")
            .select("*")
            .eq("user_id", user_id)
            .order("sort_position", desc=False)
            .execute()
        )
        return r.data or []

    rows = await sb_run(q)
    folders = [ProjectFolder.from_row(x) for x in rows]
    folders.sort(key=lambda f: (f.sort_position, -f.updated_at.timestamp()))
    return folders


async def project_folder_get(
    client: Client, folder_id: str, user_id: str
) -> ProjectFolder | None:
    def q():
        r = (
            client.table("project_folders")
            .select("*")
            .eq("id", folder_id)
            .eq("user_id", user_id)
            .limit(1)
            .execute()
        )
        return r.data or []

    rows = await sb_run(q)
    return ProjectFolder.from_row(rows[0]) if rows else None


async def project_folder_insert(client: Client, folder: ProjectFolder) -> ProjectFolder:
    def q():
        r = client.table("project_folders").insert(folder.to_insert_row()).execute()
        return r.data or []

    rows = await sb_run(q)
    return ProjectFolder.from_row(rows[0])


async def project_folder_update(client: Client, folder_id: str, user_id: str, patch: dict) -> bool:
    if not patch:
        return True
    patch = {**patch, "updated_at": _iso_now()}

    def q():
        r = (
            client.table("project_folders")
            .update(patch)
            .eq("id", folder_id)
            .eq("user_id", user_id)
            .execute()
        )
        return r.data or []

    rows = await sb_run(q)
    return bool(rows)


async def project_folder_delete(client: Client, folder_id: str, user_id: str) -> bool:
    def q():
        r = (
            client.table("project_folders")
            .delete()
            .eq("id", folder_id)
            .eq("user_id", user_id)
            .execute()
        )
        return r.data or []

    rows = await sb_run(q)
    return bool(rows)


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


async def message_update(
    client: Client, message_id: str, patch: dict, conversation_id: str | None = None
) -> None:
    await sb_run(lambda: client.table("messages").update(patch).eq("id", message_id).execute())
    if conversation_id:
        await conversation_touch(client, conversation_id)


async def search_history_insert(client: Client, record: SearchHistory) -> SearchHistory:
    row = record.to_insert_row()

    def _insert(payload: dict):
        r = client.table("search_history").insert(payload).execute()
        return r.data or []

    try:
        rows = await sb_run(lambda: _insert(row))
    except Exception as e:
        if "mode" in row and _missing_mode_column_error(e):
            _warn_mode_column_once()
            without = {k: v for k, v in row.items() if k != "mode"}
            rows = await sb_run(lambda: _insert(without))
        else:
            raise

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


# ── Admin : versions d'agents, runs, étapes ─────────────────────────────────


async def agent_version_active_get(client: Client, agent_id: str) -> dict | None:
    def q():
        r = (
            client.table("agent_versions")
            .select("*")
            .eq("agent_id", agent_id)
            .eq("is_active", True)
            .limit(1)
            .execute()
        )
        return r.data or []

    rows = await sb_run(q)
    return rows[0] if rows else None


async def agent_version_get(client: Client, version_id: str) -> dict | None:
    def q():
        r = client.table("agent_versions").select("*").eq("id", version_id).limit(1).execute()
        return r.data or []

    rows = await sb_run(q)
    return rows[0] if rows else None


async def agent_versions_list(client: Client, agent_id: str, limit: int = 100) -> list[dict]:
    def q():
        r = (
            client.table("agent_versions")
            .select("*")
            .eq("agent_id", agent_id)
            .order("version_number", desc=True)
            .limit(limit)
            .execute()
        )
        return r.data or []

    return await sb_run(q)


async def agent_version_next_number(client: Client, agent_id: str) -> int:
    def q():
        r = (
            client.table("agent_versions")
            .select("version_number")
            .eq("agent_id", agent_id)
            .order("version_number", desc=True)
            .limit(1)
            .execute()
        )
        return r.data or []

    rows = await sb_run(q)
    if not rows:
        return 1
    return int(rows[0]["version_number"]) + 1


async def agent_version_deactivate_all(client: Client, agent_id: str) -> None:
    await sb_run(
        lambda: client.table("agent_versions")
        .update({"is_active": False})
        .eq("agent_id", agent_id)
        .execute()
    )


async def agent_version_insert(client: Client, row: dict) -> dict:
    def ins():
        r = client.table("agent_versions").insert(row).execute()
        return r.data or []

    rows = await sb_run(ins)
    return rows[0]


async def agent_version_update(client: Client, version_id: str, patch: dict) -> None:
    await sb_run(lambda: client.table("agent_versions").update(patch).eq("id", version_id).execute())


async def agent_run_insert(client: Client, row: dict) -> dict:
    def ins():
        r = client.table("agent_runs").insert(row).execute()
        return r.data or []

    rows = await sb_run(ins)
    return rows[0]


async def agent_run_update(client: Client, run_id: str, patch: dict) -> None:
    await sb_run(lambda: client.table("agent_runs").update(patch).eq("id", run_id).execute())


async def agent_run_get(client: Client, run_id: str) -> dict | None:
    def q():
        r = client.table("agent_runs").select("*").eq("id", run_id).limit(1).execute()
        return r.data or []

    rows = await sb_run(q)
    return rows[0] if rows else None


async def agent_runs_list(
    client: Client,
    *,
    agent_id: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[dict]:
    def q():
        qb = client.table("agent_runs").select("*").order("started_at", desc=True).range(offset, offset + limit - 1)
        if agent_id:
            qb = qb.eq("agent_id", agent_id)
        r = qb.execute()
        return r.data or []

    return await sb_run(q)


async def agent_run_steps_list(client: Client, run_id: str) -> list[dict]:
    def q():
        r = (
            client.table("agent_run_steps")
            .select("*")
            .eq("run_id", run_id)
            .order("started_at", desc=False)
            .execute()
        )
        return r.data or []

    return await sb_run(q)


async def agent_run_step_insert(client: Client, row: dict) -> dict:
    def ins():
        r = client.table("agent_run_steps").insert(row).execute()
        return r.data or []

    rows = await sb_run(ins)
    return rows[0]


async def agent_runs_count_errors_since(
    client: Client, agent_id: str, since_iso: str
) -> int:
    """Compte les runs en erreur (approximatif, max 2000 lignes scannées)."""

    def q():
        r = (
            client.table("agent_runs")
            .select("id")
            .eq("agent_id", agent_id)
            .eq("status", "failed")
            .gte("started_at", since_iso)
            .limit(2000)
            .execute()
        )
        return len(r.data or [])

    try:
        return await sb_run(q)
    except Exception:
        return 0


async def agent_runs_count_since(client: Client, agent_id: str, since_iso: str) -> int:
    def q():
        r = (
            client.table("agent_runs")
            .select("id")
            .eq("agent_id", agent_id)
            .gte("started_at", since_iso)
            .limit(5000)
            .execute()
        )
        return len(r.data or [])

    try:
        return await sb_run(q)
    except Exception:
        return 0
