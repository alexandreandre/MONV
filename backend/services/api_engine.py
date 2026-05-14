"""
Couche 3 — Moteur d'exécution API
Exécute le plan de l'orchestrateur, agrège et déduplique les résultats.

Le graphe admin (``agent_registry``) expose une étape « fusion + dédoublonnage » distincte des
connecteurs HTTP : tout vit ici dans ``execute_plan``, mais la topologie documente le contrat
**une liste unifiée → un seul scoring pertinence** côté chat / Atelier.
"""

import asyncio
import time

from config import settings
from models.schemas import APICall, BusinessSignal, ExecutionPlan, CompanyResult, SearchResults
from services.sirene import search_sirene
from services.pappers import (
    enrich_missing_contacts_pappers_fr,
    get_company_dirigeants,
    get_company_finances,
    search_pappers,
)
from services.google_places import search_google_places
from services.orchestrator import extend_columns_for_plan
from services.modes import apply_result_columns_for_mode, normalize_mode
from services.bodacc import get_bodacc_signals_for_siren
from services.marches_publics import get_marches_for_siren
from services.signals import detect_signals
from services.geocoding import geocode_results
from utils.pipeline_log import plog

MAX_TOTAL_RESULTS = settings.MAX_RESULTS_PER_QUERY * 4


def _safe_float(value: object) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _compute_tva(siren: str) -> str | None:
    """N° TVA intracommunautaire français depuis un SIREN à 9 chiffres."""
    s = siren.strip().replace(" ", "")
    if not s.isdigit() or len(s) != 9:
        return None
    key = (12 + 3 * (int(s) % 97)) % 97
    return f"FR{key:02d}{s}"


def _apply_finance_row(result: CompanyResult, last: dict, capital_from_company: float | None) -> None:
    """Fusionne la ligne comptable la plus récente + capital issu de la fiche entreprise."""
    y = last.get("annee") or last.get("year")
    if y is not None and result.annee_dernier_ca is None:
        try:
            result.annee_dernier_ca = int(y)
        except (TypeError, ValueError):
            pass
    dc = last.get("date_cloture_exercice") or last.get("date_cloture")
    if dc and not result.date_cloture_exercice:
        result.date_cloture_exercice = str(dc)
    if not result.chiffre_affaires:
        result.chiffre_affaires = _safe_float(last.get("chiffre_affaires"))
    if not result.resultat_net:
        result.resultat_net = _safe_float(last.get("resultat") or last.get("resultat_net"))
    if not result.marge_brute:
        result.marge_brute = _safe_float(last.get("marge_brute"))
    if not result.ebe:
        result.ebe = _safe_float(
            last.get("excedent_brut_exploitation") or last.get("ebe")
        )
    if not result.capitaux_propres:
        result.capitaux_propres = _safe_float(last.get("capitaux_propres"))
    if not result.effectif_financier:
        result.effectif_financier = _safe_float(
            last.get("effectif") or last.get("effectif_moyen")
        )
    if capital_from_company is not None and result.capital_social is None:
        result.capital_social = capital_from_company


def _apply_previous_year(result: CompanyResult, finances: list[dict]) -> None:
    """Peuple les champs N-1 et la variation CA depuis l'historique financier."""
    if len(finances) < 2:
        return
    prev = finances[1]
    if result.ca_n_minus_1 is None:
        result.ca_n_minus_1 = _safe_float(prev.get("chiffre_affaires"))
    if result.resultat_n_minus_1 is None:
        result.resultat_n_minus_1 = _safe_float(prev.get("resultat") or prev.get("resultat_net"))
    ay = prev.get("annee") or prev.get("year")
    if ay is not None and result.annee_n_minus_1 is None:
        try:
            result.annee_n_minus_1 = int(ay)
        except (TypeError, ValueError):
            pass
    if result.chiffre_affaires is not None and result.ca_n_minus_1 is not None and result.ca_n_minus_1 != 0:
        result.variation_ca_pct = round(
            (result.chiffre_affaires - result.ca_n_minus_1) / abs(result.ca_n_minus_1) * 100, 1
        )


def _dedup_key(r: CompanyResult) -> str:
    """Clé de déduplication : SIREN si disponible, sinon nom+ville normalisés."""
    if r.siren:
        return f"siren:{r.siren}"
    return f"name:{(r.nom or '').lower().strip()}|{(r.ville or '').lower().strip()}"


_SEARCH_PARALLEL_SOURCES = frozenset({"sirene", "google_places", "pappers"})


def _is_parallel_search_call(c: APICall) -> bool:
    return c.action == "search" and c.source in _SEARCH_PARALLEL_SOURCES


async def _run_search_api_call(call: APICall) -> tuple[APICall, list[CompanyResult]]:
    """Un appel search isolé (SIRENE / Places / Pappers) pour exécution parallèle."""
    if call.source == "google_places" and call.action == "search":
        plog("api_call_start", source=call.source, action=call.action, params=call.params)
        results = await search_google_places(
            query=call.params.get("query", ""),
            location=call.params.get("location"),
        )
        plog("api_call_end", source=call.source, action=call.action, nb=len(results))
        return call, results
    if call.source == "sirene" and call.action == "search":
        plog("api_call_start", source=call.source, action=call.action, params=call.params)
        results = await search_sirene(call.params)
        plog("api_call_end", source=call.source, action=call.action, nb=len(results))
        return call, results
    if call.source == "pappers" and call.action == "search":
        plog("api_call_start", source=call.source, action=call.action, params=call.params)
        results = await search_pappers(call.params)
        plog("api_call_end", source=call.source, action=call.action, nb=len(results))
        return call, results
    raise ValueError(f"unexpected search call: {call.source} {call.action}")


def _ingest_google_results(
    results: list[CompanyResult],
    all_results: list[CompanyResult],
    seen_keys: set[str],
) -> None:
    for r in results:
        if len(all_results) >= MAX_TOTAL_RESULTS:
            return
        key = _dedup_key(r)
        if key not in seen_keys:
            seen_keys.add(key)
            all_results.append(r)


def _ingest_sirene_results(
    results: list[CompanyResult],
    all_results: list[CompanyResult],
    seen_keys: set[str],
) -> None:
    for r in results:
        if len(all_results) >= MAX_TOTAL_RESULTS:
            return
        key = _dedup_key(r)
        if key not in seen_keys:
            seen_keys.add(key)
            all_results.append(r)
        else:
            _merge_result(all_results, r)


def _ingest_pappers_search_results(
    results: list[CompanyResult],
    all_results: list[CompanyResult],
    seen_keys: set[str],
) -> None:
    for r in results:
        if len(all_results) >= MAX_TOTAL_RESULTS:
            return
        key = _dedup_key(r)
        if key not in seen_keys:
            seen_keys.add(key)
            all_results.append(r)
        else:
            _merge_result(all_results, r)


def _ingest_search_batch(
    ordered: list[tuple[APICall, list[CompanyResult]]],
    all_results: list[CompanyResult],
    seen_keys: set[str],
) -> None:
    """Applique les résultats dans l'ordre du plan (déterminisme dédup)."""
    for call, results in ordered:
        if call.source == "google_places":
            _ingest_google_results(results, all_results, seen_keys)
        elif call.source == "sirene":
            _ingest_sirene_results(results, all_results, seen_keys)
        elif call.source == "pappers":
            _ingest_pappers_search_results(results, all_results, seen_keys)


async def execute_plan(plan: ExecutionPlan, *, mode: str | None = None) -> SearchResults:
    """Execute all API calls from the plan and merge results."""
    t_plan = time.perf_counter()
    timing_ms: dict[str, float] = {}

    all_results: list[CompanyResult] = []
    seen_keys: set[str] = set()

    _finances_by_siren: dict[str, list[dict]] = {}
    _dirigeants_by_siren: dict[str, list[dict]] = {}
    _bodacc_by_siren: dict[str, list[BusinessSignal]] = {}
    _marches_publics_by_siren: dict[str, BusinessSignal] = {}

    sorted_calls = sorted(plan.api_calls, key=lambda c: c.priority)
    n_calls = len(sorted_calls)

    t_loop_start = time.perf_counter()
    i = 0
    while i < n_calls:
        call = sorted_calls[i]

        if len(all_results) >= MAX_TOTAL_RESULTS and call.action == "search":
            plog("execute_plan_cap_reached", total=len(all_results),
                 skipped_source=call.source, skipped_action=call.action)
            i += 1
            continue

        if _is_parallel_search_call(call):
            prio = call.priority
            group: list[APICall] = []
            j = i
            while j < n_calls and _is_parallel_search_call(sorted_calls[j]) and sorted_calls[j].priority == prio:
                if len(all_results) >= MAX_TOTAL_RESULTS:
                    break
                group.append(sorted_calls[j])
                j += 1
            if group:
                raw = await asyncio.gather(
                    *[_run_search_api_call(c) for c in group],
                    return_exceptions=True,
                )
                ordered: list[tuple[APICall, list[CompanyResult]]] = []
                for part in raw:
                    if isinstance(part, BaseException):
                        plog("parallel_search_error", error=repr(part))
                        continue
                    ordered.append(part)
                _ingest_search_batch(ordered, all_results, seen_keys)
                i = j
                continue
            i += 1
            continue

        if call.source == "pappers" and call.action == "get_dirigeants":
            plog("api_call_start", source=call.source, action=call.action, nb_targets=min(50, len(all_results)))
            targets = [r for r in all_results[:50] if r.siren]
            sem_d = asyncio.Semaphore(12)

            async def _one_dirigeant(result: CompanyResult) -> tuple[CompanyResult, object]:
                async with sem_d:
                    try:
                        return result, await get_company_dirigeants(result.siren)
                    except Exception as ex:
                        return result, ex

            dir_pairs = await asyncio.gather(*[_one_dirigeant(r) for r in targets], return_exceptions=True)
            for item in dir_pairs:
                if isinstance(item, Exception):
                    plog("get_dirigeants_row_error", error=repr(item))
                    continue
                result, dir_data = item
                if isinstance(dir_data, Exception):
                    plog("get_dirigeants_row_error", error=repr(dir_data))
                    continue
                if not isinstance(dir_data, dict):
                    continue
                reps = dir_data.get("representants", [])
                if reps:
                    _dirigeants_by_siren[result.siren] = reps
                    first = reps[0]
                    if not result.dirigeant_nom:
                        result.dirigeant_nom = first.get("nom") or first.get("nom_complet", "")
                        result.dirigeant_prenom = first.get("prenom", "")
                        result.dirigeant_fonction = first.get("qualite", "")
                    if len(reps) >= 2 and not result.dirigeant_2_nom:
                        second = reps[1]
                        result.dirigeant_2_nom = second.get("nom") or second.get("nom_complet", "")
                        result.dirigeant_2_fonction = second.get("qualite", "")
            plog("api_call_end", source=call.source, action=call.action)

        elif call.source == "bodacc" and call.action == "get_signals":
            plog("api_call_start", source="bodacc", action="get_signals",
                 nb_targets=min(20, len(all_results)))
            targets_b = [r for r in all_results[:20] if r.siren]
            sem_b = asyncio.Semaphore(8)

            async def _one_bodacc(result: CompanyResult) -> tuple[CompanyResult, object]:
                async with sem_b:
                    try:
                        return result, await get_bodacc_signals_for_siren(result.siren)
                    except Exception as ex:
                        return result, ex

            bod_pairs = await asyncio.gather(*[_one_bodacc(r) for r in targets_b], return_exceptions=True)
            for item in bod_pairs:
                if isinstance(item, Exception):
                    plog("bodacc_row_error", error=repr(item))
                    continue
                result, bodacc_signals = item
                if isinstance(bodacc_signals, Exception):
                    plog("bodacc_row_error", error=repr(bodacc_signals))
                    continue
                if not isinstance(bodacc_signals, list):
                    continue
                bucket = _bodacc_by_siren.setdefault(result.siren, [])
                existing_types = {s.type for s in bucket}
                for sig in bodacc_signals:
                    if sig["type"] not in existing_types:
                        bucket.append(BusinessSignal(
                            type=sig["type"],
                            label=sig["label"],
                            detail=sig.get("detail"),
                            severity=sig["severity"],
                        ))
                        existing_types.add(sig["type"])
            plog("api_call_end", source="bodacc", action="get_signals")

        elif call.source == "marches_publics" and call.action == "get_marches":
            plog("api_call_start", source="marches_publics",
                 action="get_marches", nb_targets=min(20, len(all_results)))
            targets = all_results[:20]
            marches_list = await asyncio.gather(
                *[get_marches_for_siren(r.siren) for r in targets if r.siren],
                return_exceptions=True,
            )
            targets_with_siren = [r for r in targets if r.siren]
            for result, marches in zip(targets_with_siren, marches_list):
                if isinstance(marches, Exception) or not marches:
                    continue
                nb = len(marches)
                montant_total = sum(
                    (_safe_float(m.get("montant")) or 0)
                    for m in marches
                    if m.get("montant") is not None
                )
                _marches_publics_by_siren[result.siren] = BusinessSignal(
                    type="marche_public",
                    label=f"Marchés publics ({nb})",
                    detail=f"{nb} marché(s) — {montant_total / 1000:.0f} k€ cumulés",
                    severity="positive",
                )
            plog("api_call_end", source="marches_publics",
                 action="get_marches")

        elif call.source == "pappers" and call.action == "get_finances":
            plog("api_call_start", source=call.source, action=call.action, nb_targets=min(50, len(all_results)))
            targets_f = [r for r in all_results[:50] if r.siren]
            sem_f = asyncio.Semaphore(12)

            async def _one_finance(result: CompanyResult) -> tuple[CompanyResult, object]:
                async with sem_f:
                    try:
                        return result, await get_company_finances(result.siren)
                    except Exception as ex:
                        return result, ex

            fin_pairs = await asyncio.gather(*[_one_finance(r) for r in targets_f], return_exceptions=True)
            for item in fin_pairs:
                if isinstance(item, Exception):
                    plog("get_finances_row_error", error=repr(item))
                    continue
                result, fin_data = item
                if isinstance(fin_data, Exception):
                    plog("get_finances_row_error", error=repr(fin_data))
                    continue
                if not isinstance(fin_data, dict):
                    continue
                finances = fin_data.get("finances", [])
                cap_co = fin_data.get("capital_social")
                if cap_co is not None:
                    cap_co = _safe_float(cap_co)
                if finances and isinstance(finances, list) and finances:
                    _finances_by_siren[result.siren] = finances
                    last = finances[0]
                    if isinstance(last, dict):
                        _apply_finance_row(result, last, cap_co)
                    _apply_previous_year(result, finances)
                tel_fd = fin_data.get("telephone")
                if tel_fd and not (result.telephone and str(result.telephone).strip()):
                    result.telephone = str(tel_fd).strip()
                web_fd = fin_data.get("site_web")
                if web_fd and not (result.site_web and str(result.site_web).strip()):
                    result.site_web = str(web_fd).strip()
            plog("api_call_end", source=call.source, action=call.action)

        i += 1

    timing_ms["execute_plan_api_loop_ms"] = (time.perf_counter() - t_loop_start) * 1000

    t_broaden = time.perf_counter()
    if len(all_results) < 5:
        for call in sorted_calls:
            if call.source != "sirene" or call.action != "search":
                continue

            # Stratégie 1 : retirer "q" si d'autres filtres existent
            if call.params.get("q"):
                has_filter = (
                    call.params.get("activite_principale")
                    or call.params.get("section_activite_principale")
                    or call.params.get("region")
                    or call.params.get("departement")
                    or call.params.get("code_commune")
                )
                if has_filter:
                    broadened = {k: v for k, v in call.params.items() if k != "q"}
                    plog("sirene_broaden_retry", original_q=call.params["q"], params=broadened)
                    results = await search_sirene(broadened, max_pages=5)
                    plog("sirene_broaden_result", nb=len(results))
                    for r in results:
                        key = _dedup_key(r)
                        if key not in seen_keys:
                            seen_keys.add(key)
                            all_results.append(r)

            # Stratégie 2 : élargir code_commune → departement
            if len(all_results) < 5 and call.params.get("code_commune"):
                cc = str(call.params["code_commune"])
                dept = cc[:2] if not cc.startswith("97") else cc[:3]
                broadened = {k: v for k, v in call.params.items() if k != "code_commune"}
                broadened["departement"] = dept
                plog("sirene_broaden_geo", from_commune=cc, to_dept=dept)
                results = await search_sirene(broadened, max_pages=5)
                plog("sirene_broaden_geo_result", nb=len(results))
                for r in results:
                    key = _dedup_key(r)
                    if key not in seen_keys:
                        seen_keys.add(key)
                        all_results.append(r)

            # Stratégie 3 : élargir departement → region
            if len(all_results) < 5 and call.params.get("departement") and not call.params.get("code_commune"):
                broadened = {k: v for k, v in call.params.items() if k != "departement"}
                if call.params.get("region"):
                    pass
                else:
                    plog("sirene_broaden_dept_drop", dept=call.params["departement"])
                    results = await search_sirene(broadened, max_pages=5)
                    plog("sirene_broaden_dept_result", nb=len(results))
                    for r in results:
                        key = _dedup_key(r)
                        if key not in seen_keys:
                            seen_keys.add(key)
                            all_results.append(r)

    timing_ms["execute_plan_broaden_ms"] = (time.perf_counter() - t_broaden) * 1000

    t_signals = time.perf_counter()
    for result in all_results:
        if not result.numero_tva and result.siren:
            result.numero_tva = _compute_tva(result.siren)
        result.signaux = detect_signals(
            result,
            finances=_finances_by_siren.get(result.siren, []),
            representants=_dirigeants_by_siren.get(result.siren, []),
            mode=normalize_mode(mode),
        )
        for sig in _bodacc_by_siren.get(result.siren, []):
            existing_types = {s.type for s in result.signaux}
            if sig.type not in existing_types:
                result.signaux.append(sig)
        sig_mp = _marches_publics_by_siren.get(result.siren)
        if sig_mp is not None:
            existing_types_mp = {s.type for s in result.signaux}
            if sig_mp.type not in existing_types_mp:
                result.signaux.append(sig_mp)

    timing_ms["execute_plan_signals_ms"] = (time.perf_counter() - t_signals) * 1000

    cols = extend_columns_for_plan(plan.columns, plan.api_calls)
    nm = normalize_mode(mode)
    # Prospection : ``signaux`` est déjà dans le panneau figé (``apply_result_columns_for_mode``).
    if nm != "prospection" and any(r.signaux for r in all_results) and "signaux" not in cols:
        cols.insert(0, "signaux")
    cols = apply_result_columns_for_mode(cols, nm)

    plog("signals_detected",
         total_with_signals=sum(1 for r in all_results if r.signaux),
         total_results=len(all_results))

    t_geo = time.perf_counter()
    await geocode_results(all_results)
    timing_ms["geocode_ms"] = (time.perf_counter() - t_geo) * 1000

    t_pap = time.perf_counter()
    if normalize_mode(mode) not in ("benchmark", "rachat"):
        max_contact = max(1, int(getattr(settings, "PAPPERS_CONTACT_ENRICH_MAX", 60) or 60))
        await enrich_missing_contacts_pappers_fr(all_results, max_companies=max_contact)
    timing_ms["pappers_contacts_enrich_ms"] = (time.perf_counter() - t_pap) * 1000

    timing_ms["execute_plan_total_ms"] = (time.perf_counter() - t_plan) * 1000

    return SearchResults(
        total=len(all_results),
        results=all_results,
        columns=cols,
        credits_required=plan.estimated_credits,
        timing_ms=timing_ms,
    )


def _merge_result(results: list[CompanyResult], new: CompanyResult) -> None:
    """Merge enriched data from a secondary source into existing results."""
    for existing in results:
        if existing.siren and new.siren and existing.siren == new.siren:
            _merge_fields(existing, new)
            break
        if (
            not existing.siren
            and (existing.nom or "").lower().strip() == (new.nom or "").lower().strip()
            and (existing.ville or "").lower().strip() == (new.ville or "").lower().strip()
        ):
            _merge_fields(existing, new)
            break


def _merge_fields(existing: CompanyResult, new: CompanyResult) -> None:
    if new.siren and not existing.siren:
        existing.siren = new.siren
    if new.siret and not existing.siret:
        existing.siret = new.siret
    if new.activite_principale and not existing.activite_principale:
        existing.activite_principale = new.activite_principale
    if new.libelle_activite and not existing.libelle_activite:
        existing.libelle_activite = new.libelle_activite
    if new.chiffre_affaires and not existing.chiffre_affaires:
        existing.chiffre_affaires = new.chiffre_affaires
    if new.resultat_net and not existing.resultat_net:
        existing.resultat_net = new.resultat_net
    if new.annee_dernier_ca is not None and existing.annee_dernier_ca is None:
        existing.annee_dernier_ca = new.annee_dernier_ca
    if new.date_cloture_exercice and not existing.date_cloture_exercice:
        existing.date_cloture_exercice = new.date_cloture_exercice
    if new.marge_brute is not None and existing.marge_brute is None:
        existing.marge_brute = new.marge_brute
    if new.ebe is not None and existing.ebe is None:
        existing.ebe = new.ebe
    if new.capitaux_propres is not None and existing.capitaux_propres is None:
        existing.capitaux_propres = new.capitaux_propres
    if new.effectif_financier is not None and existing.effectif_financier is None:
        existing.effectif_financier = new.effectif_financier
    if new.capital_social is not None and existing.capital_social is None:
        existing.capital_social = new.capital_social
    if new.categorie_entreprise and not existing.categorie_entreprise:
        existing.categorie_entreprise = new.categorie_entreprise
    if new.dirigeant_nom and not existing.dirigeant_nom:
        existing.dirigeant_nom = new.dirigeant_nom
        existing.dirigeant_prenom = new.dirigeant_prenom
        existing.dirigeant_fonction = new.dirigeant_fonction
    if new.site_web and not existing.site_web:
        existing.site_web = new.site_web
    if new.email and not existing.email:
        existing.email = new.email
    if new.telephone and not existing.telephone:
        existing.telephone = new.telephone
    if new.google_maps_url and not existing.google_maps_url:
        existing.google_maps_url = new.google_maps_url
    if new.latitude is not None and existing.latitude is None:
        existing.latitude = new.latitude
    if new.longitude is not None and existing.longitude is None:
        existing.longitude = new.longitude
    if new.tranche_effectif and not existing.tranche_effectif:
        existing.tranche_effectif = new.tranche_effectif
        existing.effectif_label = new.effectif_label
    if new.date_creation and not existing.date_creation:
        existing.date_creation = new.date_creation
    if new.numero_tva and not existing.numero_tva:
        existing.numero_tva = new.numero_tva
    if new.ca_n_minus_1 is not None and existing.ca_n_minus_1 is None:
        existing.ca_n_minus_1 = new.ca_n_minus_1
    if new.resultat_n_minus_1 is not None and existing.resultat_n_minus_1 is None:
        existing.resultat_n_minus_1 = new.resultat_n_minus_1
    if new.annee_n_minus_1 is not None and existing.annee_n_minus_1 is None:
        existing.annee_n_minus_1 = new.annee_n_minus_1
    if new.variation_ca_pct is not None and existing.variation_ca_pct is None:
        existing.variation_ca_pct = new.variation_ca_pct
    if new.dirigeant_2_nom and not existing.dirigeant_2_nom:
        existing.dirigeant_2_nom = new.dirigeant_2_nom
        existing.dirigeant_2_fonction = new.dirigeant_2_fonction
    if new.lien_annuaire and not existing.lien_annuaire:
        existing.lien_annuaire = new.lien_annuaire
    if new.signaux:
        existing_types = {s.type for s in existing.signaux}
        for s in new.signaux:
            if s.type not in existing_types:
                existing.signaux.append(s)
                existing_types.add(s.type)
