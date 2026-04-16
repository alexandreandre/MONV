"""
Router principal — Chat conversationnel.

Pipeline en 4 couches + conversation :
  Couche 0  — Filter       (modèle cheap)  : in-scope / hors-scope
  Couche 1  — Guard        (modèle moyen)  : intent + entités
  Couche 1b — Conversation (modèle moyen)  : clarification multi-tour
  Couche 2  — Orchestrator (meilleur modèle): plan d'exécution API
  Couche 3  — API Engine   (déterministe)  : exécution SIRENE / Pappers
"""

import asyncio
import json
import traceback
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from supabase import Client

from models.db import (
    get_supabase,
    conversation_get,
    conversation_insert,
    conversations_list_for_user,
    message_insert,
    messages_list_asc,
    messages_recent_for_llm,
    search_history_insert,
)
from models.entities import User, Conversation, Message, SearchHistory, gen_uuid
from models.schemas import (
    ChatRequest, ChatResponse, MessageOut,
    ConversationOut, SearchResults,
)
from services.filter import run_filter
from services.guard import run_guard
from services.conversationalist import generate_qcm
from services.orchestrator import run_orchestrator
from services.api_engine import execute_plan
from services.sirene import patch_sirene_calls_from_guard_entities
from routers.auth import get_current_user
from utils.credits_policy import credits_for_api, user_has_unlimited_credits
from utils.pipeline_log import plog

router = APIRouter(prefix="/api/chat", tags=["chat"])

OUT_OF_SCOPE_MESSAGE = (
    "Je suis **MONV**, ton assistant pour trouver des entreprises en France.\n\n"
    "Je peux t'aider à :\n"
    "- **Trouver des clients** : prospects, leads qualifiés\n"
    "- **Trouver des prestataires** : comptables, avocats, agences, ESN...\n"
    "- **Trouver des fournisseurs** : matériaux, équipements, services\n"
    "- **Trouver des partenaires** : sous-traitants, co-traitants\n"
    "- **Explorer un marché** : concurrents, acteurs d'un secteur\n\n"
    "Décris-moi simplement ce que tu cherches ! Par exemple :\n"
    "- *\"Je cherche des PME du BTP à Lyon\"*\n"
    "- *\"Trouve-moi un cabinet comptable à Paris\"*\n"
    "- *\"Quels sont les fournisseurs d'emballage en Île-de-France ?\"*"
)

GREETING_MESSAGE = (
    "Bonjour ! Je suis **MONV**, ton assistant de prospection B2B.\n\n"
    "Dis-moi quel type d'entreprise tu cherches et où, et je lance la recherche pour toi.\n\n"
    "Par exemple :\n"
    "- *\"Je cherche des PME du BTP à Lyon\"*\n"
    "- *\"Restaurants japonais à Bordeaux\"*\n"
    "- *\"Cabinets comptables à Paris\"*"
)

META_QUESTION_MESSAGE = (
    "**MONV** est un outil de recherche d'entreprises en France.\n\n"
    "**Comment ça marche :**\n"
    "1. Décris ta cible (secteur, zone, taille...)\n"
    "2. Je lance la recherche sur les bases officielles (SIRENE, Pappers, Google Places)\n"
    "3. Tu obtiens un aperçu des résultats\n"
    "4. Tu peux exporter la liste complète (Excel / CSV) en utilisant tes crédits\n\n"
    "**Ce que je sais chercher :** clients, prestataires, fournisseurs, partenaires, "
    "concurrents, dirigeants — dans tous les secteurs et toutes les régions de France.\n\n"
    "Essaie par exemple : *\"Trouve-moi des ESN en Île-de-France\"*"
)

THANKS_MESSAGE = (
    "Avec plaisir ! N'hésite pas si tu as une autre recherche à lancer."
)


@router.post("/send")
async def send_message(
    req: ChatRequest,
    user: User = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
  try:
    now = datetime.now(timezone.utc)

    if req.conversation_id:
        conv = await conversation_get(supabase, req.conversation_id, user.id)
        if not conv:
            raise HTTPException(404, "Conversation non trouvée")
    else:
        conv = Conversation(
            id=gen_uuid(),
            user_id=user.id,
            title=req.message[:60],
            created_at=now,
            updated_at=now,
        )
        await conversation_insert(supabase, conv)

    user_msg = Message(
        id=gen_uuid(),
        conversation_id=conv.id,
        role="user",
        content=req.message,
        message_type="text",
        metadata_json=None,
        created_at=now,
    )
    await message_insert(supabase, user_msg)

    response_messages: list[Message] = []

    # ── Couche 0 — Filtre scope (modèle cheap) ─────────────────────
    filter_result = await run_filter(req.message)

    if not filter_result.in_scope:
        msg = Message(
            id=gen_uuid(),
            conversation_id=conv.id,
            role="assistant",
            content=OUT_OF_SCOPE_MESSAGE,
            message_type="text",
            metadata_json=None,
            created_at=datetime.now(timezone.utc),
        )
        await message_insert(supabase, msg)
        response_messages.append(msg)
        return _build_response(conv.id, response_messages)

    # ── Couche 1 — Guard extraction (modèle moyen) ─────────────────
    history = await _get_conversation_history(supabase, conv.id)
    guard_result = await run_guard(req.message, history)

    plog(
        "guard",
        intent=guard_result.intent,
        clarification_needed=guard_result.clarification_needed,
        entities=guard_result.entities.model_dump(),
        missing=guard_result.missing_criteria,
    )

    if guard_result.intent in ("hors_scope", "salutation", "meta_question"):
        if guard_result.intent == "salutation":
            reply = GREETING_MESSAGE
        elif guard_result.intent == "meta_question":
            reply = META_QUESTION_MESSAGE
        else:
            reply = OUT_OF_SCOPE_MESSAGE

        # "Merci" détecté
        lower_msg = req.message.strip().lower()
        if any(w in lower_msg for w in ("merci", "thanks", "super", "parfait", "génial")):
            reply = THANKS_MESSAGE

        msg = Message(
            id=gen_uuid(),
            conversation_id=conv.id,
            role="assistant",
            content=reply,
            message_type="text",
            metadata_json=None,
            created_at=datetime.now(timezone.utc),
        )
        await message_insert(supabase, msg)
        response_messages.append(msg)
        return _build_response(conv.id, response_messages)

    # ── Garde-fou : secteur + zone présents → on lance la recherche ─
    e = guard_result.entities
    has_secteur = bool(e.secteur or e.code_naf or e.mots_cles)
    has_zone = bool(e.localisation or e.departement or e.region)
    if guard_result.clarification_needed and has_secteur and has_zone:
        plog("guard_override_skip_clarification",
             reason="secteur+zone present",
             original_missing=guard_result.missing_criteria)
        guard_result.clarification_needed = False
        guard_result.missing_criteria = []

    # ── Couche 1b — QCM de clarification (modèle moyen) ────────────
    if guard_result.clarification_needed:
        intro, questions = await generate_qcm(guard_result, history)
        qcm_payload = {
            "intro": intro,
            "questions": [q.model_dump() for q in questions],
        }
        msg = Message(
            id=gen_uuid(),
            conversation_id=conv.id,
            role="assistant",
            content=intro,
            message_type="qcm",
            metadata_json=json.dumps(qcm_payload, ensure_ascii=False),
            created_at=datetime.now(timezone.utc),
        )
        await message_insert(supabase, msg)
        response_messages.append(msg)
        return _build_response(conv.id, response_messages)

    # ── Couche 2 — Orchestrateur (meilleur modèle) ─────────────────
    plan = await run_orchestrator(guard_result)

    plog(
        "orchestrator_plan",
        description=plan.description,
        estimated_credits=plan.estimated_credits,
        clarification_needed=plan.clarification_needed,
        api_calls=[
            {"source": c.source, "action": c.action, "priority": c.priority, "params": c.params}
            for c in plan.api_calls
        ],
    )

    if plan.clarification_needed:
        intro, questions = await generate_qcm(guard_result, history)
        qcm_payload = {
            "intro": intro,
            "questions": [q.model_dump() for q in questions],
        }
        msg = Message(
            id=gen_uuid(),
            conversation_id=conv.id,
            role="assistant",
            content=plan.clarification_question or intro,
            message_type="qcm",
            metadata_json=json.dumps(qcm_payload, ensure_ascii=False),
            created_at=datetime.now(timezone.utc),
        )
        await message_insert(supabase, msg)
        response_messages.append(msg)
        return _build_response(conv.id, response_messages)

    # ── Couche 3 — Exécution API (déterministe) ────────────────────
    status_msg = Message(
        id=gen_uuid(),
        conversation_id=conv.id,
        role="assistant",
        content=f"Recherche en cours... {plan.description}",
        message_type="text",
        metadata_json=None,
        created_at=datetime.now(timezone.utc),
    )
    await message_insert(supabase, status_msg)
    response_messages.append(status_msg)

    patch_sirene_calls_from_guard_entities(plan, guard_result.entities)
    search_results = await execute_plan(plan)

    plog(
        "execute_plan_done",
        total=search_results.total,
        credits_required=search_results.credits_required,
        columns=search_results.columns,
    )

    total = search_results.total

    if total == 0:
        result_msg = Message(
            id=gen_uuid(),
            conversation_id=conv.id,
            role="assistant",
            content=(
                "Aucune entreprise trouvée pour ces critères. "
                "Essaie d'élargir ta recherche (zone géographique plus large, "
                "tranche d'effectif plus souple, etc.)."
            ),
            message_type="text",
            metadata_json=None,
            created_at=datetime.now(timezone.utc),
        )
        await message_insert(supabase, result_msg)
        response_messages.append(result_msg)
        return _build_response(conv.id, response_messages)

    # ── Sauvegarder l'historique de recherche (background) ─────────
    search_id = gen_uuid()
    search_results.search_id = search_id

    search_record = SearchHistory(
        id=search_id,
        user_id=user.id,
        conversation_id=conv.id,
        query_text=req.message,
        intent=guard_result.intent,
        entities_json=guard_result.entities.model_dump_json(),
        results_count=search_results.total,
        credits_used=search_results.credits_required,
        results_json=json.dumps(
            [r.model_dump() for r in search_results.results],
            ensure_ascii=False, default=str,
        ),
        exported=False,
        export_path=None,
        created_at=datetime.now(timezone.utc),
    )

    async def _bg_insert_search_history() -> None:
        try:
            await search_history_insert(supabase, search_record)
        except Exception:
            plog("search_history_insert_error",
                 error=traceback.format_exc()[-1500:])

    # ── Construire le message de résultats ─────────────────────────
    credits_needed = search_results.credits_required
    preview_text = f"J'ai trouvé **{total} entreprises** correspondant à ta recherche."
    if total > 10:
        solde = (
            "**crédits illimités**"
            if user_has_unlimited_credits(user)
            else str(credits_for_api(user))
        )
        preview_text += (
            f" Voici les 10 premières. "
            f"**Exporter tout = {credits_needed} crédits** (tu en as {solde})."
        )

    map_points = [
        {
            "nom": r.nom,
            "latitude": r.latitude,
            "longitude": r.longitude,
            "adresse": r.adresse,
            "code_postal": r.code_postal,
            "ville": r.ville,
            "libelle_activite": r.libelle_activite,
            "telephone": r.telephone,
            "site_web": r.site_web,
            "lien_annuaire": r.lien_annuaire,
        }
        for r in search_results.results
        if r.latitude is not None and r.longitude is not None
    ]

    result_msg = Message(
        id=gen_uuid(),
        conversation_id=conv.id,
        role="assistant",
        content=preview_text,
        message_type="results",
        metadata_json=json.dumps({
            "search_id": search_id,
            "total": total,
            "credits_required": credits_needed,
            "columns": search_results.columns,
            "preview": [r.model_dump() for r in search_results.results[:10]],
            "map_points": map_points,
        }, ensure_ascii=False, default=str),
        created_at=datetime.now(timezone.utc),
    )

    await message_insert(supabase, result_msg)
    response_messages.append(result_msg)

    # Lancer l'insert historique APRÈS message_insert pour éviter le deadlock sur _sb_lock
    asyncio.create_task(_bg_insert_search_history())

    return _build_response(conv.id, response_messages)

  except HTTPException:
    raise
  except Exception:
    plog("send_message_crash", error=traceback.format_exc()[-2000:])
    return JSONResponse(
        status_code=500,
        content={"detail": "Erreur interne du serveur. Consulte les logs pour plus de détails."},
    )


def _build_response(conv_id: str, messages: list[Message]) -> ChatResponse:
    return ChatResponse(
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


@router.get("/conversations", response_model=list[ConversationOut])
async def list_conversations(
    user: User = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    """Metadonnees seulement : les messages sont charges via GET /conversations/{id}."""
    convs = await conversations_list_for_user(supabase, user.id)
    return [
        ConversationOut(
            id=c.id,
            title=c.title,
            created_at=c.created_at,
            updated_at=c.updated_at,
            messages=[],
        )
        for c in convs
    ]


@router.get("/conversations/{conversation_id}", response_model=ConversationOut)
async def get_conversation(
    conversation_id: str,
    user: User = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    conv = await conversation_get(supabase, conversation_id, user.id)
    if not conv:
        raise HTTPException(404, "Conversation non trouvée")

    messages = await messages_list_asc(supabase, conv.id)

    return ConversationOut(
        id=conv.id,
        title=conv.title,
        created_at=conv.created_at,
        updated_at=conv.updated_at,
        messages=[
            MessageOut(
                id=m.id, role=m.role, content=m.content,
                message_type=m.message_type, metadata_json=m.metadata_json,
                created_at=m.created_at,
            )
            for m in messages
        ],
    )


async def _get_conversation_history(supabase: Client, conv_id: str) -> list[dict]:
    """Derniers messages pour le contexte LLM."""
    messages = await messages_recent_for_llm(supabase, conv_id, 10)

    history = []
    for m in messages:
        if m.role in ("user", "assistant"):
            history.append({"role": m.role, "content": m.content})
    return history
