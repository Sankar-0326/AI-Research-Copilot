import uuid
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from research_copilot.auth.jwt_handler import get_user_id_from_token
from research_copilot.auth.encryption import decrypt_api_key
from research_copilot.db.database import get_db_session
from research_copilot.db.models.user import User
from research_copilot.db.models.api_keys import UserAPIKey, APIKeyProvider
from research_copilot.logging import get_logger

logger = get_logger("auth.dependencies")

# Extracts Bearer token from Authorization header automatically
bearer_scheme = HTTPBearer()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db_session),
) -> User:
    """
    FastAPI dependency — extracts and validates the JWT from
    the Authorization header, then loads the user from DB.

    Usage in any protected route:
        async def my_route(user: User = Depends(get_current_user)):

    Raises 401 if:
    - No token provided
    - Token is invalid or expired
    - User not found or inactive
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired token.",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        user_id = get_user_id_from_token(credentials.credentials)
    except ValueError:
        raise credentials_exception

    # Load user from DB
    result = await db.execute(
        select(User).where(User.id == uuid.UUID(user_id))
    )
    user = result.scalar_one_or_none()

    if user is None:
        logger.warning("auth_user_not_found", user_id=user_id[:8])
        raise credentials_exception

    if not user.is_active:
        logger.warning("auth_user_inactive", user_id=user_id[:8])
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is inactive.",
        )

    logger.debug("auth_user_verified", user_id=user_id[:8])
    return user


async def get_user_api_keys(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> dict[str, str]:
    """
    FastAPI dependency — loads and decrypts all API keys for
    the current user. Returns a dict of provider → plain key.

    Usage in routes that need to call OpenAI / Pinecone / Tavily:
        async def my_route(keys: dict = Depends(get_user_api_keys)):
            openai_key = keys.get("openai")

    Raises 400 if required keys are missing.
    Keys are decrypted in memory only — never logged or returned
    in API responses.
    """
    result = await db.execute(
        select(UserAPIKey).where(UserAPIKey.user_id == user.id)
    )
    api_key_rows = result.scalars().all()

    decrypted_keys: dict[str, str] = {}

    for row in api_key_rows:
        try:
            plain_key = decrypt_api_key(row.encrypted_key)
            decrypted_keys[row.provider.value] = plain_key
        except ValueError:
            logger.error(
                "api_key_decrypt_error",
                user_id=str(user.id)[:8],
                provider=row.provider.value,
            )
            # Skip broken keys — don't fail the whole request
            continue

    logger.debug(
        "api_keys_loaded",
        user_id=str(user.id)[:8],
        providers=list(decrypted_keys.keys()),
    )

    return decrypted_keys


async def require_api_keys(
    keys: dict[str, str] = Depends(get_user_api_keys),
) -> dict[str, str]:
    """
    Stricter version of get_user_api_keys.
    Raises 400 if any of the three required keys are missing.

    Usage in routes that absolutely need all keys to proceed:
        async def my_route(keys: dict = Depends(require_api_keys)):
    """
    required = {
        APIKeyProvider.openai.value,
        APIKeyProvider.pinecone.value,
        APIKeyProvider.tavily.value,
    }
    missing = required - set(keys.keys())

    if missing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Missing API keys for: {', '.join(sorted(missing))}. "
                   f"Add them at /settings/keys.",
        )

    return keys