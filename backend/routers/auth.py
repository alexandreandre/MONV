from fastapi import APIRouter, Depends, HTTPException, Header
from datetime import datetime, timezone, timedelta
from jose import jwt
from passlib.context import CryptContext
from supabase import Client

from models.db import (
    get_supabase,
    try_supabase_auth_sign_in,
    user_by_email,
    user_by_id,
    user_insert,
    user_update_hashed_password,
)
from models.entities import User, gen_uuid
from models.schemas import UserRegister, UserLogin, TokenOut, UserOut
from config import settings
from utils.credits_policy import user_to_user_out

router = APIRouter(prefix="/api/auth", tags=["auth"])
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def _verify_password(plain: str, hashed: str) -> bool:
    try:
        return pwd_context.verify(plain, hashed)
    except Exception:
        return False


def _create_token(user_id: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(hours=settings.JWT_EXPIRE_HOURS)
    return jwt.encode(
        {"sub": user_id, "exp": expire},
        settings.JWT_SECRET,
        algorithm=settings.JWT_ALGORITHM,
    )


async def get_current_user(
    authorization: str | None = Header(None),
    supabase: Client = Depends(get_supabase),
) -> User:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "Token manquant")
    token = authorization.removeprefix("Bearer ").strip()
    try:
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
        user_id = payload.get("sub")
    except Exception:
        raise HTTPException(401, "Token invalide")

    if not user_id:
        raise HTTPException(401, "Token invalide")

    user = await user_by_id(supabase, str(user_id))
    if not user:
        raise HTTPException(401, "Utilisateur non trouvé")
    return user


@router.post("/register", response_model=TokenOut)
async def register(data: UserRegister, supabase: Client = Depends(get_supabase)):
    existing = await user_by_email(supabase, data.email)
    if existing:
        raise HTTPException(400, "Cet email est déjà utilisé")

    now = datetime.now(timezone.utc)
    user = User(
        id=gen_uuid(),
        email=data.email,
        name=data.name,
        hashed_password=pwd_context.hash(data.password),
        credits=settings.FREE_CREDITS,
        created_at=now,
    )
    try:
        user = await user_insert(supabase, user)
    except Exception as e:
        msg = str(e).lower()
        if "duplicate" in msg or "unique" in msg or "23505" in msg:
            raise HTTPException(400, "Cet email est déjà utilisé") from e
        raise

    token = _create_token(user.id)
    return TokenOut(
        access_token=token,
        user=user_to_user_out(user),
    )


@router.post("/login", response_model=TokenOut)
async def login(data: UserLogin, supabase: Client = Depends(get_supabase)):
    """
    1) Compte MONV (`public.users`, mot de passe bcrypt).
    2) Sinon : Supabase Authentication (`auth.users`) puis synchro vers `public.users`.
    """
    email = str(data.email)
    password = data.password

    user = await user_by_email(supabase, email)
    if user and _verify_password(password, user.hashed_password):
        return _login_success(user)

    auth_res = await try_supabase_auth_sign_in(email, password)
    if not auth_res or not auth_res.user or not auth_res.session:
        raise HTTPException(401, "Email ou mot de passe incorrect")

    go = auth_res.user
    auth_id = str(go.id)
    meta = go.user_metadata or {}
    name = (
        meta.get("full_name")
        or meta.get("name")
        or (go.email or email).split("@", 1)[0]
    )

    user = await user_by_email(supabase, email)
    if user is None:
        now = datetime.now(timezone.utc)
        user = User(
            id=auth_id,
            email=email,
            name=str(name)[:255],
            hashed_password=pwd_context.hash(password),
            credits=settings.FREE_CREDITS,
            created_at=now,
        )
        user = await user_insert(supabase, user)
    elif not _verify_password(password, user.hashed_password):
        await user_update_hashed_password(supabase, user.id, pwd_context.hash(password))
        user = await user_by_id(supabase, user.id)
        if not user:
            raise HTTPException(401, "Email ou mot de passe incorrect")

    return _login_success(user)


def _login_success(user: User) -> TokenOut:
    token = _create_token(user.id)
    return TokenOut(
        access_token=token,
        user=user_to_user_out(user),
    )


@router.get("/me", response_model=UserOut)
async def get_me(user: User = Depends(get_current_user)):
    return user_to_user_out(user)
