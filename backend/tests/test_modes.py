"""Tests des 4 modes d'usage MONV — fonctions pures, sans LLM ni Supabase."""

from __future__ import annotations

import os

import pytest

# Avant tout import applicatif : évite la vérif DB et les clés réelles.
os.environ.setdefault("SKIP_DB_VERIFY_ON_STARTUP", "true")
os.environ.setdefault("SUPABASE_URL", "https://placeholder.supabase.co")
os.environ.setdefault("SUPABASE_SERVICE_KEY", "placeholder-service-key")
# Clé Pappers vide par défaut (tests orchestrateur / modes sans appel réel).
os.environ.setdefault("PAPPERS_API_KEY", "")


from models.schemas import ChatRequest, GuardEntity, GuardResult, APICall, BusinessSignal, CompanyResult, SearchResults  # noqa: E402
from services.modes import (  # noqa: E402
    DEFAULT_MODE,
    MODE_LABELS,
    PROSPECTION_RESULT_COLUMNS,
    VALID_MODES,
    addendum_for_mode,
    apply_result_columns_for_mode,
    credits_floor_for_mode,
    normalize_mode,
    reorder_columns_for_mode,
)
from services.orchestrator import (  # noqa: E402
    _build_fallback_plan,
    _orchestrator_merged_system,
    clamp_prospection_pappers_calls,
    orchestrator_needs_niche_appendix,
)


# ── Schéma & contrat API ──────────────────────────────────────────────────────

def test_chat_request_accepts_mode():
    req = ChatRequest(message="Cherche des hôtels", mode="rachat")
    assert req.mode == "rachat"


def test_chat_request_mode_optional_for_backward_compat():
    """Une requête sans `mode` doit rester valide → pas de régression."""
    req = ChatRequest(message="Cherche des hôtels")
    assert req.mode is None


def test_chat_request_accepts_unknown_mode_string():
    """La validation du mode est tolérante côté Pydantic ; la normalisation
    se fait dans `services.modes.normalize_mode`."""
    req = ChatRequest(message="Cherche", mode="inconnu")
    assert req.mode == "inconnu"
    assert normalize_mode(req.mode) == DEFAULT_MODE


# ── Normalisation ────────────────────────────────────────────────────────────

@pytest.mark.parametrize("value", list(VALID_MODES))
def test_normalize_mode_keeps_valid_values(value):
    assert normalize_mode(value) == value


@pytest.mark.parametrize("value", [None, "", "autre", "prospect"])
def test_normalize_mode_falls_back_to_default(value):
    assert normalize_mode(value) == DEFAULT_MODE


def test_normalize_mode_legacy_fournisseurs_alias():
    assert normalize_mode("fournisseurs") == "sous_traitant"


def test_normalize_mode_legacy_client_alias():
    assert normalize_mode("client") == "benchmark"


def test_normalize_mode_legacy_achat_alias():
    assert normalize_mode("achat") == "benchmark"


def test_default_mode_is_prospection():
    assert DEFAULT_MODE == "prospection"


def test_prospection_addendum_warns_pappers_cost():
    add = addendum_for_mode("prospection").lower()
    assert "pappers" in add
    assert "interdit" in add or "retire" in add


def test_prospection_addendum_documents_columns_and_post_plan_contact_enrich():
    """Addendum : panneau colonnes + complément fiche Pappers hors plan (plafond)."""
    add = addendum_for_mode("prospection").lower()
    assert "signaux" in add
    assert "pappers_contact_enrich_max" in add
    assert "après exécution" in add or "exécution du plan" in add


def test_export_dataframe_prospection_includes_signaux_column():
    from services.export import _results_to_dataframe

    rows = [
        CompanyResult(
            siren="123456789",
            nom="ACME",
            signaux=[
                BusinessSignal(
                    type="entreprise_recente",
                    label="Entreprise récente",
                    detail="12 mois",
                    severity="info",
                )
            ],
        )
    ]
    sr = SearchResults(
        total=1,
        results=rows,
        columns=list(PROSPECTION_RESULT_COLUMNS),
        credits_required=1,
    )
    df = _results_to_dataframe(sr, rename=False, prospection_export=True)
    assert "signaux" in df.columns
    assert "Entreprise récente" in str(df["signaux"].iloc[0])


# ── Addendum prompt orchestrateur ────────────────────────────────────────────

@pytest.mark.parametrize("mode", ["sous_traitant", "benchmark", "rachat"])
def test_other_modes_have_distinct_addendum(mode):
    addendum = addendum_for_mode(mode)
    assert addendum != ""
    # Chaque addendum nomme explicitement son mode pour que le LLM le voie.
    assert "mode actif" in addendum.lower()


def test_rachat_addendum_includes_safety_clause():
    """Mode Rachat ne doit jamais produire de conseil personnalisé."""
    addendum = addendum_for_mode("rachat")
    assert "valorisation" in addendum.lower()
    assert "conseil" in addendum.lower()
    assert "ne pas appeler pappers" in addendum.lower()


def test_benchmark_addendum_includes_safety_clause():
    addendum = addendum_for_mode("benchmark")
    assert "valorisation" in addendum.lower()
    assert "secteur" in addendum.lower() or "marché" in addendum.lower()
    assert "ne pas appeler pappers" in addendum.lower()


# ── Réordonnancement des colonnes ────────────────────────────────────────────

BASE_COLUMNS = [
    "nom",
    "siren",
    "siret",
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
    "categorie_entreprise",
    "chiffre_affaires",
    "ca_n_minus_1",
    "annee_dernier_ca",
    "annee_n_minus_1",
    "resultat_net",
    "variation_ca_pct",
    "ebe",
    "capitaux_propres",
    "capital_social",
    "numero_tva",
    "site_web",
    "telephone",
    "dirigeant_nom",
    "dirigeant_fonction",
]


def test_reorder_prospection_keeps_original_order():
    cols = reorder_columns_for_mode(BASE_COLUMNS, "prospection")
    assert cols == BASE_COLUMNS


def test_apply_result_columns_prospection_fixed_panel():
    messy = ["nom", "siren", "signaux", "effectif_label", "ville"]
    assert apply_result_columns_for_mode(messy, "prospection") == PROSPECTION_RESULT_COLUMNS


def test_reorder_sous_traitant_promotes_capacity_columns():
    cols = reorder_columns_for_mode(BASE_COLUMNS, "sous_traitant")
    # Les colonnes capacité doivent apparaître juste après `nom`.
    head = cols[:8]
    assert head[0] == "nom"
    for c in ("effectif_label", "date_creation", "forme_juridique"):
        assert c in head, f"{c} attendu dans le top 8 du mode sous_traitant"
    # Aucune colonne perdue.
    assert set(cols) == set(BASE_COLUMNS)


def test_reorder_rachat_promotes_sirene_panel_columns():
    cols = reorder_columns_for_mode(BASE_COLUMNS, "rachat")
    # nom + 14 colonnes prio rachat → au moins 15 entrées avant le « reste »
    head = cols[:16]
    for c in (
        "categorie_entreprise",
        "date_creation",
        "effectif_label",
        "chiffre_affaires",
        "variation_ca_pct",
        "resultat_net",
        "ca_n_minus_1",
        "annee_dernier_ca",
        "dirigeant_nom",
        "dirigeant_fonction",
        "forme_juridique",
        "siren",
        "ville",
        "region",
    ):
        assert c in head, f"{c} attendu dans le haut du mode rachat"
    assert set(cols) == set(BASE_COLUMNS)


def test_reorder_benchmark_promotes_sirene_panel_columns():
    cols = reorder_columns_for_mode(BASE_COLUMNS, "benchmark")
    head = cols[:12]
    for c in (
        "libelle_activite",
        "activite_principale",
        "categorie_entreprise",
        "effectif_label",
        "date_creation",
        "forme_juridique",
        "dirigeant_nom",
    ):
        assert c in head, f"{c} attendu dans le top 12 du mode benchmark"


def test_reorder_is_stable_when_priority_columns_absent():
    """Si une colonne prio n'existe pas dans la liste, pas d'ajout magique."""
    minimal = ["nom", "siren", "ville"]
    cols = reorder_columns_for_mode(minimal, "rachat")
    assert set(cols) == set(minimal)


# ── Crédits plancher ──────────────────────────────────────────────────────────

def test_credits_floor_per_mode():
    assert credits_floor_for_mode("prospection") == 1
    assert credits_floor_for_mode("sous_traitant") == 1
    assert credits_floor_for_mode("benchmark") == 1
    assert credits_floor_for_mode("rachat") == 1


# ── Plan fallback (sans LLM) ──────────────────────────────────────────────────

def _make_guard_result(query: str = "PME du BTP à Lyon") -> GuardResult:
    return GuardResult(
        intent="recherche_entreprise",
        entities=GuardEntity(
            secteur="BTP",
            code_naf="41",
            localisation="Lyon",
            mots_cles=["BTP"],
        ),
        confidence=0.9,
        clarification_needed=False,
        original_query=query,
    )


@pytest.mark.parametrize("mode", list(VALID_MODES))
def test_fallback_plan_works_for_every_mode(mode):
    plan = _build_fallback_plan(_make_guard_result(), mode)
    assert plan.api_calls, f"Le plan fallback ne doit pas être vide pour {mode}"
    assert plan.estimated_credits >= credits_floor_for_mode(mode)
    # `nom` reste en tête, pas de duplication.
    assert plan.columns[0] == "nom"
    assert len(plan.columns) == len(set(plan.columns))
    if mode == "prospection":
        assert plan.columns == PROSPECTION_RESULT_COLUMNS


def test_fallback_plan_rachat_excludes_pappers_when_key_present(monkeypatch):
    """Rachat n'injecte plus Pappers même si la clé est configurée."""
    monkeypatch.setattr("services.orchestrator.settings.PAPPERS_API_KEY", "fake-key")
    plan = _build_fallback_plan(_make_guard_result(), "rachat")
    pappers_calls = [c for c in plan.api_calls if c.source == "pappers"]
    assert pappers_calls == []


def test_fallback_plan_benchmark_excludes_pappers_when_key_present(monkeypatch):
    """Benchmark n'injecte plus Pappers même si la clé est configurée."""
    monkeypatch.setattr("services.orchestrator.settings.PAPPERS_API_KEY", "fake-key")
    plan = _build_fallback_plan(_make_guard_result(), "benchmark")
    pappers_calls = [c for c in plan.api_calls if c.source == "pappers"]
    assert pappers_calls == []


def test_fallback_plan_rachat_has_sirene_without_pappers(monkeypatch):
    """Mode rachat : plan SIRENE (+ BODACC), jamais Pappers."""
    monkeypatch.setattr("services.orchestrator.settings.PAPPERS_API_KEY", "")
    plan = _build_fallback_plan(_make_guard_result(), "rachat")
    assert [c for c in plan.api_calls if c.source == "pappers"] == []
    assert any(c.source == "sirene" for c in plan.api_calls)
    assert any(c.source == "bodacc" for c in plan.api_calls)


def test_fallback_plan_default_mode_matches_prospection():
    """Régression : un appel sans mode = comportement prospection."""
    plan_default = _build_fallback_plan(_make_guard_result())
    plan_prospection = _build_fallback_plan(_make_guard_result(), "prospection")
    assert plan_default.columns == plan_prospection.columns
    assert plan_default.estimated_credits == plan_prospection.estimated_credits


# ── Clamp Pappers (prospection) ───────────────────────────────────────────────


def test_clamp_prospection_strips_pappers_search_without_signals():
    g = _make_guard_result("PME BTP Lyon")
    calls = [
        APICall(source="sirene", action="search", params={"departement": "69", "per_page": 25}, priority=1),
        APICall(source="pappers", action="search", params={"q": "BTP"}, priority=2),
    ]
    clamp_prospection_pappers_calls(calls, g)
    assert [c.source for c in calls] == ["sirene"]


def test_clamp_prospection_keeps_pappers_search_when_ca_bounds_on_entity():
    g = GuardResult(
        intent="recherche_entreprise",
        entities=GuardEntity(ca_min=100_000, ca_max=5_000_000, region="11"),
        confidence=0.9,
        original_query="PME IDF",
    )
    calls = [
        APICall(source="sirene", action="search", params={"region": "11", "per_page": 25}, priority=1),
        APICall(source="pappers", action="search", params={"ca_min": 100000}, priority=2),
    ]
    clamp_prospection_pappers_calls(calls, g)
    assert len(calls) == 2


def test_clamp_prospection_keeps_get_dirigeants_when_narrow_commune():
    g = _make_guard_result()
    calls = [
        APICall(source="sirene", action="search", params={"code_commune": "69123", "per_page": 25}, priority=1),
        APICall(source="pappers", action="get_dirigeants", params={}, priority=3),
    ]
    clamp_prospection_pappers_calls(calls, g)
    assert [c.action for c in calls if c.source == "pappers"] == ["get_dirigeants"]


def test_clamp_prospection_strips_get_finances_without_need():
    g = _make_guard_result()
    calls = [
        APICall(source="sirene", action="search", params={"departement": "69"}, priority=1),
        APICall(source="pappers", action="get_finances", params={}, priority=3),
    ]
    clamp_prospection_pappers_calls(calls, g)
    assert [c.source for c in calls] == ["sirene"]


def test_clamp_prospection_keeps_get_finances_when_user_asks_ca():
    g = GuardResult(
        intent="recherche_entreprise",
        entities=GuardEntity(secteur="BTP"),
        confidence=0.9,
        original_query="Liste des entreprises avec leur chiffre d'affaires à Lyon",
    )
    calls = [
        APICall(source="sirene", action="search", params={"departement": "69"}, priority=1),
        APICall(source="pappers", action="get_finances", params={}, priority=3),
    ]
    clamp_prospection_pappers_calls(calls, g)
    assert any(c.source == "pappers" and c.action == "get_finances" for c in calls)


def test_clamp_prospection_recherche_dirigeant_keeps_get_dirigeants():
    g = GuardResult(
        intent="recherche_dirigeant",
        entities=GuardEntity(secteur="BTP", localisation="Lyon"),
        confidence=0.9,
        original_query="Qui dirige les entreprises du BTP à Lyon",
    )
    calls = [
        APICall(source="sirene", action="search", params={"departement": "69"}, priority=1),
        APICall(source="pappers", action="get_dirigeants", params={}, priority=3),
    ]
    clamp_prospection_pappers_calls(calls, g)
    assert any(c.source == "pappers" and c.action == "get_dirigeants" for c in calls)


def test_clamp_prospection_enrichissement_keeps_get_finances():
    g = GuardResult(
        intent="enrichissement",
        entities=GuardEntity(),
        confidence=0.95,
        original_query="Enrichis les fiches",
    )
    calls = [
        APICall(source="sirene", action="search", params={"departement": "69"}, priority=1),
        APICall(source="pappers", action="get_finances", params={}, priority=3),
    ]
    clamp_prospection_pappers_calls(calls, g)
    assert any(c.source == "pappers" and c.action == "get_finances" for c in calls)


# ── Prompt orchestrateur : annexe niche conditionnelle ───────────────────────


def test_orchestrator_needs_niche_appendix_false_without_geo():
    g = GuardResult(
        intent="recherche_entreprise",
        entities=GuardEntity(mots_cles=["padel"]),
        confidence=0.9,
        original_query="padel",
    )
    assert orchestrator_needs_niche_appendix(g) is False


def test_orchestrator_needs_niche_appendix_true_with_geo_and_keywords():
    g = GuardResult(
        intent="recherche_entreprise",
        entities=GuardEntity(mots_cles=["padel"], region="PACA"),
        confidence=0.9,
        original_query="padel PACA",
    )
    assert orchestrator_needs_niche_appendix(g) is True


def test_orchestrator_merged_system_includes_niche_appendix_when_needed():
    g_narrow = GuardResult(
        intent="recherche_entreprise",
        entities=GuardEntity(code_naf="41"),
        confidence=0.9,
        original_query="BTP",
    )
    short = _orchestrator_merged_system("prospection", g_narrow)
    assert "CODES NAF POUR NICHES FRÉQUENTES" not in short

    g_niche = GuardResult(
        intent="recherche_entreprise",
        entities=GuardEntity(mots_cles=["padel"], region="PACA"),
        confidence=0.9,
        original_query="padel",
    )
    long = _orchestrator_merged_system("prospection", g_niche)
    assert "CODES NAF POUR NICHES FRÉQUENTES" in long
    assert len(long) > len(short)


# ── Étiquettes UI ────────────────────────────────────────────────────────────

def test_mode_labels_cover_all_modes():
    assert set(MODE_LABELS.keys()) == set(VALID_MODES)
    for label in MODE_LABELS.values():
        assert label and label[0].isupper(), "Label affiché doit commencer par majuscule"
