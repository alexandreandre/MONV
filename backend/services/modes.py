"""
Définitions des 4 modes d'usage MONV.

Un mode adapte trois choses :
  1. Le prompt orchestrateur (quels critères privilégier, quelles colonnes inclure)
  2. L'ordre des colonnes par défaut renvoyées dans `ExecutionPlan.columns`
  3. Le cadre éditorial du message d'introduction des résultats (cf. chat.py)

Le mode `prospection` reproduit le comportement historique : c'est le défaut
quand `mode` est absent du `ChatRequest`, ce qui garantit la non-régression.
"""

from __future__ import annotations

from typing import Literal

Mode = Literal["prospection", "sous_traitant", "benchmark", "rachat"]

VALID_MODES: tuple[Mode, ...] = ("prospection", "sous_traitant", "benchmark", "rachat")
DEFAULT_MODE: Mode = "prospection"


def _legacy_alias(value: str | None) -> str | None:
    """Compatibilité ascendante : anciens identifiants acceptés."""
    _ALIASES: dict[str, str] = {
        "fournisseurs": "sous_traitant",
        "achat": "benchmark",
        "client": "benchmark",
    }
    if value in _ALIASES:
        return _ALIASES[value]
    return value


def normalize_mode(value: str | None) -> Mode:
    """Renvoie un mode valide ou le défaut. Les valeurs inconnues sont ignorées
    plutôt que rejetées : robustesse pour l'historique sans `mode`."""
    aliased = _legacy_alias(value)
    if aliased and aliased in VALID_MODES:
        return aliased  # type: ignore[return-value]
    return DEFAULT_MODE


# ── Métadonnées affichables côté UI (synchronisées avec frontend/src/lib/modes.ts) ──

MODE_LABELS: dict[Mode, str] = {
    "prospection": "Prospection",
    "sous_traitant": "Sous-traitant",
    "benchmark": "Benchmark",
    "rachat": "Rachat",
}


# ── Colonnes prioritaires par mode ────────────────────────────────────────────
#
# Les colonnes listées ici sont ajoutées en TÊTE de la liste renvoyée par
# l'orchestrateur (après `nom`). Les colonnes par défaut historiques restent
# présentes derrière. Aucune n'est retirée → pas de régression sur l'export.

# Colonnes affichées / exportées en mode prospection (ordre figé).
PROSPECTION_RESULT_COLUMNS: list[str] = [
    "nom",
    "telephone",
    "site_web",
    "adresse",
    "code_postal",
    "ville",
    "google_maps_url",
]

MODE_PRIORITY_COLUMNS: dict[Mode, list[str]] = {
    "prospection": [
        # Comportement actuel : on garde l'ordre par défaut.
    ],
    "sous_traitant": [
        "effectif_label",
        "date_creation",
        "categorie_entreprise",
        "telephone",
        "site_web",
        "ville",
        "forme_juridique",
    ],
    "benchmark": [
        "libelle_activite",
        "activite_principale",
        "categorie_entreprise",
        "effectif_label",
        "date_creation",
        "forme_juridique",
        "dirigeant_nom",
        "dirigeant_fonction",
        "siren",
        "ville",
        "region",
    ],
    "rachat": [
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
    ],
}


# ── Addendum injecté dans le system prompt de l'orchestrateur ─────────────────
#
# L'orchestrateur reçoit un message système de base (générique) ; on lui ajoute
# un suffixe contextualisé par mode. Il reste libre de choisir les sources mais
# on cadre l'intention.

MODE_ORCHESTRATOR_ADDENDUM: dict[Mode, str] = {
    "prospection": "",
    "sous_traitant": (
        "\n\nMODE ACTIF : SOUS-TRAITANT.\n"
        "L'utilisateur cherche un prestataire ou sous-traitant à qui confier "
        "une exécution. Il n'est PAS en mode prospection commerciale.\n"
        "CRITÈRES CLÉS à extraire et prioriser :\n"
        "1. Type de prestation exacte (métier, spécialité technique)\n"
        "2. Capacité minimale : effectif, tranche de taille\n"
        "3. Zone géographique d'intervention\n"
        "4. Ancienneté minimum si mentionnée (entreprise établie = gage de sérieux)\n"
        "RÈGLES :\n"
        "- Priorise SIRENE avec filtres NAF/effectif/zone stricts.\n"
        "- Si aucun effectif précisé : suppose minimum 3 salariés "
        "(tranche_effectif_salarie='02,03,11,12,21,22,31,32,41,42,51,52,53').\n"
        "- Ne propose PAS Pappers sauf si l'utilisateur demande explicitement CA ou dirigeants.\n"
        "- Inclure dans `columns` : effectif_label, date_creation, categorie_entreprise, "
        "telephone, site_web, ville, forme_juridique.\n"
        "- Le message de résultats doit cadrer les résultats comme une liste de "
        "prestataires potentiels à qualifier, pas comme des prospects à démarcher."
    ),
    "benchmark": (
        "\n\nMODE ACTIF : BENCHMARK (secteur / marché).\n"
        "L'utilisateur veut un panorama chiffré et comparable d'un secteur, d'un "
        "marché ou d'un périmètre NAF/géographique — pour un livrable type "
        "note consultant, mémo banque ou pitch fondateur (données publiques, pas de "
        "conseil personnalisé ni de valorisation).\n"
        "- Construire un panneau d'entreprises représentatif (tailles et zones variées "
        "si la requête est large ; sinon respecter strictement les filtres).\n"
        "- Ne pas appeler Pappers en mode benchmark (source remplacée).\n"
        "- Inclure dans `columns` : libelle_activite, activite_principale, "
        "categorie_entreprise, effectif_label, date_creation, forme_juridique, "
        "dirigeant_nom, dirigeant_fonction, siren, ville, region.\n"
        "- Ne pas inventer de tendance de marché non vérifiable ; les agrégats "
        "éventuels se déduisent des lignes exportées.\n"
        "- Coût plancher : 1 crédit (panneau SIRENE / signaux sans enrichissement Pappers)."
    ),
    "rachat": (
        "\n\nMODE ACTIF : RACHAT (cadre d'analyse business).\n"
        "L'utilisateur identifie des cibles potentielles d'acquisition.\n"
        "- Ne pas appeler Pappers (source remplacée par SIRENE natif).\n"
        "- Privilégie les entreprises créées il y a 15 ans ou plus quand la "
        "requête évoque transmission / cession / reprise.\n"
        "- Inclure dans `columns` : categorie_entreprise, date_creation, "
        "effectif_label, chiffre_affaires, variation_ca_pct, resultat_net, "
        "ca_n_minus_1, annee_dernier_ca, dirigeant_nom, dirigeant_fonction, "
        "forme_juridique, siren, ville, region.\n"
        "- Coût plancher : 1 crédit (panneau SIRENE / signaux sans enrichissement Pappers).\n"
        "- IMPORTANT : tu ne fournis aucune valorisation, aucun conseil "
        "d'investissement, aucune recommandation juridique ou comptable. "
        "Tu produis un cadre d'analyse factuel à partir des données publiques."
    ),
}


# Coût plancher conseillé à l'orchestrateur (le LLM peut dépasser).
MODE_CREDITS_FLOOR: dict[Mode, int] = {
    "prospection": 1,
    "sous_traitant": 1,
    "benchmark": 1,
    "rachat": 1,
}



def addendum_for_mode(mode: Mode) -> str:
    return MODE_ORCHESTRATOR_ADDENDUM.get(mode, "")


def reorder_columns_for_mode(columns: list[str], mode: Mode) -> list[str]:
    """Place les colonnes prioritaires du mode juste après `nom` sans rien retirer."""
    priority = MODE_PRIORITY_COLUMNS.get(mode, [])
    if not priority:
        return columns

    seen: set[str] = set()
    ordered: list[str] = []

    for col in columns:
        if col == "nom":
            ordered.append(col)
            seen.add(col)
            for pcol in priority:
                if pcol not in seen and pcol in columns:
                    ordered.append(pcol)
                    seen.add(pcol)
        elif col not in seen:
            ordered.append(col)
            seen.add(col)

    if "nom" not in seen:
        ordered = ["nom"] + [c for c in priority if c in columns and c != "nom"] + [
            c for c in ordered if c != "nom"
        ]

    return ordered


def apply_result_columns_for_mode(columns: list[str], mode: Mode) -> list[str]:
    """Réduit l’aperçu / les métadonnées `columns` au panneau attendu par mode."""
    if mode == "prospection":
        return list(PROSPECTION_RESULT_COLUMNS)
    return columns


def credits_floor_for_mode(mode: Mode) -> int:
    return MODE_CREDITS_FLOOR.get(mode, 1)
