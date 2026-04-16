"""QCM Atelier — parsing et finalisation (sans LLM)."""

from __future__ import annotations

from models.schemas import QcmOption, QcmQuestion

_FALLBACK_ATELIER_QUESTIONS: list[QcmQuestion] = [
    QcmQuestion(
        id="cible",
        question="À qui s'adresse ton offre principalement ?",
        options=[
            QcmOption(id="b2c", label="Particuliers (B2C)"),
            QcmOption(id="b2b", label="Entreprises (B2B)"),
            QcmOption(id="b2b2c", label="Les deux (B2B2C)"),
            QcmOption(id="admin", label="Administrations / Collectivités"),
            QcmOption(id="autre", label="Autre", free_text=True),
        ],
        multiple=False,
    ),
    QcmQuestion(
        id="modele_revenus",
        question="Quel modèle de revenus envisages-tu ?",
        options=[
            QcmOption(id="vente", label="Ventes directes"),
            QcmOption(id="abo", label="Abonnement / récurrent"),
            QcmOption(id="commission", label="Commission / place de marché"),
            QcmOption(id="service", label="Services / prestations"),
            QcmOption(id="licence", label="Licence / SaaS"),
            QcmOption(id="autre", label="Autre", free_text=True),
        ],
        multiple=False,
    ),
    QcmQuestion(
        id="budget",
        question="Quelle enveloppe prévois-tu pour le lancement ?",
        options=[
            QcmOption(id="lt20k", label="Moins de 20 k€"),
            QcmOption(id="20_80k", label="20 k€ – 80 k€"),
            QcmOption(id="80_250k", label="80 k€ – 250 k€"),
            QcmOption(id="250k_1m", label="250 k€ – 1 M€"),
            QcmOption(id="gt1m", label="Plus de 1 M€"),
            QcmOption(id="autre", label="Autre", free_text=True),
        ],
        multiple=False,
    ),
    QcmQuestion(
        id="ambition",
        question="Quelle taille vises-tu à 2-3 ans ?",
        options=[
            QcmOption(id="solo", label="Solo / indépendant"),
            QcmOption(id="tpe", label="Très petite équipe (2-9)"),
            QcmOption(id="pme", label="PME (10-50)"),
            QcmOption(id="scale", label="Scale-up (50+)"),
            QcmOption(id="autre", label="Autre", free_text=True),
        ],
        multiple=False,
    ),
]

_ATELIER_QCM_STEP_ORDER: dict[str, int] = {
    "cible": 0,
    "modele_revenus": 1,
    "localisation": 2,
    "budget": 3,
    "canaux": 4,
    "ambition": 5,
}

_PITCH_COMPLETE_CONFIRM_Q = QcmQuestion(
    id="validation_dossier",
    question=(
        "Souhaites-tu ajouter une dernière précision avant que je génère "
        "ton dossier complet ?"
    ),
    options=[
        QcmOption(
            id="pret",
            label="Non, génère le dossier à partir de mon pitch",
            free_text=False,
        ),
        QcmOption(
            id="precision",
            label="Oui, j'ai une précision à ajouter",
            free_text=True,
        ),
    ],
    multiple=False,
)


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
    """Filtre, déduplique, trie et plafonne le QCM ; complète si zéro question."""
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
    ordered = _sort_atelier_questions(cleaned)[:5]

    if not ordered:
        intro_out = (
            intro.strip()
            or "Ton pitch est déjà très clair — une dernière étape avant le dossier."
        )
        return intro_out, [_PITCH_COMPLETE_CONFIRM_Q]

    intro_out = intro.strip() or "Affinons ton projet :"
    return intro_out, ordered
