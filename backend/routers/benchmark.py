"""Router Benchmark — endpoints spécifiques au mode Benchmark."""

from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from config import settings
from models.entities import User
from routers.auth import get_current_user
from utils.llm import llm_json_call

router = APIRouter(prefix="/api/chat", tags=["benchmark"])

INSIGHTS_SYSTEM_PROMPT = """\
Tu es l'assistant analytique de MONV, un outil de recherche
d'entreprises en France. Tu reçois un résumé statistique d'un
panel d'entreprises et tu génères des insights factuels et
sourcés, NON prescriptifs.

RÈGLES STRICTES :
- Jamais de conseil en investissement, valorisation ou
  recommandation d'achat/vente
- Jamais d'affirmation non sourcée
- Toujours indiquer la source (SIRENE, Pappers, ou "Panel MONV")
- Maximum 5 insights, minimum 3
- Chaque insight est une observation factuelle courte (2-3 lignes)
- Langue : français

Réponds UNIQUEMENT avec un JSON valide :
{
  "insights": [
    {
      "n": 1,
      "text": "Observation factuelle courte et précise.",
      "source": "SIRENE"
    }
  ]
}
"""


class BenchmarkInsightsRequest(BaseModel):
    panel_summary: dict[str, Any]


@router.post("/benchmark-insights")
async def generate_benchmark_insights(
    req: BenchmarkInsightsRequest,
    user: User = Depends(get_current_user),
):
    _ = user
    context = f"Panel résumé : {json.dumps(req.panel_summary, ensure_ascii=False)}"
    try:
        result = await llm_json_call(
            model=settings.GUARD_MODEL,
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
