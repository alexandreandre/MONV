"""
Connecteur API Recherche Entreprises (data.gouv.fr)
Gratuit, sans clé API, données publiques INSEE.
"""

from __future__ import annotations

import asyncio
import re
import unicodedata
import httpx

import traceback

from models.schemas import CompanyResult, ExecutionPlan, GuardEntity
from config import settings
from utils.pipeline_log import plog

BASE_URL = settings.SIRENE_BASE_URL


def _fold_key(s: str) -> str:
    s = "".join(
        c
        for c in unicodedata.normalize("NFD", s)
        if unicodedata.category(c) != "Mn"
    )
    return s.lower().strip()


# Libellés fréquents (QCM, Guard) → code région INSEE (2 chiffres)
_REGION_NAME_TO_CODE: dict[str, str] = {
    "11": "11",
    "24": "24",
    "27": "27",
    "28": "28",
    "32": "32",
    "44": "44",
    "52": "52",
    "53": "53",
    "75": "75",
    "76": "76",
    "84": "84",
    "93": "93",
    "94": "94",
    "ile-de-france": "11",
    "ile de france": "11",
    "idf": "11",
    "paris": "11",
    "centre-val de loire": "24",
    "bourgogne-franche-comte": "27",
    "normandie": "28",
    "hauts-de-france": "32",
    "grand est": "44",
    "pays de la loire": "52",
    "bretagne": "53",
    "nouvelle-aquitaine": "75",
    "occitanie": "76",
    "auvergne-rhone-alpes": "84",
    "aura": "84",
    "paca": "93",
    "provence-alpes-cote d'azur": "93",
    "provence alpes cote d'azur": "93",
    "corse": "94",
}

def _codes_marseille_arrondissements() -> str:
    """Marseille : l’ancien code 13055 ne renvoie plus de résultats ; l’API attend les 13201–13216."""
    return ",".join(f"132{i:02d}" for i in range(1, 17))


def _codes_lyon_arrondissements() -> str:
    return ",".join(str(c) for c in range(69381, 69390))


# Villes → code(s) commune INSEE (siège ; évite le paramètre texte « commune » rejeté par l’API)
_VILLE_A_CODE_COMMUNE: dict[str, str] = {
    "marseille": _codes_marseille_arrondissements(),
    "lyon": _codes_lyon_arrondissements(),
    "toulouse": "31555",
    "nice": "06088",
    "nantes": "44109",
    "bordeaux": "33063",
    "lille": "59350",
    "strasbourg": "67482",
    "montpellier": "34172",
    "rennes": "35238",
    "reims": "51454",
    "saint-etienne": "42218",
    "toulon": "83137",
    "grenoble": "38185",
    "dijon": "21231",
    "angers": "49007",
    "nimes": "30189",
    "villeurbanne": "69266",
    "le havre": "76351",
    "aix-en-provence": "13001",
    "aix en provence": "13001",
}

_DEPT_NAME_TO_CODE: dict[str, str] = {
    "ain": "01",
    "aisne": "02",
    "allier": "03",
    "alpes-de-haute-provence": "04",
    "hautes-alpes": "05",
    "alpes-maritimes": "06",
    "ardeche": "07",
    "ardennes": "08",
    "ariege": "09",
    "aube": "10",
    "aude": "11",
    "aveyron": "12",
    "bouches-du-rhone": "13",
    "bouches du rhone": "13",
    "calvados": "14",
    "cantal": "15",
    "charente": "16",
    "charente-maritime": "17",
    "cher": "18",
    "correze": "19",
    "cote-d'or": "21",
    "cotes-d'armor": "22",
    "creuse": "23",
    "dordogne": "24",
    "doubs": "25",
    "drome": "26",
    "eure": "27",
    "eure-et-loir": "28",
    "finistere": "29",
    "gard": "30",
    "haute-garonne": "31",
    "gers": "32",
    "gironde": "33",
    "herault": "34",
    "ille-et-vilaine": "35",
    "indre": "36",
    "indre-et-loire": "37",
    "isere": "38",
    "jura": "39",
    "landes": "40",
    "loir-et-cher": "41",
    "loire": "42",
    "haute-loire": "43",
    "loire-atlantique": "44",
    "loiret": "45",
    "lot": "46",
    "lot-et-garonne": "47",
    "lozere": "48",
    "maine-et-loire": "49",
    "manche": "50",
    "marne": "51",
    "haute-marne": "52",
    "mayenne": "53",
    "meurthe-et-moselle": "54",
    "meuse": "55",
    "morbihan": "56",
    "moselle": "57",
    "nievre": "58",
    "nord": "59",
    "oise": "60",
    "orne": "61",
    "pas-de-calais": "62",
    "puy-de-dome": "63",
    "pyrenees-atlantiques": "64",
    "hautes-pyrenees": "65",
    "pyrenees-orientales": "66",
    "bas-rhin": "67",
    "haut-rhin": "68",
    "rhone": "69",
    "haute-saone": "70",
    "saone-et-loire": "71",
    "sarthe": "72",
    "savoie": "73",
    "haute-savoie": "74",
    "paris": "75",
    "seine-maritime": "76",
    "seine-et-marne": "77",
    "yvelines": "78",
    "deux-sevres": "79",
    "somme": "80",
    "tarn": "81",
    "tarn-et-garonne": "82",
    "var": "83",
    "vaucluse": "84",
    "vendee": "85",
    "vienne": "86",
    "haute-vienne": "87",
    "vosges": "88",
    "yonne": "89",
    "territoire de belfort": "90",
    "essonne": "91",
    "hauts-de-seine": "92",
    "seine-saint-denis": "93",
    "val-de-marne": "94",
    "val-d'oise": "95",
}


def _norm_dept_code(raw: object) -> str | None:
    if raw is None:
        return None
    s = str(raw).strip().upper().replace(" ", "")
    if re.fullmatch(r"2[Aa]", s):
        return "2A"
    if re.fullmatch(r"2[Bb]", s):
        return "2B"
    if re.fullmatch(r"\d{1,2}", s):
        return s.zfill(2)
    if re.fullmatch(r"97[1-6]", s):
        return s
    folded = _fold_key(s)
    return _DEPT_NAME_TO_CODE.get(folded)


def _norm_region_code(raw: object) -> str | None:
    if raw is None:
        return None
    s = str(raw).strip()
    if re.fullmatch(r"\d{2}", s):
        return s
    return _REGION_NAME_TO_CODE.get(_fold_key(s))


def _ville_fallback_departement(raw: object) -> str | None:
    """Paris intramuros : l’API attend plutôt le département 75 que l’ancien code unique."""
    if raw is None:
        return None
    first = str(raw).strip().split("/")[0].strip()
    if _fold_key(first) == "paris":
        return "75"
    return None


def _ville_to_code_commune(raw: object) -> str | None:
    if raw is None:
        return None
    s = str(raw).strip()
    if re.fullmatch(r"\d{5}", s):
        return s
    # « Marseille / PACA » → prendre le premier segment comme ville
    first = s.split("/")[0].strip()
    return _VILLE_A_CODE_COMMUNE.get(_fold_key(first))


_SECTOR_KEYWORDS: set[str] = {
    "saas", "tech", "btp", "informatique", "digital", "numerique", "numérique",
    "logiciel", "software", "fintech", "edtech", "medtech", "biotech",
    "proptech", "insurtech", "healthtech", "greentech", "cleantech",
    "e-commerce", "ecommerce", "ia", "ai", "cloud", "cyber",
    "startup", "start-up",
}

# Code APE NAF rév. 2 tel qu'attendu par l'API (ex. 62.01Z, 10.13A) — pas une division seule (ex. 62).
_NAF_APE_CODE_RE = re.compile(r"^\d{2}\.\d{2}[A-Z]$")


def _sanitize_activite_principale_param(p: dict) -> None:
    """
    L'API Recherche d'entreprises renvoie une 400 si ``activite_principale`` n'est pas
    un ou plusieurs codes APE complets. Un code « division » sur 2 chiffres (ex. 62) est refusé.
    On retire alors ce paramètre et on applique un préfixe via ``activite_principale_filter``
    (filtrage déjà géré dans ``search_sirene``).
    """
    raw = p.get("activite_principale")
    if raw is None:
        return
    s = str(raw).strip()
    if not s:
        p.pop("activite_principale", None)
        return
    parts = [x.strip() for x in s.split(",") if x.strip()]
    valid = [x for x in parts if _NAF_APE_CODE_RE.match(x)]
    if valid:
        p["activite_principale"] = ",".join(valid)
        return
    p.pop("activite_principale", None)
    if p.get("activite_principale_filter"):
        return
    for one in parts:
        if re.fullmatch(r"\d{2}", one):
            p["activite_principale_filter"] = one
            plog(
                "sirene_activite_division_to_prefix_filter",
                invalid_param=s,
                prefix=one,
            )
            break


# Codes postaux « génériques » invalides pour les grandes villes
# (ex. 75000 pour Paris, 13000 pour Marseille) — l’API ne les connaît pas.
_INVALID_CP_TO_DEPT: dict[str, str] = {
    "75000": "75",
    "13000": "13",
    "69000": "69",
    "31000": "31",
    "06000": "06",
    "44000": "44",
    "33000": "33",
    "59000": "59",
    "67000": "67",
    "34000": "34",
    "35000": "35",
}


def normalize_recherche_entreprises_params(params: dict) -> dict:
    """
    Adapte les paramètres au contrat de l’API Recherche d’entreprises :
    - ``commune`` en libellé provoque une 400 ; on utilise ``code_commune`` (5 chiffres).
    - Régions / départements en texte → codes INSEE.
    - ``code_postal`` invalide (ex. 75000) → ``departement``.
    - ``q`` avec mots-clés sectoriels redondants quand un filtre NAF est déjà présent.
    - ``activite_principale`` : codes APE complets uniquement ; division seule (ex. 62) → filtre préfixe.
    """
    p = dict(params)

    # ── code_postal invalide → departement ──────────────────────────
    if "code_postal" in p:
        cp = str(p["code_postal"]).strip()
        dept = _INVALID_CP_TO_DEPT.get(cp)
        if dept:
            p.pop("code_postal")
            if not p.get("departement"):
                p["departement"] = dept

    # Alias historique / LLM → canonique
    if "commune" in p and "code_commune" not in p:
        v = p.pop("commune")
        code = _ville_to_code_commune(v)
        if code:
            p["code_commune"] = code
        elif isinstance(v, str) and re.fullmatch(r"\d{5}", v.strip()):
            p["code_commune"] = v.strip()
        elif isinstance(v, str) and v.strip():
            # Libellé non résolu : ne pas envoyer ``commune=`` (400) ; enrichir ``q``
            label = v.strip()
            q0 = (p.get("q") or "").strip()
            if label.lower() not in q0.lower():
                p["q"] = f"{label} {q0}".strip() if q0 else label
            dfb = _ville_fallback_departement(v)
            if dfb and not p.get("departement"):
                p["departement"] = dfb

    cc = p.get("code_commune")
    if isinstance(cc, str) and "," in cc:
        # liste déjà supportée par l’API ; ne pas casser
        pass
    elif cc is not None and str(cc).strip():
        sc = str(cc).strip()
        if not re.fullmatch(r"\d{5}", sc):
            mapped = _ville_to_code_commune(sc)
            if mapped:
                p["code_commune"] = mapped

    if "departement" in p and p["departement"] is not None:
        nd = _norm_dept_code(p["departement"])
        if nd:
            p["departement"] = nd
        else:
            p.pop("departement", None)

    if "region" in p and p["region"] is not None:
        nr = _norm_region_code(p["region"])
        if nr:
            p["region"] = nr
        else:
            p.pop("region", None)

    _sanitize_activite_principale_param(p)

    # ── q : retirer les mots-clés sectoriels si un filtre NAF est déjà actif ─
    has_naf = bool(
        p.get("section_activite_principale")
        or p.get("activite_principale")
        or p.get("activite_principale_filter")
    )
    if has_naf and p.get("q"):
        q_words = p["q"].strip().split()
        filtered = [w for w in q_words if w.lower() not in _SECTOR_KEYWORDS]
        if filtered:
            p["q"] = " ".join(filtered)
        else:
            p.pop("q")

    # Virgule dans « q » + filtre NAF : l'API interprète souvent comme une intersection
    # stricte sur le nom → 0 résultat (ex. "ESN, agence de développement"). On ne garde
    # que le premier segment s'il ressemble à un acronyme / nom court.
    if has_naf and p.get("q") and "," in str(p["q"]):
        qs = str(p["q"]).strip()
        first = qs.split(",")[0].strip()
        if first and " " not in first and len(first) <= 40:
            p["q"] = first
            plog("sirene_q_comma_first_segment", kept=first)
        else:
            p.pop("q", None)
            plog("sirene_q_dropped_comma_phrase", reason="has_naf")

    # Section NAF + tranche d'effectif + q : l'API renvoie souvent 0 résultat (intersection trop stricte).
    if has_naf and p.get("tranche_effectif_salarie") and p.get("q"):
        p.pop("q", None)
        plog("sirene_q_dropped_with_tranche_and_naf", reason="api_intersection_souvent_vide")

    return p


def _entity_targets_ile_de_france_region(entities: GuardEntity) -> bool:
    """L'utilisateur vise l'Île-de-France comme région, pas Paris seul (localisation explicite)."""
    dep = _fold_key(entities.departement or "")
    reg = _fold_key(entities.region or "")
    loc = (entities.localisation or "").strip()
    floc = _fold_key(loc)

    idf = (
        "ile-de-france" in dep
        or dep in ("idf", "ile de france")
        or "ile-de-france" in reg
        or reg in ("idf", "ile de france")
    )
    if not idf:
        return False
    if loc and (floc == "paris" or floc.startswith("paris ")):
        return False
    return True


def patch_sirene_calls_from_guard_entities(
    plan: ExecutionPlan, entities: GuardEntity
) -> None:
    """
    Corrige des sorties orchestrateur trop étroites par rapport au guard.
    Ex. « Île-de-France » dans les entités mais ``departement=75`` seul (Paris) dans le plan.
    """
    if not _entity_targets_ile_de_france_region(entities):
        return
    for call in plan.api_calls:
        if call.source != "sirene" or call.action != "search":
            continue
        p = call.params
        if p.get("departement") == "75" and not p.get("code_commune"):
            p.pop("departement", None)
            if str(p.get("region") or "").strip() != "11":
                p["region"] = "11"
            plog("sirene_plan_patch_idf", detail="departement_75_retire_region_11")


def _siege_geo_constraints(p: dict) -> dict[str, str] | None:
    g: dict[str, str] = {}
    for k in ("code_commune", "departement", "region"):
        v = p.get(k)
        if v is None or v == "":
            continue
        s = str(v).strip()
        if s:
            g[k] = s
    return g or None


def _siege_matches_geo(siege: dict, g: dict[str, str]) -> bool:
    if "code_commune" in g:
        allowed = {x.strip() for x in g["code_commune"].split(",") if x.strip()}
        if allowed and siege.get("commune") not in allowed:
            return False
    if "departement" in g and siege.get("departement") != g["departement"]:
        return False
    if "region" in g and siege.get("region") != g["region"]:
        return False
    return True

TRANCHE_LABELS = {
    "00": "0 salarié", "01": "1-2", "02": "3-5", "03": "6-9",
    "11": "10-19", "12": "20-49", "21": "50-99", "22": "100-199",
    "31": "200-249", "32": "250-499", "41": "500-999", "42": "1000-1999",
    "51": "2000-4999", "52": "5000-9999", "53": "10000+",
}


def _parse_company(raw: dict) -> CompanyResult:
    siege = raw.get("siege", {})
    dirigeants = raw.get("dirigeants", [])

    dirigeant_nom, dirigeant_prenom, dirigeant_fonction = "", "", ""
    priority_titles = ["président", "directeur général", "gérant", "pdg", "dirigeant"]
    for d in dirigeants:
        qualite = (d.get("qualite") or d.get("fonction") or "").lower()
        if any(k in qualite for k in priority_titles):
            dirigeant_prenom = d.get("prenom") or d.get("prenoms") or ""
            dirigeant_nom = d.get("nom") or ""
            dirigeant_fonction = d.get("qualite") or d.get("fonction") or ""
            break
    if not dirigeant_nom and dirigeants:
        d = dirigeants[0]
        dirigeant_prenom = d.get("prenom") or d.get("prenoms") or ""
        dirigeant_nom = d.get("nom") or ""
        dirigeant_fonction = d.get("qualite") or d.get("fonction") or ""

    addr_parts = []
    for field in ["numero_voie", "type_voie", "libelle_voie"]:
        val = siege.get(field)
        if val:
            addr_parts.append(str(val))

    tranche = raw.get("tranche_effectif_salarie") or ""

    return CompanyResult(
        siren=raw.get("siren", ""),
        siret=siege.get("siret"),
        nom=raw.get("nom_complet", ""),
        activite_principale=raw.get("activite_principale"),
        libelle_activite=raw.get("libelle_activite_principale"),
        adresse=" ".join(addr_parts) if addr_parts else None,
        code_postal=siege.get("code_postal"),
        ville=siege.get("libelle_commune"),
        region=siege.get("region"),
        departement=siege.get("departement"),
        tranche_effectif=tranche,
        effectif_label=TRANCHE_LABELS.get(tranche, tranche),
        date_creation=raw.get("date_creation"),
        forme_juridique=str(raw.get("nature_juridique", "")),
        dirigeant_nom=dirigeant_nom or None,
        dirigeant_prenom=dirigeant_prenom or None,
        dirigeant_fonction=dirigeant_fonction or None,
        lien_annuaire=f"https://annuaire-entreprises.data.gouv.fr/entreprise/{raw.get('siren', '')}",
    )


async def search_sirene(params: dict, max_pages: int = 20) -> list[CompanyResult]:
    """Search the SIRENE API with given parameters, paginating through results."""
    results: list[CompanyResult] = []
    seen_sirens: set[str] = set()

    params = normalize_recherche_entreprises_params(dict(params))
    siege_geo = _siege_geo_constraints(params)

    params.setdefault("per_page", 25)
    params.setdefault("etat_administratif", "A")

    naf_filter = None
    if "activite_principale_filter" in params:
        naf_filter = params.pop("activite_principale_filter")

    plog(
        "sirene_search_start",
        params_after_normalize=params,
        siege_geo_filter=siege_geo,
        naf_prefix_filter=naf_filter,
    )

    async with httpx.AsyncClient(timeout=15.0) as client:
        for page in range(1, max_pages + 1):
            params["page"] = page

            try:
                resp = await client.get(BASE_URL, params=params)
                if resp.status_code == 429:
                    await asyncio.sleep(5)
                    resp = await client.get(BASE_URL, params=params)
                resp.raise_for_status()
                data = resp.json()
            except Exception as e:
                plog(
                    "sirene_request_failed",
                    page=page,
                    url=BASE_URL,
                    error=repr(e),
                    traceback_tail=traceback.format_exc()[-1500:],
                )
                break

            if data.get("erreur"):
                plog(
                    "sirene_api_error_body",
                    page=page,
                    http_status=resp.status_code,
                    erreur=data.get("erreur"),
                )
                break

            raw_results = data.get("results", [])
            total = data.get("total_results", 0)

            if not raw_results:
                plog("sirene_empty_page", page=page, total_results_api=total)
                break

            skipped_dup = skipped_geo = skipped_naf = 0
            kept_page = 0

            for r in raw_results:
                siren = r.get("siren")
                if not siren:
                    continue
                if siren in seen_sirens:
                    skipped_dup += 1
                    continue

                if siege_geo:
                    siege = r.get("siege") or {}
                    if not _siege_matches_geo(siege, siege_geo):
                        skipped_geo += 1
                        if skipped_geo <= 3 and page == 1:
                            plog(
                                "sirene_sample_skipped_geo",
                                siren=siren,
                                nom=(r.get("nom_complet") or "")[:60],
                                siege_commune=siege.get("commune"),
                                siege_ville=siege.get("libelle_commune"),
                                siege_dept=siege.get("departement"),
                                siege_region=siege.get("region"),
                            )
                        continue

                if naf_filter:
                    activite = r.get("activite_principale", "")
                    if activite and not activite.startswith(naf_filter):
                        skipped_naf += 1
                        continue

                seen_sirens.add(siren)
                results.append(_parse_company(r))
                kept_page += 1

            plog(
                "sirene_page_summary",
                page=page,
                http_status=resp.status_code,
                total_results_api=total,
                raw_batch=len(raw_results),
                kept_this_page=kept_page,
                skipped_dup=skipped_dup,
                skipped_geo=skipped_geo,
                skipped_naf=skipped_naf,
                cumul_kept=len(results),
            )

            if len(results) >= settings.MAX_RESULTS_PER_QUERY or page * 25 >= total:
                break

            await asyncio.sleep(0.15)

    plog("sirene_search_done", total_kept=len(results))
    return results


async def search_by_text(query: str, max_results: int = 100) -> list[CompanyResult]:
    """Simple text search on SIRENE."""
    params = {
        "q": query,
        "per_page": 25,
        "etat_administratif": "A",
    }
    max_pages = min(max_results // 25 + 1, 20)
    return await search_sirene(params, max_pages=max_pages)
