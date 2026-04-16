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

Mode = Literal["prospection", "sous_traitant", "client", "rachat"]

VALID_MODES: tuple[Mode, ...] = ("prospection", "sous_traitant", "client", "rachat")
DEFAULT_MODE: Mode = "prospection"


def _legacy_alias(value: str | None) -> str | None:
    """Compatibilité ascendante : anciens identifiants acceptés."""
    _ALIASES: dict[str, str] = {
        "fournisseurs": "sous_traitant",
        "achat": "client",
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
    "client": "Client",
    "rachat": "Rachat",
}


# ── Colonnes prioritaires par mode ────────────────────────────────────────────
#
# Les colonnes listées ici sont ajoutées en TÊTE de la liste renvoyée par
# l'orchestrateur (après `nom`). Les colonnes par défaut historiques restent
# présentes derrière. Aucune n'est retirée → pas de régression sur l'export.

MODE_PRIORITY_COLUMNS: dict[Mode, list[str]] = {
    "prospection": [
        # Comportement actuel : on garde l'ordre par défaut.
    ],
    "sous_traitant": [
        # Acheteur : on veut juger taille, ancienneté, capacité.
        "effectif_label",
        "date_creation",
        "forme_juridique",
        "categorie_entreprise",
        "numero_tva",
        "site_web",
        "telephone",
    ],
    "client": [
        # Compte existant : on veut identifier vite + signaux d'évolution.
        "siren",
        "effectif_label",
        "chiffre_affaires",
        "variation_ca_pct",
        "dirigeant_nom",
        "site_web",
    ],
    "rachat": [
        # Repreneur : focus financier + transmission.
        "categorie_entreprise",
        "date_creation",
        "effectif_label",
        "chiffre_affaires",
        "variation_ca_pct",
        "resultat_net",
        "ebe",
        "capitaux_propres",
        "capital_social",
        "dirigeant_nom",
        "dirigeant_fonction",
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
        "L'utilisateur cherche un sous-traitant ou prestataire à qui confier "
        "une exécution, pas un client à démarcher.\n"
        "- Priorise SIRENE pour les filtres NAF/effectif/zone (capacité = critère clé).\n"
        "- Si aucun effectif n'est précisé, suppose au minimum 3 salariés "
        "(tranche_effectif_salarie='02,03,11,12,21,22,31,32,41,42,51,52,53').\n"
        "- Inclure dans `columns` : effectif_label, date_creation, forme_juridique, "
        "categorie_entreprise, numero_tva, site_web, telephone.\n"
        "- Ne propose pas Pappers sauf si l'utilisateur demande explicitement CA / dirigeants."
    ),
    "client": (
        "\n\nMODE ACTIF : CLIENT (analyse portefeuille).\n"
        "L'utilisateur veut analyser ou enrichir des comptes qu'il connaît déjà.\n"
        "- Si la requête contient un ou plusieurs SIREN à 9 chiffres, génère un "
        "appel `pappers` action `search` par SIREN (params={\"siren\": \"...\"}) "
        "puis un `get_finances` et un `get_dirigeants` (priority croissants).\n"
        "- Sinon, fais une recherche SIRENE classique.\n"
        "- Inclure dans `columns` : siren, effectif_label, chiffre_affaires, "
        "variation_ca_pct, dirigeant_nom, site_web.\n"
        "- Coût plancher : 3 crédits (enrichissement requis)."
    ),
    "rachat": (
        "\n\nMODE ACTIF : RACHAT (cadre d'analyse business).\n"
        "L'utilisateur identifie des cibles potentielles d'acquisition.\n"
        "- Si la clé Pappers est disponible, ajoute SYSTÉMATIQUEMENT un appel "
        "`pappers` action `get_finances` ET `get_dirigeants` après la recherche "
        "principale (filtre rentabilité + âge dirigeant = signaux transmission).\n"
        "- Privilégie les entreprises créées il y a 15 ans ou plus quand la "
        "requête évoque transmission / cession / reprise.\n"
        "- Inclure dans `columns` : categorie_entreprise, date_creation, "
        "effectif_label, chiffre_affaires, variation_ca_pct, resultat_net, ebe, "
        "capitaux_propres, capital_social, dirigeant_nom, dirigeant_fonction.\n"
        "- Coût plancher : 3 crédits (Pappers requis pour analyse).\n"
        "- IMPORTANT : tu ne fournis aucune valorisation, aucun conseil "
        "d'investissement, aucune recommandation juridique ou comptable. "
        "Tu produis un cadre d'analyse factuel à partir des données publiques."
    ),
}


# Coût plancher conseillé à l'orchestrateur (le LLM peut dépasser).
MODE_CREDITS_FLOOR: dict[Mode, int] = {
    "prospection": 1,
    "sous_traitant": 1,
    "client": 3,
    "rachat": 3,
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


def credits_floor_for_mode(mode: Mode) -> int:
    return MODE_CREDITS_FLOOR.get(mode, 1)
