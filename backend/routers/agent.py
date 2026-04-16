"""
Router de l'agent « Atelier ».

Expérience en deux tours :

  Tour 1 — POST /api/agent/send avec `{ pitch }`
    → crée une conversation (mode="atelier"), persiste le pitch utilisateur,
      génère un QCM de clarification et renvoie un message_type="agent_brief".

  Tour 2 — POST /api/agent/send avec `{ conversation_id, answers }`
    → récupère le pitch initial depuis la conversation, combine avec les
      réponses QCM, génère le squelette de dossier via le LLM
      orchestrateur, lance en parallèle UN appel au pipeline MONV par
      segment, puis persiste le message_type="business_dossier".

Les crédits pour les recherches d'entreprises ne sont PAS débités à ce
stade : l'utilisateur ne paie qu'à l'export (comme dans /api/chat/send).
Chaque segment est enregistré dans `search_history` afin de rendre
l'export disponible via le bouton Excel/CSV classique.
"""

from __future__ import annotations

import json
import traceback
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from supabase import Client

from models.db import (
    conversation_get,
    conversation_insert,
    get_supabase,
    message_insert,
    messages_list_asc,
    search_history_insert,
)
from models.entities import Conversation, Message, SearchHistory, gen_uuid
from models.schemas import (
    AgentRequest,
    AgentResponse,
    BusinessDossier,
    MessageOut,
)
from routers.auth import get_current_user
from services.agent import (
    ATELIER_MODE_LABEL,
    build_brief_metadata,
    coerce_dossier,
    dossier_metadata_json,
    generate_atelier_qcm,
    generate_dossier_skeleton,
    run_segment_searches,
)
from utils.pipeline_log import plog


router = APIRouter(prefix="/api/agent", tags=["agent"])


AGENT_WELCOME_COPY = (
    "Parfait, on structure ton projet. Réponds à quelques questions courtes "
    "pour que je produise un dossier complet (business model, flux et "
    "tableaux d'entreprises réelles à contacter)."
)


@router.post("/send", response_model=AgentResponse)
async def agent_send(
    req: AgentRequest,
    user=Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    try:
        now = datetime.now(timezone.utc)

        # ── Tour 1 — nouveau projet, pas d'identifiant de conversation ────
        if not req.conversation_id:
            pitch = (req.pitch or "").strip()
            if not pitch:
                raise HTTPException(400, "Décris ton projet en quelques phrases.")

            conv = Conversation(
                id=gen_uuid(),
                user_id=user.id,
                title=f"Atelier — {pitch[:48]}",
                created_at=now,
                updated_at=now,
                mode=ATELIER_MODE_LABEL,
            )
            await conversation_insert(supabase, conv)

            user_msg = Message(
                id=gen_uuid(),
                conversation_id=conv.id,
                role="user",
                content=pitch,
                message_type="text",
                metadata_json=None,
                created_at=now,
            )
            await message_insert(supabase, user_msg)

            intro, questions = await generate_atelier_qcm(pitch)
            qcm_payload = {
                "intro": intro,
                "questions": [q.model_dump() for q in questions],
                "mode": ATELIER_MODE_LABEL,
            }
            qcm_msg = Message(
                id=gen_uuid(),
                conversation_id=conv.id,
                role="assistant",
                content=intro,
                message_type="agent_brief",
                metadata_json=json.dumps(qcm_payload, ensure_ascii=False),
                created_at=datetime.now(timezone.utc),
            )
            await message_insert(supabase, qcm_msg)
            return _build_response(conv.id, [qcm_msg])

        # ── Tour 2 — on reçoit des réponses, on produit le dossier ────────
        conv = await conversation_get(supabase, req.conversation_id, user.id)
        if not conv:
            raise HTTPException(404, "Atelier introuvable.")

        answers = (req.answers or "").strip()
        if not answers:
            raise HTTPException(400, "Réponds d'abord aux questions.")

        prior_msgs = await messages_list_asc(supabase, conv.id)
        pitch_msg = next(
            (m for m in prior_msgs if m.role == "user" and m.message_type == "text"),
            None,
        )
        if not pitch_msg:
            raise HTTPException(400, "Pitch introuvable pour cet Atelier.")

        # Persiste la réponse utilisateur AVANT la génération pour que le
        # frontend puisse rejouer la conversation s'il refresh pendant les
        # recherches (elles peuvent prendre plusieurs secondes).
        answer_msg = Message(
            id=gen_uuid(),
            conversation_id=conv.id,
            role="user",
            content=answers,
            message_type="text",
            metadata_json=None,
            created_at=datetime.now(timezone.utc),
        )
        await message_insert(supabase, answer_msg)

        try:
            raw = await generate_dossier_skeleton(pitch_msg.content, answers)
        except Exception as exc:
            plog("atelier_skeleton_error", error=str(exc)[:400])
            raise HTTPException(
                502,
                "Génération du dossier indisponible. Réessaie dans quelques instants.",
            ) from exc

        brief, canvas, flows, segments_brief, synthesis = coerce_dossier(raw)
        plog(
            "atelier_skeleton_ok",
            nom=brief.nom,
            nb_segments=len(segments_brief),
            modes=[s.mode for s in segments_brief],
        )

        segment_results = await run_segment_searches(segments_brief)

        # Persister chaque segment dans search_history → l'utilisateur peut
        # cliquer « Exporter » sur n'importe quel tableau (comme une
        # recherche classique), les crédits sont débités à l'export.
        for seg in segment_results:
            if seg.total <= 0 or not seg.preview:
                continue
            seg.search_id = gen_uuid()
            try:
                await search_history_insert(
                    supabase,
                    SearchHistory(
                        id=seg.search_id,
                        user_id=user.id,
                        conversation_id=conv.id,
                        query_text=seg.query,
                        intent="atelier_segment",
                        entities_json=None,
                        results_count=seg.total,
                        credits_used=seg.credits_required,
                        results_json=json.dumps(seg.preview, ensure_ascii=False, default=str),
                        exported=False,
                        export_path=None,
                        created_at=datetime.now(timezone.utc),
                        mode=seg.mode,
                    ),
                )
            except Exception:
                plog(
                    "atelier_segment_history_error",
                    key=seg.key,
                    error=traceback.format_exc()[-1200:],
                )
                seg.search_id = None

        dossier = BusinessDossier(
            brief=brief,
            canvas=canvas,
            flows=flows,
            segments=segment_results,
            synthesis=synthesis,
        )

        nb_usable = sum(1 for s in segment_results if s.total > 0)
        lead_line = (
            f"Dossier **{brief.nom}** prêt : business model, flux et "
            f"{nb_usable} tableau(x) d'entreprises réelles à activer."
        )

        dossier_msg = Message(
            id=gen_uuid(),
            conversation_id=conv.id,
            role="assistant",
            content=lead_line,
            message_type="business_dossier",
            metadata_json=dossier_metadata_json(dossier),
            created_at=datetime.now(timezone.utc),
        )
        await message_insert(supabase, dossier_msg)

        return _build_response(conv.id, [answer_msg, dossier_msg])

    except HTTPException:
        raise
    except Exception:
        plog("atelier_send_crash", error=traceback.format_exc()[-2000:])
        return JSONResponse(
            status_code=500,
            content={
                "detail": "Atelier indisponible. Consulte les logs pour plus de détails."
            },
        )


def _build_response(conv_id: str, messages: list[Message]) -> AgentResponse:
    return AgentResponse(
        conversation_id=conv_id,
        messages=[
            MessageOut(
                id=m.id,
                role=m.role,
                content=m.content,
                message_type=m.message_type,
                metadata_json=m.metadata_json,
                created_at=m.created_at,
            )
            for m in messages
        ],
    )
