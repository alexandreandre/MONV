from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from pathlib import Path
from supabase import Client
import json

from config import settings
from models.db import (
    get_supabase,
    search_history_get,
    search_history_list,
    search_history_update,
    user_update_credits,
)
from models.entities import User
from models.schemas import SearchResults, CompanyResult, ExportRequest, ExportResponse
from services.export import generate_excel, generate_csv
from routers.auth import get_current_user
from utils.credits_policy import user_has_unlimited_credits

router = APIRouter(prefix="/api/search", tags=["search"])


@router.get("/history")
async def search_history(
    user: User = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    searches = await search_history_list(supabase, user.id)

    return [
        {
            "id": s.id,
            "query": s.query_text,
            "intent": s.intent,
            "results_count": s.results_count,
            "credits_used": s.credits_used,
            "exported": s.exported,
            "created_at": s.created_at.isoformat(),
        }
        for s in searches
    ]


@router.post("/export", response_model=ExportResponse)
async def export_results(
    req: ExportRequest,
    user: User = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    search = await search_history_get(supabase, req.search_id, user.id)
    if not search:
        raise HTTPException(404, "Recherche non trouvée")

    if not search.results_json:
        raise HTTPException(400, "Pas de résultats à exporter")

    raw_results = json.loads(search.results_json)
    companies = [CompanyResult(**r) for r in raw_results]

    entities = json.loads(search.entities_json) if search.entities_json else {}
    columns = _infer_columns(search.intent, entities, companies)

    search_results = SearchResults(
        total=len(companies),
        results=companies,
        columns=columns,
        credits_required=search.credits_used,
    )

    credits_needed = search.credits_used
    was_exported = search.exported

    if not search.exported:
        if not user_has_unlimited_credits(user):
            if user.credits < credits_needed:
                raise HTTPException(
                    402,
                    f"Crédits insuffisants. Il te faut {credits_needed} crédits, tu en as {user.credits}.",
                )
            new_credits = user.credits - credits_needed
            await user_update_credits(supabase, user.id, new_credits)
            user.credits = new_credits
        await search_history_update(supabase, search.id, {"exported": True})

    if req.format == "csv":
        filepath = generate_csv(search_results)
    else:
        filepath = generate_excel(
            search_results,
            query_text=search.query_text or "",
            intent=search.intent or "recherche_entreprise",
            entities=entities,
            credits_used=search.credits_used,
        )

    await search_history_update(
        supabase,
        search.id,
        {"export_path": filepath},
    )

    filename = filepath.split("/")[-1]
    debited = not was_exported and not user_has_unlimited_credits(user)
    return ExportResponse(
        download_url=f"/api/search/download/{filename}",
        filename=filename,
        credits_used=credits_needed if debited else 0,
    )


@router.get("/download/{filename}")
async def download_file(filename: str):
    filepath = Path(settings.EXPORTS_DIR) / filename
    if not filepath.exists():
        raise HTTPException(404, "Fichier non trouvé")
    return FileResponse(
        str(filepath),
        media_type="application/octet-stream",
        filename=filename,
    )


def _infer_columns(
    intent: str,
    entities: dict,
    results: list[CompanyResult] | None = None,
) -> list[str]:
    base = [
        "nom",
        "siren",
        "siret",
        "categorie_entreprise",
        "activite_principale",
        "libelle_activite",
        "adresse",
        "code_postal",
        "ville",
        "departement",
        "region",
        "forme_juridique",
        "tranche_effectif",
        "effectif_label",
        "date_creation",
    ]
    if intent == "recherche_dirigeant":
        base.extend(["dirigeant_nom", "dirigeant_prenom", "dirigeant_fonction"])
    want_finance = bool(entities.get("ca_min") or entities.get("ca_max"))
    if results and not want_finance:
        want_finance = any(
            getattr(r, "chiffre_affaires", None) is not None
            or getattr(r, "resultat_net", None) is not None
            or getattr(r, "annee_dernier_ca", None) is not None
            for r in results
        )
    if want_finance:
        base.extend([
            "annee_dernier_ca",
            "date_cloture_exercice",
            "chiffre_affaires",
            "resultat_net",
            "marge_brute",
            "ebe",
            "capitaux_propres",
            "effectif_financier",
            "capital_social",
        ])
    if results and any(r.telephone for r in results):
        base.append("telephone")
    if results and any(r.site_web for r in results):
        base.append("site_web")
    if results and any(r.email for r in results):
        base.append("email")
    if results and any(r.signaux for r in results):
        base.append("signaux")
    base.append("lien_annuaire")
    if results and any(r.google_maps_url for r in results):
        base.append("google_maps_url")
    return base
