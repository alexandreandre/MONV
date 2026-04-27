"""
Moteur de statistiques benchmark — calcul de positionnement relatif au panel.
Enrichit chaque CompanyResult avec un score de position sur le panel affiché.
"""
from __future__ import annotations
from datetime import date
from statistics import median, quantiles
from models.schemas import CompanyResult

def _extract_floats(results: list[CompanyResult], field: str) -> list[float]:
    values = []
    for r in results:
        v = getattr(r, field, None)
        if v is not None:
            try:
                values.append(float(v))
            except (TypeError, ValueError):
                pass
    return values

def _position_label(value: float, q1: float, median_val: float, q3: float, p90: float) -> str:
    if value >= p90:
        return "top_10"
    if value >= q3:
        return "top_25"
    if value >= median_val:
        return "median"
    return "bottom_25"

def compute_panel_stats(results: list[CompanyResult]) -> dict:
    """Calcule les statistiques globales du panel (médiane, quartiles, min, max)."""
    stats: dict = {}
    for field in (
        "chiffre_affaires",
        "effectif_financier",
        "variation_ca_pct",
        "resultat_net",
        "benchmark_productivite",
        "benchmark_anciennete",
    ):
        values = _extract_floats(results, field)
        if len(values) < 2:
            stats[field] = {"count": len(values), "median": None, "q1": None, "q3": None, "p90": None, "min": None, "max": None}
            continue
        values_sorted = sorted(values)
        qs = quantiles(values_sorted, n=4)  # [Q1, Q2/median, Q3]
        p90_idx = int(len(values_sorted) * 0.9)
        stats[field] = {
            "count": len(values),
            "median": median(values_sorted),
            "q1": qs[0],
            "q3": qs[2],
            "p90": values_sorted[min(p90_idx, len(values_sorted) - 1)],
            "min": values_sorted[0],
            "max": values_sorted[-1],
        }
    return stats

def enrich_with_benchmark_positions(results: list[CompanyResult]) -> dict:
    """
    Enrichit chaque CompanyResult avec benchmark_ca_position,
    benchmark_effectif_position, benchmark_productivite_position,
    benchmark_anciennete_position.
    Retourne aussi les stats globales du panel.
    """
    if not results:
        return {}

    # Calcul productivité (CA / effectif) pour chaque entreprise
    for r in results:
        ca = getattr(r, "chiffre_affaires", None)
        eff = getattr(r, "effectif_financier", None)
        if ca and eff and float(eff) > 0:
            r.benchmark_productivite = round(float(ca) / float(eff))
        else:
            r.benchmark_productivite = None

    current_year = date.today().year
    for r in results:
        dc = getattr(r, "date_creation", None)
        if dc:
            try:
                year = int(str(dc)[:4])
                r.benchmark_anciennete = current_year - year
            except (ValueError, TypeError):
                r.benchmark_anciennete = None
        else:
            r.benchmark_anciennete = None

    panel_stats = compute_panel_stats(results)

    # Enrichissement de chaque résultat
    for r in results:
        for field, stat_key, attr_name in [
            ("chiffre_affaires", "chiffre_affaires", "benchmark_ca_position"),
            ("effectif_financier", "effectif_financier", "benchmark_effectif_position"),
            ("benchmark_productivite", "benchmark_productivite", "benchmark_productivite_position"),
            ("benchmark_anciennete", "benchmark_anciennete", "benchmark_anciennete_position"),
        ]:
            s = panel_stats.get(stat_key, {})
            if s.get("median") is None:
                setattr(r, attr_name, None)
                continue
            val = getattr(r, field, None)
            if val is None:
                setattr(r, attr_name, None)
                continue
            try:
                setattr(r, attr_name, _position_label(
                    float(val), s["q1"], s["median"], s["q3"], s["p90"]
                ))
            except (TypeError, ValueError):
                setattr(r, attr_name, None)

    return panel_stats
