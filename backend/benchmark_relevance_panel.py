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
import types
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

if "services.agent_config" not in sys.modules:
    _stub_ac = types.ModuleType("services.agent_config")

    async def _fake_resolve_llm_block(
        agent_id: str,
        block_id: str,
        *,
        default_model: str,
        default_system: str,
        default_max_tokens: int,
        default_temperature: float,
        default_top_p: float = 1.0,
    ):
        return types.SimpleNamespace(
            model=default_model,
            system_prompt=default_system,
            max_tokens=default_max_tokens,
            temperature=default_temperature,
            top_p=default_top_p,
        )

    _stub_ac.resolve_llm_for_block = _fake_resolve_llm_block
    sys.modules["services.agent_config"] = _stub_ac

from models.schemas import CompanyResult, GuardEntity, GuardResult  # noqa: E402
from services.relevance import _compute_threshold  # noqa: E402

_BASE = 5
_BASE_PROSPECTION = 4
_NICHE = 6
_PLACES_NICHE = 7


def _gr(**entity_fields) -> GuardResult:
    return GuardResult(
        intent="recherche_entreprise",
        entities=GuardEntity(**entity_fields),
        confidence=0.9,
    )


def _maps_rows(n: int, *, maps_ratio: float) -> list[CompanyResult]:
    """Lignes factices avec ou sans google_maps_url."""
    n_maps = int(round(n * maps_ratio))
    out: list[CompanyResult] = []
    for i in range(n):
        url = f"https://maps.example/{i}" if i < n_maps else None
        out.append(CompanyResult(siren=f"{i:09d}", nom=f"E{i}", google_maps_url=url))
    return out


# Cas : id, guard, n, mode, results, expected
THRESHOLD_CASES: list[dict] = []

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
        {
            "id": f"niche_geo_{i}",
            "guard": _gr(mots_cles=["commerce", "sport"], **geo),
            "n": 50,
            "mode": "prospection",
            "results": None,
            "expected": _NICHE,
        }
    )

for n in (1, 50, 100, 200, 201, 500):
    THRESHOLD_CASES.append(
        {
            "id": f"kw_only_n_{n}",
            "guard": _gr(mots_cles=["usinage"]),
            "n": n,
            "mode": "prospection",
            "results": None,
            "expected": _NICHE if n > 200 else _BASE_PROSPECTION,
        }
    )

for n in (299, 300, 301, 400):
    exp = _BASE_PROSPECTION if n <= 300 else _BASE
    THRESHOLD_CASES.append(
        {
            "id": f"geo_sector_n_{n}",
            "guard": _gr(localisation="Paris", secteur="BTP"),
            "n": n,
            "mode": "prospection",
            "results": None,
            "expected": exp,
        }
    )

THRESHOLD_CASES.append(
    {
        "id": "kw_region",
        "guard": _gr(mots_cles=["pharmacie"], region="Bretagne"),
        "n": 30,
        "mode": "prospection",
        "results": None,
        "expected": _NICHE,
    }
)
THRESHOLD_CASES.append(
    {
        "id": "kw_dept_only",
        "guard": _gr(mots_cles=["boutique", "sport"], departement="13"),
        "n": 80,
        "mode": "prospection",
        "results": None,
        "expected": _NICHE,
    }
)

for key, gr, n, exp in (
    ("empty_entities", _gr(), 100, _BASE_PROSPECTION),
    ("sector_only", _gr(secteur="informatique"), 100, _BASE_PROSPECTION),
    ("loc_only", _gr(localisation="Nice"), 100, _BASE_PROSPECTION),
):
    THRESHOLD_CASES.append({"id": key, "guard": gr, "n": n, "mode": "prospection", "results": None, "expected": exp})

THRESHOLD_CASES.append(
    {
        "id": "geo_sector_vol",
        "guard": _gr(localisation="Toulouse", secteur="restauration"),
        "n": 350,
        "mode": "prospection",
        "results": None,
        "expected": _BASE,
    }
)

for d in ("06", "33", "59", "44", "67", "974"):
    THRESHOLD_CASES.append(
        {
            "id": f"kw_dept_{d}",
            "guard": _gr(mots_cles=["prestataire"], departement=d),
            "n": 120,
            "mode": "prospection",
            "results": None,
            "expected": _NICHE,
        }
    )

for city in ("Bordeaux", "Nantes", "Strasbourg", "Lille"):
    THRESHOLD_CASES.append(
        {
            "id": f"kw_city_{city.lower()}",
            "guard": _gr(mots_cles=["agence", "web"], localisation=city),
            "n": 40,
            "mode": "prospection",
            "results": None,
            "expected": _NICHE,
        }
    )

# Benchmark : pas d’assouplissement « prospection large »
THRESHOLD_CASES.append(
    {
        "id": "benchmark_broad",
        "guard": _gr(),
        "n": 100,
        "mode": "benchmark",
        "results": None,
        "expected": _BASE,
    }
)

# Niche + panel dominé par Places
THRESHOLD_CASES.append(
    {
        "id": "niche_places_strict",
        "guard": _gr(mots_cles=["padel"], localisation="Marseille"),
        "n": 40,
        "mode": "prospection",
        "results": _maps_rows(40, maps_ratio=0.35),
        "expected": _PLACES_NICHE,
    }
)


def run_threshold_panel() -> dict:
    passed = 0
    failures: list[dict] = []
    for c in THRESHOLD_CASES:
        got = _compute_threshold(
            c["guard"],
            c["n"],
            mode=c.get("mode", "prospection"),
            results=c.get("results"),
        )
        expected = c["expected"]
        ok = got == expected
        if ok:
            passed += 1
        else:
            failures.append(
                {"id": c["id"], "n": c["n"], "mode": c.get("mode"), "expected": expected, "got": got}
            )
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
