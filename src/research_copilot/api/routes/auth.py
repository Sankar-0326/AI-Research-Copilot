import uuid
from fastapi import APIRouter, Depends, HTTPException, status, Response, Cookie
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel, EmailStr, Field

from research_copilot.auth.password import hash_password, verify_password
from research_copilot.auth.jwt_handler import (
    create_access_token,
    create_refresh_token,
    decode_token,
)
from research_copilot.auth.encryption import encrypt_api_key, get_key_hint
from research_copilot.auth.dependencies import get_current_user
from research_copilot.db.database import get_db_session
from research_copilot.db.models.user import User
from research_copilot.db.models.api_keys import UserAPIKey, APIKeyProvider
from research_copilot.logging import get_logger
from research_copilot.config import get_settings

logger = get_logger("routes.auth")
router = APIRouter(prefix="/auth", tags=["Auth"])
settings = get_settings()

def set_refresh_cookie(response: Response, refresh_token: str, expire_days: int):
    """Set refresh token as httpOnly cookie — inaccessible to JavaScript."""
    response.set_cookie(
        key="rc_refresh",
        value=refresh_token,
        httponly=True,       # ← JS cannot read this
        secure= settings.app_env == "production",  # ← False in dev, True in prod
        # ← HTTPS only (set False for local dev)
        samesite="lax",      # ← CSRF protection
        max_age=expire_days * 24 * 60 * 60,
        path="/", # ← cookie only sent to refresh endpoint
    )

# ─────────────────────────────────────────────────────────────────────────────
# Schemas
# ─────────────────────────────────────────────────────────────────────────────

class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    refresh_token: str


class APIKeyRequest(BaseModel):
    provider: APIKeyProvider
    api_key: str = Field(min_length=10)


class APIKeyResponse(BaseModel):
    id: str
    provider: str
    key_hint: str
    created_at: str


class UserResponse(BaseModel):
    id: str
    email: str
    is_active: bool


# ─────────────────────────────────────────────────────────────────────────────
# Auth endpoints
# ─────────────────────────────────────────────────────────────────────────────

@router.post(
    "/register",
    response_model=TokenResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user",
)
async def register(
    request: RegisterRequest,
    response: Response,
    db: AsyncSession = Depends(get_db_session),
):
    """
    Register a new user account.
    Returns access + refresh tokens immediately on success
    so the user doesn't need a separate login step.
    """
    # Check email not already taken
    result = await db.execute(
        select(User).where(User.email == request.email)
    )
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists.",
        )

    user = User(
        email=request.email,
        hashed_password=hash_password(request.password),
    )
    db.add(user)
    await db.flush()   # flush to get user.id without committing yet

    logger.info("user_registered", user_id=str(user.id)[:8], email=request.email)


    
    access_token = create_access_token(str(user.id))
    refresh_token = create_refresh_token(str(user.id))

    set_refresh_cookie(response, refresh_token, settings.jwt_refresh_expire_days)

    return TokenResponse(
        access_token=access_token,
        refresh_token="",    # ← no longer returned in body
        token_type="bearer",
    )


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Login and receive JWT tokens",
)
async def login(
    request: LoginRequest,
    response: Response,  
    db: AsyncSession = Depends(get_db_session),
):
    """
    Authenticate with email + password.
    Returns access token (15min) + refresh token (7 days).
    """
    result = await db.execute(
        select(User).where(User.email == request.email)
    )
    user = result.scalar_one_or_none()

    # Deliberate vague error — don't reveal whether email exists
    invalid_credentials = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid email or password.",
    )

    if user is None:
        raise invalid_credentials

    if not verify_password(request.password, user.hashed_password):
        logger.warning("login_failed_wrong_password", email=request.email)
        raise invalid_credentials

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is inactive.",
        )

    logger.info("user_logged_in", user_id=str(user.id)[:8])

    access_token = create_access_token(str(user.id))
    refresh_token = create_refresh_token(str(user.id))

    set_refresh_cookie(response, refresh_token, settings.jwt_refresh_expire_days)

    return TokenResponse(
        access_token=access_token,
        refresh_token="",    # ← no longer returned in body
        token_type="bearer",
    )


@router.post(
    "/refresh",
    response_model=TokenResponse,
    summary="Refresh access token using refresh token",
)
async def refresh_token(
    response: Response,
    db: AsyncSession = Depends(get_db_session),
    rc_refresh: str | None = Cookie(default=None),   # ← read from cookie
):
    """
    Exchange a valid refresh token for a new access + refresh token pair.
    Both tokens are rotated on every refresh for security.
    """
    if not rc_refresh:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No refresh token provided.",
        )

    try:
        payload = decode_token(rc_refresh, expected_type="refresh")
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token.",
        )

    user_id = payload.get("sub")

    # Verify user still exists and is active
    result = await db.execute(
        select(User).where(User.id == uuid.UUID(user_id))
    )
    user = result.scalar_one_or_none()

    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive.",
        )

    logger.info("tokens_refreshed", user_id=user_id[:8])

    new_access_token=create_access_token(user_id)
    new_refresh_token=create_refresh_token(user_id)

    set_refresh_cookie(response, new_refresh_token, settings.jwt_refresh_expire_days)

    return TokenResponse(
        access_token=new_access_token,
        refresh_token="",    # ← not in body
        token_type="bearer",
    )


@router.get(
    "/me",
    response_model=UserResponse,
    summary="Get current user info",
)
async def get_me(user: User = Depends(get_current_user)):
    """Returns the currently authenticated user's profile."""
    return UserResponse(
        id=str(user.id),
        email=user.email,
        is_active=user.is_active,
    )


# ─────────────────────────────────────────────────────────────────────────────
# API Key management endpoints
# ─────────────────────────────────────────────────────────────────────────────

@router.post(
    "/keys",
    response_model=APIKeyResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Store an encrypted API key for a provider",
)
async def add_api_key(
    request: APIKeyRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    """
    Encrypt and store an API key for a provider.
    If a key for this provider already exists, it is replaced.
    The plain key is never stored — only the Fernet-encrypted form
    and the last 4 characters as a hint.
    """
    # Check if key for this provider already exists
    result = await db.execute(
        select(UserAPIKey).where(
            UserAPIKey.user_id == user.id,
            UserAPIKey.provider == request.provider,
        )
    )
    existing = result.scalar_one_or_none()

    if existing:
        # Update in place
        existing.encrypted_key = encrypt_api_key(request.api_key)
        existing.key_hint = get_key_hint(request.api_key)
        key_record = existing
        logger.info(
            "api_key_updated",
            user_id=str(user.id)[:8],
            provider=request.provider.value,
        )
    else:
        key_record = UserAPIKey(
            user_id=user.id,
            provider=request.provider,
            encrypted_key=encrypt_api_key(request.api_key),
            key_hint=get_key_hint(request.api_key),
        )
        db.add(key_record)
        await db.flush()
        logger.info(
            "api_key_added",
            user_id=str(user.id)[:8],
            provider=request.provider.value,
        )

    return APIKeyResponse(
        id=str(key_record.id),
        provider=key_record.provider.value,
        key_hint=f"...{key_record.key_hint}",
        created_at=key_record.created_at.isoformat(),
    )


@router.get(
    "/keys",
    response_model=list[APIKeyResponse],
    summary="List stored API keys (hints only — no plain keys returned)",
)
async def list_api_keys(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    """
    List all stored API keys for the current user.
    Returns provider name and key hint only.
    Plain keys are never returned in any response.
    """
    result = await db.execute(
        select(UserAPIKey).where(UserAPIKey.user_id == user.id)
    )
    keys = result.scalars().all()

    return [
        APIKeyResponse(
            id=str(k.id),
            provider=k.provider.value,
            key_hint=f"...{k.key_hint}",
            created_at=k.created_at.isoformat(),
        )
        for k in keys
    ]


@router.delete(
    "/keys/{provider}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a stored API key",
)
async def delete_api_key(
    provider: APIKeyProvider,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    """Delete the stored API key for a given provider."""
    result = await db.execute(
        select(UserAPIKey).where(
            UserAPIKey.user_id == user.id,
            UserAPIKey.provider == provider,
        )
    )
    key = result.scalar_one_or_none()

    if not key:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No key found for provider '{provider.value}'.",
        )

    await db.delete(key)
    logger.info(
        "api_key_deleted",
        user_id=str(user.id)[:8],
        provider=provider.value,
    )


@router.post("/logout")
async def logout(response: Response):
    response.delete_cookie(
        key="rc_refresh",
        path="/",
        httponly=True,
        secure=settings.app_env == "production",
        samesite="lax",
    )
    return {"message": "Logged out successfully."}