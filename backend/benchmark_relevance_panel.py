#!/usr/bin/env python3
"""
Panel unitaire du filtre de pertinence (seuil + invariants), sans appel réseau.

Usage (depuis le dossier backend) :
    python benchmark_relevance_panel.py

Découvre aussi les cas via pytest :
    pytest benchmark_relevance_panel.py -q
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from models.schemas import GuardEntity, GuardResult  # noqa: E402
from services.relevance import _compute_threshold  # noqa: E402

_BASE = 5
_NICHE = 6


def _gr(**entity_fields) -> GuardResult:
    return GuardResult(
        intent="recherche_entreprise",
        entities=GuardEntity(**entity_fields),
        confidence=0.9,
    )


# ≥30 cas : combinaisons mots_cles × géographie × secteur × volume
THRESHOLD_CASES: list[tuple[str, GuardResult, int, int]] = []

# 1) Niche : mots-clés + au moins un ancrage géographique
_geo_fields = [
    {"localisation": "Marseille"},
    {"departement": "13"},
    {"departement": "75"},
    {"region": "PACA"},
    {"region": "Île-de-France"},
    {"localisation": "Lyon", "departement": "69"},
]
for i, geo in enumerate(_geo_fields):
    THRESHOLD_CASES.append(
        (f"niche_geo_{i}", _gr(mots_cles=["commerce", "sport"], **geo), 50, _NICHE)
    )

# 2) Mots-clés seuls : seuil de base sauf gros volume
for n in (1, 50, 100, 200, 201, 500):
    THRESHOLD_CASES.append(("kw_only_n_%d" % n, _gr(mots_cles=["usinage"]), n, _NICHE if n > 200 else _BASE))

# 3) Géo + secteur + volume (sans mots-clés)
for n in (299, 300, 301, 400):
    THRESHOLD_CASES.append(
        (
            "geo_sector_n_%d" % n,
            _gr(localisation="Paris", secteur="BTP"),
            n,
            _BASE if n <= 300 else _NICHE,
        )
    )

# 4) Région seule + mots-clés
THRESHOLD_CASES.append(("kw_region", _gr(mots_cles=["pharmacie"], region="Bretagne"), 30, _NICHE))

# 5) Département seul + mots-clés (cas « dans le 13 »)
THRESHOLD_CASES.append(("kw_dept_only", _gr(mots_cles=["boutique", "sport"], departement="13"), 80, _NICHE))

# 6) Aucun critère « niche » : base
THRESHOLD_CASES.append(("empty_entities", _gr(), 100, _BASE))
THRESHOLD_CASES.append(("sector_only", _gr(secteur="informatique"), 100, _BASE))
THRESHOLD_CASES.append(("loc_only", _gr(localisation="Nice"), 100, _BASE))

# 7) Mots-clés vides mais geo+secteur+volume (>300)
THRESHOLD_CASES.append(
    ("geo_sector_vol", _gr(localisation="Toulouse", secteur="restauration"), 350, _NICHE)
)

# 8) Variantes départements × mots-clés (volume modéré)
for d in ("06", "33", "59", "44", "67", "974"):
    THRESHOLD_CASES.append(
        ("kw_dept_%s" % d, _gr(mots_cles=["prestataire"], departement=d), 120, _NICHE)
    )

# 9) Mots-clés + ville (autres villes)
for city in ("Bordeaux", "Nantes", "Strasbourg", "Lille"):
    THRESHOLD_CASES.append(
        ("kw_city_%s" % city.lower(), _gr(mots_cles=["agence", "web"], localisation=city), 40, _NICHE)
    )


def run_threshold_panel() -> dict:
    passed = 0
    failures: list[dict] = []
    for case_id, guard, n_res, expected in THRESHOLD_CASES:
        got = _compute_threshold(guard, n_res)
        ok = got == expected
        if ok:
            passed += 1
        else:
            failures.append({"id": case_id, "n": n_res, "expected": expected, "got": got})
    total = len(THRESHOLD_CASES)
    report = {
        "tool": "relevance._compute_threshold",
        "total": total,
        "passed": passed,
        "failed": len(failures),
        "failures": failures,
    }
    return report


def main() -> int:
    import argparse

    ap = argparse.ArgumentParser(description="Panel unitaire relevance._compute_threshold")
    ap.add_argument(
        "--write-report",
        action="store_true",
        help="Écrit benchmark_relevance_panel_report.json dans backend/",
    )
    args = ap.parse_args()

    r = run_threshold_panel()
    pct = 100.0 * r["passed"] / r["total"] if r["total"] else 0
    print("=" * 60)
    print("  BENCHMARK PANEL — relevance._compute_threshold")
    print(f"  PASS {r['passed']}/{r['total']} ({pct:.0f}%)")
    print("=" * 60)
    for f in r["failures"]:
        print("  FAIL:", f)
    if args.write_report:
        out = Path(__file__).resolve().parent / "benchmark_relevance_panel_report.json"
        out.write_text(json.dumps(r, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"  Rapport : {out}")
    return 0 if r["failed"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
