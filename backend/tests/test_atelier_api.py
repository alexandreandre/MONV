"""Routes HTTP Atelier (itération dossier) — sans Supabase ni LLM réels."""

from __future__ import annotations

import os
from datetime import datetime, timezone

import pytest

os.environ.setdefault("SKIP_DB_VERIFY_ON_STARTUP", "true")
os.environ.setdefault("SUPABASE_URL", "https://placeholder.supabase.co")
os.environ.setdefault("SUPABASE_SERVICE_KEY", "placeholder-service-key")


@pytest.fixture()
def client():
    """Évite `create_client` Supabase (clé placeholder rejetée) lors des 401."""
    from fastapi.testclient import TestClient

    from main import app
    from models.db import get_supabase

    async def stub_supabase():
        return object()

    prev_sb = app.dependency_overrides.get(get_supabase)
    app.dependency_overrides[get_supabase] = stub_supabase
    try:
        with TestClient(app) as c:
            yield c
    finally:
        if prev_sb is not None:
            app.dependency_overrides[get_supabase] = prev_sb
        else:
            app.dependency_overrides.pop(get_supabase, None)


@pytest.fixture(autouse=True)
def clear_dependency_overrides():
    from main import app

    yield
    app.dependency_overrides.clear()


def test_atelier_routes_require_auth(client):
    assert client.get("/api/agent/dossier/any-id").status_code == 401
    assert (
        client.post(
            "/api/agent/segments/foo/regenerate",
            json={"conversation_id": "c"},
        ).status_code
        == 401
    )
    assert (
        client.post(
            "/api/agent/canvas/regenerate",
            json={"conversation_id": "c"},
        ).status_code
        == 401
    )
    assert (
        client.post(
            "/api/agent/brief/update",
            json={
                "conversation_id": "c",
                "brief": {
                    "nom": "X",
                    "tagline": "",
                    "secteur": "",
                    "localisation": "",
                    "cible": "B2B",
                    "budget": "",
                    "modele_revenus": "",
                    "ambition": "",
                },
                "impacts": ["canvas"],
            },
        ).status_code
        == 401
    )


def _sample_dossier_metadata() -> str:
    from tests.test_agent import _VALID_RAW_DOSSIER

    from models.schemas import BusinessDossier, SegmentResult
    from services.agent import ATELIER_MODE_LABEL, coerce_dossier, dossier_metadata_json

    brief, canvas, flows, segs_brief, synthesis = coerce_dossier(_VALID_RAW_DOSSIER)
    segments = [
        SegmentResult(
            key=s.key,
            label=s.label,
            description=s.description,
            mode=s.mode,
            icon=s.icon,
            query=s.query,
            search_id=None,
            total=2,
            credits_required=1,
            columns=[],
            preview=[],
            map_points=[],
        )
        for s in segs_brief
    ]
    dossier = BusinessDossier(
        brief=brief,
        canvas=canvas,
        flows=flows,
        segments=segments,
        synthesis=synthesis,
    )
    raw = dossier_metadata_json(dossier)
    import json as _json

    p = _json.loads(raw)
    assert p.get("mode") == ATELIER_MODE_LABEL
    return raw


def test_get_atelier_dossier_404_wrong_mode(client, monkeypatch):
    from main import app
    from models.db import get_supabase
    from models.entities import Conversation, User
    from routers import agent as agent_router
    from routers.auth import get_current_user

    async def fake_user():
        return User(
            id="u1",
            email="t@t.co",
            name="T",
            hashed_password="x",
            credits=10,
            created_at=datetime.now(timezone.utc),
        )

    async def fake_sb():
        return object()

    async def conv_prospection(_sb, _cid, _uid):
        return Conversation(
            id="conv-1",
            user_id="u1",
            title="X",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
            mode="prospection",
        )

    app.dependency_overrides[get_current_user] = fake_user
    app.dependency_overrides[get_supabase] = fake_sb
    monkeypatch.setattr(agent_router, "conversation_get", conv_prospection)

    r = client.get(
        "/api/agent/dossier/conv-1",
        headers={"Authorization": "Bearer dummy"},
    )
    assert r.status_code == 404


def test_get_atelier_dossier_200(client, monkeypatch):
    from main import app
    from models.db import get_supabase
    from models.entities import Conversation, Message, User
    from routers import agent as agent_router
    from routers.auth import get_current_user

    meta = _sample_dossier_metadata()

    async def fake_user():
        return User(
            id="u1",
            email="t@t.co",
            name="T",
            hashed_password="x",
            credits=10,
            created_at=datetime.now(timezone.utc),
        )

    async def fake_sb():
        return object()

    async def conv_atelier(_sb, cid, uid):
        if cid == "conv-1" and uid == "u1":
            return Conversation(
                id=cid,
                user_id=uid,
                title="Atelier",
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
                mode="atelier",
            )
        return None

    async def msgs(_sb, cid):
        return [
            Message(
                id="m1",
                conversation_id=cid,
                role="assistant",
                content="Voici ton dossier.",
                message_type="business_dossier",
                metadata_json=meta,
                created_at=datetime.now(timezone.utc),
            )
        ]

    app.dependency_overrides[get_current_user] = fake_user
    app.dependency_overrides[get_supabase] = fake_sb
    monkeypatch.setattr(agent_router, "conversation_get", conv_atelier)
    monkeypatch.setattr(agent_router, "messages_list_asc", msgs)

    r = client.get(
        "/api/agent/dossier/conv-1",
        headers={"Authorization": "Bearer dummy"},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["message_id"] == "m1"
    assert data["dossier"]["brief"]["nom"] == "Sushi Lyon"


def test_get_atelier_dossier_404_no_dossier_message(client, monkeypatch):
    from main import app
    from models.db import get_supabase
    from models.entities import Conversation, Message, User
    from routers import agent as agent_router
    from routers.auth import get_current_user

    async def fake_user():
        return User(
            id="u1",
            email="t@t.co",
            name="T",
            hashed_password="x",
            credits=10,
            created_at=datetime.now(timezone.utc),
        )

    async def fake_sb():
        return object()

    async def conv_atelier(_sb, cid, uid):
        return Conversation(
            id=cid,
            user_id=uid,
            title="A",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
            mode="atelier",
        )

    async def msgs_text_only(_sb, _cid):
        return [
            Message(
                id="m0",
                conversation_id="conv-1",
                role="user",
                content="pitch",
                message_type="text",
                metadata_json=None,
                created_at=datetime.now(timezone.utc),
            )
        ]

    app.dependency_overrides[get_current_user] = fake_user
    app.dependency_overrides[get_supabase] = fake_sb
    monkeypatch.setattr(agent_router, "conversation_get", conv_atelier)
    monkeypatch.setattr(agent_router, "messages_list_asc", msgs_text_only)

    r = client.get(
        "/api/agent/dossier/conv-1",
        headers={"Authorization": "Bearer dummy"},
    )
    assert r.status_code == 404
