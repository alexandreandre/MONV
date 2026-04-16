"""
Connecteur Google Places (New) — Text Search.

Complément au SIRENE pour la découverte de commerces de niche :
boutiques spécialisées, restaurants thématiques, clubs sportifs, etc.

Stratégie :
  1. Recherche Google Places Text Search avec pagination (jusqu'à 60 résultats)
  2. Cross-référence SIRENE pour obtenir SIREN/SIRET/NAF officiels
  3. Fusion dans le modèle CompanyResult commun

Ref API : https://developers.google.com/maps/documentation/places/web-service/text-search
"""

from __future__ import annotations

import asyncio
import re
import unicodedata

import httpx

from config import settings
from models.schemas import CompanyResult
from utils.pipeline_log import plog

PLACES_URL = "https://places.googleapis.com/v1/places:searchText"

# SKU Text Search Pro (displayName, formattedAddress, googleMapsUri, addressComponents, …)
# + SKU Enterprise (nationalPhoneNumber, websiteUri, rating, userRatingCount)
FIELD_MASK = ",".join([
    "places.id",
    "places.displayName",
    "places.formattedAddress",
    "places.shortFormattedAddress",
    "places.nationalPhoneNumber",
    "places.internationalPhoneNumber",
    "places.websiteUri",
    "places.googleMapsUri",
    "places.addressComponents",
    "places.location",
    "places.types",
    "places.primaryType",
    "places.primaryTypeDisplayName",
    "places.rating",
    "places.userRatingCount",
    "nextPageToken",
])

_SIRENE_ENRICH_CONCURRENCY = 5
_SIRENE_MATCH_THRESHOLD = 0.45
_MAX_PAGES = 3  # 3 pages × 20 = 60 résultats max (limite Google)


def _fold(s: str) -> str:
    """Minuscules, sans accents, sans ponctuation superflue."""
    s = "".join(
        c
        for c in unicodedata.normalize("NFD", s)
        if unicodedata.category(c) != "Mn"
    )
    return re.sub(r"[^\w\s]", " ", s.lower()).strip()


def _fold_words(s: str) -> set[str]:
    noise = {"sarl", "sas", "sa", "eurl", "sasu", "sci", "eirl", "et", "de", "la", "le", "les", "du", "des", "l", "d"}
    return {w for w in _fold(s).split() if w and w not in noise}


# ---------------------------------------------------------------------------
# Parsing adresse Google → composants français
# ---------------------------------------------------------------------------

def _parse_address_components(
    formatted: str,
    components: list[dict],
) -> tuple[str | None, str | None, str | None]:
    """Renvoie (code_postal, ville, adresse_rue)."""
    code_postal = ville = street_number = route = None

    for comp in components:
        types = comp.get("types", [])
        text = comp.get("longText") or comp.get("shortText") or ""
        if "postalCode" in types:
            code_postal = text
        elif "locality" in types:
            ville = text
        elif "streetNumber" in types:
            street_number = text
        elif "route" in types:
            route = text

    adresse = None
    if street_number and route:
        adresse = f"{street_number} {route}"
    elif route:
        adresse = route

    if not code_postal and formatted:
        m = re.search(r"\b(\d{5})\b", formatted)
        if m:
            code_postal = m.group(1)

    if not ville and formatted and code_postal:
        m = re.search(rf"{re.escape(code_postal)}\s+([^,]+)", formatted)
        if m:
            ville = m.group(1).strip()

    return code_postal, ville, adresse


def _dept_from_cp(cp: str | None) -> str | None:
    if not cp or len(cp) != 5:
        return None
    if cp.startswith("97"):
        return cp[:3]
    return cp[:2]


# ---------------------------------------------------------------------------
# Parsing d'un résultat Google Places → CompanyResult
# ---------------------------------------------------------------------------

def _parse_place(place: dict) -> CompanyResult | None:
    name = (place.get("displayName") or {}).get("text", "")
    if not name:
        return None

    formatted_addr = place.get("formattedAddress", "")
    components = place.get("addressComponents", [])
    code_postal, ville, adresse = _parse_address_components(formatted_addr, components)
    departement = _dept_from_cp(code_postal)

    phone = place.get("nationalPhoneNumber") or place.get("internationalPhoneNumber")
    website = place.get("websiteUri")
    maps_url = place.get("googleMapsUri")

    # Type principal lisible (ex. "Magasin d'articles de sport")
    primary_type_label = (place.get("primaryTypeDisplayName") or {}).get("text")

    loc = place.get("location") or {}
    lat = loc.get("latitude")
    lng = loc.get("longitude")

    return CompanyResult(
        siren="",
        nom=name,
        libelle_activite=primary_type_label,
        adresse=adresse,
        code_postal=code_postal,
        ville=ville,
        departement=departement,
        telephone=phone,
        site_web=website,
        google_maps_url=maps_url,
        lien_annuaire=maps_url,
        latitude=lat,
        longitude=lng,
    )


# ---------------------------------------------------------------------------
# Cross-référence SIRENE (enrichissement SIREN/SIRET/NAF)
# ---------------------------------------------------------------------------

def _name_similarity(google_name: str, sirene_name: str) -> float:
    gw = _fold_words(google_name)
    sw = _fold_words(sirene_name)
    if not gw or not sw:
        return 0.0
    common = gw & sw
    return (len(common) / len(gw) + len(common) / len(sw)) / 2


def _find_best_sirene_match(
    google_result: CompanyResult,
    sirene_candidates: list[CompanyResult],
) -> CompanyResult | None:
    best_score = 0.0
    best = None

    for sr in sirene_candidates:
        score = _name_similarity(google_result.nom, sr.nom)

        if google_result.ville and sr.ville:
            if _fold(google_result.ville) == _fold(sr.ville):
                score += 0.2
        if google_result.code_postal and sr.code_postal:
            if google_result.code_postal == sr.code_postal:
                score += 0.1

        if score > best_score:
            best_score = score
            best = sr

    if best_score >= _SIRENE_MATCH_THRESHOLD:
        plog("google_places_sirene_match", nom=google_result.nom, sirene_nom=best.nom if best else "", score=round(best_score, 2))
        return best
    return None


async def _enrich_with_sirene(results: list[CompanyResult]) -> None:
    """Tente de trouver le SIREN/SIRET officiel pour chaque résultat Google."""
    from services.sirene import search_sirene

    sem = asyncio.Semaphore(_SIRENE_ENRICH_CONCURRENCY)

    async def _enrich_one(result: CompanyResult) -> None:
        if not result.nom:
            return
        async with sem:
            try:
                params: dict = {
                    "q": result.nom,
                    "per_page": 5,
                    "etat_administratif": "A",
                }
                if result.departement:
                    params["departement"] = result.departement

                candidates = await search_sirene(params, max_pages=1)
                if not candidates:
                    return

                best = _find_best_sirene_match(result, candidates)
                if not best:
                    return

                result.siren = best.siren
                result.siret = best.siret
                result.activite_principale = best.activite_principale
                if not result.libelle_activite:
                    result.libelle_activite = best.libelle_activite
                result.tranche_effectif = best.tranche_effectif
                result.effectif_label = best.effectif_label
                result.date_creation = best.date_creation
                result.forme_juridique = best.forme_juridique
                result.dirigeant_nom = best.dirigeant_nom
                result.dirigeant_prenom = best.dirigeant_prenom
                result.dirigeant_fonction = best.dirigeant_fonction
                if best.lien_annuaire:
                    result.lien_annuaire = best.lien_annuaire

            except Exception as e:
                plog("google_places_sirene_enrich_failed", nom=result.nom[:60], error=repr(e))

    await asyncio.gather(*[_enrich_one(r) for r in results])


# ---------------------------------------------------------------------------
# Point d'entrée principal
# ---------------------------------------------------------------------------

async def search_google_places(
    query: str,
    location: str | None = None,
    max_results: int = 60,
) -> list[CompanyResult]:
    """
    Recherche Google Places Text Search avec pagination.

    ``query``    — termes métier (ex. « boutique padel »)
    ``location`` — contexte géographique (ex. « PACA », « Marseille »)
    ``max_results`` — nombre maximum de résultats (jusqu'à 60, limite Google)
    """
    if not settings.GOOGLE_PLACES_API_KEY:
        plog("google_places_skip", reason="no_api_key")
        return []

    text_query = f"{query} {location}".strip() if location else query

    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": settings.GOOGLE_PLACES_API_KEY,
        "X-Goog-FieldMask": FIELD_MASK,
    }

    page_size = min(max_results, 20)
    body: dict = {
        "textQuery": text_query,
        "languageCode": "fr",
        "regionCode": "fr",
        "pageSize": page_size,
    }

    plog("google_places_search_start", query=text_query, max_results=max_results)

    results: list[CompanyResult] = []
    seen_names: set[str] = set()

    async with httpx.AsyncClient(timeout=20.0) as client:
        for page_num in range(1, _MAX_PAGES + 1):
            try:
                resp = await client.post(PLACES_URL, json=body, headers=headers)
                resp.raise_for_status()
                data = resp.json()
            except httpx.HTTPStatusError as e:
                plog(
                    "google_places_http_error",
                    page=page_num,
                    status=e.response.status_code,
                    body=e.response.text[:500],
                )
                break
            except Exception as e:
                plog("google_places_request_failed", page=page_num, error=repr(e))
                break

            places = data.get("places", [])
            plog("google_places_page", page=page_num, raw_count=len(places))

            if not places:
                break

            for p in places:
                result = _parse_place(p)
                if not result:
                    continue
                key = _fold(result.nom)
                if key in seen_names:
                    continue
                seen_names.add(key)
                results.append(result)

            if len(results) >= max_results:
                break

            next_token = data.get("nextPageToken")
            if not next_token:
                break

            body = {
                "textQuery": text_query,
                "languageCode": "fr",
                "regionCode": "fr",
                "pageSize": page_size,
                "pageToken": next_token,
            }
            await asyncio.sleep(0.3)

    if results:
        await _enrich_with_sirene(results)

    plog(
        "google_places_search_done",
        total=len(results),
        enriched_with_siren=sum(1 for r in results if r.siren),
    )
    return results
