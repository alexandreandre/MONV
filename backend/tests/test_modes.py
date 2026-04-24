"""Tests des 4 modes d'usage MONV — fonctions pures, sans LLM ni Supabase."""

from __future__ import annotations

import os

import pytest

# Avant tout import applicatif : évite la vérif DB et les clés réelles.
os.environ.setdefault("SKIP_DB_VERIFY_ON_STARTUP", "true")
os.environ.setdefault("SUPABASE_URL", "https://placeholder.supabase.co")
os.environ.setdefault("SUPABASE_SERVICE_KEY", "placeholder-service-key")
# Pas de clé Pappers : permet de vérifier le fallback gracieux du mode rachat.
os.environ.setdefault("PAPPERS_API_KEY", "")


from models.schemas import ChatRequest, GuardEntity, GuardResult  # noqa: E402
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
from services.orchestrator import _build_fallback_plan  # noqa: E402


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


# ── Addendum prompt orchestrateur ────────────────────────────────────────────

def test_prospection_has_no_addendum():
    """Mode défaut → prompt système identique à avant l'introduction des modes."""
    assert addendum_for_mode("prospection") == ""


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


def test_reorder_rachat_promotes_financial_columns():
    cols = reorder_columns_for_mode(BASE_COLUMNS, "rachat")
    head = cols[:10]
    for c in ("chiffre_affaires", "resultat_net", "ebe", "capitaux_propres"):
        assert c in head, f"{c} attendu dans le top 10 du mode rachat"
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
    assert credits_floor_for_mode("rachat") == 3


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


def test_fallback_plan_rachat_includes_pappers_when_key_present(monkeypatch):
    monkeypatch.setattr("services.orchestrator.settings.PAPPERS_API_KEY", "fake-key")
    plan = _build_fallback_plan(_make_guard_result(), "rachat")
    sources = {(c.source, c.action) for c in plan.api_calls}
    assert ("pappers", "get_finances") in sources
    assert ("pappers", "get_dirigeants") in sources


def test_fallback_plan_benchmark_excludes_pappers_when_key_present(monkeypatch):
    """Benchmark n'injecte plus Pappers même si la clé est configurée."""
    monkeypatch.setattr("services.orchestrator.settings.PAPPERS_API_KEY", "fake-key")
    plan = _build_fallback_plan(_make_guard_result(), "benchmark")
    pappers_calls = [c for c in plan.api_calls if c.source == "pappers"]
    assert pappers_calls == []


def test_fallback_plan_rachat_degrades_without_pappers_key(monkeypatch):
    """Sans clé Pappers, le mode rachat reste utilisable (pas de blocage)."""
    monkeypatch.setattr("services.orchestrator.settings.PAPPERS_API_KEY", "")
    plan = _build_fallback_plan(_make_guard_result(), "rachat")
    pappers_calls = [c for c in plan.api_calls if c.source == "pappers"]
    assert pappers_calls == []
    # On a tout de même des appels SIRENE.
    assert any(c.source == "sirene" for c in plan.api_calls)


def test_fallback_plan_default_mode_matches_prospection():
    """Régression : un appel sans mode = comportement prospection."""
    plan_default = _build_fallback_plan(_make_guard_result())
    plan_prospection = _build_fallback_plan(_make_guard_result(), "prospection")
    assert plan_default.columns == plan_prospection.columns
    assert plan_default.estimated_credits == plan_prospection.estimated_credits


# ── Étiquettes UI ────────────────────────────────────────────────────────────

def test_mode_labels_cover_all_modes():
    assert set(MODE_LABELS.keys()) == set(VALID_MODES)
    for label in MODE_LABELS.values():
        assert label and label[0].isupper(), "Label affiché doit commencer par majuscule"
