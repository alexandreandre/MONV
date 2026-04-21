"""Normalisation QCM (sélection multiple + option neutre)."""

from __future__ import annotations

import os

os.environ.setdefault("SKIP_DB_VERIFY_ON_STARTUP", "true")
os.environ.setdefault("SUPABASE_URL", "https://placeholder.supabase.co")
os.environ.setdefault("SUPABASE_SERVICE_KEY", "placeholder-service-key")

from models.schemas import QcmOption, QcmQuestion  # noqa: E402
from services import conversationalist as conv  # noqa: E402


def test_normalize_forces_multiple_except_budget():
    q = QcmQuestion(
        id="zone_geo",
        question="Zone ?",
        options=[
            QcmOption(id="lyon", label="Lyon"),
            QcmOption(id="autre", label="Autre", free_text=True),
        ],
        multiple=False,
    )
    out = conv._normalize_qcm_question(q)
    assert out.multiple is True
    assert any(o.id == "pas_de_preference" for o in out.options)


def test_normalize_budget_stays_single_choice():
    q = QcmQuestion(
        id="budget_acquisition",
        question="Budget ?",
        options=[
            QcmOption(id="a", label="Moins de 500k€"),
            QcmOption(id="autre", label="Autre", free_text=True),
        ],
        multiple=True,
    )
    out = conv._normalize_qcm_question(q)
    assert out.multiple is False
    assert any(o.id == "pas_de_preference" for o in out.options)


def test_normalize_sector_confirm_multiple_and_neutral():
    q = QcmQuestion(
        id="secteur_confirmation",
        question="Lesquels ?",
        options=[
            QcmOption(id="a", label="A"),
            QcmOption(id="autre", label="Autre", free_text=True),
        ],
        multiple=False,
    )
    out = conv._normalize_qcm_question(q)
    assert out.multiple is True
    assert any(o.id == "pas_de_preference" for o in out.options)


def test_parse_questions_then_normalize():
    raw = {
        "intro": "Hi",
        "questions": [
            {
                "id": "taille",
                "question": "Taille ?",
                "options": [
                    {"id": "tpe", "label": "TPE"},
                    {"id": "autre", "label": "Autre", "free_text": True},
                ],
                "multiple": False,
            }
        ],
    }
    intro, qs = conv._parse_questions(raw)
    assert intro == "Hi"
    norm = conv._normalize_qcm_questions(qs)
    assert norm[0].multiple is True
    assert any(o.id == "pas_de_preference" for o in norm[0].options)
