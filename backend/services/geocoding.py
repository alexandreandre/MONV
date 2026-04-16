"""
Géocodage batch via api-adresse.data.gouv.fr (gratuit, sans clé API).
Enrichit les CompanyResult qui n'ont pas encore de latitude/longitude.
"""

import asyncio
import httpx
from models.schemas import CompanyResult
from utils.pipeline_log import plog

_GEOCODE_URL = "https://api-adresse.data.gouv.fr/search/"
_CONCURRENCY = 10
_TIMEOUT = 5.0


def _build_query(r: CompanyResult) -> str | None:
    parts = [p for p in (r.adresse, r.code_postal, r.ville) if p]
    return " ".join(parts) if parts else None


async def _geocode_one(
    client: httpx.AsyncClient,
    result: CompanyResult,
    sem: asyncio.Semaphore,
) -> None:
    q = _build_query(result)
    if not q:
        return
    try:
        async with sem:
            resp = await client.get(
                _GEOCODE_URL,
                params={"q": q, "limit": 1},
                timeout=_TIMEOUT,
            )
        if resp.status_code != 200:
            return
        features = resp.json().get("features", [])
        if not features:
            return
        props = features[0].get("properties", {})
        coords = features[0].get("geometry", {}).get("coordinates", [])
        if len(coords) >= 2 and props.get("score", 0) > 0.4:
            result.longitude = coords[0]
            result.latitude = coords[1]
    except Exception:
        pass


async def geocode_results(results: list[CompanyResult]) -> None:
    """Géocode en batch les résultats sans coordonnées."""
    to_geocode = [r for r in results if r.latitude is None or r.longitude is None]
    if not to_geocode:
        return
    plog("geocoding_start", count=len(to_geocode))
    sem = asyncio.Semaphore(_CONCURRENCY)
    async with httpx.AsyncClient() as client:
        await asyncio.gather(*[_geocode_one(client, r, sem) for r in to_geocode])
    geocoded = sum(1 for r in to_geocode if r.latitude is not None)
    plog("geocoding_done", geocoded=geocoded, total=len(to_geocode))
