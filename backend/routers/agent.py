"""
Router de l'agent « Atelier ».

Expérience en deux tours :

  Tour 1 — POST /api/agent/send avec `{ pitch }` et optionnellement `folder_id`
    → crée un projet PROJETS (sauf si `folder_id` pointe vers un projet existant),
      crée une conversation (mode="atelier") rattachée à ce projet, persiste le
      pitch utilisateur, génère un QCM de clarification (0 à N questions selon le pitch)
      et renvoie un message_type="agent_brief".

  Tour 2 — POST /api/agent/send avec `{ conversation_id, answers }`
    → récupère le pitch initial depuis la conversation, combine avec les
      réponses QCM (ou le pitch seul si le QCM était vide), génère le squelette de dossier via le LLM
      orchestrateur, lance en parallèle UN appel au pipeline MONV par
      segment, puis persiste le message_type="business_dossier".

Les crédits pour les recherches d'entreprises ne sont PAS débités à ce
stade : l'utilisateur ne paie qu'à l'export (comme dans /api/chat/send).
Chaque segment est enregistré dans `search_history` afin de rendre
l'export disponible via le bouton Excel/CSV classique.
"""

from __future__ import annotations

import asyncio
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
    message_update,
    messages_list_asc,
    project_folder_get,
    project_folder_insert,
    project_folders_list_for_user,
    search_history_insert,
    user_update_credits,
)
from models.entities import Conversation, Message, ProjectFolder, SearchHistory, gen_uuid
from models.schemas import (
    AgentRequest,
    AgentResponse,
    AtelierBriefUpdateRequest,
    AtelierCanvasRegenerateRequest,
    AtelierDossierGetResponse,
    AtelierDossierMutationResponse,
    AtelierGenerationStats,
    AtelierSegmentRegenerateRequest,
    BusinessDossier,
    MessageOut,
    SegmentResult,
)
from routers.auth import get_current_user
from services.agent import (
    ATELIER_MODE_LABEL,
    build_brief_metadata,
    coerce_dossier,
    dossier_metadata_json,
    generate_atelier_qcm,
    generate_dossier_skeleton,
    regenerate_atelier_canvas_llm,
    regenerate_atelier_flows_llm,
    run_segment_search,
    run_segment_searches,
    suggest_atelier_conversation_title,
    suggest_atelier_project_folder_name,
)
from services.atelier_mutations import (
    atelier_dossier_rollup_fields,
    business_dossier_from_metadata_json,
    dossier_after_segment_list_refresh,
    dossier_with_replaced_segment,
    merge_atelier_cross_segment_tags,
    segment_result_to_brief,
)
from services.modes import normalize_mode
from utils.credits_policy import user_has_unlimited_credits
from utils.pipeline_log import plog


router = APIRouter(prefix="/api/agent", tags=["agent"])


def _atelier_project_name_from_pitch(pitch: str) -> str:
    line = " ".join(pitch.split())
    if not line:
        return "Projet Atelier"
    name = line[:80].strip()
    return name or "Projet Atelier"


AGENT_WELCOME_COPY = (
    "Décris ton projet en quelques phrases (métier, cible, zone, ce qui te "
    "différencie). L'Atelier te répond avec une lecture structurée puis, seulement "
    "si c'est utile, quelques questions ciblées (ou aucune si ton pitch suffit déjà) "
    "— ensuite : dossier, schéma de flux et listes d'entreprises à contacter."
)

ATELIER_REGEN_SEGMENT_CREDITS = 1


def _atelier_pitch_and_qcm_answers(messages: list[Message]) -> tuple[str, str]:
    user_texts = [m for m in messages if m.role == "user" and m.message_type == "text"]
    pitch = (user_texts[0].content if user_texts else "") or ""
    answers = (user_texts[1].content if len(user_texts) >= 2 else "") or ""
    return pitch.strip(), answers.strip()


def _find_latest_dossier_pair(messages: list[Message]) -> tuple[Message, BusinessDossier] | None:
    for m in reversed(messages):
        if m.message_type != "business_dossier" or not m.metadata_json:
            continue
        d = business_dossier_from_metadata_json(m.metadata_json)
        if d:
            return m, d
    return None


async def _persist_atelier_segment_search(
    supabase: Client,
    user_id: str,
    conv_id: str,
    seg: SegmentResult,
) -> None:
    if seg.total <= 0 or not seg.preview:
        return
    sid = gen_uuid()
    seg.search_id = sid
    try:
        await search_history_insert(
            supabase,
            SearchHistory(
                id=sid,
                user_id=user_id,
                conversation_id=conv_id,
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


@router.get("/dossier/{conversation_id}", response_model=AtelierDossierGetResponse)
async def atelier_get_dossier(
    conversation_id: str,
    user=Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    conv = await conversation_get(supabase, conversation_id, user.id)
    if not conv or (conv.mode or "") != ATELIER_MODE_LABEL:
        raise HTTPException(404, "Conversation Atelier introuvable.")
    msgs = await messages_list_asc(supabase, conversation_id)
    pair = _find_latest_dossier_pair(msgs)
    if not pair:
        raise HTTPException(404, "Aucun dossier Atelier dans cette conversation.")
    msg, dossier = pair
    raw = json.loads(dossier_metadata_json(dossier))
    return AtelierDossierGetResponse(message_id=msg.id, dossier=raw)


@router.post("/segments/{segment_key}/regenerate", response_model=AtelierDossierMutationResponse)
async def atelier_regenerate_segment(
    segment_key: str,
    body: AtelierSegmentRegenerateRequest,
    user=Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    conv = await conversation_get(supabase, body.conversation_id, user.id)
    if not conv or (conv.mode or "") != ATELIER_MODE_LABEL:
        raise HTTPException(404, "Conversation Atelier introuvable.")
    msgs = await messages_list_asc(supabase, body.conversation_id)
    pair = _find_latest_dossier_pair(msgs)
    if not pair:
        raise HTTPException(404, "Aucun dossier Atelier à mettre à jour.")
    msg, dossier = pair
    sk = segment_key.strip().lower()
    target = next((s for s in dossier.segments if s.key.lower().strip() == sk), None)
    if not target:
        raise HTTPException(404, "Segment inconnu dans ce dossier.")
    if target.out_of_scope:
        raise HTTPException(400, "Ce segment est hors périmètre MONV et ne peut pas être relancé.")

    debited = 0
    if not user_has_unlimited_credits(user):
        if user.credits < ATELIER_REGEN_SEGMENT_CREDITS:
            raise HTTPException(
                400,
                f"Crédits insuffisants pour regénérer ce segment ({ATELIER_REGEN_SEGMENT_CREDITS} crédit requis).",
            )
        new_bal = user.credits - ATELIER_REGEN_SEGMENT_CREDITS
        await user_update_credits(supabase, user.id, new_bal)
        user.credits = new_bal
        debited = ATELIER_REGEN_SEGMENT_CREDITS

    stats = AtelierGenerationStats(llm_calls=0, api_calls=1, credits_charged=debited)
    try:
        brief = segment_result_to_brief(target)
        if body.query_override and body.query_override.strip():
            brief = brief.model_copy(update={"query": body.query_override.strip()[:400]})
        if body.mode_override and body.mode_override.strip():
            brief = brief.model_copy(
                update={"mode": str(normalize_mode(body.mode_override))}
            )
        new_seg = await run_segment_search(brief)
        await _persist_atelier_segment_search(supabase, user.id, body.conversation_id, new_seg)
        d2 = dossier_with_replaced_segment(dossier, sk, new_seg)
        d3 = dossier_after_segment_list_refresh(d2)
        rel_rm: dict[str, int] = {}
        if target.total and new_seg.total_relevant is not None:
            rel_rm[sk] = max(0, int(target.total) - int(new_seg.total_relevant))
        stats.relevance_removed_per_segment = rel_rm
        await message_update(
            supabase,
            msg.id,
            {"metadata_json": dossier_metadata_json(d3)},
            body.conversation_id,
        )
        plog(
            "atelier_segment_regenerate",
            conversation_id=body.conversation_id,
            segment_key=sk,
            credits_charged=debited,
        )
        return AtelierDossierMutationResponse(
            dossier=d3,
            generation_stats=stats,
            credits_remaining=user.credits if not user_has_unlimited_credits(user) else None,
        )
    except HTTPException:
        raise
    except Exception as exc:
        if debited and not user_has_unlimited_credits(user):
            await user_update_credits(supabase, user.id, user.credits + debited)
            user.credits += debited
        plog("atelier_segment_regenerate_error", error=str(exc)[:500])
        raise HTTPException(502, "Regénération du segment indisponible.") from exc


@router.post("/canvas/regenerate", response_model=AtelierDossierMutationResponse)
async def atelier_regenerate_canvas(
    body: AtelierCanvasRegenerateRequest,
    user=Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    conv = await conversation_get(supabase, body.conversation_id, user.id)
    if not conv or (conv.mode or "") != ATELIER_MODE_LABEL:
        raise HTTPException(404, "Conversation Atelier introuvable.")
    msgs = await messages_list_asc(supabase, body.conversation_id)
    pair = _find_latest_dossier_pair(msgs)
    if not pair:
        raise HTTPException(404, "Aucun dossier Atelier à mettre à jour.")
    msg, dossier = pair
    pitch, answers = _atelier_pitch_and_qcm_answers(msgs)
    try:
        new_canvas = await regenerate_atelier_canvas_llm(
            pitch, answers, dossier.brief, dossier.canvas
        )
        d2 = dossier.model_copy(
            update={
                "canvas": new_canvas,
                "version": (dossier.version or 1) + 1,
                "generated_at": datetime.now(timezone.utc),
            }
        )
        await message_update(
            supabase,
            msg.id,
            {"metadata_json": dossier_metadata_json(d2)},
            body.conversation_id,
        )
        plog("atelier_canvas_regenerate", conversation_id=body.conversation_id)
        return AtelierDossierMutationResponse(
            dossier=d2,
            generation_stats=AtelierGenerationStats(llm_calls=1, api_calls=0, credits_charged=0),
            credits_remaining=user.credits if not user_has_unlimited_credits(user) else None,
        )
    except HTTPException:
        raise
    except Exception as exc:
        plog("atelier_canvas_regenerate_error", error=str(exc)[:500])
        raise HTTPException(502, "Regénération du canvas indisponible.") from exc


@router.post("/brief/update", response_model=AtelierDossierMutationResponse)
async def atelier_brief_update(
    body: AtelierBriefUpdateRequest,
    user=Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    if not body.impacts:
        raise HTTPException(400, "Indique au moins une zone à recalculer (impacts).")
    conv = await conversation_get(supabase, body.conversation_id, user.id)
    if not conv or (conv.mode or "") != ATELIER_MODE_LABEL:
        raise HTTPException(404, "Conversation Atelier introuvable.")
    msgs = await messages_list_asc(supabase, body.conversation_id)
    pair = _find_latest_dossier_pair(msgs)
    if not pair:
        raise HTTPException(404, "Aucun dossier Atelier à mettre à jour.")
    msg, dossier = pair
    pitch, answers = _atelier_pitch_and_qcm_answers(msgs)

    stats = AtelierGenerationStats()
    d = dossier.model_copy(update={"brief": body.brief})
    try:
        if "canvas" in body.impacts:
            d = d.model_copy(
                update={
                    "canvas": await regenerate_atelier_canvas_llm(
                        pitch, answers, d.brief, d.canvas
                    )
                }
            )
            stats.llm_calls += 1
        if "flows" in body.impacts:
            keys = [s.key for s in d.segments]
            d = d.model_copy(
                update={
                    "flows": await regenerate_atelier_flows_llm(
                        pitch, answers, d.brief, keys, d.flows
                    )
                }
            )
            stats.llm_calls += 1
        if "segments" in body.impacts:
            brs = [segment_result_to_brief(s) for s in d.segments]
            new_segs = await run_segment_searches(brs)
            stats.api_calls += len(brs)
            for seg in new_segs:
                await _persist_atelier_segment_search(supabase, user.id, body.conversation_id, seg)
            d = d.model_copy(update={"segments": new_segs})
            d = dossier_after_segment_list_refresh(d)
        else:
            segs = list(d.segments)
            merge_atelier_cross_segment_tags(segs)
            roll = atelier_dossier_rollup_fields(segs)
            d = d.model_copy(
                update={
                    "segments": segs,
                    "total_raw": roll["total_raw"],
                    "total_unique": roll["total_unique"],
                    "total_relevant": roll["total_relevant"],
                    "total_credits": roll["total_credits"],
                    "version": (dossier.version or 1) + 1,
                    "generated_at": datetime.now(timezone.utc),
                }
            )

        await message_update(
            supabase,
            msg.id,
            {"metadata_json": dossier_metadata_json(d)},
            body.conversation_id,
        )
        plog("atelier_brief_update", conversation_id=body.conversation_id, impacts=body.impacts)
        return AtelierDossierMutationResponse(
            dossier=d,
            generation_stats=stats,
            credits_remaining=user.credits if not user_has_unlimited_credits(user) else None,
        )
    except HTTPException:
        raise
    except Exception as exc:
        plog("atelier_brief_update_error", error=str(exc)[:500])
        raise HTTPException(502, "Mise à jour du brief indisponible.") from exc


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

            target_folder_id: str | None = None
            existing_folder_id = (req.folder_id or "").strip() or None
            if existing_folder_id:
                fld = await project_folder_get(supabase, existing_folder_id, user.id)
                if not fld:
                    raise HTTPException(400, "Projet invalide ou inaccessible.")
                target_folder_id = existing_folder_id

            project_folder_name, smart_title, (intro, questions) = await asyncio.gather(
                suggest_atelier_project_folder_name(pitch),
                suggest_atelier_conversation_title(pitch),
                generate_atelier_qcm(pitch),
            )

            if not existing_folder_id:
                existing_pf = await project_folders_list_for_user(supabase, user.id)
                next_pos = max((f.sort_position for f in existing_pf), default=-1) + 1
                folder_label = (
                    project_folder_name or _atelier_project_name_from_pitch(pitch)
                )[:160]
                pf = ProjectFolder(
                    id=gen_uuid(),
                    user_id=user.id,
                    name=folder_label,
                    sort_position=next_pos,
                    created_at=now,
                    updated_at=now,
                )
                created_pf = await project_folder_insert(supabase, pf)
                target_folder_id = created_pf.id

            conv = Conversation(
                id=gen_uuid(),
                user_id=user.id,
                title=f"Atelier — {smart_title}"[:255],
                created_at=now,
                updated_at=now,
                mode=ATELIER_MODE_LABEL,
                folder_id=target_folder_id,
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
            return _build_response(conv.id, [qcm_msg], folder_id=target_folder_id)

        # ── Tour 2 — on reçoit des réponses, on produit le dossier ────────
        conv = await conversation_get(supabase, req.conversation_id, user.id)
        if not conv:
            raise HTTPException(404, "Atelier introuvable.")

        prior_msgs = await messages_list_asc(supabase, conv.id)
        pitch_msg = next(
            (m for m in prior_msgs if m.role == "user" and m.message_type == "text"),
            None,
        )
        if not pitch_msg:
            raise HTTPException(400, "Pitch introuvable pour cet Atelier.")

        atelier_brief_n_questions = 0
        for m in prior_msgs:
            if m.role != "assistant" or (m.message_type or "") != "agent_brief":
                continue
            if m.metadata_json:
                try:
                    meta = json.loads(m.metadata_json)
                    qs = meta.get("questions")
                    if isinstance(qs, list):
                        atelier_brief_n_questions = len(qs)
                except json.JSONDecodeError:
                    pass
            break

        answers = (req.answers or "").strip()
        if not answers and atelier_brief_n_questions > 0:
            raise HTTPException(400, "Réponds d'abord aux questions.")

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
        merge_atelier_cross_segment_tags(segment_results)
        roll = atelier_dossier_rollup_fields(segment_results)

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
            generated_at=datetime.now(timezone.utc),
            total_raw=roll["total_raw"],
            total_unique=roll["total_unique"],
            total_relevant=roll["total_relevant"],
            total_credits=roll["total_credits"],
        )

        nb_usable = sum(1 for s in segment_results if s.total > 0)
        seg_hint = (
            f" ({nb_usable} segment(s) avec résultats)" if nb_usable else ""
        )
        lead_line = (
            f"Dossier **{brief.nom}** prêt.\n\n"
            "- Parcours le **canvas**, puis la **cartographie des flux** (schéma interactif).\n"
            f"- **Clique sur un acteur** relié à un segment pour ouvrir la liste d'entreprises "
            f"correspondante{seg_hint}.\n"
            "- Tu peux **continuer dans cette conversation** : pose une question ou une "
            "recherche dans le champ en bas (mode prospection par défaut), ou ouvre un "
            "**nouveau chat** pour repartir de zéro."
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

        return _build_response(conv.id, [answer_msg, dossier_msg], folder_id=conv.folder_id)

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


def _build_response(
    conv_id: str,
    messages: list[Message],
    folder_id: str | None = None,
) -> AgentResponse:
    return AgentResponse(
        conversation_id=conv_id,
        folder_id=folder_id,
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
