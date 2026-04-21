"""Liens Google Maps de secours (sans Places) — géocodage."""

from __future__ import annotations

import os

os.environ.setdefault("SKIP_DB_VERIFY_ON_STARTUP", "true")
os.environ.setdefault("SUPABASE_URL", "https://placeholder.supabase.co")
os.environ.setdefault("SUPABASE_SERVICE_KEY", "placeholder-service-key")

from models.schemas import CompanyResult  # noqa: E402
from services.geocoding import fill_fallback_google_maps_urls  # noqa: E402


def test_fill_maps_from_coordinates():
    r = CompanyResult(
        siren="123456789",
        nom="Test",
        latitude=43.3,
        longitude=5.37,
    )
    fill_fallback_google_maps_urls([r])
    assert r.google_maps_url
    assert "43.3" in r.google_maps_url or "43.3%2C5.37" in r.google_maps_url.replace(",", ".")


def test_fill_maps_from_address_when_no_coords():
    r = CompanyResult(
        siren="123456789",
        nom="Boulangerie",
        adresse="10 rue de la Paix",
        code_postal="75002",
        ville="Paris",
    )
    fill_fallback_google_maps_urls([r])
    assert r.google_maps_url
    assert "google.com/maps" in r.google_maps_url
    assert "Paris" in r.google_maps_url or "75002" in r.google_maps_url


def test_preserves_existing_places_uri():
    url = "https://maps.google.com/?cid=123"
    r = CompanyResult(siren="123456789", nom="X", google_maps_url=url)
    fill_fallback_google_maps_urls([r])
    assert r.google_maps_url == url
