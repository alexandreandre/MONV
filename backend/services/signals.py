"""
Détection de signaux business à partir des données d'entreprise.

Analyse les champs CompanyResult + données brutes d'enrichissement
(finances multi-années, liste de dirigeants) pour produire des indicateurs
exploitables : croissance, baisse, dirigeant récent, etc.
"""

from __future__ import annotations

from datetime import date, datetime

from models.schemas import BusinessSignal, CompanyResult

_GROWTH_THRESHOLD = 0.20
_DECLINE_THRESHOLD = 0.15
_RECENT_DAYS = 730  # ~2 ans
_NEW_DIRECTOR_DAYS = 365
_CAPITAL_INCREASE_THRESHOLD = 0.25


def _safe_float(value: object) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _parse_date(raw: str | None) -> date | None:
    if not raw:
        return None
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y"):
        try:
            return datetime.strptime(str(raw)[:10], fmt).date()
        except (ValueError, TypeError):
            continue
    return None


# ── Signaux de base (champs CompanyResult) ───────────────────────────

def _basic_signals(result: CompanyResult) -> list[BusinessSignal]:
    signals: list[BusinessSignal] = []
    today = date.today()

    created = _parse_date(result.date_creation)
    if created and (today - created).days < _RECENT_DAYS:
        age_months = (today - created).days // 30
        signals.append(BusinessSignal(
            type="entreprise_recente",
            label="Entreprise récente",
            detail=f"Créée il y a {age_months} mois",
            severity="info",
        ))

    if result.resultat_net is not None and result.resultat_net < 0:
        formatted = f"{result.resultat_net:,.0f} €".replace(",", "\u202f")
        signals.append(BusinessSignal(
            type="resultat_negatif",
            label="Résultat négatif",
            detail=formatted,
            severity="warning",
        ))

    return signals


# ── Signaux financiers (données multi-années Pappers) ────────────────

def _ca_from_row(row: dict) -> float | None:
    return _safe_float(
        row.get("chiffre_affaires")
        or row.get("turnover")
        or row.get("revenue")
        or row.get("ca")
    )


def _capital_from_row(row: dict) -> float | None:
    return _safe_float(
        row.get("capital_social")
        or row.get("capital")
    )


def _finance_signals(finances: list[dict]) -> list[BusinessSignal]:
    signals: list[BusinessSignal] = []
    if len(finances) < 2:
        return signals

    last, prev = finances[0], finances[1]
    ca_last = _ca_from_row(last)
    ca_prev = _ca_from_row(prev)

    if ca_last is not None and ca_prev is not None and ca_prev > 0:
        growth = (ca_last - ca_prev) / abs(ca_prev)
        if growth > _GROWTH_THRESHOLD:
            signals.append(BusinessSignal(
                type="forte_croissance",
                label="Forte croissance",
                detail=f"CA +{growth:.0%} sur 1 an",
                severity="positive",
            ))
        elif growth < -_DECLINE_THRESHOLD:
            signals.append(BusinessSignal(
                type="ca_en_baisse",
                label="CA en baisse",
                detail=f"CA {growth:+.0%} sur 1 an",
                severity="warning",
            ))

    cap_last = _capital_from_row(last)
    cap_prev = _capital_from_row(prev)
    if cap_last and cap_prev and cap_prev > 0:
        cap_growth = (cap_last - cap_prev) / abs(cap_prev)
        if cap_growth > _CAPITAL_INCREASE_THRESHOLD:
            signals.append(BusinessSignal(
                type="augmentation_capital",
                label="Augmentation de capital",
                detail=f"+{cap_growth:.0%}",
                severity="positive",
            ))

    return signals


# ── Signaux dirigeants (données Pappers) ─────────────────────────────

def _dirigeant_signals(representants: list[dict]) -> list[BusinessSignal]:
    signals: list[BusinessSignal] = []
    today = date.today()

    for rep in representants:
        raw_date = (
            rep.get("date_prise_poste")
            or rep.get("date_nomination")
            or rep.get("date")
            or rep.get("date_debut")
        )
        d = _parse_date(raw_date)
        if not d:
            continue
        if (today - d).days > _NEW_DIRECTOR_DAYS:
            continue

        nom = rep.get("nom_complet") or rep.get("nom") or rep.get("name") or ""
        qualite = rep.get("qualite") or rep.get("role") or rep.get("function") or ""
        detail = f"{nom} ({qualite})" if qualite else nom
        signals.append(BusinessSignal(
            type="nouveau_dirigeant",
            label="Nouveau dirigeant",
            detail=detail.strip() or None,
            severity="info",
        ))
        break  # un seul signal suffit

    return signals


# ── Point d'entrée ───────────────────────────────────────────────────

def detect_signals(
    result: CompanyResult,
    *,
    finances: list[dict] | None = None,
    representants: list[dict] | None = None,
) -> list[BusinessSignal]:
    """Produit la liste des signaux business pour une entreprise."""
    out: list[BusinessSignal] = []
    out.extend(_basic_signals(result))
    if finances:
        out.extend(_finance_signals(finances))
    if representants:
        out.extend(_dirigeant_signals(representants))

    seen_types: set[str] = set()
    deduped: list[BusinessSignal] = []
    for s in out:
        if s.type not in seen_types:
            seen_types.add(s.type)
            deduped.append(s)
    return deduped
