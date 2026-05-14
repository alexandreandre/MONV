"""Registre admin : graphes déclaratifs présents pour chaque agent."""

from models.schemas import GUARD_STATIC_REPLY_EDGE_CONDITION, GuardEntity, GuardResult
from services.agent_registry import (
    AGENT_IDS,
    EXTERNAL_APIS,
    get_agent_graph_definition,
)
from services.modes import addendum_for_mode


def test_agent_registry_covers_all_ids():
    for aid in AGENT_IDS:
        g = get_agent_graph_definition(aid)
        assert g["agent_id"] == aid
        assert "nodes" in g["graph"] and "edges" in g["graph"]
        assert len(g["graph"]["nodes"]) >= 3


def test_each_chat_mode_has_filter_and_orchestrator():
    for aid in ("prospection", "sous_traitant", "benchmark", "rachat"):
        g = get_agent_graph_definition(aid)["graph"]
        ids = {n["id"] for n in g["nodes"]}
        assert "filter" in ids and "orchestrator" in ids


def test_atelier_has_qcm_and_dossier():
    g = get_agent_graph_definition("atelier")["graph"]
    ids = {n["id"] for n in g["nodes"]}
    assert "atelier_qcm" in ids and "dossier_fill" in ids


def test_atelier_graph_exposes_segment_apis():
    graph = get_agent_graph_definition("atelier")["graph"]
    ids = {n["id"] for n in graph["nodes"]}
    for api_id in ("sirene_api", "google_places_api", "pappers_api", "openrouter_api"):
        assert api_id in ids
    assert "segment_merge_dedup" in ids


def test_api_nodes_carry_full_metadata():
    graph = get_agent_graph_definition("prospection")["graph"]
    api_nodes = [n for n in graph["nodes"] if n["type"] == "api"]
    assert api_nodes, "Aucun nœud API trouvé"
    for node in api_nodes:
        api = node.get("api") or {}
        assert api.get("base_url"), f"{node['id']} : base_url manquant"
        assert "endpoints" in api and isinstance(api["endpoints"], list)
        assert "auth" in api
        assert "usage" in api


def test_external_apis_catalog_has_required_fields():
    required = {"label", "provider", "base_url", "endpoints", "auth", "cost",
                "rate_limit", "timeout_s", "doc_url", "usage", "source_file"}
    for api_id, spec in EXTERNAL_APIS.items():
        missing = required - set(spec.keys())
        assert not missing, f"{api_id} : champs manquants {missing}"


# ── Spécificités par mode (chaque graphe doit être unique) ───────────────────


def _ids(aid: str) -> set[str]:
    return {n["id"] for n in get_agent_graph_definition(aid)["graph"]["nodes"]}


def _branches(aid: str) -> set[tuple[str, str]]:
    return {(e["from"], e["to"]) for e in get_agent_graph_definition(aid)["graph"]["edges"]}


def test_prospection_specifics():
    ids = _ids("prospection")
    assert {"sirene_api", "google_places_api", "pappers_api", "geocoding_api", "merge_dedup"} <= ids
    assert "digital_pitch" in ids and "digital_pitch_trigger" in ids
    assert "bodacc_api" not in ids and "decp_api" not in ids
    assert "benchmark_stats" not in ids and "rachat_framing" not in ids
    assert "force_qcm_qualification" not in ids
    br = _branches("prospection")
    assert ("merge_dedup", "geocoding_api") in br
    assert ("geocoding_api", "relevance") in br
    assert ("sirene_api", "relevance") not in br


def test_sous_traitant_specifics():
    ids = _ids("sous_traitant")
    assert {"sirene_api", "pappers_api", "force_qcm_qualification", "qcm", "merge_dedup"} <= ids
    assert "google_places_api" not in ids
    assert "bodacc_api" not in ids and "decp_api" not in ids
    assert "digital_pitch" not in ids
    assert "benchmark_stats" not in ids and "rachat_framing" not in ids
    branches = _branches("sous_traitant")
    assert ("force_qcm_qualification", "qcm") in branches
    assert ("force_qcm_qualification", "orchestrator") in branches


def test_benchmark_specifics():
    ids = _ids("benchmark")
    assert {"sirene_api", "google_places_api", "benchmark_stats", "benchmark_framing", "merge_dedup"} <= ids
    assert "pappers_api" not in ids
    assert "bodacc_api" not in ids and "decp_api" not in ids
    assert "digital_pitch" not in ids and "rachat_framing" not in ids
    assert "force_qcm_qualification" not in ids
    branches = _branches("benchmark")
    assert ("benchmark_stats", "benchmark_framing") in branches
    assert ("benchmark_framing", "user_output") in branches


def test_rachat_specifics():
    ids = _ids("rachat")
    assert {"sirene_api", "bodacc_api", "decp_api", "signals_compute",
            "rachat_framing", "force_qcm_qualification"} <= ids
    assert "pappers_api" not in ids
    assert "google_places_api" not in ids
    assert "digital_pitch" not in ids
    assert "benchmark_stats" not in ids
    branches = _branches("rachat")
    assert ("bodacc_api", "signals_compute") in branches
    assert ("decp_api", "signals_compute") in branches
    assert ("rachat_framing", "user_output") in branches


def test_each_chat_mode_has_unique_graph():
    """Garde-fou : aucun mode ne doit avoir exactement le même set de nœuds qu'un autre."""
    sets = {aid: _ids(aid) for aid in ("prospection", "sous_traitant", "benchmark", "rachat")}
    seen: dict[frozenset, str] = {}
    for aid, s in sets.items():
        key = frozenset(s)
        assert key not in seen, f"{aid} et {seen[key]} ont des graphes identiques"
        seen[key] = aid


def test_orchestrator_label_includes_mode():
    for aid in ("prospection", "sous_traitant", "benchmark", "rachat"):
        graph = get_agent_graph_definition(aid)["graph"]
        orch = next(n for n in graph["nodes"] if n["id"] == "orchestrator")
        from services.modes import MODE_LABELS as ML
        assert ML[aid] in orch["label"], f"label orchestrateur {aid} ne contient pas le label de mode"


def test_guard_static_reply_edge_matches_chat_contract():
    """Arête admin = routage ``chat`` (réponse statique), pas de libellé « search »."""
    for aid in ("prospection", "sous_traitant", "benchmark", "rachat"):
        graph = get_agent_graph_definition(aid)["graph"]
        edge = next(
            (e for e in graph["edges"] if e["from"] == "guard" and e["to"] == "static_reply"),
            None,
        )
        assert edge is not None, aid
        assert edge.get("condition") == GUARD_STATIC_REPLY_EDGE_CONDITION
        assert "search" not in (edge.get("condition") or "").lower()


def test_guard_result_intent_coercion_unknown():
    g = GuardResult(intent="salutation", entities=GuardEntity(), confidence=1.0)
    assert g.intent == "salutation"
    g2 = GuardResult(intent="typo_inconnu", entities=GuardEntity(), confidence=0.5)
    assert g2.intent == "recherche_entreprise"


def test_prospection_addendum_priority_hierarchy():
    """Addendum prospection : tranche structuré (SIRENE 1) vs niche (Places 1)."""
    a = addendum_for_mode("prospection")
    assert a != ""
    assert "mode actif" in a.lower()
    assert "priority" in a.lower()
    assert "structur" in a.lower() and "niche" in a.lower()
