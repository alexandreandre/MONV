"""QCM Atelier — parsing et finalisation (sans LLM)."""

from __future__ import annotations

from models.schemas import QcmOption, QcmQuestion

_FALLBACK_ATELIER_QUESTIONS: list[QcmQuestion] = [
    QcmQuestion(
        id="cible",
        question="Qui est ta clientèle prioritaire au démarrage ?",
        options=[
            QcmOption(id="b2c", label="Particuliers / consommateurs finaux"),
            QcmOption(id="b2b", label="Entreprises, pros ou B2B"),
            QcmOption(id="mixte", label="Mixte (B2C et B2B dès le début)"),
            QcmOption(id="communaute", label="Communauté / adhérents / membres"),
            QcmOption(id="autre", label="Autre", free_text=True),
        ],
        multiple=False,
    ),
    QcmQuestion(
        id="modele_revenus",
        question="Comment l'argent rentre surtout les 12–24 premiers mois ?",
        options=[
            QcmOption(
                id="vente_directe",
                label="Vente directe (sur place, boutique, service rendu)",
            ),
            QcmOption(
                id="omnicanal",
                label="Mix sur place + livraison / commande en ligne",
            ),
            QcmOption(id="ecommerce", label="Vente en ligne (expédition ou retrait)"),
            QcmOption(id="abo", label="Abonnement, adhésion ou récurrence"),
            QcmOption(id="presta", label="Prestations / projet / conseil"),
            QcmOption(id="autre", label="Autre", free_text=True),
        ],
        multiple=True,
    ),
    QcmQuestion(
        id="localisation",
        question="Où se joue concrètement ton activité (et la vente à distance si tu en fais) ?",
        options=[
            QcmOption(id="ville", label="Une ville ou agglomération précise"),
            QcmOption(id="region", label="Une région ou plusieurs départements"),
            QcmOption(id="national", label="France entière (dont e-commerce)"),
            QcmOption(id="ue", label="France + export / UE"),
            QcmOption(id="autre", label="Autre", free_text=True),
        ],
        multiple=False,
    ),
    QcmQuestion(
        id="canaux",
        question="Comment comptes-tu surtout toucher tes clients au lancement ?",
        options=[
            QcmOption(id="lieu", label="Lieu physique (passage, réservations, vitrine)"),
            QcmOption(id="web", label="Site, réseaux, marketplaces en ligne"),
            QcmOption(id="partenaires", label="Partenaires, prescripteurs, distributeurs"),
            QcmOption(id="reseau", label="Bouche-à-oreille / réseau perso / B2B direct"),
            QcmOption(id="autre", label="Autre", free_text=True),
        ],
        multiple=True,
    ),
    QcmQuestion(
        id="budget",
        question="Quelle fourchette de lancement est réaliste pour ton format (local, stock, équipe) ?",
        options=[
            QcmOption(id="lt80k", label="Moins de 80 k€"),
            QcmOption(id="80_200k", label="80 k€ – 200 k€"),
            QcmOption(id="200_500k", label="200 k€ – 500 k€"),
            QcmOption(id="500k_1m5", label="500 k€ – 1,5 M€"),
            QcmOption(id="gt1m5", label="Plus de 1,5 M€"),
            QcmOption(id="autre", label="Autre", free_text=True),
        ],
        multiple=False,
    ),
]

_ATELIER_QCM_STEP_ORDER: dict[str, int] = {
    "cible": 0,
    "priorite_marche": 0,
    "segments_clients": 0,
    "modele_revenus": 1,
    "sources_revenus": 1,
    "localisation": 2,
    "zone_livraison": 2,
    "perimetre_geo": 2,
    "canaux": 3,
    "go_to_market": 3,
    "conformite": 4,
    "reglementation": 4,
    "import_logistique": 4,
    "licences": 4,
    "budget": 5,
    "ambition": 6,
}

def _sort_atelier_questions(questions: list[QcmQuestion]) -> list[QcmQuestion]:
    def rank(q: QcmQuestion) -> tuple[int, str]:
        return (_ATELIER_QCM_STEP_ORDER.get(q.id, 50), q.id)

    return sorted(questions, key=rank)


def parse_qcm_raw(raw: dict) -> tuple[str, list[QcmQuestion]]:
    intro = raw.get("intro") or "Affinons ton projet en quelques questions :"
    questions: list[QcmQuestion] = []
    for q in raw.get("questions", []) or []:
        options: list[QcmOption] = []
        has_autre = False
        for o in q.get("options", []) or []:
            opt = QcmOption(
                id=str(o.get("id", "") or ""),
                label=str(o.get("label", "") or ""),
                free_text=bool(o.get("free_text", False)),
            )
            if opt.free_text:
                has_autre = True
            options.append(opt)
        if not has_autre:
            options.append(QcmOption(id="autre", label="Autre", free_text=True))
        questions.append(
            QcmQuestion(
                id=str(q.get("id", "") or ""),
                question=str(q.get("question", "") or ""),
                options=options,
                multiple=bool(q.get("multiple", False)),
            )
        )
    return intro, questions


def finalize_atelier_qcm(
    intro: str,
    questions: list[QcmQuestion],
) -> tuple[str, list[QcmQuestion]]:
    """Filtre, déduplique, trie et plafonne le QCM.

    Si aucune question n'est exploitable après nettoyage, renvoie une liste vide :
    le pitch suffit et l'UI enchaîne sur la génération du dossier sans QCM.
    """
    seen: set[str] = set()
    cleaned: list[QcmQuestion] = []
    for q in questions:
        qid = (q.id or "").strip()
        if not qid or not (q.question or "").strip():
            continue
        if qid in seen:
            continue
        seen.add(qid)
        cleaned.append(q)
    ordered = _sort_atelier_questions(cleaned)[:8]

    if not ordered:
        intro_out = (
            intro.strip()
            or "Ton pitch est assez complet pour enchaîner sur le dossier sans question "
            "complémentaire."
        )
        return intro_out, []

    intro_out = intro.strip() or "Affinons ton projet :"
    return intro_out, ordered
