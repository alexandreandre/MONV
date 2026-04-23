"""
Service BODACC — Bulletin Officiel des Annonces Civiles et Commerciales.
API gratuite data.gouv.fr — pas de clé requise.
Fournit : créations, cessations, procédures collectives, ventes de fonds.
"""
from __future__ import annotations
import json
from datetime import datetime, timedelta
from typing import Any
import httpx
from utils.pipeline_log import plog

BODACC_BASE = (
    "https://bodacc-datadila.opendatasoft.com"
    "/api/explore/v2.1/catalog/datasets/annonces-commerciales/records"
)

# Types d'annonces BODACC utilisés dans MONV
FAMILLE_LABELS: dict[str, str] = {
    "immatriculation": "Immatriculation",
    "vente":           "Vente / Cession",
    "procol":          "Procédure collective",
    "modification":    "Modification",
    "radiation":       "Radiation",
    "dpc":             "Dépôt de comptes",
}

def _clean_siren(registre: list[str] | None) -> str | None:
    """Extrait le SIREN propre (9 chiffres) depuis le champ registre."""
    if not registre:
        return None
    for r in registre:
        clean = r.replace(" ", "").strip()
        if clean.isdigit() and len(clean) == 9:
            return clean
    return None

def _parse_annonce(record: dict) -> dict:
    """Normalise un enregistrement BODACC en dict exploitable."""
    siren = _clean_siren(record.get("registre"))
    famille = record.get("familleavis", "")
    
    # Extraire activité depuis listeetablissements si dispo
    activite = None
    le = record.get("listeetablissements")
    if le and isinstance(le, str):
        try:
            le_data = json.loads(le)
            etab = le_data.get("etablissement", {})
            if isinstance(etab, list):
                etab = etab[0]
            activite = etab.get("activite")
        except Exception:
            pass

    return {
        "id":           record.get("id"),
        "siren":        siren,
        "nom":          record.get("commercant"),
        "ville":        record.get("ville"),
        "cp":           record.get("cp"),
        "departement":  record.get("numerodepartement"),
        "region":       record.get("region_nom_officiel"),
        "date":         record.get("dateparution"),
        "famille":      famille,
        "famille_lib":  FAMILLE_LABELS.get(famille, famille),
        "activite":     activite,
        "url":          record.get("url_complete"),
        "tribunal":     record.get("tribunal"),
    }

async def search_bodacc(
    *,
    siren: str | None = None,
    famille: str | None = None,
    region: str | None = None,
    departement: str | None = None,
    days_back: int = 365,
    limit: int = 20,
) -> list[dict]:
    """
    Recherche des annonces BODACC.
    
    Paramètres :
    - siren      : filtre sur un SIREN précis
    - famille    : immatriculation | vente | procol | modification | radiation
    - region     : nom de région (ex: "Île-de-France")
    - departement: numéro de département (ex: "75")
    - days_back  : fenêtre temporelle en jours (défaut 365)
    - limit      : nombre max de résultats
    """
    # Sécurité : sans SIREN ni famille ni région,
    # on ne fait pas de requête globale
    if not siren and not famille and not region and not departement:
        plog("bodacc_search_skipped", reason="no_filter")
        return []

    date_min = (datetime.now() - timedelta(days=days_back)).strftime("%Y-%m-%d")
    
    conditions: list[str] = [f'dateparution >= "{date_min}"']
    
    if siren:
        siren_clean = siren.replace(" ", "").strip()
        if not siren_clean.isdigit() or len(siren_clean) != 9:
            plog("bodacc_invalid_siren", siren=siren)
            return []
        siren_fmt = f"{siren_clean[:3]} {siren_clean[3:6]} {siren_clean[6:]}"
        conditions.append(
            f'(registre="{siren_clean}" OR registre="{siren_fmt}")'
        )
    if famille:
        conditions.append(f'familleavis="{famille}"')
    if region:
        conditions.append(f'region_nom_officiel="{region}"')
    if departement:
        conditions.append(f'numerodepartement="{departement}"')
    
    where = " AND ".join(conditions)
    
    params = {
        "limit": limit,
        "where": where,
        "order_by": "dateparution DESC",
    }
    
    plog("bodacc_search_start",
         famille=famille, region=region, departement=departement,
         days_back=days_back)
    
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(BODACC_BASE, params=params)
            resp.raise_for_status()
            data = resp.json()
            results = data.get("results", [])
            total = data.get("total_count", 0)
            
            annonces = [_parse_annonce(r) for r in results]
            
            plog("bodacc_search_done",
                 total_api=total, returned=len(annonces))
            
            return annonces
    except Exception as e:
        plog("bodacc_search_error", error=str(e)[:200])
        return []

async def get_bodacc_signals_for_siren(siren: str) -> list[dict]:
    """
    Retourne les événements BODACC récents pour un SIREN donné.
    Utilisé pour enrichir les fiches entreprise avec des signaux business.
    """
    annonces = await search_bodacc(siren=siren, days_back=730, limit=10)
    
    signals = []
    for a in annonces:
        famille = a.get("famille", "")
        if famille == "procol":
            signals.append({
                "type": "procedure_collective",
                "label": "Procédure collective",
                "detail": f"Annonce du {a.get('date', '')}",
                "severity": "warning",
                "source": "BODACC",
                "date": a.get("date"),
                "url": a.get("url"),
            })
        elif famille == "vente":
            signals.append({
                "type": "vente_fonds",
                "label": "Vente de fonds",
                "detail": f"Cession annoncée le {a.get('date', '')}",
                "severity": "info",
                "source": "BODACC",
                "date": a.get("date"),
                "url": a.get("url"),
            })
        elif famille == "radiation":
            signals.append({
                "type": "radiation",
                "label": "Radiation RCS",
                "detail": f"Radiation le {a.get('date', '')}",
                "severity": "warning",
                "source": "BODACC",
                "date": a.get("date"),
                "url": a.get("url"),
            })
        elif famille == "modification":
            signals.append({
                "type": "modification_bodacc",
                "label": "Modification RCS",
                "detail": f"Modification le {a.get('date', '')}",
                "severity": "info",
                "source": "BODACC",
                "date": a.get("date"),
                "url": a.get("url"),
            })
    
    return signals

async def get_bodacc_stats_for_benchmark(
    *,
    region: str | None = None,
    departement: str | None = None,
    days_back: int = 365,
) -> dict:
    """
    Agrégats BODACC pour l'onglet Dynamique du Benchmark.
    Retourne créations, cessations, procédures sur la période.
    """
    familles = ["immatriculation", "radiation", "procol", "vente"]
    results: dict[str, list] = {}
    
    for famille in familles:
        annonces = await search_bodacc(
            famille=famille,
            region=region,
            departement=departement,
            days_back=days_back,
            limit=100,
        )
        results[famille] = annonces
    
    # Agrégats par mois
    by_month: dict[str, dict] = {}
    for famille, annonces in results.items():
        for a in annonces:
            date_str = a.get("date", "")
            if not date_str or len(date_str) < 7:
                continue
            month = date_str[:7]  # "YYYY-MM"
            if month not in by_month:
                by_month[month] = {
                    "month": month,
                    "immatriculations": 0,
                    "radiations": 0,
                    "procol": 0,
                    "ventes": 0,
                }
            key_map = {
                "immatriculation": "immatriculations",
                "radiation": "radiations",
                "procol": "procol",
                "vente": "ventes",
            }
            if famille in key_map:
                by_month[month][key_map[famille]] += 1
    
    timeline = sorted(by_month.values(), key=lambda x: x["month"])
    
    return {
        "total_immatriculations": len(results.get("immatriculation", [])),
        "total_radiations": len(results.get("radiation", [])),
        "total_procol": len(results.get("procol", [])),
        "total_ventes": len(results.get("vente", [])),
        "timeline": timeline,
        "region": region,
        "departement": departement,
        "days_back": days_back,
    }
