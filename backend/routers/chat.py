"""
Router principal — Chat conversationnel.

Pipeline en 4 couches + conversation :
  Couche 0  — Filter       (modèle cheap)  : in-scope / hors-scope
  Couche 1  — Guard        (modèle moyen)  : intent + entités
  Couche 1b — Conversation (modèle moyen)  : clarification multi-tour
  Couche 2  — Orchestrator (meilleur modèle): plan d'exécution API
  Couche 3  — API Engine   (déterministe)  : exécution SIRENE / Pappers / Places
  Couche 3b — Pertinence  (LLM rapide)     : filtre des lignes hors cible
"""

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
    conversation_update_folder,
    conversations_list_for_user,
    message_insert,
    messages_list_asc,
    messages_recent_for_llm,
    project_folder_delete,
    project_folder_get,
    project_folder_insert,
    project_folder_update,
    project_folders_list_for_user,
    search_history_insert,
)
from models.entities import User, Conversation, Message, ProjectFolder, SearchHistory, gen_uuid
from models.schemas import (
    ChatRequest,
    ChatResponse,
    MessageOut,
    ConversationOut,
    ConversationFolderPatch,
    ProjectFolderCreate,
    ProjectFolderOut,
    ProjectFolderPatch,
    SearchResults,
)
from services.filter import run_filter
from services.guard import run_guard
from services.conversationalist import generate_qcm
from services.orchestrator import run_orchestrator
from services.api_engine import execute_plan
from services.relevance import filter_results_by_relevance
from services.modes import (
    MODE_LABELS,
    Mode,
    normalize_mode,
)
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

    requested_mode: Mode = normalize_mode(req.mode)

    if req.conversation_id:
        conv = await conversation_get(supabase, req.conversation_id, user.id)
        if not conv:
            raise HTTPException(404, "Conversation non trouvée")
        # Une conversation existante garde son mode initial pour cohérence d'historique.
        active_mode: Mode = normalize_mode(conv.mode) if conv.mode else requested_mode
    else:
        active_mode = requested_mode
        new_folder_id: str | None = None
        if req.folder_id:
            fld = await project_folder_get(supabase, req.folder_id, user.id)
            if not fld:
                raise HTTPException(400, "Projet invalide ou inaccessible.")
            new_folder_id = req.folder_id
        conv = Conversation(
            id=gen_uuid(),
            user_id=user.id,
            title=req.message[:60],
            created_at=now,
            updated_at=now,
            mode=active_mode,
            folder_id=new_folder_id,
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
    plan = await run_orchestrator(guard_result, mode=active_mode)

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

    relevance_meta: dict = {}
    if search_results.total > 0:
        filtered_rows, rel_stats = await filter_results_by_relevance(
            search_results.results,
            user_query=req.message,
            guard_result=guard_result,
            mode=active_mode,
        )
        search_results.results = filtered_rows
        search_results.total = len(filtered_rows)
        relevance_meta = {
            k: rel_stats[k]
            for k in (
                "relevance_skipped",
                "relevance_skip_reason",
                "relevance_before",
                "relevance_after",
                "relevance_removed",
                "relevance_fallback_unfiltered",
                "relevance_threshold",
                "relevance_avg_score",
            )
            if k in rel_stats
        }

    plog(
        "execute_plan_done",
        total=search_results.total,
        credits_required=search_results.credits_required,
        columns=search_results.columns,
        relevance=relevance_meta or None,
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
        mode=active_mode,
    )

    # ── Construire le message de résultats ─────────────────────────
    credits_needed = search_results.credits_required
    preview_text = f"J'ai trouvé **{total} entreprises** correspondant à ta recherche."
    removed = relevance_meta.get("relevance_removed") if relevance_meta else 0
    if isinstance(removed, int) and removed > 0:
        preview_text += (
            f" J'en ai écarté **{removed}** peu alignées avec ta requête après "
            "vérification automatique."
        )
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

    # Cadres d'analyse — sans recommandation personnalisée ni valorisation.
    if active_mode == "rachat":
        preview_text += "\n\n" + _build_rachat_framing(search_results.results)
    elif active_mode == "benchmark":
        preview_text += "\n\n" + _build_benchmark_framing(search_results.results)

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
            "signaux": [s.model_dump() for s in r.signaux] if r.signaux else [],
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
            "mode": active_mode,
            "mode_label": MODE_LABELS.get(active_mode, active_mode),
            "relevance": relevance_meta or None,
        }, ensure_ascii=False, default=str),
        created_at=datetime.now(timezone.utc),
    )

    await message_insert(supabase, result_msg)
    response_messages.append(result_msg)

    # Persister l'historique avant de répondre : l'export utilise ce row (évite 404 si clic rapide).
    try:
        await search_history_insert(supabase, search_record)
    except Exception:
        plog("search_history_insert_error", error=traceback.format_exc()[-1500:])

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
            mode=c.mode,
            folder_id=c.folder_id,
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
        mode=conv.mode,
        folder_id=conv.folder_id,
        messages=[
            MessageOut(
                id=m.id, role=m.role, content=m.content,
                message_type=m.message_type, metadata_json=m.metadata_json,
                created_at=m.created_at,
            )
            for m in messages
        ],
    )


@router.get("/project-folders", response_model=list[ProjectFolderOut])
async def list_project_folders(
    user: User = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    folders = await project_folders_list_for_user(supabase, user.id)
    return [
        ProjectFolderOut(
            id=f.id,
            name=f.name,
            sort_position=f.sort_position,
            created_at=f.created_at,
            updated_at=f.updated_at,
        )
        for f in folders
    ]


@router.post("/project-folders", response_model=ProjectFolderOut)
async def create_project_folder(
    body: ProjectFolderCreate,
    user: User = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    name = (body.name or "").strip() or "Nouveau projet"
    existing = await project_folders_list_for_user(supabase, user.id)
    next_pos = max((f.sort_position for f in existing), default=-1) + 1
    now = datetime.now(timezone.utc)
    folder = ProjectFolder(
        id=gen_uuid(),
        user_id=user.id,
        name=name[:160],
        sort_position=next_pos,
        created_at=now,
        updated_at=now,
    )
    created = await project_folder_insert(supabase, folder)
    return ProjectFolderOut(
        id=created.id,
        name=created.name,
        sort_position=created.sort_position,
        created_at=created.created_at,
        updated_at=created.updated_at,
    )


@router.patch("/project-folders/{folder_id}", response_model=ProjectFolderOut)
async def patch_project_folder(
    folder_id: str,
    body: ProjectFolderPatch,
    user: User = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    current = await project_folder_get(supabase, folder_id, user.id)
    if not current:
        raise HTTPException(404, "Projet non trouvé")

    patch: dict = {}
    if body.name is not None:
        n = body.name.strip()
        if not n:
            raise HTTPException(400, "Le nom du projet ne peut pas être vide.")
        patch["name"] = n[:160]
    if body.sort_position is not None:
        patch["sort_position"] = body.sort_position

    if patch:
        ok = await project_folder_update(supabase, folder_id, user.id, patch)
        if not ok:
            raise HTTPException(404, "Projet non trouvé")

    updated = await project_folder_get(supabase, folder_id, user.id)
    assert updated is not None
    return ProjectFolderOut(
        id=updated.id,
        name=updated.name,
        sort_position=updated.sort_position,
        created_at=updated.created_at,
        updated_at=updated.updated_at,
    )


@router.delete("/project-folders/{folder_id}")
async def delete_project_folder(
    folder_id: str,
    user: User = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    ok = await project_folder_delete(supabase, folder_id, user.id)
    if not ok:
        raise HTTPException(404, "Projet non trouvé")
    return {"ok": True}


@router.patch("/conversations/{conversation_id}/folder", response_model=ConversationOut)
async def patch_conversation_folder(
    conversation_id: str,
    body: ConversationFolderPatch,
    user: User = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    conv = await conversation_get(supabase, conversation_id, user.id)
    if not conv:
        raise HTTPException(404, "Conversation non trouvée")

    if body.folder_id is not None:
        fld = await project_folder_get(supabase, body.folder_id, user.id)
        if not fld:
            raise HTTPException(400, "Projet invalide ou inaccessible.")

    ok = await conversation_update_folder(
        supabase, conversation_id, user.id, body.folder_id
    )
    if not ok:
        raise HTTPException(404, "Conversation non trouvée")

    conv2 = await conversation_get(supabase, conversation_id, user.id)
    assert conv2 is not None
    return ConversationOut(
        id=conv2.id,
        title=conv2.title,
        created_at=conv2.created_at,
        updated_at=conv2.updated_at,
        mode=conv2.mode,
        folder_id=conv2.folder_id,
        messages=[],
    )


async def _get_conversation_history(supabase: Client, conv_id: str) -> list[dict]:
    """Derniers messages pour le contexte LLM."""
    messages = await messages_recent_for_llm(supabase, conv_id, 10)

    history = []
    for m in messages:
        if m.role in ("user", "assistant"):
            history.append({"role": m.role, "content": m.content})
    return history


# ── Cadre d'analyse Rachat ────────────────────────────────────────────────────
#
# On ne formule AUCUNE recommandation chiffrée ni avis personnalisé : on liste
# les indicateurs collectés, ce qui manque, et les questions à investiguer.

def _build_rachat_framing(results: list) -> str:  # results: list[CompanyResult]
    if not results:
        return ""

    sample = results[:50]
    nb = len(sample)

    nb_with_ca = sum(1 for r in sample if getattr(r, "chiffre_affaires", None))
    nb_with_resultat = sum(1 for r in sample if getattr(r, "resultat_net", None) is not None)
    nb_with_dirigeant = sum(1 for r in sample if getattr(r, "dirigeant_nom", None))
    nb_with_age_societe = sum(1 for r in sample if getattr(r, "date_creation", None))

    lines = [
        "---",
        "**Cadre d'analyse — mode Rachat**",
        "",
        f"Sur les {nb} fiches affichées :",
        f"- {nb_with_ca}/{nb} avec un chiffre d'affaires connu",
        f"- {nb_with_resultat}/{nb} avec un résultat net connu",
        f"- {nb_with_dirigeant}/{nb} avec un dirigeant identifié",
        f"- {nb_with_age_societe}/{nb} avec une date de création connue",
        "",
        "**Hypothèses à valider avant tout contact :**",
        "1. La cible est-elle effectivement à céder (signal de transmission, "
        "âge dirigeant, absence de relève) ?",
        "2. La rentabilité affichée est-elle structurelle (3 derniers exercices) "
        "ou conjoncturelle ?",
        "3. La structure juridique permet-elle une reprise simple "
        "(SARL/SAS vs holding complexe) ?",
        "",
        "**Questions à investiguer (hors champ MONV) :**",
        "- Niveau d'endettement réel (compte courant associés, leasing) — "
        "à demander en data room.",
        "- Dépendance client / fournisseur (top 3 clients = ?% du CA).",
        "- Conditions de bail commercial / propriété des actifs.",
        "- Audit social (turnover, conventions, primes d'ancienneté).",
        "",
        "_Ce cadre est purement indicatif. Il ne constitue ni un conseil "
        "juridique, ni un conseil financier, ni une valorisation. Toute "
        "décision d'acquisition doit s'appuyer sur un audit professionnel._",
    ]
    return "\n".join(lines)


def _build_benchmark_framing(results: list) -> str:
    """Livrable secteur / marché : couverture des chiffres, pas d'agrégat inventé."""
    if not results:
        return ""

    sample = results[:50]
    nb = len(sample)

    nb_with_ca = sum(1 for r in sample if getattr(r, "chiffre_affaires", None))
    nb_with_ca_n1 = sum(1 for r in sample if getattr(r, "ca_n_minus_1", None))
    nb_with_var = sum(
        1 for r in sample if getattr(r, "variation_ca_pct", None) is not None
    )
    nb_with_eff = sum(1 for r in sample if getattr(r, "effectif_label", None))
    nb_with_rn = sum(1 for r in sample if getattr(r, "resultat_net", None) is not None)
    nb_with_ebe = sum(1 for r in sample if getattr(r, "ebe", None) is not None)
    nb_with_ape = sum(1 for r in sample if getattr(r, "libelle_activite", None))

    lines = [
        "---",
        "**Livrable — mode Benchmark (secteur / marché)**",
        "",
        f"Échantillon affiché : **{nb}** entreprises.",
        "",
        "**Couverture des données (indicateurs utiles consultant / banque / entrepreneur)** :",
        f"- {nb_with_ape}/{nb} avec libellé d'activité (lecture homogène du périmètre)",
        f"- {nb_with_eff}/{nb} avec effectif (tranche ou effectif financier)",
        f"- {nb_with_ca}/{nb} avec dernier CA connu",
        f"- {nb_with_ca_n1}/{nb} avec CA de l'exercice précédent (comparaison N / N-1)",
        f"- {nb_with_var}/{nb} avec variation de CA % (quand N et N-1 sont disponibles)",
        f"- {nb_with_rn}/{nb} avec résultat net",
        f"- {nb_with_ebe}/{nb} avec EBE",
        "",
        "**Lecture recommandée** :",
        "1. **Consultant** : segmenter par tranche d'effectif et par zone, puis "
        "exporter pour tableaux croisés (structure de coûts implicite via RN / CA).",
        "2. **Banque / risque** : vérifier la dispersion du CA et du RN (concentration "
        "vs médiane à calculer hors outil), l'ancienneté (`date_creation`) et la forme "
        "juridique.",
        "3. **Entrepreneur** : comparer ton projet aux fiches du même code APE / même "
        "zone pour calibrer taille et dynamique, sans inférer une « taille de marché » "
        "non sourcée.",
        "",
        "**Export** : les colonnes incluent CA, exercices, variation, effectifs et "
        "rentabilité lorsque Pappers a pu enrichir — prêt pour slide ou annexe Excel.",
        "",
        "_Les chiffres sont issus de sources publiques et peuvent être incomplets. "
        "Ce bloc ne remplace pas une étude de marché commandée, une due diligence ni "
        "un conseil en investissement._",
    ]
    return "\n".join(lines)
