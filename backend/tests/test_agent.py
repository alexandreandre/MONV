"""Tests du service Atelier — fonctions pures, sans LLM ni Supabase."""

from __future__ import annotations

import os

import pytest

os.environ.setdefault("SKIP_DB_VERIFY_ON_STARTUP", "true")
os.environ.setdefault("SUPABASE_URL", "https://placeholder.supabase.co")
os.environ.setdefault("SUPABASE_SERVICE_KEY", "placeholder-service-key")


import asyncio

from services.agent import (  # noqa: E402
    ATELIER_MODE_LABEL,
    _FALLBACK_ATELIER_QUESTIONS,
    _finalize_atelier_qcm,
    _parse_qcm_raw,
    atelier_dossier_rollup_fields,
    build_brief_metadata,
    coerce_dossier,
    dossier_metadata_json,
    heuristic_atelier_conversation_title,
    heuristic_atelier_project_folder_name,
    merge_atelier_cross_segment_tags,
    run_segment_search,
)
from models.schemas import (  # noqa: E402
    AgentSynthesis,
    BusinessCanvas,
    BusinessDossier,
    FlowActor,
    FlowMap,
    ProjectBrief,
    QcmOption,
    QcmQuestion,
    SegmentBrief,
    SegmentResult,
)


# ── Constantes & labels ─────────────────────────────────────────────────────

def test_atelier_mode_label_is_atelier():
    assert ATELIER_MODE_LABEL == "atelier"


def test_heuristic_atelier_title_strips_greeting_and_truncates():
    pitch = (
        "Bonjour je veux lancer une marketplace de matériaux de construction "
        "recyclés en Bretagne avec focus artisans du second œuvre"
    )
    t = heuristic_atelier_conversation_title(pitch, max_len=50)
    assert not t.lower().startswith("bonjour")
    assert len(t) <= 52
    assert "…" in t or len(" ".join(pitch.split())) <= 50


def test_heuristic_atelier_title_uses_first_sentence_when_short():
    pitch = "Food truck de tacos fusion à Rennes. Le reste est du détail."
    t = heuristic_atelier_conversation_title(pitch, max_len=80)
    assert "tacos" in t.lower()
    assert "rennes" in t.lower()


def test_heuristic_project_folder_name_strips_intent_and_formats():
    pitch = "Je veux créer une boite de nuit à marseille"
    n = heuristic_atelier_project_folder_name(pitch)
    assert "je veux" not in n.lower()
    assert "créer" not in n.lower()
    assert "marseille" in n.lower()
    assert n.split()[0][0].isupper()
    assert n.split()[-1][0].isupper()


def test_fallback_questions_cover_core_topics():
    """Le fallback doit couvrir cible, revenus, zone, canaux et budget."""
    ids = {q.id for q in _FALLBACK_ATELIER_QUESTIONS}
    assert {"cible", "modele_revenus", "localisation", "canaux", "budget"} <= ids
    for q in _FALLBACK_ATELIER_QUESTIONS:
        assert any(opt.free_text for opt in q.options), (
            f"Question {q.id} devrait proposer 'Autre' (free_text)"
        )


# ── Parsing QCM LLM ─────────────────────────────────────────────────────────

def test_parse_qcm_adds_autre_when_missing():
    raw = {
        "intro": "Hop :",
        "questions": [
            {
                "id": "cible",
                "question": "Cible ?",
                "options": [{"id": "b2c", "label": "B2C"}],
                "multiple": False,
            }
        ],
    }
    intro, qs = _parse_qcm_raw(raw)
    assert intro == "Hop :"
    assert len(qs) == 1
    assert any(o.free_text for o in qs[0].options), (
        "Une option 'Autre' free_text doit être ajoutée automatiquement"
    )


def test_parse_qcm_keeps_existing_autre():
    raw = {
        "intro": "Questions :",
        "questions": [
            {
                "id": "budget",
                "question": "Budget ?",
                "options": [
                    {"id": "lt20k", "label": "Moins de 20 k€"},
                    {"id": "autre", "label": "Autre", "free_text": True},
                ],
            }
        ],
    }
    _, qs = _parse_qcm_raw(raw)
    assert sum(1 for o in qs[0].options if o.free_text) == 1


def test_parse_qcm_tolerates_empty_payload():
    intro, qs = _parse_qcm_raw({})
    assert intro
    assert qs == []


def test_finalize_injects_validation_when_no_questions():
    intro, qs = _finalize_atelier_qcm("", [])
    assert len(qs) == 1
    assert qs[0].id == "validation_dossier"
    assert "clair" in intro.lower()

    intro2, qs2 = _finalize_atelier_qcm("  Pitch nickel.  ", [])
    assert qs2[0].id == "validation_dossier"
    assert "Pitch nickel" in intro2


def test_finalize_sorts_canonical_ids_and_caps():
    raw = [
        QcmQuestion(
            id="budget",
            question="Budget ?",
            options=[QcmOption(id="a", label="A"), QcmOption(id="autre", label="Autre", free_text=True)],
        ),
        QcmQuestion(
            id="cible",
            question="Cible ?",
            options=[QcmOption(id="b", label="B"), QcmOption(id="autre", label="Autre", free_text=True)],
        ),
    ]
    intro, qs = _finalize_atelier_qcm("Hi", raw)
    assert [q.id for q in qs] == ["cible", "budget"]


def test_finalize_dedupes_question_ids():
    q = QcmQuestion(
        id="cible",
        question="Une",
        options=[QcmOption(id="x", label="X"), QcmOption(id="autre", label="Autre", free_text=True)],
    )
    intro, qs = _finalize_atelier_qcm("x", [q, q])
    assert len(qs) == 1


def test_finalize_drops_sixth_question():
    qs_in = [
        QcmQuestion(
            id=f"q{i}",
            question=f"Q{i} ?",
            options=[
                QcmOption(id="o", label="O"),
                QcmOption(id="autre", label="Autre", free_text=True),
            ],
        )
        for i in range(6)
    ]
    _, qs = _finalize_atelier_qcm("intro", qs_in)
    assert len(qs) == 5


# ── Coercion du dossier LLM ─────────────────────────────────────────────────

_VALID_RAW_DOSSIER = {
    "brief": {
        "nom": "Sushi Lyon",
        "tagline": "Restaurant japonais haut de gamme avec sakés en ligne",
        "secteur": "Restauration japonaise premium",
        "localisation": "Lyon",
        "cible": "B2C",
        "budget": "250 k€ – 1 M€",
        "modele_revenus": "Vente sur place + livraison + e-commerce sakés",
        "ambition": "1 restaurant flagship + 500 clients e-commerce mensuels",
    },
    "canvas": {
        "proposition_valeur": ["Cuisine authentique", "Sakés rares"],
        "segments_clients": ["CSP+ lyonnais", "Amateurs de saké"],
        "canaux": ["Boutique physique", "Boutique en ligne"],
        "relation_client": ["Service à table", "Newsletter"],
        "sources_revenus": ["Ventes restaurant", "Ventes en ligne"],
        "ressources_cles": ["Chef sushi", "Cave à saké"],
        "activites_cles": ["Production", "Logistique"],
        "partenaires_cles": ["Importateurs japonais"],
        "structure_couts": ["Loyer", "Matières premières"],
    },
    "flows": {
        "acteurs": ["Client", "Restaurant", "Importateur"],
        "flux_valeur": [
            {"origine": "Importateur", "destination": "Restaurant", "label": "Sakés"},
            {"origine": "Restaurant", "destination": "Client", "label": "Repas"},
        ],
        "flux_financiers": [
            {"origine": "Client", "destination": "Restaurant", "label": "Paiement"}
        ],
        "flux_information": [
            {"origine": "Restaurant", "destination": "Client", "label": "Menu"}
        ],
    },
    "segments": [
        {
            "key": "fournisseurs",
            "label": "Fournisseurs",
            "description": "Importateurs de produits japonais",
            "mode": "sous_traitant",
            "query": "Fournisseurs de produits japonais à Lyon",
            "icon": "truck",
        },
        {
            "key": "concurrents",
            "label": "Concurrents",
            "description": "Restaurants japonais haut de gamme Lyon",
            "mode": "prospection",
            "query": "Restaurants japonais haut de gamme à Lyon",
            "icon": "target",
        },
    ],
    "synthesis": {
        "forces": ["Positionnement premium", "Double canal"],
        "risques": ["Coût du loyer", "Approvisionnement"],
        "prochaines_etapes": ["Étude marché", "Business plan", "Local"],
        "kpis": ["CA mensuel", "Panier moyen"],
        "budget_estimatif": "400 k€ sur 12 mois",
    },
}


def test_coerce_dossier_parses_full_payload():
    brief, canvas, flows, segments, synthesis = coerce_dossier(_VALID_RAW_DOSSIER)
    assert isinstance(brief, ProjectBrief)
    assert brief.nom == "Sushi Lyon"
    assert isinstance(canvas, BusinessCanvas)
    assert "Cuisine authentique" in canvas.proposition_valeur
    assert isinstance(flows, FlowMap)
    assert len(flows.acteurs) == 3
    assert all(isinstance(a, FlowActor) for a in flows.acteurs)
    assert flows.acteurs[0].label == "Client"
    assert len(flows.flux_valeur) == 2
    assert len(segments) == 2
    assert {s.mode for s in segments} <= {"prospection", "sous_traitant", "rachat"}
    assert isinstance(synthesis, AgentSynthesis)
    assert synthesis.budget_estimatif == "400 k€ sur 12 mois"


def test_coerce_dossier_rejects_invalid_segment_mode():
    """Un segment avec mode 'client' ou 'atelier' doit retomber sur prospection."""
    bad = dict(_VALID_RAW_DOSSIER)
    bad = {
        **bad,
        "segments": [
            {**bad["segments"][0], "mode": "atelier"},
            {**bad["segments"][1], "mode": "client"},
        ],
    }
    _, _, _, segments, _ = coerce_dossier(bad)
    assert all(s.mode in {"prospection", "sous_traitant", "rachat"} for s in segments)
    assert all(s.mode == "prospection" for s in segments)


def test_coerce_dossier_drops_segments_without_query():
    bad = {**_VALID_RAW_DOSSIER, "segments": [{"key": "x", "mode": "prospection"}]}
    _, _, _, segments, _ = coerce_dossier(bad)
    assert segments == []


def test_coerce_dossier_caps_segments_at_five():
    many = {
        **_VALID_RAW_DOSSIER,
        "segments": [
            {
                "key": f"seg_{i}",
                "label": f"Segment {i}",
                "mode": "prospection",
                "query": f"requête {i}",
            }
            for i in range(12)
        ],
    }
    _, _, _, segments, _ = coerce_dossier(many)
    assert len(segments) <= 5


def test_coerce_dossier_survives_partial_payload():
    """Un payload très incomplet produit un dossier par défaut, pas un crash."""
    brief, canvas, flows, segments, synthesis = coerce_dossier({})
    assert brief.nom == "Mon projet"
    assert canvas.proposition_valeur == []
    assert flows.flux_valeur == []
    assert segments == []
    assert synthesis.forces == []


def test_coerce_dossier_flow_metadata_and_rich_edges():
    raw = dict(_VALID_RAW_DOSSIER)
    raw["flows"] = {
        "diagram_title": "Chaîne test",
        "layout": "horizontal",
        "flow_insight": "Lecture synthétique.",
        "acteurs": [
            {"label": "A", "role": "Entrée", "hint": "Indice", "emphasis": "primary"},
            {"label": "B", "segment_key": "fournisseurs"},
        ],
        "flux_valeur": [
            {
                "origine": "A",
                "destination": "B",
                "label": "Flux",
                "detail": "Précision au clic.",
                "pattern": "dashed",
            }
        ],
        "flux_financiers": [],
        "flux_information": [],
    }
    _, _, flows, segments, _ = coerce_dossier(raw)
    assert flows.diagram_title == "Chaîne test"
    assert flows.layout == "horizontal"
    assert flows.flow_insight == "Lecture synthétique."
    assert flows.acteurs[0].role == "Entrée"
    assert flows.acteurs[0].emphasis == "primary"
    assert flows.flux_valeur[0].detail == "Précision au clic."
    assert flows.flux_valeur[0].pattern == "dashed"
    assert len(segments) >= 1


def test_coerce_dossier_acteurs_segment_key_invalid_dropped():
    raw = dict(_VALID_RAW_DOSSIER)
    raw["flows"] = {
        **raw["flows"],
        "acteurs": [
            {"label": "Importateur", "segment_key": "fournisseurs"},
            {"label": "Inconnu", "segment_key": "nope_pas_un_segment"},
        ],
    }
    _, _, flows, segments, _ = coerce_dossier(raw)
    assert {a.label for a in flows.acteurs} == {"Importateur", "Inconnu"}
    assert flows.acteurs[0].segment_key == "fournisseurs"
    assert flows.acteurs[1].segment_key is None


def test_coerce_dossier_dedupes_segment_keys():
    dup = {
        **_VALID_RAW_DOSSIER,
        "segments": [
            {"key": "fournisseurs", "label": "A", "mode": "sous_traitant", "query": "q1"},
            {"key": "fournisseurs", "label": "B", "mode": "prospection", "query": "q2"},
        ],
    }
    _, _, _, segments, _ = coerce_dossier(dup)
    assert len(segments) == 1
    assert segments[0].label == "A"


# ── Sérialisation metadata_json ─────────────────────────────────────────────

def test_dossier_metadata_json_embeds_mode_atelier():
    brief, canvas, flows, segments_brief, synthesis = coerce_dossier(_VALID_RAW_DOSSIER)
    dossier = BusinessDossier(
        brief=brief,
        canvas=canvas,
        flows=flows,
        segments=[
            SegmentResult(
                key=s.key,
                label=s.label,
                description=s.description,
                mode=s.mode,
                icon=s.icon,
                query=s.query,
                total=0,
                credits_required=0,
                columns=[],
                preview=[],
                map_points=[],
            )
            for s in segments_brief
        ],
        synthesis=synthesis,
    )
    raw = dossier_metadata_json(dossier)
    import json as _json
    payload = _json.loads(raw)
    assert payload["mode"] == ATELIER_MODE_LABEL
    assert payload["brief"]["nom"] == "Sushi Lyon"
    assert isinstance(payload["segments"], list)


def test_build_brief_metadata_carries_pitch():
    raw = build_brief_metadata("Mon pitch secret")
    import json as _json
    payload = _json.loads(raw)
    assert payload["pitch"] == "Mon pitch secret"
    assert payload["mode"] == ATELIER_MODE_LABEL


def test_coerce_dossier_budget_structured_and_long_text():
    raw = {
        **_VALID_RAW_DOSSIER,
        "brief": {
            **_VALID_RAW_DOSSIER["brief"],
            "budget": "80 k€ – 200 k€ dont fonds de roulement 6 mois et loyer 12 mois",
            "budget_min_eur": 80000,
            "budget_max_eur": 200000,
            "budget_hypotheses": ["Fonds de roulement 6 mois", "Loyer équipement"],
        },
    }
    brief, _, _, _, _ = coerce_dossier(raw)
    assert "fonds de roulement 6 mois" in brief.budget
    assert brief.budget_min_eur == 80000
    assert brief.budget_max_eur == 200000
    assert brief.budget_hypotheses[0] == "Fonds de roulement 6 mois"


def test_coerce_dossier_out_of_scope_segment_without_query():
    raw = {
        **_VALID_RAW_DOSSIER,
        "segments": [
            {
                "key": "producteurs_japon",
                "label": "Producteurs au Japon",
                "description": "Hors annuaires FR",
                "mode": "prospection",
                "query": "",
                "icon": "building",
                "out_of_scope": True,
                "out_of_scope_note": "Cible à l'étranger : compléter par recherche web.",
            },
            _VALID_RAW_DOSSIER["segments"][0],
        ],
    }
    _, _, _, segments, _ = coerce_dossier(raw)
    assert len(segments) == 2
    oos = next(s for s in segments if s.key == "producteurs_japon")
    assert oos.out_of_scope is True
    assert oos.query == ""


def test_merge_atelier_cross_segment_tags_and_rollup():
    """Même SIREN dans deux segments → tags multi-segments visibles."""
    a = SegmentResult(
        key="importateurs",
        label="Importateurs",
        description="",
        mode="prospection",
        icon="truck",
        query="q1",
        total=2,
        credits_required=1,
        columns=[],
        preview=[
            {
                "siren": "123456789",
                "nom": "Alpha Grossiste",
                "_dedup_key": "siren:123456789",
                "relevance_flag": "ok",
            }
        ],
        map_points=[],
    )
    b = SegmentResult(
        key="distributeurs",
        label="Distributeurs",
        description="",
        mode="prospection",
        icon="truck",
        query="q2",
        total=1,
        credits_required=1,
        columns=[],
        preview=[
            {
                "siren": "123456789",
                "nom": "Alpha Grossiste",
                "_dedup_key": "siren:123456789",
                "relevance_flag": "warning",
            }
        ],
        map_points=[],
    )
    merge_atelier_cross_segment_tags([a, b])
    assert a.preview[0]["segments"] == ["distributeurs", "importateurs"]
    assert b.preview[0]["segments"] == ["distributeurs", "importateurs"]
    roll = atelier_dossier_rollup_fields([a, b])
    assert roll["total_raw"] == 3
    assert roll["total_unique"] == 1
    assert roll["total_relevant"] == 1


def test_kappo_import_segment_preview_excludes_bank_when_scored_low():
    """Contrat Atelier : une banque avec score exclu ne compte pas dans total_relevant."""
    seg = SegmentResult(
        key="importateurs",
        label="Importateurs B2B boissons",
        description="",
        mode="prospection",
        icon="truck",
        query="Grossistes commerce de gros boissons Rhône",
        total=2,
        credits_required=1,
        columns=[],
        preview=[
            {
                "siren": "3000210276",
                "nom": "Crédit Lyonnais",
                "_dedup_key": "siren:3000210276",
                "relevance_flag": "excluded",
            },
            {
                "siren": "999999999",
                "nom": "Saké Import Lyon",
                "_dedup_key": "siren:999999999",
                "relevance_flag": "ok",
            },
        ],
        map_points=[],
    )
    roll = atelier_dossier_rollup_fields([seg])
    assert roll["total_unique"] == 2
    assert roll["total_relevant"] == 1


def test_run_segment_search_out_of_scope_no_pipeline():
    async def run():
        return await run_segment_search(
            SegmentBrief(
                key="particuliers",
                label="CSP+",
                description="",
                mode="prospection",
                query="",
                icon="users",
                out_of_scope=True,
                out_of_scope_note="Particuliers non listés dans SIRENE.",
            )
        )

    seg = asyncio.run(run())
    assert seg.out_of_scope is True
    assert seg.total == 0
    assert seg.preview == []
    assert "SIRENE" in (seg.out_of_scope_note or "")
