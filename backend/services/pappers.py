"""
Connecteur API Pappers — enrichissement (dirigeants, finances).

Deux modes selon ``PAPPERS_BASE_URL`` :
- **International** (``api.pappers.in``) : en-tête ``api-key``, routes ``/search`` et ``/company``.
- **France** (``api.pappers.fr``) : paramètre ``api_token``, routes v2 ``/recherche`` et ``/entreprise``.
"""

from __future__ import annotations

import asyncio
import httpx
from models.schemas import CompanyResult
from config import settings
from utils.pipeline_log import plog

BASE_URL = settings.PAPPERS_BASE_URL.rstrip("/")


def _is_available() -> bool:
    return bool(settings.PAPPERS_API_KEY)


def _is_international() -> bool:
    return "pappers.in" in (settings.PAPPERS_BASE_URL or "").lower()


def _intl_headers() -> dict[str, str]:
    return {"api-key": settings.PAPPERS_API_KEY}


def _intl_country(params: dict) -> str:
    return (params.get("country_code") or settings.PAPPERS_COUNTRY_CODE or "FR").upper()


def _safe_float(value: object) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _first_activity_intl(r: dict) -> tuple[str | None, str | None]:
    activities = r.get("activities")
    if isinstance(activities, list) and activities:
        a0 = activities[0]
        if isinstance(a0, dict):
            code = a0.get("code") or a0.get("nace_code") or a0.get("activity_code")
            label = a0.get("label") or a0.get("name") or a0.get("description")
            return (str(code) if code is not None else None, str(label) if label is not None else None)
    fields = r.get("fields_of_activity")
    if isinstance(fields, list) and fields:
        return (str(fields[0]), None)
    return (None, None)


def _head_office_intl(r: dict) -> dict:
    ho = r.get("head_office")
    return ho if isinstance(ho, dict) else {}


def _officer_to_representant_fr(o: dict) -> dict:
    """Normalise un dirigeant API International vers le format attendu par ``api_engine``."""
    last = o.get("last_name") or o.get("nom") or o.get("family_name")
    first = o.get("first_name") or o.get("prenom") or o.get("given_name")
    full = o.get("name") or o.get("full_name") or o.get("nom_complet")
    role = (
        o.get("role")
        or o.get("function")
        or o.get("position")
        or o.get("title")
        or o.get("mandate")
        or o.get("qualite")
        or ""
    )
    nom = last or full or ""
    prenom = first or ""
    return {
        "nom": nom,
        "prenom": prenom,
        "nom_complet": full or (f"{prenom} {nom}".strip() if (prenom or nom) else ""),
        "qualite": str(role) if role else "",
    }


def _financial_year_key(row: dict) -> int:
    for k in ("year", "fiscal_year", "exercise_year", "annee"):
        v = row.get(k)
        if v is not None:
            try:
                return int(v)
            except (TypeError, ValueError):
                pass
    return 0


def _normalize_fr_finances(finances: object) -> list[dict]:
    """Normalise la clé `finances` Pappers FR (dict par année ou liste) en liste triée par année décroissante."""
    if finances is None:
        return []
    if isinstance(finances, dict):
        rows: list[dict] = []
        for k, v in finances.items():
            if not isinstance(v, dict):
                continue
            row = dict(v)
            try:
                y = int(str(k).strip())
            except (TypeError, ValueError):
                y = int(row.get("annee") or row.get("year") or 0)
            if row.get("annee") is None and row.get("year") is None:
                row["annee"] = y
            rows.append(row)
        rows.sort(key=lambda r: int(r.get("annee") or r.get("year") or 0), reverse=True)
        return rows
    if isinstance(finances, list):
        rows = [dict(x) for x in finances if isinstance(x, dict)]
        rows.sort(key=lambda r: int(r.get("annee") or r.get("year") or 0), reverse=True)
        return rows
    return []


def _norm_contact_str(v: object) -> str | None:
    if v is None:
        return None
    if isinstance(v, list):
        for x in v:
            s = _norm_contact_str(x)
            if s:
                return s
        return None
    if isinstance(v, dict):
        for k in ("url", "site", "valeur", "value", "libelle"):
            s = _norm_contact_str(v.get(k))
            if s:
                return s
        return None
    s = str(v).strip()
    return s or None


def _contacts_from_entreprise_payload(data: dict) -> tuple[str | None, str | None]:
    """Téléphone et site web depuis une fiche `/entreprise` Pappers (FR)."""
    siege = data.get("siege") if isinstance(data.get("siege"), dict) else {}
    tel = (
        data.get("telephone")
        or data.get("telephone_entreprise")
        or data.get("telephone_formate")
        or siege.get("telephone")
    )
    web = (
        data.get("site_internet")
        or data.get("site_web")
        or data.get("website")
        or data.get("sites_internet")
    )
    return (_norm_contact_str(tel), _norm_contact_str(web))


def _contacts_from_recherche_row(r: dict, siege: dict) -> tuple[str | None, str | None]:
    """Téléphone / site issus d’une ligne de `/recherche` (souvent partiels)."""
    tel = r.get("telephone") or r.get("telephone_entreprise") or siege.get("telephone")
    web = r.get("site_internet") or r.get("site_web") or r.get("sites_internet")
    return (_norm_contact_str(tel), _norm_contact_str(web))


def _capital_from_entreprise_payload(data: dict) -> float | None:
    return _safe_float(
        data.get("capital_social")
        or data.get("capital")
        or data.get("capital_social_entreprise")
    )


def _financial_ca_result(row: dict) -> tuple[float | None, float | None]:
    ca = _safe_float(
        row.get("chiffre_affaires")
        or row.get("turnover")
        or row.get("revenue")
        or row.get("ca")
        or row.get("sales")
    )
    res = _safe_float(
        row.get("resultat")
        or row.get("net_result")
        or row.get("net_income")
        or row.get("profit")
        or row.get("resultat_net")
    )
    return ca, res


def _company_result_from_intl(r: dict) -> CompanyResult | None:
    num = r.get("company_number") or r.get("siren") or ""
    if not num:
        return None
    ho = _head_office_intl(r)
    code, label = _first_activity_intl(r)
    workforce = r.get("workforce_range") or r.get("workforce")
    eff_label = str(workforce) if workforce is not None else None

    officers = r.get("officers") if isinstance(r.get("officers"), list) else []
    dir_nom, dir_prenom, dir_fonction = "", "", ""
    for o in officers:
        if not isinstance(o, dict):
            continue
        rep = _officer_to_representant_fr(o)
        q = (rep.get("qualite") or "").lower()
        if any(k in q for k in ["président", "president", "directeur", "gérant", "gerant", "ceo", "manager"]):
            dir_nom = rep.get("nom_complet") or rep.get("nom") or ""
            dir_prenom = rep.get("prenom") or ""
            dir_fonction = rep.get("qualite") or ""
            break
    if not dir_nom and officers and isinstance(officers[0], dict):
        rep = _officer_to_representant_fr(officers[0])
        dir_nom = rep.get("nom_complet") or rep.get("nom") or ""
        dir_prenom = rep.get("prenom") or ""
        dir_fonction = rep.get("qualite") or ""

    web_src = r.get("website") or r.get("web_site") or r.get("site_web")
    if not web_src and isinstance(r.get("domains"), list) and r["domains"]:
        d0 = r["domains"][0]
        if isinstance(d0, str):
            web_src = d0
        elif isinstance(d0, dict):
            web_src = d0.get("domain") or d0.get("url")
    tel_src = r.get("phone") or r.get("telephone") or ho.get("phone")

    ca, rn = None, None
    annee_ca: int | None = None
    fins = r.get("financials")
    if isinstance(fins, list) and fins:
        rows = [x for x in fins if isinstance(x, dict)]
        rows.sort(key=_financial_year_key, reverse=True)
        if rows:
            ca, rn = _financial_ca_result(rows[0])
            yk = _financial_year_key(rows[0])
            annee_ca = yk if yk else None

    return CompanyResult(
        siren=str(num).replace(" ", ""),
        siret=None,
        nom=r.get("name") or r.get("trade_name") or "",
        activite_principale=code,
        libelle_activite=label,
        adresse=ho.get("address_line_1"),
        code_postal=ho.get("postal_code"),
        ville=ho.get("city"),
        tranche_effectif=eff_label,
        effectif_label=eff_label,
        date_creation=r.get("date_of_creation") or r.get("date_creation"),
        forme_juridique=r.get("local_legal_form_name") or r.get("legal_form_code"),
        dirigeant_nom=dir_nom or None,
        dirigeant_prenom=dir_prenom or None,
        dirigeant_fonction=dir_fonction or None,
        chiffre_affaires=ca,
        resultat_net=rn,
        annee_dernier_ca=annee_ca,
        telephone=_norm_contact_str(tel_src),
        site_web=_norm_contact_str(web_src),
    )


async def _search_international(params: dict) -> list[CompanyResult]:
    q = (params.get("q") or "").strip()
    if not q:
        plog("pappers_intl_skip", reason="param q vide")
        return []

    country = _intl_country(params)
    search_params: dict[str, str | int] = {
        "country_code": country,
        "q": q,
        "page": int(params.get("page", 1)),
        "per_page": min(int(params.get("per_page", 25)), 100),
    }
    if params.get("code_naf"):
        search_params["activity_code"] = str(params["code_naf"])
    if params.get("date_creation_min"):
        search_params["date_of_creation_min"] = str(params["date_creation_min"])
    if params.get("date_creation_max"):
        search_params["date_of_creation_max"] = str(params["date_creation_max"])

    results: list[CompanyResult] = []
    async with httpx.AsyncClient(timeout=20.0) as client:
        try:
            resp = await client.get(
                f"{BASE_URL}/search",
                params=search_params,
                headers=_intl_headers(),
            )
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            plog("pappers_intl_search_failed", error=repr(e))
            return []

    for r in data.get("results") or []:
        if isinstance(r, dict):
            row = _company_result_from_intl(r)
            if row:
                results.append(row)
    plog("pappers_intl_search_ok", nb=len(results))
    return results


async def _search_france(params: dict) -> list[CompanyResult]:
    search_params: dict[str, str | int] = {"api_token": settings.PAPPERS_API_KEY}

    if "q" in params:
        search_params["q"] = params["q"]
    if "code_naf" in params:
        search_params["code_naf"] = params["code_naf"]
    if "departement" in params:
        search_params["departement"] = params["departement"]
    if "region" in params:
        search_params["region"] = params["region"]
    if "ville" in params:
        search_params["ville_siege"] = params["ville"]
    if "ca_min" in params:
        search_params["chiffre_affaires_min"] = int(params["ca_min"])
    if "ca_max" in params:
        search_params["chiffre_affaires_max"] = int(params["ca_max"])
    if "effectif_min" in params:
        search_params["effectif_min"] = int(params["effectif_min"])
    if "effectif_max" in params:
        search_params["effectif_max"] = int(params["effectif_max"])
    if "date_creation_min" in params:
        search_params["date_creation_min"] = params["date_creation_min"]
    if "date_creation_max" in params:
        search_params["date_creation_max"] = params["date_creation_max"]

    search_params["par_page"] = min(params.get("per_page", 25), 100)
    search_params["page"] = params.get("page", 1)

    safe_params = {k: v for k, v in search_params.items() if k != "api_token"}
    plog("pappers_recherche_request", params=safe_params)

    results: list[CompanyResult] = []

    async with httpx.AsyncClient(timeout=15.0) as client:
        try:
            resp = await client.get(f"{BASE_URL}/recherche", params=search_params)
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            plog("pappers_recherche_failed", error=repr(e))
            return []

        for r in data.get("resultats", []):
            siege = r.get("siege", {})
            dirigeants = r.get("representants", [])

            important_dirs: list[dict] = []
            other_dirs: list[dict] = []
            for d in dirigeants:
                qualite = (d.get("qualite") or "").lower()
                if any(k in qualite for k in ["président", "directeur", "gérant"]):
                    important_dirs.append(d)
                else:
                    other_dirs.append(d)
            ordered_dirs = important_dirs + other_dirs

            dir_nom, dir_prenom, dir_fonction = "", "", ""
            dir_2_nom, dir_2_fonction = None, None
            if ordered_dirs:
                d0 = ordered_dirs[0]
                dir_nom = d0.get("nom_complet") or d0.get("nom") or ""
                dir_prenom = d0.get("prenom") or ""
                dir_fonction = d0.get("qualite") or ""
            if len(ordered_dirs) >= 2:
                d1 = ordered_dirs[1]
                dir_2_nom = d1.get("nom_complet") or d1.get("nom") or ""
                dir_2_fonction = d1.get("qualite") or ""

            fin_rows = _normalize_fr_finances(r.get("finances"))
            ca = rn = None
            annee_ca = None
            date_cloture = None
            marge = ebe_val = cap_prop = eff_fin = None
            ca_n1, rn_n1, annee_n1 = None, None, None
            variation_ca = None
            cap_soc = _capital_from_entreprise_payload(r) if isinstance(r, dict) else None
            if fin_rows:
                ly = fin_rows[0]
                ca = _safe_float(ly.get("chiffre_affaires"))
                rn = _safe_float(ly.get("resultat") or ly.get("resultat_net"))
                ay = ly.get("annee") or ly.get("year")
                if ay is not None:
                    try:
                        annee_ca = int(ay)
                    except (TypeError, ValueError):
                        annee_ca = None
                date_cloture = ly.get("date_cloture_exercice") or ly.get("date_cloture")
                marge = _safe_float(ly.get("marge_brute"))
                ebe_val = _safe_float(
                    ly.get("excedent_brut_exploitation")
                    or ly.get("ebe")
                    or ly.get("excédent_brut_exploitation")
                )
                cap_prop = _safe_float(ly.get("capitaux_propres"))
                eff_fin = _safe_float(ly.get("effectif") or ly.get("effectif_moyen"))

            if len(fin_rows) >= 2:
                prev = fin_rows[1]
                ca_n1 = _safe_float(prev.get("chiffre_affaires"))
                rn_n1 = _safe_float(prev.get("resultat") or prev.get("resultat_net"))
                ay1 = prev.get("annee") or prev.get("year")
                if ay1 is not None:
                    try:
                        annee_n1 = int(ay1)
                    except (TypeError, ValueError):
                        pass
                if ca is not None and ca_n1 is not None and ca_n1 != 0:
                    variation_ca = round((ca - ca_n1) / abs(ca_n1) * 100, 1)

            tel_row, web_row = _contacts_from_recherche_row(r, siege if isinstance(siege, dict) else {})
            site_merged = web_row or r.get("site_web")

            results.append(
                CompanyResult(
                    siren=r.get("siren", ""),
                    siret=siege.get("siret") if siege else None,
                    nom=r.get("nom_entreprise") or r.get("denomination") or "",
                    activite_principale=r.get("code_naf"),
                    libelle_activite=r.get("libelle_code_naf"),
                    adresse=siege.get("adresse_ligne_1") if siege else None,
                    code_postal=siege.get("code_postal") if siege else None,
                    ville=siege.get("ville") if siege else None,
                    date_creation=r.get("date_creation"),
                    dirigeant_nom=dir_nom or None,
                    dirigeant_prenom=dir_prenom or None,
                    dirigeant_fonction=dir_fonction or None,
                    dirigeant_2_nom=dir_2_nom,
                    dirigeant_2_fonction=dir_2_fonction,
                    chiffre_affaires=ca,
                    resultat_net=rn,
                    annee_dernier_ca=annee_ca,
                    date_cloture_exercice=str(date_cloture) if date_cloture else None,
                    ca_n_minus_1=ca_n1,
                    resultat_n_minus_1=rn_n1,
                    annee_n_minus_1=annee_n1,
                    variation_ca_pct=variation_ca,
                    marge_brute=marge,
                    ebe=ebe_val,
                    capitaux_propres=cap_prop,
                    effectif_financier=eff_fin,
                    capital_social=cap_soc,
                    telephone=tel_row,
                    site_web=_norm_contact_str(site_merged),
                )
            )

    plog("pappers_recherche_ok", nb=len(results))
    return results


async def search_pappers(params: dict) -> list[CompanyResult]:
    """Recherche d'entreprises via Pappers (International ou France selon l'URL)."""
    if not _is_available():
        plog("pappers_skip", reason="PAPPERS_API_KEY manquant ou vide")
        return []
    if _is_international():
        plog("pappers_mode", mode="international", base_url=BASE_URL)
        return await _search_international(params)
    plog("pappers_mode", mode="france", base_url=BASE_URL)
    return await _search_france(params)


async def _get_company_intl(siren: str, fields: str) -> dict | None:
    async with httpx.AsyncClient(timeout=20.0) as client:
        try:
            resp = await client.get(
                f"{BASE_URL}/company",
                params={
                    "country_code": settings.PAPPERS_COUNTRY_CODE or "FR",
                    "company_number": siren.strip(),
                    "fields": fields,
                },
                headers=_intl_headers(),
            )
            resp.raise_for_status()
            return resp.json()
        except Exception:
            return None


async def get_company_dirigeants(siren: str) -> dict:
    """Dirigeants / représentants pour un SIREN (France) ou numéro d'immatriculation."""
    if not _is_available():
        return {}

    if _is_international():
        data = await _get_company_intl(siren, "officers,ubos")
        if not data:
            return {}
        reps = [_officer_to_representant_fr(o) for o in (data.get("officers") or []) if isinstance(o, dict)]
        ubos = data.get("ubos") if isinstance(data.get("ubos"), list) else []
        return {"siren": siren, "representants": reps, "beneficiaires": ubos}

    async with httpx.AsyncClient(timeout=15.0) as client:
        try:
            resp = await client.get(
                f"{BASE_URL}/entreprise",
                params={"api_token": settings.PAPPERS_API_KEY, "siren": siren},
            )
            resp.raise_for_status()
            data = resp.json()
        except Exception:
            return {}

    return {
        "siren": siren,
        "representants": data.get("representants", []),
        "beneficiaires": data.get("beneficiaires_effectifs", []),
    }


async def get_company_finances(siren: str) -> dict:
    """Données financières agrégées pour l'affichage / fusion dans les résultats."""
    if not _is_available():
        return {}

    if _is_international():
        data = await _get_company_intl(siren, "financials")
        if not data:
            return {"siren": siren, "denomination": None, "finances": []}
        fins = [x for x in (data.get("financials") or []) if isinstance(x, dict)]
        fins.sort(key=_financial_year_key, reverse=True)
        normalized: list[dict] = []
        for row in fins:
            ca, rn = _financial_ca_result(row)
            y = _financial_year_key(row)
            merged = dict(row)
            if ca is not None:
                merged["chiffre_affaires"] = ca
            if rn is not None:
                merged["resultat"] = rn
            merged["annee"] = y or merged.get("annee")
            normalized.append(merged)
        return {
            "siren": siren,
            "denomination": data.get("name"),
            "finances": normalized,
        }

    async with httpx.AsyncClient(timeout=15.0) as client:
        try:
            base_params: dict[str, str] = {
                "api_token": settings.PAPPERS_API_KEY,
                "siren": siren,
            }
            params_full = {
                **base_params,
                "champs_supplementaires": "telephone,site_internet",
            }
            resp = await client.get(f"{BASE_URL}/entreprise", params=params_full)
            if resp.status_code == 400:
                resp = await client.get(
                    f"{BASE_URL}/entreprise",
                    params={
                        **base_params,
                        "champsSupplementaires": "telephone,site_internet",
                    },
                )
            if resp.status_code == 400:
                resp = await client.get(f"{BASE_URL}/entreprise", params=base_params)
            resp.raise_for_status()
            data = resp.json()
        except Exception:
            return {}

    finances = _normalize_fr_finances(data.get("finances"))
    tel, web = _contacts_from_entreprise_payload(data)
    return {
        "siren": siren,
        "denomination": data.get("denomination"),
        "finances": finances,
        "capital_social": _capital_from_entreprise_payload(data),
        "telephone": tel,
        "site_web": web,
    }


async def enrich_missing_contacts_pappers_fr(
    results: list[CompanyResult],
    *,
    max_companies: int = 60,
    concurrency: int = 8,
) -> None:
    """Complète téléphone / site web via fiche Pappers France (SIREN), si clé configurée."""
    if not _is_available() or _is_international():
        return

    targets: list[tuple[str, CompanyResult]] = []
    seen: set[str] = set()
    for r in results:
        sid = (r.siren or "").strip().replace(" ", "")
        if len(sid) != 9 or not sid.isdigit():
            continue
        if sid in seen:
            continue
        seen.add(sid)
        need_tel = not (r.telephone and str(r.telephone).strip())
        need_web = not (r.site_web and str(r.site_web).strip())
        if need_tel or need_web:
            targets.append((sid, r))
        if len(targets) >= max_companies:
            break

    if not targets:
        return

    plog("pappers_contact_enrich_start", nb=len(targets))
    sem = asyncio.Semaphore(concurrency)

    async def _one(client: httpx.AsyncClient, siren: str, row: CompanyResult) -> None:
        async with sem:
            try:
                base_params: dict[str, str] = {
                    "api_token": settings.PAPPERS_API_KEY,
                    "siren": siren,
                }
                params_full = {
                    **base_params,
                    "champs_supplementaires": "telephone,site_internet",
                }
                resp = await client.get(
                    f"{BASE_URL}/entreprise",
                    params=params_full,
                    timeout=18.0,
                )
                if resp.status_code == 400:
                    resp = await client.get(
                        f"{BASE_URL}/entreprise",
                        params={
                            **base_params,
                            "champsSupplementaires": "telephone,site_internet",
                        },
                        timeout=18.0,
                    )
                if resp.status_code == 400:
                    resp = await client.get(
                        f"{BASE_URL}/entreprise",
                        params=base_params,
                        timeout=18.0,
                    )
                resp.raise_for_status()
                data = resp.json()
            except Exception:
                return
        tel, web = _contacts_from_entreprise_payload(data)
        if tel and not (row.telephone and str(row.telephone).strip()):
            row.telephone = tel
        if web and not (row.site_web and str(row.site_web).strip()):
            row.site_web = web

    async with httpx.AsyncClient() as client:
        await asyncio.gather(*(_one(client, sid, row) for sid, row in targets))
    plog("pappers_contact_enrich_done", nb=len(targets))
