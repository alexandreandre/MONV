"""
Service Marchés Publics — DECP (Données Essentielles Commande Publique).
API gratuite data.economie.gouv.fr — pas de clé requise.
Permet de savoir si une entreprise a remporté des marchés publics récemment.
Signal fort d'activité B2B réelle et de capacité à répondre aux appels d'offres.
"""
from __future__ import annotations
from typing import Any
import httpx
from utils.pipeline_log import plog

DECP_BASE = (
    "https://data.economie.gouv.fr"
    "/api/explore/v2.1/catalog/datasets/decp_augmente/records"
)

def _clean_siren(siret: str | None) -> str | None:
    if not siret:
        return None
    clean = str(siret).replace(" ", "").strip()
    if len(clean) >= 9:
        return clean[:9]
    return None

def _parse_marche(record: dict) -> dict:
    siren = _clean_siren(record.get("siretetablissement"))
    return {
        "id":           record.get("id"),
        "siren":        siren,
        "siret":        record.get("siretetablissement"),
        "objet":        record.get("objetmarche"),
        "montant":      record.get("montant"),
        "date":         record.get("datenotification"),
        "annee":        record.get("anneenotification"),
        "acheteur":     record.get("nomacheteur"),
        "departement":  record.get("codedepartementexecution"),
        "lieu":         record.get("lieuexecutionnom"),
        "nature":       record.get("nature"),
        "procedure":    record.get("procedure"),
        "cpv":          record.get("codecpv"),
        "cpv_label":    record.get("referencecpv"),
    }

async def get_marches_for_siren(
    siren: str,
    *,
    limit: int = 5,
) -> list[dict]:
    """
    Retourne les marchés publics remportés par un SIREN.
    L'API DECP stocke parfois le SIREN (9 chiffres) directement
    dans siretetablissement au lieu du SIRET (14 chiffres).
    On essaie les deux.
    """
    if not siren or not siren.strip().isdigit():
        return []

    siren_clean = siren.strip()[:9]

    # Tentative 1 : SIREN exact (9 chiffres) — cas fréquent dans DECP
    # Tentative 2 : SIRET commençant par le SIREN (filtre textuel)
    wheres = [
        f'siretetablissement="{siren_clean}"',
        f'siretetablissement="{siren_clean}00001"',
    ]

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            for where in wheres:
                params = {
                    "limit": limit,
                    "where": where,
                    "order_by": "datenotification DESC",
                }
                resp = await client.get(DECP_BASE, params=params)
                if resp.status_code == 200:
                    data = resp.json()
                    results = data.get("results", [])
                    if results:
                        return [_parse_marche(r) for r in results]
    except Exception as e:
        plog("marches_publics_error", siren=siren, error=str(e)[:200])

    return []

async def search_marches_by_sector(
    *,
    cpv_division: str | None = None,
    departement: str | None = None,
    annee: str | None = None,
    limit: int = 100,
) -> list[dict]:
    """
    Recherche des marchés publics par secteur CPV et/ou département.
    Utile pour le mode Benchmark — volume et valeur des marchés dans un secteur.
    """
    conditions: list[str] = []
    
    if cpv_division:
        conditions.append(f'codecpv_division="{cpv_division}"')
    if departement:
        conditions.append(f'codedepartementexecution="{departement}"')
    if annee:
        conditions.append(f'anneenotification="{annee}"')
    else:
        # Par défaut : 3 dernières années
        conditions.append('anneenotification>="2022"')
    
    where = " AND ".join(conditions) if conditions else None
    
    params: dict[str, Any] = {
        "limit": limit,
        "order_by": "datenotification DESC",
    }
    if where:
        params["where"] = where
    
    plog("marches_publics_search_start",
         cpv_division=cpv_division, departement=departement)
    
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(DECP_BASE, params=params)
            resp.raise_for_status()
            data = resp.json()
            results = data.get("results", [])
            total = data.get("total_count", 0)
            
            marches = [_parse_marche(r) for r in results]
            
            plog("marches_publics_search_done",
                 total_api=total, returned=len(marches))
            
            return marches
    except Exception as e:
        plog("marches_publics_search_error", error=str(e)[:200])
        return []

async def get_marches_stats_for_benchmark(
    *,
    cpv_division: str | None = None,
    departement: str | None = None,
) -> dict:
    """
    Agrégats marchés publics pour l'onglet Benchmark.
    Retourne volume, valeur totale, top acheteurs, top entreprises.
    """
    marches = await search_marches_by_sector(
        cpv_division=cpv_division,
        departement=departement,
        limit=100,
    )
    
    if not marches:
        return {
            "total": 0,
            "montant_total": 0,
            "montant_moyen": 0,
            "top_acheteurs": [],
            "top_entreprises": [],
            "by_nature": {},
        }
    
    # Montants
    montants = [m["montant"] for m in marches if m["montant"] is not None]
    montant_total = sum(montants)
    montant_moyen = montant_total / len(montants) if montants else 0
    
    # Top acheteurs
    acheteurs: dict[str, float] = {}
    for m in marches:
        nom = m.get("acheteur") or "Inconnu"
        acheteurs[nom] = acheteurs.get(nom, 0) + (m["montant"] or 0)
    top_acheteurs = sorted(
        [{"nom": k, "montant": v} for k, v in acheteurs.items()],
        key=lambda x: x["montant"], reverse=True
    )[:5]
    
    # Top entreprises bénéficiaires
    entreprises: dict[str, int] = {}
    for m in marches:
        siren = m.get("siren") or "Inconnu"
        entreprises[siren] = entreprises.get(siren, 0) + 1
    top_entreprises = sorted(
        [{"siren": k, "nb_marches": v} for k, v in entreprises.items()],
        key=lambda x: x["nb_marches"], reverse=True
    )[:5]
    
    # Par nature
    by_nature: dict[str, int] = {}
    for m in marches:
        nature = m.get("nature") or "Autre"
        by_nature[nature] = by_nature.get(nature, 0) + 1
    
    return {
        "total": len(marches),
        "montant_total": montant_total,
        "montant_moyen": montant_moyen,
        "top_acheteurs": top_acheteurs,
        "top_entreprises": top_entreprises,
        "by_nature": by_nature,
    }
