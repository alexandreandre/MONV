"""
Couche 3 — Moteur d'exécution API
Exécute le plan de l'orchestrateur, agrège et déduplique les résultats.
"""

from config import settings
from models.schemas import ExecutionPlan, CompanyResult, SearchResults
from services.sirene import search_sirene
from services.pappers import search_pappers, get_company_dirigeants, get_company_finances
from services.google_places import search_google_places
from services.orchestrator import extend_columns_for_plan
from utils.pipeline_log import plog

MAX_TOTAL_RESULTS = settings.MAX_RESULTS_PER_QUERY * 4


def _safe_float(value: object) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


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


def _dedup_key(r: CompanyResult) -> str:
    """Clé de déduplication : SIREN si disponible, sinon nom+ville normalisés."""
    if r.siren:
        return f"siren:{r.siren}"
    return f"name:{(r.nom or '').lower().strip()}|{(r.ville or '').lower().strip()}"


async def execute_plan(plan: ExecutionPlan) -> SearchResults:
    """Execute all API calls from the plan and merge results."""
    all_results: list[CompanyResult] = []
    seen_keys: set[str] = set()

    sorted_calls = sorted(plan.api_calls, key=lambda c: c.priority)

    for call in sorted_calls:
        if len(all_results) >= MAX_TOTAL_RESULTS and call.action == "search":
            plog("execute_plan_cap_reached", total=len(all_results),
                 skipped_source=call.source, skipped_action=call.action)
            continue

        if call.source == "google_places" and call.action == "search":
            plog("api_call_start", source=call.source, action=call.action, params=call.params)
            results = await search_google_places(
                query=call.params.get("query", ""),
                location=call.params.get("location"),
            )
            plog("api_call_end", source=call.source, action=call.action, nb=len(results))
            for r in results:
                key = _dedup_key(r)
                if key not in seen_keys:
                    seen_keys.add(key)
                    all_results.append(r)

        elif call.source == "sirene" and call.action == "search":
            plog("api_call_start", source=call.source, action=call.action, params=call.params)
            results = await search_sirene(call.params)
            plog("api_call_end", source=call.source, action=call.action, nb=len(results))
            for r in results:
                key = _dedup_key(r)
                if key not in seen_keys:
                    seen_keys.add(key)
                    all_results.append(r)
                else:
                    _merge_result(all_results, r)

        elif call.source == "pappers" and call.action == "search":
            plog("api_call_start", source=call.source, action=call.action, params=call.params)
            results = await search_pappers(call.params)
            plog("api_call_end", source=call.source, action=call.action, nb=len(results))
            for r in results:
                key = _dedup_key(r)
                if key not in seen_keys:
                    seen_keys.add(key)
                    all_results.append(r)
                else:
                    _merge_result(all_results, r)

        elif call.source == "pappers" and call.action == "get_dirigeants":
            plog("api_call_start", source=call.source, action=call.action, nb_targets=min(50, len(all_results)))
            for result in all_results[:50]:
                dir_data = await get_company_dirigeants(result.siren)
                reps = dir_data.get("representants", [])
                if reps:
                    first = reps[0]
                    if not result.dirigeant_nom:
                        result.dirigeant_nom = first.get("nom") or first.get("nom_complet", "")
                        result.dirigeant_prenom = first.get("prenom", "")
                        result.dirigeant_fonction = first.get("qualite", "")
            plog("api_call_end", source=call.source, action=call.action)

        elif call.source == "pappers" and call.action == "get_finances":
            plog("api_call_start", source=call.source, action=call.action, nb_targets=min(50, len(all_results)))
            for result in all_results[:50]:
                fin_data = await get_company_finances(result.siren)
                finances = fin_data.get("finances", [])
                cap_co = fin_data.get("capital_social")
                if cap_co is not None:
                    cap_co = _safe_float(cap_co)
                if finances and isinstance(finances, list) and finances:
                    last = finances[0]
                    if isinstance(last, dict):
                        _apply_finance_row(result, last, cap_co)
            plog("api_call_end", source=call.source, action=call.action)

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

    cols = extend_columns_for_plan(plan.columns, plan.api_calls)
    return SearchResults(
        total=len(all_results),
        results=all_results,
        columns=cols,
        credits_required=plan.estimated_credits,
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
    if new.tranche_effectif and not existing.tranche_effectif:
        existing.tranche_effectif = new.tranche_effectif
        existing.effectif_label = new.effectif_label
    if new.date_creation and not existing.date_creation:
        existing.date_creation = new.date_creation
    if new.lien_annuaire and not existing.lien_annuaire:
        existing.lien_annuaire = new.lien_annuaire
