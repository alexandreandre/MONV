"""Router Benchmark — endpoints spécifiques au mode Benchmark."""

from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from models.entities import User
from routers.auth import get_current_user
from services.bodacc import get_bodacc_stats_for_benchmark
from services.marches_publics import get_marches_stats_for_benchmark
from utils.llm import llm_json_call

router = APIRouter(prefix="/api/chat", tags=["benchmark"])

INSIGHTS_SYSTEM_PROMPT = """\
Tu es l'assistant analytique de MONV, un outil de recherche
d'entreprises en France. Tu reçois un résumé statistique d'un
panel d'entreprises et tu génères des insights factuels et
sourcés, enrichis par ta connaissance du marché en temps réel.

RÈGLES STRICTES :
- Chaque insight doit être factuel et vérifiable
- Cite des données réelles quand tu en as (études sectorielles,
  rapports INSEE, FFA, FFB, etc.)
- Jamais de conseil en investissement ni recommandation d'achat
- Jamais d'affirmation inventée — si tu n'es pas sûr, dis-le
- Maximum 5 insights, minimum 3
- Langue : français uniquement

FORMAT de réponse — JSON uniquement, rien d'autre :
{
  "insights": [
    {
      "n": 1,
      "text": "Observation factuelle avec chiffre ou référence si possible.",
      "source": "SIRENE" | "Pappers" | "Panel MONV" | "INSEE" | "Web"
    }
  ]
}
"""


class BenchmarkInsightsRequest(BaseModel):
    panel_summary: dict[str, Any]


class BodaccStatsRequest(BaseModel):
    region: str | None = None
    departement: str | None = None
    days_back: int = 365


@router.post("/benchmark-bodacc-stats")
async def get_benchmark_bodacc_stats(
    req: BodaccStatsRequest,
    user: User = Depends(get_current_user),
):
    """Stats BODACC pour l'onglet Dynamique du Benchmark."""
    _ = user
    stats = await get_bodacc_stats_for_benchmark(
        region=req.region,
        departement=req.departement,
        days_back=req.days_back,
    )
    return stats


class MarchesStatsRequest(BaseModel):
    cpv_division: str | None = None
    departement: str | None = None


@router.post("/benchmark-marches-stats")
async def get_benchmark_marches_stats(
    req: MarchesStatsRequest,
    user: User = Depends(get_current_user),
):
    """Stats marchés publics pour le Benchmark."""
    _ = user
    stats = await get_marches_stats_for_benchmark(
        cpv_division=req.cpv_division,
        departement=req.departement,
    )
    return stats


@router.post("/benchmark-insights")
async def generate_benchmark_insights(
    req: BenchmarkInsightsRequest,
    user: User = Depends(get_current_user),
):
    _ = user
    context = f"Panel résumé : {json.dumps(req.panel_summary, ensure_ascii=False)}"
    try:
        result = await llm_json_call(
            model="perplexity/sonar",
            system=INSIGHTS_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": context}],
            max_tokens=1024,
            temperature=0.3,
        )
    except Exception as e:
        raise HTTPException(
            status_code=502,
            detail=f"Échec génération insights: {str(e)[:200]}",
        ) from e

    raw = result.get("insights", [])
    if not isinstance(raw, list):
        return {"insights": []}
    insights: list[dict[str, Any]] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        try:
            n = int(item.get("n", 0))
            text = str(item.get("text", "")).strip()
            source = str(item.get("source", "Panel MONV")).strip()
        except (TypeError, ValueError):
            continue
        if not text:
            continue
        insights.append({"n": n, "text": text, "source": source})
    return {"insights": insights}
