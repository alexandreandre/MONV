from models.schemas import APICall, ExecutionPlan, GuardEntity
from services.plan_google_places import (
    augment_google_places_boutique_and_club_queries,
    augment_google_places_regional_variant,
)


def test_augment_adds_second_places_when_localisation_slash():
    plan = ExecutionPlan(
        api_calls=[
            APICall(
                source="google_places",
                action="search",
                params={"query": "padel", "location": "Marseille"},
                priority=1,
            )
        ],
        estimated_credits=1,
        description="t",
    )
    ent = GuardEntity(localisation="Marseille/PACA")
    augment_google_places_regional_variant(plan, ent)
    assert len(plan.api_calls) == 2
    assert plan.api_calls[1].params["location"] == "PACA"
    assert plan.api_calls[1].params["query"] == "padel"


def test_augment_idempotent_when_second_already_present():
    plan = ExecutionPlan(
        api_calls=[
            APICall(
                source="google_places",
                action="search",
                params={"query": "padel", "location": "Marseille"},
                priority=1,
            ),
            APICall(
                source="google_places",
                action="search",
                params={"query": "padel", "location": "PACA"},
                priority=1,
            ),
        ],
        estimated_credits=1,
        description="t",
    )
    ent = GuardEntity(localisation="Marseille/PACA")
    augment_google_places_regional_variant(plan, ent)
    assert len(plan.api_calls) == 2


def test_augment_boutique_club_query_variants():
    plan = ExecutionPlan(
        api_calls=[
            APICall(
                source="google_places",
                action="search",
                params={"query": "padel", "location": "PACA"},
                priority=1,
            )
        ],
        estimated_credits=1,
        description="t",
    )
    msg = "Je cherche des boutiques de padel et clubs de padel à Lyon"
    augment_google_places_boutique_and_club_queries(plan, msg)
    assert len(plan.api_calls) == 3
    qs = {c.params["query"] for c in plan.api_calls}
    assert "padel boutique" in qs and "padel club" in qs
