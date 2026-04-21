"""Sanitation des indices conversationnels Guard (hors contrat orchestrateur)."""

from models.schemas import GuardEntity, GuardResult
from services.conversationalist import _qcm_intro_from_hints
from services.guard import sanitize_context_hints


def test_sanitize_context_hints_filters_and_caps():
    # Seuls les 5 premiers éléments de la liste sont examinés (max_items).
    raw = [
        "  Urgence sous 6 mois  ",
        "x" * 250,
        "ok",
        42,
        None,
        "ignoré car hors fenêtre",
    ]
    out = sanitize_context_hints(raw, max_items=5, max_len=200)
    assert out == ["Urgence sous 6 mois", "ok"]
    assert all(len(s) <= 200 for s in out)


def test_sanitize_context_hints_non_list():
    assert sanitize_context_hints(None) == []
    assert sanitize_context_hints("a") == []


def test_qcm_intro_from_hints():
    g = GuardResult(
        intent="recherche_entreprise",
        entities=GuardEntity(),
        confidence=0.5,
        context_hints=["Cible PME", "Pas d'urgence"],
        original_query="test",
    )
    intro = _qcm_intro_from_hints(g)
    assert intro.startswith("Pour affiner ta recherche")
    assert "Cible PME" in intro
    assert "Pas d'urgence" in intro
