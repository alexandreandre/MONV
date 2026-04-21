"""Politique de zone géographique (sans LLM)."""

from __future__ import annotations

import os

os.environ.setdefault("SKIP_DB_VERIFY_ON_STARTUP", "true")
os.environ.setdefault("SUPABASE_URL", "https://placeholder.supabase.co")
os.environ.setdefault("SUPABASE_SERVICE_KEY", "placeholder-service-key")

from models.schemas import GuardEntity  # noqa: E402
from services.zone_policy import (  # noqa: E402
    apply_natural_scope_from_user_message,
    corroborate_zone_entities,
    entity_has_resolved_geography,
    post_process_guard_geography,
)


def test_corroborate_strips_location_not_in_message():
    e = GuardEntity(localisation="Paris")
    corroborate_zone_entities("Je cherche des ESN", e)
    assert e.localisation is None


def test_corroborate_keeps_location_in_message():
    e = GuardEntity(localisation="Lyon")
    corroborate_zone_entities("ESN à Lyon pour un projet", e)
    assert e.localisation == "Lyon"


def test_natural_scope_france_sets_region():
    e = GuardEntity()
    apply_natural_scope_from_user_message("Pharmacies en France entière", e)
    assert entity_has_resolved_geography(e)
    assert "France" in (e.region or "")


def test_post_process_appends_zone_geo_for_recherche():
    e = GuardEntity(secteur="BTP", mots_cles=["BTP"])
    missing: list[str] = []
    clar = post_process_guard_geography(
        "PME du bâtiment svp",
        "recherche_entreprise",
        e,
        missing,
        False,
    )
    assert clar is True
    assert "zone_geo" in missing


def test_post_process_skips_enrichissement():
    e = GuardEntity(secteur="X")
    missing: list[str] = []
    clar = post_process_guard_geography(
        "email du dirigeant",
        "enrichissement",
        e,
        missing,
        False,
    )
    assert clar is False
    assert "zone_geo" not in missing
