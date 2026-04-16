#!/usr/bin/env python3
"""
Benchmark déterministe — Agent Atelier (création business).

Sans LLM ni HTTP : coercion dossier, QCM, heuristiques, sérialisation.
Usage : depuis le dossier backend/ :
  PYTHONPATH=. python3 benchmark_atelier.py

Sortie : rapport JSON (benchmark_atelier_report.json) + résumé console.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import traceback
from pathlib import Path
from typing import Any, Callable

# Exécution en script : racine = backend/
_BACKEND = Path(__file__).resolve().parent
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from models.schemas import (  # noqa: E402
    AgentSynthesis,
    BusinessDossier,
    FlowActor,
    QcmOption,
    QcmQuestion,
    SegmentResult,
)
from services.atelier_constants import ATELIER_MODE_LABEL  # noqa: E402
from services.atelier_coerce import coerce_dossier  # noqa: E402
from services.atelier_heuristics import (  # noqa: E402
    heuristic_atelier_conversation_title,
    heuristic_atelier_project_folder_name,
)
from services.atelier_qcm import (  # noqa: E402
    finalize_atelier_qcm,
    parse_qcm_raw,
)


def build_brief_metadata(pitch: str) -> str:
    return json.dumps(
        {"pitch": pitch, "mode": ATELIER_MODE_LABEL},
        ensure_ascii=False,
    )


def dossier_metadata_json(dossier: BusinessDossier) -> str:
    payload: dict[str, Any] = dossier.model_dump()
    payload["mode"] = ATELIER_MODE_LABEL
    return json.dumps(payload, ensure_ascii=False, default=str)

# ── Fixture minimale (alignée sur tests/test_agent.py) ──────────────────────

_VALID_RAW_DOSSIER: dict[str, Any] = {
    "brief": {
        "nom": "Sushi Lyon",
        "tagline": "Restaurant japonais",
        "secteur": "Restauration",
        "localisation": "Lyon",
        "cible": "B2C",
        "budget": "100 k€",
        "modele_revenus": "Vente",
        "ambition": "1 site",
    },
    "canvas": {
        "proposition_valeur": ["A", "B"],
        "segments_clients": ["C1"],
        "canaux": ["D"],
        "relation_client": ["E"],
        "sources_revenus": ["F"],
        "ressources_cles": ["G"],
        "activites_cles": ["H"],
        "partenaires_cles": ["I"],
        "structure_couts": ["J"],
    },
    "flows": {
        "acteurs": ["Client", "Restaurant", "Importateur"],
        "flux_valeur": [
            {"origine": "Importateur", "destination": "Restaurant", "label": "Sakés"},
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
            "description": "Import",
            "mode": "sous_traitant",
            "query": "Fournisseurs produits japonais à Lyon",
            "icon": "truck",
        },
        {
            "key": "concurrents",
            "label": "Concurrents",
            "description": "Restos",
            "mode": "prospection",
            "query": "Restaurants japonais à Lyon",
            "icon": "target",
        },
    ],
    "synthesis": {
        "forces": ["F1"],
        "risques": ["R1"],
        "prochaines_etapes": ["E1"],
        "kpis": ["K1"],
        "budget_estimatif": "200 k€",
    },
}


def _expect_true(cond: bool, msg: str) -> tuple[str, str | None]:
    return ("PASS", None) if cond else ("FAIL", msg)


def run_panel() -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []

    cases: list[dict[str, Any]] = []

    def add(
        cid: str,
        category: str,
        notes: str,
        fn: Callable[[], tuple[str, str | None]],
    ) -> None:
        cases.append({"id": cid, "category": category, "notes": notes, "fn": fn})

    # ── happy_path ────────────────────────────────────────────────────────
    def hp01():
        b, _, _, _, _ = coerce_dossier(_VALID_RAW_DOSSIER)
        return _expect_true(b.nom == "Sushi Lyon", f"nom={b.nom!r}")

    def hp02():
        b, _, f, segs, syn = coerce_dossier(_VALID_RAW_DOSSIER)
        ok = (
            len(f.flux_valeur) >= 1
            and len(segs) == 2
            and syn.budget_estimatif == "200 k€"
        )
        return _expect_true(ok, "flux/segments/synthèse")

    def hp03():
        raw = build_brief_metadata("pitch test")
        p = json.loads(raw)
        return _expect_true(
            p.get("pitch") == "pitch test" and p.get("mode") == ATELIER_MODE_LABEL,
            str(p),
        )

    def hp04():
        b, c, flows, segs, syn = coerce_dossier(_VALID_RAW_DOSSIER)
        dossier = BusinessDossier(
            brief=b,
            canvas=c,
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
                for s in segs
            ],
            synthesis=syn,
        )
        payload = json.loads(dossier_metadata_json(dossier))
        return _expect_true(
            payload["mode"] == ATELIER_MODE_LABEL and payload["brief"]["nom"] == "Sushi Lyon",
            "metadata",
        )

    def hp05():
        t = heuristic_atelier_conversation_title("Food truck tacos à Rennes", max_len=80)
        return _expect_true("rennes" in t.lower() and "tacos" in t.lower(), t)

    def hp06():
        n = heuristic_atelier_project_folder_name("Startup SaaS RH à Bordeaux")
        return _expect_true("bordeaux" in n.lower(), n)

    # ── variantes ─────────────────────────────────────────────────────────
    def var01():
        raw = dict(_VALID_RAW_DOSSIER)
        raw["flows"] = {
            **raw["flows"],
            "acteurs": [
                {"label": "A", "segment_key": "fournisseurs"},
                {"label": "B", "segment_key": None},
            ],
        }
        _, _, flows, segs, _ = coerce_dossier(raw)
        return _expect_true(
            flows.acteurs[0].segment_key == "fournisseurs" and len(segs) == 2,
            "segment_key",
        )

    def var02():
        intro, qs = parse_qcm_raw(
            {
                "intro": "Hello",
                "questions": [
                    {
                        "id": "cible",
                        "question": "Q?",
                        "options": [{"id": "x", "label": "X"}],
                    }
                ],
            }
        )
        return _expect_true(intro == "Hello" and len(qs) == 1, str(len(qs)))

    def var03():
        intro, qs = finalize_atelier_qcm(
            "Intro",
            [
                QcmQuestion(
                    id="budget",
                    question="B?",
                    options=[QcmOption(id="a", label="A"), QcmOption(id="autre", label="Autre", free_text=True)],
                ),
                QcmQuestion(
                    id="cible",
                    question="C?",
                    options=[QcmOption(id="b", label="B"), QcmOption(id="autre", label="Autre", free_text=True)],
                ),
            ],
        )
        return _expect_true(qs[0].id == "cible", [q.id for q in qs])

    def var04():
        _, _, flows, _, _ = coerce_dossier(_VALID_RAW_DOSSIER)
        return _expect_true(
            all(isinstance(a, FlowActor) for a in flows.acteurs),
            "acteurs types",
        )

    def var05():
        raw = dict(_VALID_RAW_DOSSIER)
        raw["flows"] = {
            "flux_valeur": [{"from": "A", "to": "B", "label": "x"}],
            "flux_financiers": [],
            "flux_information": [],
            "acteurs": [],
        }
        _, _, flows, _, _ = coerce_dossier(raw)
        return _expect_true(
            len(flows.flux_valeur) == 1 and flows.flux_valeur[0].origine == "A",
            "alias from/to",
        )

    def var06():
        intro, qs = finalize_atelier_qcm("", [])
        return _expect_true(len(qs) == 1 and qs[0].id == "validation_dossier", qs[0].id)

    # ── edge_case ───────────────────────────────────────────────────────────
    def edge01():
        b, _, _, _, _ = coerce_dossier({})
        return _expect_true(b.nom == "Mon projet", b.nom)

    def edge02():
        many = {
            **_VALID_RAW_DOSSIER,
            "segments": [
                {
                    "key": f"k{i}",
                    "label": f"L{i}",
                    "mode": "prospection",
                    "query": f"q{i}",
                }
                for i in range(12)
            ],
        }
        _, _, _, segs, _ = coerce_dossier(many)
        return _expect_true(len(segs) == 5, len(segs))

    def edge03():
        raw = dict(_VALID_RAW_DOSSIER)
        raw["brief"] = {"nom": "x" * 200}
        b, _, _, _, _ = coerce_dossier(raw)
        return _expect_true(len(b.nom) <= 60, len(b.nom))

    def edge04():
        raw = dict(_VALID_RAW_DOSSIER)
        raw["canvas"] = {"proposition_valeur": ["a", "b", "c", "d", "e", "f", "g"]}
        _, c, _, _, _ = coerce_dossier(raw)
        return _expect_true(len(c.proposition_valeur) <= 6, len(c.proposition_valeur))

    def edge05():
        raw = dict(_VALID_RAW_DOSSIER)
        raw["flows"] = {"flux_valeur": [], "flux_financiers": [], "flux_information": []}
        _, _, flows, _, _ = coerce_dossier(raw)
        return _expect_true(flows.flux_valeur == [], flows)

    def edge06():
        intro, qs = finalize_atelier_qcm("   ", [])
        return _expect_true(len(qs) == 1, len(qs))

    # ── erreur_input ────────────────────────────────────────────────────────
    def err01():
        raw = dict(_VALID_RAW_DOSSIER)
        raw["segments"] = "pas une liste"
        _, _, _, segs, _ = coerce_dossier(raw)
        return _expect_true(segs == [], f"got {segs!r}")

    def err02():
        raw = dict(_VALID_RAW_DOSSIER)
        raw["segments"] = [{"key": "x", "mode": "prospection"}]
        _, _, _, segs, _ = coerce_dossier(raw)
        return _expect_true(segs == [], "segment sans query")

    def err03():
        raw = dict(_VALID_RAW_DOSSIER)
        raw["flows"] = None
        _, _, flows, _, _ = coerce_dossier(raw)
        return _expect_true(flows.flux_valeur == [], "flows None")

    def err04():
        intro, qs = parse_qcm_raw({"intro": None, "questions": None})
        return _expect_true(isinstance(intro, str) and qs == [], str(qs))

    def err05():
        _, _, flows, _, _ = coerce_dossier(
            {
                "brief": {},
                "flows": {
                    "acteurs": [{"label": "", "segment_key": "fournisseurs"}],
                    "flux_valeur": [],
                    "flux_financiers": [],
                    "flux_information": [],
                },
                "segments": _VALID_RAW_DOSSIER["segments"],
            }
        )
        return _expect_true(len(flows.acteurs) == 0, len(flows.acteurs))

    def err06():
        raw = dict(_VALID_RAW_DOSSIER)
        raw["synthesis"] = None
        _, _, _, _, syn = coerce_dossier(raw)
        return _expect_true(isinstance(syn, AgentSynthesis), type(syn).__name__)

    # ── combinatoire ────────────────────────────────────────────────────────
    def com01():
        raw = dict(_VALID_RAW_DOSSIER)
        raw["segments"] = [
            {"key": "a", "label": "A", "mode": "rachat", "query": "q1"},
            {"key": "b", "label": "B", "mode": "sous_traitant", "query": "q2"},
        ]
        _, _, _, segs, _ = coerce_dossier(raw)
        modes = {s.mode for s in segs}
        return _expect_true(modes == {"rachat", "sous_traitant"}, modes)

    def com02():
        raw = dict(_VALID_RAW_DOSSIER)
        raw["flows"] = {
            **raw["flows"],
            "flux_valeur": [
                {"origine": "X", "destination": "Y", "label": "ok"},
                {"origine": "", "destination": "Z", "label": "bad"},
            ],
        }
        _, _, flows, _, _ = coerce_dossier(raw)
        return _expect_true(len(flows.flux_valeur) == 1, len(flows.flux_valeur))

    def com03():
        dup = {
            **_VALID_RAW_DOSSIER,
            "segments": [
                {"key": "x", "label": "A", "mode": "prospection", "query": "q1"},
                {"key": "x", "label": "B", "mode": "prospection", "query": "q2"},
            ],
        }
        _, _, _, segs, _ = coerce_dossier(dup)
        return _expect_true(len(segs) == 1 and segs[0].label == "A", len(segs))

    # ── idempotence ─────────────────────────────────────────────────────────
    def idem01():
        a = coerce_dossier(_VALID_RAW_DOSSIER)
        b = coerce_dossier(_VALID_RAW_DOSSIER)
        return _expect_true(
            a[0].nom == b[0].nom and len(a[3]) == len(b[3]),
            f"{a[0].nom} vs {b[0].nom}",
        )

    def idem02():
        t1 = heuristic_atelier_project_folder_name("Test Lyon")
        t2 = heuristic_atelier_project_folder_name("Test Lyon")
        return _expect_true(t1 == t2, f"{t1!r} != {t2!r}")

    # ── performance (léger) ─────────────────────────────────────────────────
    def perf01():
        t0 = time.perf_counter()
        for _ in range(200):
            coerce_dossier(_VALID_RAW_DOSSIER)
        ms = (time.perf_counter() - t0) * 1000
        return _expect_true(ms < 5000, f"trop lent: {ms:.0f}ms")

    def perf02():
        t0 = time.perf_counter()
        parse_qcm_raw({"intro": "i", "questions": [{"id": "a", "question": "q", "options": []}]})
        ms = (time.perf_counter() - t0) * 1000
        return _expect_true(ms < 50, f"{ms:.1f}ms")

    def int01():
        try:
            import pytest  # noqa: F401
        except ImportError:
            return "WARN", "pytest absent — pip install pytest pour activer INT-01"
        env = {**os.environ, "PYTHONPATH": str(_BACKEND)}
        env.setdefault("SKIP_DB_VERIFY_ON_STARTUP", "true")
        env.setdefault("SUPABASE_URL", "https://placeholder.supabase.co")
        env.setdefault("SUPABASE_SERVICE_KEY", "placeholder-service-key")
        r = subprocess.run(
            [
                sys.executable,
                "-m",
                "pytest",
                str(_BACKEND / "tests/test_agent.py"),
                "-q",
                "--tb=no",
            ],
            cwd=str(_BACKEND),
            env=env,
            capture_output=True,
            text=True,
        )
        tail = (r.stdout or "") + (r.stderr or "")
        return _expect_true(r.returncode == 0, tail[-800:])

    add("HP-01", "happy_path", "coerce nom projet", hp01)
    add("HP-02", "happy_path", "flux + segments + synthèse", hp02)
    add("HP-03", "happy_path", "build_brief_metadata", hp03)
    add("HP-04", "happy_path", "dossier_metadata_json", hp04)
    add("HP-05", "happy_path", "heuristic conversation title", hp05)
    add("HP-06", "happy_path", "heuristic folder name", hp06)
    add("VAR-01", "variantes", "acteurs + segment_key", var01)
    add("VAR-02", "variantes", "parse_qcm_raw", var02)
    add("VAR-03", "variantes", "_finalize ordre cible avant budget", var03)
    add("VAR-04", "variantes", "acteurs -> FlowActor", var04)
    add("VAR-05", "variantes", "edges from/to alias", var05)
    add("VAR-06", "variantes", "QCM vide -> validation_dossier", var06)
    add("EDGE-01", "edge_case", "payload vide", edge01)
    add("EDGE-02", "edge_case", "12 segments -> cap 5", edge02)
    add("EDGE-03", "edge_case", "nom très long tronqué", edge03)
    add("EDGE-04", "edge_case", "canvas bullets cap", edge04)
    add("EDGE-05", "edge_case", "flows vides", edge05)
    add("EDGE-06", "edge_case", "intro whitespace seulement", edge06)
    add("ERR-01", "erreur_input", "segments type invalide", err01)
    add("ERR-02", "erreur_input", "segment sans query", err02)
    add("ERR-03", "erreur_input", "flows null", err03)
    add("ERR-04", "erreur_input", "QCM null intro/questions", err04)
    add("ERR-05", "erreur_input", "acteur label vide ignoré", err05)
    add("ERR-06", "erreur_input", "synthesis null", err06)
    add("COMBO-01", "combinatoire", "modes rachat + sous_traitant", com01)
    add("COMBO-02", "combinatoire", "arête origine vide ignorée", com02)
    add("COMBO-03", "combinatoire", "dedupe keys segments", com03)
    add("IDEM-01", "idempotence", "coerce x2 identique", idem01)
    add("IDEM-02", "idempotence", "heuristic folder stable", idem02)
    add("PERF-01", "performance", "200x coerce < 5s", perf01)
    add("PERF-02", "performance", "parse QCM rapide", perf02)
    add("INT-01", "integration", "pytest tests/test_agent.py", int01)

    for c in cases:
        t0 = time.perf_counter()
        verdict = "PASS"
        detail: str | None = None
        err_trace: str | None = None
        try:
            v, d = c["fn"]()
            if v == "WARN":
                verdict = "WARN"
            elif v == "PASS":
                verdict = "PASS"
            else:
                verdict = "FAIL"
            detail = d
        except Exception as exc:
            verdict = "CRASH"
            err_trace = traceback.format_exc()[-1200:]
            detail = str(exc)
        ms = (time.perf_counter() - t0) * 1000
        results.append(
            {
                "id": c["id"],
                "category": c["category"],
                "notes": c["notes"],
                "verdict": verdict,
                "detail": detail,
                "error": err_trace,
                "ms": round(ms, 3),
            }
        )

    return results


def main() -> int:
    results = run_panel()
    total = len(results)
    passed = sum(1 for r in results if r["verdict"] == "PASS")
    warned = sum(1 for r in results if r["verdict"] == "WARN")
    failed = sum(1 for r in results if r["verdict"] == "FAIL")
    crashed = sum(1 for r in results if r["verdict"] == "CRASH")
    by_cat: dict[str, list[str]] = {}
    for r in results:
        by_cat.setdefault(r["category"], []).append(r["verdict"])

    cat_scores: dict[str, tuple[int, int]] = {}
    for cat, vs in by_cat.items():
        cat_scores[cat] = (sum(1 for x in vs if x == "PASS"), len(vs))

    report = {
        "tool": "atelier_agent",
        "score_global": f"{passed}/{total}",
        "warn": warned,
        "fail": failed,
        "crash": crashed,
        "pct": round(100 * passed / total, 1) if total else 0,
        "by_category": {k: {"pass": v[0], "total": v[1]} for k, v in cat_scores.items()},
        "results": results,
    }

    out_path = _BACKEND / "benchmark_atelier_report.json"
    out_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    print("## Benchmark Agent Atelier (déterministe)\n")
    print(f"Score global : **{passed}/{total}** PASS ({report['pct']}%)\n")
    print("### Par catégorie\n")
    print("| Catégorie | Score |")
    print("|-----------|-------|")
    for cat, (p, t) in sorted(cat_scores.items()):
        bar = "█" * p + "░" * (t - p)
        print(f"| {cat} | {p}/{t} {bar} |")
    print()
    for r in results:
        if r["verdict"] not in ("PASS", "WARN"):
            print(f"- **{r['id']}** [{r['verdict']}] {r.get('detail') or r.get('error', '')[:200]}")
        elif r["verdict"] == "WARN":
            print(f"- **{r['id']}** [WARN] {r.get('detail', '')[:200]}")
    print(f"\nRapport JSON : {out_path}")
    return 0 if failed == 0 and crashed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
