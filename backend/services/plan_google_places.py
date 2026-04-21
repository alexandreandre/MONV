"""
Ajustements déterministes du plan d'API — Google Places.

Si l'utilisateur ancre à la fois une ville (ou libellé « ville / région ») et une
zone plus large (région, département, ou segment après « / » dans la localisation),
on ajoute un second Text Search Places avec la même requête métier et la zone large,
lorsque l'orchestrateur n'a produit qu'un seul contexte géographique étroit.
"""

from __future__ import annotations

import unicodedata

from models.schemas import APICall, ExecutionPlan, GuardEntity
from utils.pipeline_log import plog


def _fold(s: str) -> str:
    s = "".join(
        c
        for c in unicodedata.normalize("NFD", s)
        if unicodedata.category(c) != "Mn"
    )
    return s.lower().strip()


def augment_google_places_regional_variant(plan: ExecutionPlan, entities: GuardEntity) -> None:
    gp_ix = [
        i
        for i, c in enumerate(plan.api_calls)
        if c.source == "google_places" and c.action == "search"
    ]
    if not gp_ix:
        return
    ref = plan.api_calls[gp_ix[0]]
    q = str(ref.params.get("query") or "").strip()
    if not q:
        return
    cur_loc = str(ref.params.get("location") or "").strip()

    secondary: str | None = None
    loc_field = (entities.localisation or "").strip()
    if "/" in loc_field:
        left, right = [p.strip() for p in loc_field.split("/", 1)]
        if right and _fold(right) != _fold(cur_loc):
            secondary = right
        elif left and _fold(left) != _fold(cur_loc) and not cur_loc:
            secondary = left
    if secondary is None and entities.region:
        r = entities.region.strip()
        if r and _fold(r) != _fold(cur_loc):
            secondary = r
    if secondary is None and entities.departement:
        d = entities.departement.strip()
        if d and _fold(d) != _fold(cur_loc):
            secondary = d

    if not secondary:
        return

    for c in plan.api_calls:
        if c.source != "google_places" or c.action != "search":
            continue
        if _fold(str(c.params.get("location") or "")) == _fold(secondary):
            return

    plan.api_calls.append(
        APICall(
            source="google_places",
            action="search",
            params={"query": q, "location": secondary},
            priority=int(ref.priority),
        )
    )
    plog("google_places_regional_augment", query=q[:80], secondary=secondary[:80])


def augment_google_places_boutique_and_club_queries(plan: ExecutionPlan, user_message: str) -> None:
    """
    Si l'utilisateur demande explicitement plusieurs types d'établissements (ex. boutiques ET clubs),
    duplique les recherches Places avec des requêtes texte affinées, même zone.
    """
    low = (user_message or "").lower()
    if "boutique" not in low or "club" not in low:
        return
    gp = [c for c in plan.api_calls if c.source == "google_places" and c.action == "search"]
    if not gp:
        return
    ref = gp[0]
    base_q = str(ref.params.get("query") or "").strip()
    loc = str(ref.params.get("location") or "").strip()
    if not base_q:
        return
    prio = int(ref.priority)

    def _sig_pair(query: str, location: str) -> tuple[str, str]:
        return (query.strip().lower(), location.strip().lower())

    existing = {_sig_pair(str(c.params.get("query") or ""), str(c.params.get("location") or "")) for c in gp}
    variants: list[str] = []
    bq = f"{base_q} boutique".strip()
    cq = f"{base_q} club".strip()
    if _sig_pair(bq, loc) not in existing:
        variants.append(bq)
    if _sig_pair(cq, loc) not in existing:
        variants.append(cq)

    for vq in variants:
        plan.api_calls.append(
            APICall(
                source="google_places",
                action="search",
                params={"query": vq, "location": loc},
                priority=prio,
            )
        )
        plog("google_places_query_variant", query=vq[:80], location=loc[:40])
