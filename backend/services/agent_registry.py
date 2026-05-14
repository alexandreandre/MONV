"""
Registre déclaratif des graphes d'agents (topologie = code ; l'UI admin affiche ce JSON).

Les identifiants d'agent alignés sur les modes chat + ``atelier``.

Contrat multi-sources (modes chat + segments Atelier) : les connecteurs SIRENE / Google Places /
Pappers alimentent une étape interne **fusion + dédoublonnage** (`execute_plan` dans
``api_engine.py``), puis **un seul** passage pertinence sur la liste unifiée — le graphe expose un
nœud outil dédié pour éviter l'ambiguïté « trois flux parallèles vers relevance ».

Trois familles de nœuds :
  - ``llm``       : appel LLM (modèle paramétrable via overrides)
  - ``tool``      : code interne pur (heuristiques, formatting, scoring local)
  - ``api``       : API externe HTTP (métadonnées détaillées dans ``EXTERNAL_APIS``)
  - ``output``    : sortie vers utilisateur
"""

from __future__ import annotations

from typing import Any

from models.schemas import GUARD_STATIC_REPLY_EDGE_CONDITION
from services.modes import MODE_LABELS

AGENT_IDS: tuple[str, ...] = ("prospection", "sous_traitant", "benchmark", "rachat", "atelier")


# ─────────────────────────────────────────────────────────────────────────────
# Catalogue des APIs externes (métadonnées affichées dans l'inspecteur admin)
# ─────────────────────────────────────────────────────────────────────────────

EXTERNAL_APIS: dict[str, dict[str, Any]] = {
    "sirene_api": {
        "label": "API Recherche Entreprises",
        "provider": "data.gouv.fr (INSEE)",
        "base_url": "https://recherche-entreprises.api.gouv.fr/search",
        "base_url_env": "SIRENE_BASE_URL",
        "endpoints": [
            {
                "method": "GET",
                "path": "/",
                "purpose": "Recherche full-text d'entreprises FR (texte + filtres)",
                "params": ["q", "code_postal", "departement", "section_activite_principale",
                           "tranche_effectif_salarie", "etat_administratif", "page", "per_page"],
            },
        ],
        "auth": {"type": "none", "header": None, "env_var": None},
        "cost": "Gratuit (service public)",
        "rate_limit": "7 req/s soft (rate-limited 429 si dépassement)",
        "timeout_s": 15,
        "doc_url": "https://api.gouv.fr/documentation/api-recherche-entreprises",
        "usage": (
            "Source primaire en France : recherche par mots-clés + zone géographique. "
            "Renvoie SIREN/SIRET, raison sociale, activité, effectif, code NAF."
        ),
        "triggered_by": "Plan orchestrateur contenant `source=\"sirene\"`",
        "fallback": "Plan déterministe : Pappers si SIRENE en panne sur recherche brand",
        "source_file": "services/sirene.py",
    },
    "google_places_api": {
        "label": "Google Places API (Text Search v1)",
        "provider": "Google Cloud",
        "base_url": "https://places.googleapis.com/v1/places:searchText",
        "endpoints": [
            {
                "method": "POST",
                "path": "/v1/places:searchText",
                "purpose": "Recherche géolocalisée de commerces (texte + biais lat/lng/rayon)",
                "params": ["textQuery", "locationBias.circle"],
            },
        ],
        "auth": {"type": "api_key_header", "header": "X-Goog-Api-Key", "env_var": "GOOGLE_PLACES_API_KEY"},
        "cost": "Payant — facturation par session Places (essential, contact, atmosphere)",
        "rate_limit": "QPS configurable Google Cloud (par défaut ~600 req/min)",
        "timeout_s": 20,
        "doc_url": "https://developers.google.com/maps/documentation/places/web-service/text-search",
        "usage": (
            "Sourcing local + résolution adresse/téléphone/site web pour commerces et restaurants. "
            "Bias par cercle lat/lng + rayon issu du géocodage."
        ),
        "triggered_by": "Plan contenant `source=\"google_places\"` (typiquement secteur restaurant/coiffeur/etc.)",
        "fallback": "Sans clé → bloc skip, plan déterministe se rabat sur SIRENE",
        "source_file": "services/google_places.py",
    },
    "pappers_api": {
        "label": "Pappers API",
        "provider": "Pappers SAS (France) ou Pappers.in (international)",
        "base_url": "https://api.pappers.in/v1",
        "base_url_env": "PAPPERS_BASE_URL",
        "endpoints": [
            {"method": "GET", "path": "/search", "purpose": "Recherche (mode international)"},
            {"method": "GET", "path": "/recherche", "purpose": "Recherche (mode France)"},
            {"method": "GET", "path": "/entreprise", "purpose": "Fiche entreprise + finances + dirigeants (FR)"},
            {"method": "GET", "path": "/company", "purpose": "Fiche entreprise (international)"},
        ],
        "auth": {
            "type": "api_key_param_or_header",
            "header": "api-key (intl) | param `api_token` (FR)",
            "env_var": "PAPPERS_API_KEY",
        },
        "cost": "Payant — quota mensuel selon plan",
        "rate_limit": "Variable selon plan Pappers (souvent 50-100 req/s)",
        "timeout_s": 20,
        "doc_url": "https://www.pappers.fr/api/documentation",
        "usage": (
            "Enrichissement profond : finances multi-années (CA, résultat, marge, EBE, capitaux propres), "
            "dirigeants, contacts (email/téléphone), capital social, date de création."
        ),
        "triggered_by": (
            "Plan avec `source=\"pappers\"` ; en prospection le backend retire les appels superflus "
            "(search large sans filtre CA, get_* sans demande ni panneau SIRENE étroit)."
        ),
        "fallback": "Skip silencieux si clé absente, données financières restent vides",
        "source_file": "services/pappers.py",
    },
    "bodacc_api": {
        "label": "BODACC — Annonces civiles & commerciales",
        "provider": "data.gouv.fr (DILA) / Opendatasoft",
        "base_url": (
            "https://bodacc-datadila.opendatasoft.com/api/explore/v2.1"
            "/catalog/datasets/annonces-commerciales/records"
        ),
        "endpoints": [
            {
                "method": "GET",
                "path": "/records",
                "purpose": "Annonces : créations, ventes, procédures collectives, modifications, dépôts comptes",
                "params": ["where", "limit", "order_by"],
            },
        ],
        "auth": {"type": "none", "header": None, "env_var": None},
        "cost": "Gratuit",
        "rate_limit": "Opendatasoft — ~10 req/s (anonyme)",
        "timeout_s": 15,
        "doc_url": "https://bodacc-datadila.opendatasoft.com/api/explore/v2.1/console",
        "usage": (
            "Détection signaux légaux : procédure collective (sauvegarde, redressement, liquidation), "
            "vente de fonds, modification dirigeant, dépôt comptes. Filtré par SIREN sur les 24 derniers mois."
        ),
        "triggered_by": "Plan avec `source=\"bodacc\"`, action `get_signals` (typiquement mode rachat)",
        "fallback": "Tolérant : ignore les annonces non parsables",
        "source_file": "services/bodacc.py",
    },
    "decp_api": {
        "label": "Marchés Publics — DECP",
        "provider": "data.economie.gouv.fr",
        "base_url": (
            "https://data.economie.gouv.fr/api/explore/v2.1"
            "/catalog/datasets/decp_augmente/records"
        ),
        "endpoints": [
            {
                "method": "GET",
                "path": "/records",
                "purpose": "Marchés publics remportés (DECP augmentée)",
                "params": ["where", "limit", "order_by"],
            },
        ],
        "auth": {"type": "none", "header": None, "env_var": None},
        "cost": "Gratuit",
        "rate_limit": "~10 req/s anonyme",
        "timeout_s": 10,
        "doc_url": "https://www.data.gouv.fr/fr/datasets/donnees-essentielles-de-la-commande-publique/",
        "usage": (
            "Signal fort B2B : entreprise titulaire d'un marché public récent. "
            "Filtré par SIREN, montant, date de notification."
        ),
        "triggered_by": "Plan avec `source=\"marches_publics\"`, action `get_marches`",
        "fallback": "Skip si erreur réseau, signal absent",
        "source_file": "services/marches_publics.py",
    },
    "geocoding_api": {
        "label": "Base Adresse Nationale (BAN)",
        "provider": "data.gouv.fr / IGN",
        "base_url": "https://api-adresse.data.gouv.fr/search/",
        "endpoints": [
            {
                "method": "GET",
                "path": "/search",
                "purpose": "Géocodage texte → (lat, lng) + résolution code postal",
                "params": ["q", "limit"],
            },
        ],
        "auth": {"type": "none", "header": None, "env_var": None},
        "cost": "Gratuit",
        "rate_limit": "50 req/s anonyme",
        "timeout_s": 10,
        "doc_url": "https://adresse.data.gouv.fr/api-doc/adresse",
        "usage": (
            "Conversion adresse postale → coordonnées GPS pour le biais Google Places "
            "et l'affichage carte des résultats."
        ),
        "triggered_by": "`api_engine` après fusion/dédoublonnage, pour les lignes sans lat/lng",
        "fallback": "Lignes sans coordonnées : juste pas affichées sur la carte",
        "source_file": "services/geocoding.py",
    },
    "openrouter_api": {
        "label": "OpenRouter — Gateway LLM",
        "provider": "OpenRouter.ai",
        "base_url": "https://openrouter.ai/api/v1",
        "endpoints": [
            {
                "method": "POST",
                "path": "/chat/completions",
                "purpose": "Inference LLM unifiée (Gemini, Claude, GPT, Llama, etc.)",
                "params": ["model", "messages", "temperature", "max_tokens", "top_p", "response_format"],
            },
        ],
        "auth": {"type": "bearer_token", "header": "Authorization: Bearer", "env_var": "OPENROUTER_API_KEY"},
        "cost": "Payant — facturé par token selon le modèle choisi",
        "rate_limit": "Dépend du plan OpenRouter (souvent 60-200 req/min)",
        "timeout_s": 60,
        "doc_url": "https://openrouter.ai/docs",
        "usage": (
            "Tous les appels LLM du projet passent par OpenRouter (Filter, Guard, Orchestrator, "
            "Relevance, Atelier, etc.). Le modèle effectif est configurable par bloc via les overrides admin."
        ),
        "triggered_by": "Chaque nœud `llm` du graphe",
        "fallback": "Retry exponentiel sur 429/5xx (3 tentatives)",
        "source_file": "utils/llm.py",
    },
}


# ─────────────────────────────────────────────────────────────────────────────
# Helpers de construction
# ─────────────────────────────────────────────────────────────────────────────


def _edge(frm: str, to: str, *, condition: str | None = None, kind: str = "flow") -> dict[str, Any]:
    e: dict[str, Any] = {"from": frm, "to": to, "kind": kind}
    if condition:
        e["condition"] = condition
    return e


def _node(
    nid: str,
    label: str,
    ntype: str,
    *,
    model_ref: str | None = None,
    source_file: str,
    default_params: dict[str, Any] | None = None,
    default_prompt_preview: str = "",
    inputs: list[dict[str, str]] | None = None,
    outputs: list[dict[str, str]] | None = None,
    sub_blocks: list[str] | None = None,
    fallback: str | None = None,
    errors: list[str] | None = None,
    api: dict[str, Any] | None = None,
) -> dict[str, Any]:
    n: dict[str, Any] = {
        "id": nid,
        "label": label,
        "type": ntype,
        "source_file": source_file,
        "default_params": default_params or {},
        "default_prompt_preview": default_prompt_preview,
        "inputs": inputs or [],
        "outputs": outputs or [],
    }
    if model_ref:
        n["model_ref"] = model_ref
    if sub_blocks:
        n["sub_blocks"] = sub_blocks
    if fallback:
        n["fallback"] = fallback
    if errors:
        n["errors"] = errors
    if api:
        n["api"] = api
    return n


def _api_node(api_id: str, *, label_override: str | None = None) -> dict[str, Any]:
    """Construit un nœud `api` à partir de l'entrée correspondante du catalogue ``EXTERNAL_APIS``."""
    spec = EXTERNAL_APIS[api_id]
    label = label_override or spec["label"]
    return _node(
        api_id,
        label,
        "api",
        source_file=spec["source_file"],
        inputs=[{"name": "params", "type": "json"}],
        outputs=[{"name": "raw_records", "type": "json"}],
        fallback=spec.get("fallback"),
        api={
            "provider": spec.get("provider"),
            "base_url": spec.get("base_url"),
            "base_url_env": spec.get("base_url_env"),
            "endpoints": spec.get("endpoints", []),
            "auth": spec.get("auth"),
            "cost": spec.get("cost"),
            "rate_limit": spec.get("rate_limit"),
            "timeout_s": spec.get("timeout_s"),
            "doc_url": spec.get("doc_url"),
            "usage": spec.get("usage"),
            "triggered_by": spec.get("triggered_by"),
        },
    )


## ────────────────────────────────────────────────────────────────────────────
## Briques élémentaires partagées entre les graphes chat
## (chaque mode pioche dans ce vivier ce qu'il utilise vraiment)
## ────────────────────────────────────────────────────────────────────────────


def _node_filter() -> dict[str, Any]:
    return _node(
        "filter",
        "Filtre scope",
        "llm",
        model_ref="FILTER_MODEL",
        source_file="services/filter.py",
        default_params={"temperature": 0.0, "max_tokens": 32, "top_p": 1.0},
        default_prompt_preview=(
            "Pré-filtre binaire : la requête est-elle dans le scope MONV (recherche d'entreprises) ? "
            "Sortie JSON {in_scope: bool}."
        ),
        inputs=[{"name": "user_message", "type": "string"}],
        outputs=[{"name": "in_scope", "type": "boolean"}],
        fallback=(
            "config : FILTER_LLM_ERROR_POLICY (fail_open | fail_closed | heuristic_then_closed) "
            "+ rate-limit chat optionnel"
        ),
        errors=["network", "json_parse"],
    )


def _node_guard() -> dict[str, Any]:
    return _node(
        "guard",
        "Guard (intent + entités)",
        "llm",
        model_ref="GUARD_MODEL",
        source_file="services/guard.py",
        default_params={"temperature": 0.0, "max_tokens": 1024, "top_p": 1.0},
        default_prompt_preview=(
            "Extraction noyau : intent + entités + clarification + sector_ambiguous léger ; "
            "second passage optionnel `guard_sector_ambiguity` (prompt long) si détecteur lexical "
            "(voir services/guard_ambiguity.py)."
        ),
        inputs=[{"name": "user_message", "type": "string"}, {"name": "history", "type": "messages"}],
        outputs=[{"name": "GuardResult", "type": "json"}],
        errors=["llm_error"],
    )


def _node_sector_confirm() -> dict[str, Any]:
    return _node(
        "sector_confirm",
        "QCM levée d'ambiguïté secteur",
        "llm",
        model_ref="GUARD_MODEL",
        source_file="services/conversationalist.py",
        default_params={"temperature": 0.2, "max_tokens": 512, "top_p": 1.0},
        default_prompt_preview=(
            "Pose une question fermée pour lever l'ambiguïté sectorielle "
            "(ex : 'plombier' = artisan ou grossiste ?)."
        ),
        inputs=[{"name": "guard_result", "type": "json"}],
        outputs=[{"name": "QcmQuestion", "type": "json"}],
        fallback="question figée si LLM échoue",
    )


def _node_qcm(*, label: str, missing_criteria: list[str], preview_extra: str = "") -> dict[str, Any]:
    return _node(
        "qcm",
        label,
        "llm",
        model_ref="GUARD_MODEL",
        source_file="services/conversationalist.py",
        default_params={"temperature": 0.3, "max_tokens": 1024, "top_p": 1.0},
        default_prompt_preview=(
            f"Génère un QCM (intro + questions ciblées). Critères manquants : "
            f"{', '.join(missing_criteria) if missing_criteria else 'détectés à la volée'}.{(' ' + preview_extra) if preview_extra else ''}"
        ),
        inputs=[{"name": "guard_result", "type": "json"}, {"name": "missing_criteria", "type": "string[]"}],
        outputs=[{"name": "intro", "type": "string"}, {"name": "questions", "type": "json"}],
        fallback="questions de secours figées",
    )


def _node_orchestrator(mode: str, addendum_summary: str) -> dict[str, Any]:
    return _node(
        "orchestrator",
        f"Orchestrateur — plan API ({MODE_LABELS.get(mode, mode)})",  # type: ignore[arg-type]
        "llm",
        model_ref="ORCHESTRATOR_MODEL",
        source_file="services/orchestrator.py",
        default_params={"temperature": 0.0, "max_tokens": 2048, "top_p": 1.0},
        default_prompt_preview=(
            f"Prompt orchestrateur générique + addendum mode `{mode}`. {addendum_summary}"
        ),
        inputs=[{"name": "guard_json", "type": "json"}, {"name": "mode", "type": "string"}],
        outputs=[{"name": "ExecutionPlan", "type": "json"}],
        fallback="Plan déterministe (SIRENE / Places) si LLM vide",
        errors=["llm_error", "plan_vide"],
    )


def _node_plan_patches(mode: str) -> dict[str, Any]:
    if mode == "sous_traitant":
        preview = (
            "Heuristiques mode sous-traitant : `patch_sirene_calls_from_guard_entities` (force NAF + "
            "tranche d'effectif minimale 3+, départements/régions stricts). Pas d'augmentation Places."
        )
    elif mode == "rachat":
        preview = (
            "Heuristiques mode rachat : `patch_sirene_calls_from_guard_entities` + biais ancienneté "
            "≥ 15 ans quand la requête évoque transmission/cession."
        )
    elif mode == "benchmark":
        preview = (
            "Heuristiques mode benchmark : patches SIRENE + variantes Places régionales pour "
            "construire un panel représentatif."
        )
    else:
        preview = (
            "Heuristiques prospection : `augment_google_places_regional_variant`, "
            "`augment_google_places_boutique_and_club_queries`, `patch_sirene_calls_from_guard_entities` ; "
            "puis `maybe_clamp_prospection_after_plan_patches` (Pappers hors critères **dans le plan**). "
            "Après `execute_plan`, complément téléphone/site via fiche Pappers reste possible (plafond config)."
        )
    return _node(
        "plan_patches",
        "Patches plan (heuristiques)",
        "tool",
        source_file="routers/chat.py",
        default_prompt_preview=preview,
        inputs=[{"name": "ExecutionPlan", "type": "json"}, {"name": "GuardEntities", "type": "json"}],
        outputs=[{"name": "ExecutionPlan", "type": "json"}],
    )


def _node_api_engine(mode: str, sub_blocks: list[str]) -> dict[str, Any]:
    return _node(
        "api_engine",
        "Moteur API (dispatch & orchestration)",
        "tool",
        source_file="services/api_engine.py",
        default_prompt_preview=(
            f"Exécute le plan (sources actives en mode {mode}) : enchaîne les appels par priorité, "
            "délègue aux connecteurs HTTP, maintient la liste courante ; la fusion stricte et le "
            "dédoublonnage sont modélisés par le nœud « Fusion + dédoublonnage » (même fonction "
            "`execute_plan`). Post-collecte : signaux locaux, géocodage BAN ; hors benchmark/rachat, "
            "enrichissement téléphone/site via fiche Pappers (plafond `PAPPERS_CONTACT_ENRICH_MAX`, "
            "distinct du clamp sur le plan)."
        ),
        sub_blocks=sub_blocks,
        inputs=[{"name": "ExecutionPlan", "type": "json"}],
        outputs=[{"name": "CompanyResult[]", "type": "json"}],
        fallback="Plan déterministe si plan LLM vide",
        errors=["timeout", "rate_limit_429", "auth_error"],
    )


def _node_merge_dedup(*, nid: str = "merge_dedup", label: str | None = None) -> dict[str, Any]:
    """Étape documentaire : dans le code, tout se passe dans ``execute_plan`` (pas d'appel réseau)."""
    return _node(
        nid,
        label or "Fusion + dédoublonnage (liste unifiée)",
        "tool",
        source_file="services/api_engine.py",
        default_prompt_preview=(
            "Interne à `execute_plan` : agrège les flux `search` (SIRENE, Google Places, Pappers), "
            "clé `_dedup_key` (SIREN sinon nom+ville), fusion des champs sur collision (`_merge_result`). "
            "Les actions Pappers `get_*` / BODACC / marchés publics s'appliquent ensuite sur cette liste. "
            "Sortie unique vers pertinence : **un** appel LLM sur l'ensemble des lignes."
        ),
        inputs=[
            {"name": "raw_segments", "type": "json"},
            {"name": "ExecutionPlan", "type": "json"},
        ],
        outputs=[{"name": "CompanyResult[]_unifié", "type": "json"}],
    )


def _node_signals_compute() -> dict[str, Any]:
    return _node(
        "signals_compute",
        "Signaux business (interne)",
        "tool",
        source_file="services/signals.py",
        default_prompt_preview=(
            "Calcule les signaux : croissance/baisse CA, dirigeant récent, augmentation capital, "
            "procédure collective (BODACC), marchés publics récents (DECP), entreprise récente."
        ),
        inputs=[{"name": "CompanyResult[]", "type": "json"},
                {"name": "finances", "type": "json"}, {"name": "bodacc", "type": "json"},
                {"name": "marches_publics", "type": "json"}],
        outputs=[{"name": "BusinessSignal[]", "type": "json"}],
    )


def _node_relevance() -> dict[str, Any]:
    return _node(
        "relevance",
        "Pertinence (scoring LLM)",
        "llm",
        model_ref="RELEVANCE_FILTER_MODEL",
        source_file="services/relevance.py",
        default_params={"temperature": 0.0, "max_tokens": 2048, "top_p": 1.0},
        default_prompt_preview=(
            "Score 0–10 par fiche ; seuil **seuil_application** (entier dans le JSON utilisateur) "
            "calculé côté serveur : prospection « large » plus tolérante (4/10), niche mots-clés+géo/volume "
            "plus stricte (6/10), niche + panel dominé Google Maps encore plus stricte (7/10), "
            "autres modes sur barème 5/6. Entrée = liste fusionnée/dédoublonnée."
        ),
        inputs=[{"name": "fiches_compactes", "type": "json"}, {"name": "user_query", "type": "string"}],
        outputs=[{"name": "filtered_rows", "type": "json"}, {"name": "scores", "type": "json"}],
        fallback="conserve la liste brute si tout est exclu (relevance_fallback_unfiltered)",
    )


def _node_static_reply() -> dict[str, Any]:
    return _node(
        "static_reply",
        "Réponse statique (salutation / hors-scope)",
        "output",
        source_file="routers/chat.py",
        inputs=[{"name": "intent", "type": "string"}],
        outputs=[{"name": "assistant_message", "type": "string"}],
    )


def _node_user_output(label: str) -> dict[str, Any]:
    return _node(
        "user_output",
        label,
        "output",
        source_file="routers/chat.py",
        inputs=[{"name": "SearchResults", "type": "json"}],
        outputs=[{"name": "messages", "type": "Message[]"}],
    )


## ────────────────────────────────────────────────────────────────────────────
## Builders par mode (5 graphes distincts, 1 par agent)
## ────────────────────────────────────────────────────────────────────────────


def _build_prospection_graph() -> dict[str, Any]:
    """Mode prospection : pas de QCM forcé, sources larges, enrichissement pitch digital."""
    nodes = [
        _node_filter(),
        _node_guard(),
        _node_sector_confirm(),
        _node_qcm(
            label="QCM critères manquants",
            missing_criteria=[],
            preview_extra="Déclenché seulement si l'utilisateur n'a pas donné secteur+zone.",
        ),
        _node_orchestrator(
            "prospection",
            addendum_summary=(
                "Addendum court : MODE PROSPECTION + hiérarchie explicit priority (structuré = SIRENE 1 ; "
                "niche locale = Google Places 1, SIRENE ≥ 2). Après patches plan (Places + SIRENE) : "
                "``maybe_clamp_prospection_after_plan_patches`` retire les appels Pappers hors critères. "
                "Le prompt générique a la règle unifiée."
            ),
        ),
        _node_plan_patches("prospection"),
        _node_api_engine(
            "prospection",
            sub_blocks=[
                "sirene_api",
                "google_places_api",
                "pappers_api",
                "merge_dedup",
                "geocoding_api",
            ],
        ),
        _api_node("sirene_api"),
        _api_node("google_places_api"),
        _api_node("pappers_api"),
        _node_merge_dedup(),
        _api_node("geocoding_api"),
        _node_relevance(),
        _node(
            "digital_pitch_trigger",
            "Détection requête « pitch digital »",
            "tool",
            source_file="services/digital_pitch_enrichment.py",
            default_prompt_preview=(
                "Heuristique regex sur ``user_message`` : site web, site vitrine, refonte, création, "
                "proposition/offre/prestation digitale, mise en ligne, e-commerce… "
                "(reformulations type « refonte site vitrine » / « moderniser présence web »). "
                "Si oui : **réordonne** la liste (Maps en tête) via ``prioritize_google_maps_discoveries`` "
                "— **ne filtre pas** les lignes."
            ),
            inputs=[{"name": "user_message", "type": "string"}],
            outputs=[{"name": "is_digital_pitch", "type": "boolean"}],
        ),
        _node(
            "digital_pitch",
            "Enrichissement pitch digital (LLM)",
            "llm",
            model_ref="DIGITAL_PITCH_ENRICH_MODEL",
            source_file="services/digital_pitch_enrichment.py",
            default_params={"temperature": 0.0, "max_tokens": 2048, "top_p": 1.0},
            default_prompt_preview=(
                "**Après** relevance : entrée = liste **déjà filtrée** (même ``total``). "
                "N'enlève **aucune** ligne : enrichit in-place les **20** premières "
                "``DIGITAL_PITCH_ENRICH_MAX_ROWS`` (colonnes dans l'**ordre** défini par "
                "``DIGITAL_PITCH_RESULT_COLUMNS`` (dont ``signaux`` en fin de panneau) — ce n'est pas un second filtre). "
                "Le cap **20** de l'aperçu JSON ``metadata.preview`` (chat) est le même ordre de grandeur "
                "— l'export / l'historique gardent **toutes** les lignes post-pertinence."
            ),
            inputs=[{"name": "results", "type": "json"}, {"name": "user_query", "type": "string"}],
            outputs=[{"name": "results_enriched", "type": "json"}],
        ),
        _api_node("openrouter_api", label_override="OpenRouter (gateway LLM)"),
        _node_static_reply(),
        _node_user_output(
            'Sortie : intro + ``metadata.preview`` (20 lignes max si pitch digital, sinon FREE_PREVIEW_ROWS '
            "ou 50 benchmark) — **le pitch n'a pas réduit la liste**, seulement l'aperçu ; "
            "colonnes = ``DIGITAL_PITCH_RESULT_COLUMNS`` si enrichissement appliqué."
        ),
    ]
    edges = [
        _edge("filter", "guard", condition="in_scope"),
        _edge("filter", "static_reply", condition="not in_scope", kind="branch"),
        _edge("guard", "static_reply", condition=GUARD_STATIC_REPLY_EDGE_CONDITION, kind="branch"),
        _edge("guard", "sector_confirm", condition="secteur ambigu", kind="branch"),
        _edge("guard", "qcm", condition="clarification_needed", kind="branch"),
        _edge("guard", "orchestrator", condition="secteur+zone OK"),
        _edge("sector_confirm", "qcm"),
        _edge("orchestrator", "plan_patches"),
        _edge("plan_patches", "api_engine"),
        _edge("api_engine", "sirene_api", condition='source="sirene"', kind="branch"),
        _edge("api_engine", "google_places_api", condition='source="google_places"', kind="branch"),
        _edge("api_engine", "pappers_api", condition="Pappers si besoin CA/dirigeants ou panneau SIRENE étroit", kind="branch"),
        _edge("sirene_api", "merge_dedup"),
        _edge("google_places_api", "merge_dedup"),
        _edge("pappers_api", "merge_dedup"),
        _edge("merge_dedup", "geocoding_api", condition="liste unifiée → lat/lng (BAN)", kind="flow"),
        _edge("geocoding_api", "relevance"),
        _edge(
            "relevance",
            "digital_pitch_trigger",
            kind="flow",
            condition="liste post-pertinence (filtre déjà appliqué ; total inchangé)",
        ),
        _edge(
            "digital_pitch_trigger",
            "digital_pitch",
            condition=(
                "heuristique pitch = oui → enrichissement LLM sur les 20 prem. lignes "
                "(liste complète inchangée hors cap LLM)"
            ),
            kind="branch",
        ),
        _edge("digital_pitch_trigger", "user_output", condition="sinon", kind="branch"),
        _edge("digital_pitch", "user_output", kind="flow", condition="même liste + champs enrichis"),
    ]
    return {"nodes": nodes, "edges": edges}


def _build_sous_traitant_graph() -> dict[str, Any]:
    """Mode sous-traitant : QCM forcé (zone, capacité, type), SIRENE strict, pas de Places ni signaux."""
    nodes = [
        _node_filter(),
        _node_guard(),
        _node(
            "force_qcm_qualification",
            "Force QCM qualification (1re interaction)",
            "tool",
            source_file="routers/chat.py",
            default_prompt_preview=(
                "Si aucun QCM dans l'historique : injecte missing_criteria = "
                "[zone_geo, capacite, type_mission] pour forcer la qualification du besoin."
            ),
            inputs=[{"name": "history", "type": "messages"}, {"name": "guard_result", "type": "json"}],
            outputs=[{"name": "guard_result_patched", "type": "json"}],
        ),
        _node_qcm(
            label="QCM qualification sous-traitant",
            missing_criteria=["zone_geo", "capacite", "type_mission"],
            preview_extra="Toujours déclenché à la 1re interaction.",
        ),
        _node_orchestrator(
            "sous_traitant",
            addendum_summary=(
                "Priorise SIRENE strict (NAF + tranche d'effectif ≥ 3 par défaut + zone). "
                "Pas de Pappers sauf demande explicite (CA/dirigeants). Pas de Google Places."
            ),
        ),
        _node_plan_patches("sous_traitant"),
        _node_api_engine(
            "sous_traitant",
            sub_blocks=["sirene_api", "pappers_api", "merge_dedup"],
        ),
        _api_node("sirene_api"),
        _api_node(
            "pappers_api",
            label_override="Pappers (conditionnel : si CA/dirigeants demandés)",
        ),
        _node_merge_dedup(),
        _api_node("openrouter_api", label_override="OpenRouter (gateway LLM)"),
        _node_relevance(),
        _node_static_reply(),
        _node_user_output('Sortie : "X prestataires potentiels" + tableau qualifié'),
    ]
    edges = [
        _edge("filter", "guard", condition="in_scope"),
        _edge("filter", "static_reply", condition="not in_scope", kind="branch"),
        _edge("guard", "static_reply", condition=GUARD_STATIC_REPLY_EDGE_CONDITION, kind="branch"),
        _edge("guard", "force_qcm_qualification"),
        _edge("force_qcm_qualification", "qcm", condition="QCM absent de l'historique", kind="branch"),
        _edge("force_qcm_qualification", "orchestrator", condition="QCM déjà présent", kind="branch"),
        _edge("qcm", "user_output", condition="attente réponse utilisateur", kind="branch"),
        _edge("orchestrator", "plan_patches"),
        _edge("plan_patches", "api_engine"),
        _edge("api_engine", "sirene_api", condition='source="sirene" (strict)', kind="branch"),
        _edge("api_engine", "pappers_api", condition="si CA/dirigeants", kind="branch"),
        _edge("sirene_api", "merge_dedup"),
        _edge("pappers_api", "merge_dedup"),
        _edge("merge_dedup", "relevance"),
        _edge("relevance", "user_output"),
    ]
    return {"nodes": nodes, "edges": edges}


def _build_benchmark_graph() -> dict[str, Any]:
    """Mode benchmark : pas de Pappers, panel représentatif, stats + framing."""
    nodes = [
        _node_filter(),
        _node_guard(),
        _node_sector_confirm(),
        _node_qcm(
            label="QCM critères manquants",
            missing_criteria=[],
            preview_extra="Déclenché si secteur ou zone manquants.",
        ),
        _node_orchestrator(
            "benchmark",
            addendum_summary=(
                "Construit un panel représentatif (tailles + zones variées si requête large). "
                "Pas d'appel à Pappers (source remplacée). Inclut colonnes catégorie/effectif/dirigeant."
            ),
        ),
        _node_plan_patches("benchmark"),
        _node_api_engine(
            "benchmark",
            sub_blocks=["sirene_api", "google_places_api", "merge_dedup"],
        ),
        _api_node("sirene_api"),
        _api_node("google_places_api"),
        _node_merge_dedup(),
        _api_node("openrouter_api", label_override="OpenRouter (gateway LLM)"),
        _node_relevance(),
        _node(
            "benchmark_stats",
            "Stats benchmark (positions panel)",
            "tool",
            source_file="services/benchmark_stats.py",
            default_prompt_preview=(
                "`enrich_with_benchmark_positions` : calcule pour chaque ligne sa position dans le "
                "panel (CA, effectif, productivité, ancienneté). Ajoute 6 colonnes `benchmark_*`."
            ),
            inputs=[{"name": "rows", "type": "json"}],
            outputs=[{"name": "rows_enriched", "type": "json"}, {"name": "panel_stats", "type": "json"}],
        ),
        _node(
            "benchmark_framing",
            "Cadre rédactionnel benchmark",
            "tool",
            source_file="routers/chat.py",
            default_prompt_preview=(
                "`_build_benchmark_framing` : produit un markdown factuel cadrant les agrégats "
                "(panel size, distribution, plages CA / effectifs)."
            ),
            inputs=[{"name": "rows_enriched", "type": "json"}],
            outputs=[{"name": "markdown", "type": "string"}],
        ),
        _node_static_reply(),
        _node_user_output('Sortie : "X entreprises" + tableau enrichi + cadre markdown (cap preview = 50)'),
    ]
    edges = [
        _edge("filter", "guard", condition="in_scope"),
        _edge("filter", "static_reply", condition="not in_scope", kind="branch"),
        _edge("guard", "static_reply", condition=GUARD_STATIC_REPLY_EDGE_CONDITION, kind="branch"),
        _edge("guard", "sector_confirm", condition="secteur ambigu", kind="branch"),
        _edge("guard", "qcm", condition="clarification_needed", kind="branch"),
        _edge("guard", "orchestrator", condition="prêt à planifier"),
        _edge("sector_confirm", "qcm"),
        _edge("orchestrator", "plan_patches"),
        _edge("plan_patches", "api_engine"),
        _edge("api_engine", "sirene_api", condition='source="sirene" (panel)', kind="branch"),
        _edge("api_engine", "google_places_api", condition='source="google_places"', kind="branch"),
        _edge("sirene_api", "merge_dedup"),
        _edge("google_places_api", "merge_dedup"),
        _edge("merge_dedup", "relevance"),
        _edge("relevance", "benchmark_stats"),
        _edge("benchmark_stats", "benchmark_framing"),
        _edge("benchmark_framing", "user_output"),
    ]
    return {"nodes": nodes, "edges": edges}


def _build_rachat_graph() -> dict[str, Any]:
    """Mode rachat : QCM forcé, signaux légaux (BODACC) + marchés publics (DECP), framing acquisition."""
    nodes = [
        _node_filter(),
        _node_guard(),
        _node(
            "force_qcm_qualification",
            "Force QCM qualification (1re interaction)",
            "tool",
            source_file="routers/chat.py",
            default_prompt_preview=(
                "Si aucun QCM dans l'historique : injecte missing_criteria = "
                "[zone_geo, budget_acquisition, profil_cible, type_reprise]."
            ),
            inputs=[{"name": "history", "type": "messages"}, {"name": "guard_result", "type": "json"}],
            outputs=[{"name": "guard_result_patched", "type": "json"}],
        ),
        _node_qcm(
            label="QCM qualification rachat",
            missing_criteria=["zone_geo", "budget_acquisition", "profil_cible", "type_reprise"],
            preview_extra="Toujours déclenché à la 1re interaction.",
        ),
        _node_orchestrator(
            "rachat",
            addendum_summary=(
                "Pas de Pappers (source remplacée par SIRENE natif). Privilégie les entreprises "
                "≥ 15 ans pour transmission/cession. Inclut colonnes financières + dirigeants."
            ),
        ),
        _node_plan_patches("rachat"),
        _node_api_engine(
            "rachat",
            sub_blocks=["sirene_api", "bodacc_api", "decp_api", "signals_compute"],
        ),
        _api_node("sirene_api"),
        _api_node("bodacc_api"),
        _api_node("decp_api"),
        _node_signals_compute(),
        _api_node("openrouter_api", label_override="OpenRouter (gateway LLM)"),
        _node_relevance(),
        _node(
            "rachat_framing",
            "Cadre rédactionnel rachat (markdown)",
            "tool",
            source_file="routers/chat.py",
            default_prompt_preview=(
                "`_build_rachat_framing` : produit un markdown factuel sans valorisation ni "
                "recommandation (cadre transmission, indicateurs CA / âge / dirigeant)."
            ),
            inputs=[{"name": "rows", "type": "json"}],
            outputs=[{"name": "markdown", "type": "string"}],
        ),
        _node_static_reply(),
        _node_user_output('Sortie : "X cibles potentielles" + tableau financier + cadre markdown'),
    ]
    edges = [
        _edge("filter", "guard", condition="in_scope"),
        _edge("filter", "static_reply", condition="not in_scope", kind="branch"),
        _edge("guard", "static_reply", condition=GUARD_STATIC_REPLY_EDGE_CONDITION, kind="branch"),
        _edge("guard", "force_qcm_qualification"),
        _edge("force_qcm_qualification", "qcm", condition="QCM absent", kind="branch"),
        _edge("force_qcm_qualification", "orchestrator", condition="QCM déjà fait", kind="branch"),
        _edge("qcm", "user_output", condition="attente réponse utilisateur", kind="branch"),
        _edge("orchestrator", "plan_patches"),
        _edge("plan_patches", "api_engine"),
        _edge("api_engine", "sirene_api", condition='source="sirene" (≥15 ans)', kind="branch"),
        _edge("api_engine", "bodacc_api", condition="signaux légaux", kind="branch"),
        _edge("api_engine", "decp_api", condition="marchés publics récents", kind="branch"),
        _edge("sirene_api", "signals_compute"),
        _edge("bodacc_api", "signals_compute"),
        _edge("decp_api", "signals_compute"),
        _edge("signals_compute", "relevance"),
        _edge("relevance", "rachat_framing"),
        _edge("rachat_framing", "user_output"),
    ]
    return {"nodes": nodes, "edges": edges}


_CHAT_GRAPH_BUILDERS: dict[str, Any] = {
    "prospection": _build_prospection_graph,
    "sous_traitant": _build_sous_traitant_graph,
    "benchmark": _build_benchmark_graph,
    "rachat": _build_rachat_graph,
}


def build_chat_graph(agent_id: str) -> dict[str, Any]:
    builder = _CHAT_GRAPH_BUILDERS.get(agent_id)
    if builder is None:
        raise KeyError(agent_id)
    return builder()


def build_atelier_graph() -> dict[str, Any]:
    nodes: list[dict[str, Any]] = [
        _node(
            "atelier_qcm",
            "QCM projet Atelier",
            "llm",
            model_ref="GUARD_MODEL",
            source_file="services/agent.py",
            default_params={"temperature": 0.22, "max_tokens": 1408, "top_p": 1.0},
            default_prompt_preview="Génère 0–8 questions ciblées sur le pitch…",
            inputs=[{"name": "pitch", "type": "string"}],
            outputs=[{"name": "questions", "type": "json"}],
            fallback="questions de secours Atelier",
        ),
        _node(
            "strategic_plan",
            "Plan stratégique (JSON)",
            "llm",
            model_ref="ATELIER_BUSINESS_MODEL",
            source_file="services/agent.py",
            default_params={"temperature": 0.25, "max_tokens": 4096, "top_p": 1.0},
            default_prompt_preview="Plan stratégique interne (archetype, segments…)…",
            inputs=[{"name": "pitch+réponses", "type": "string"}],
            outputs=[{"name": "plan_json", "type": "json"}],
        ),
        _node(
            "dossier_fill",
            "Dossier business (JSON complet)",
            "llm",
            model_ref="ATELIER_BUSINESS_MODEL",
            source_file="services/agent.py",
            default_params={"temperature": 0.2, "max_tokens": 16384, "top_p": 1.0},
            default_prompt_preview="Remplir brief, canvas, flows, segments, synthèse…",
            inputs=[{"name": "pitch+plan", "type": "string"}],
            outputs=[{"name": "BusinessDossier", "type": "json"}],
        ),
        _node(
            "segment_guard",
            "Segment — Guard",
            "llm",
            model_ref="GUARD_MODEL",
            source_file="services/agent.py",
            default_params={"temperature": 0.0, "max_tokens": 1024, "top_p": 1.0},
            inputs=[{"name": "segment.query", "type": "string"}],
            outputs=[{"name": "GuardResult", "type": "json"}],
        ),
        _node(
            "segment_orchestrator",
            "Segment — Orchestrateur",
            "llm",
            model_ref="ORCHESTRATOR_MODEL",
            source_file="services/orchestrator.py",
            default_params={"temperature": 0.0, "max_tokens": 2048, "top_p": 1.0},
            inputs=[{"name": "guard_json", "type": "json"}],
            outputs=[{"name": "ExecutionPlan", "type": "json"}],
        ),
        _node(
            "segment_api_engine",
            "Segment — Moteur API (dispatch)",
            "tool",
            source_file="services/api_engine.py",
            sub_blocks=["sirene_api", "google_places_api", "pappers_api", "segment_merge_dedup"],
            inputs=[{"name": "plan", "type": "json"}],
            outputs=[{"name": "résultats", "type": "json"}],
        ),
        _api_node("sirene_api"),
        _api_node("google_places_api"),
        _api_node("pappers_api"),
        _node_merge_dedup(
            nid="segment_merge_dedup",
            label="Segment — Fusion + dédoublonnage",
        ),
        _api_node("openrouter_api", label_override="OpenRouter (gateway LLM)"),
        _node(
            "segment_relevance",
            "Segment — Pertinence",
            "llm",
            model_ref="RELEVANCE_FILTER_MODEL",
            source_file="services/relevance.py",
            default_params={"temperature": 0.0, "max_tokens": 2048, "top_p": 1.0},
            inputs=[{"name": "résultats", "type": "json"}],
            outputs=[{"name": "scores", "type": "json"}],
        ),
        _node(
            "checklist_outline",
            "Checklist — outline",
            "llm",
            model_ref="ATELIER_BUSINESS_MODEL",
            source_file="services/atelier_checklist_pipeline.py",
            default_params={"temperature": 0.22, "max_tokens": 4096, "top_p": 1.0},
            default_prompt_preview="Produit outline_sections + headline_draft…",
        ),
        _node(
            "checklist_detail",
            "Checklist — détail par chunks",
            "llm",
            model_ref="ATELIER_BUSINESS_MODEL",
            source_file="services/atelier_checklist_pipeline.py",
            default_params={"temperature": 0.22, "max_tokens": 8192, "top_p": 1.0},
            default_prompt_preview="Remplit les sections par paquets…",
        ),
        _node(
            "checklist_qa",
            "Checklist — QA finale",
            "llm",
            model_ref="ATELIER_BUSINESS_MODEL",
            source_file="services/atelier_checklist_pipeline.py",
            default_params={"temperature": 0.18, "max_tokens": 11000, "top_p": 1.0},
            default_prompt_preview="Contrôle qualité du brouillon checklist…",
        ),
        _node(
            "canvas_regen",
            "Régénération canvas",
            "llm",
            model_ref="ATELIER_BUSINESS_MODEL",
            source_file="services/agent.py",
            default_params={"temperature": 0.2, "max_tokens": 4096, "top_p": 1.0},
        ),
        _node(
            "flows_regen",
            "Régénération flux",
            "llm",
            model_ref="ATELIER_BUSINESS_MODEL",
            source_file="services/agent.py",
            default_params={"temperature": 0.2, "max_tokens": 4096, "top_p": 1.0},
        ),
        _node(
            "titles",
            "Titres conversation / dossier",
            "llm",
            model_ref="FILTER_MODEL",
            source_file="services/agent.py",
            default_params={"temperature": 0.2, "max_tokens": 64, "top_p": 1.0},
        ),
    ]
    edges = [
        _edge("atelier_qcm", "strategic_plan"),
        _edge("strategic_plan", "dossier_fill"),
        _edge("dossier_fill", "segment_guard", condition="pour chaque segment"),
        _edge("segment_guard", "segment_orchestrator"),
        _edge("segment_orchestrator", "segment_api_engine"),
        _edge("segment_api_engine", "sirene_api", condition='source="sirene"', kind="branch"),
        _edge("segment_api_engine", "google_places_api", condition='source="google_places"', kind="branch"),
        _edge("segment_api_engine", "pappers_api", condition='source="pappers"', kind="branch"),
        _edge("sirene_api", "segment_merge_dedup"),
        _edge("google_places_api", "segment_merge_dedup"),
        _edge("pappers_api", "segment_merge_dedup"),
        _edge("segment_merge_dedup", "segment_relevance"),
        _edge("dossier_fill", "checklist_outline", condition="régénération checklist", kind="branch"),
        _edge("checklist_outline", "checklist_detail"),
        _edge("checklist_detail", "checklist_qa"),
        _edge("dossier_fill", "canvas_regen", condition="action UI", kind="branch"),
        _edge("dossier_fill", "flows_regen", condition="action UI", kind="branch"),
        _edge("atelier_qcm", "titles", kind="branch"),
    ]
    return {"nodes": nodes, "edges": edges}


def get_agent_graph_definition(agent_id: str) -> dict[str, Any]:
    if agent_id not in AGENT_IDS:
        raise KeyError(agent_id)
    if agent_id == "atelier":
        graph = build_atelier_graph()
        label = "Atelier création d'entreprise"
    else:
        graph = build_chat_graph(agent_id)
        label = MODE_LABELS.get(agent_id, agent_id)  # type: ignore[arg-type]
    return {"agent_id": agent_id, "label": label, "graph": graph}


def list_all_agent_definitions() -> list[dict[str, Any]]:
    return [get_agent_graph_definition(aid) for aid in AGENT_IDS]
