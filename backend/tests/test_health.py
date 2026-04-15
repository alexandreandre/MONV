"""Smoke test sans Supabase (CI)."""

import os

import pytest

# Avant tout import applicatif : évite la vérif DB au lifespan.
os.environ["SKIP_DB_VERIFY_ON_STARTUP"] = "true"
os.environ["SUPABASE_URL"] = "https://placeholder.supabase.co"
os.environ["SUPABASE_SERVICE_KEY"] = "placeholder-service-key"


@pytest.fixture()
def client():
    from fastapi.testclient import TestClient

    from main import app

    with TestClient(app) as c:
        yield c


def test_health_ok(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    data = r.json()
    assert data.get("status") == "ok"
    assert "app" in data
