from fastapi import APIRouter, Depends, HTTPException
from supabase import Client

from models.db import get_supabase, user_update_credits
from models.entities import User
from models.schemas import CreditPack
from routers.auth import get_current_user
from utils.credits_policy import credits_for_api, user_has_unlimited_credits

router = APIRouter(prefix="/api/credits", tags=["credits"])

PACKS = [
    CreditPack(id="starter", name="Starter", credits=30, price_euros=9.0, price_per_credit=0.30),
    CreditPack(id="pro", name="Pro", credits=120, price_euros=29.0, price_per_credit=0.24),
    CreditPack(id="business", name="Business", credits=400, price_euros=79.0, price_per_credit=0.20),
]


@router.get("/packs", response_model=list[CreditPack])
async def get_packs():
    return PACKS


@router.get("/balance")
async def get_balance(user: User = Depends(get_current_user)):
    return {
        "credits": credits_for_api(user),
        "credits_unlimited": user_has_unlimited_credits(user),
    }


@router.post("/add/{pack_id}")
async def add_credits(
    pack_id: str,
    user: User = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    """
    En local/dev: ajoute directement les crédits (pas de Stripe).
    En production, ce serait le webhook Stripe qui déclenche l'ajout.
    """
    pack = next((p for p in PACKS if p.id == pack_id), None)
    if not pack:
        raise HTTPException(404, "Pack non trouvé")

    if user_has_unlimited_credits(user):
        return {
            "message": "Compte crédits illimités — aucun achat nécessaire.",
            "new_balance": credits_for_api(user),
            "pack": pack.model_dump(),
        }

    user.credits += pack.credits
    await user_update_credits(supabase, user.id, user.credits)

    return {
        "message": f"{pack.credits} crédits ajoutés !",
        "new_balance": credits_for_api(user),
        "pack": pack.model_dump(),
    }
