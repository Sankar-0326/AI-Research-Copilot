from datetime import datetime, timedelta, timezone
from typing import Literal

from jose import JWTError, jwt

from research_copilot.config import get_settings
from research_copilot.logging import get_logger

logger = get_logger("auth.jwt")


def _get_settings():
    return get_settings()


def create_access_token(user_id: str) -> str:
    """
    Create a short-lived JWT access token.
    Expires in JWT_EXPIRE_MINUTES (default 15 min).
    """
    settings = _get_settings()
    expire = datetime.now(timezone.utc) + timedelta(
        minutes=settings.jwt_expire_minutes
    )
    payload = {
        "sub": user_id,         # subject — always the user's UUID
        "type": "access",
        "exp": expire,
        "iat": datetime.now(timezone.utc),
    }
    token = jwt.encode(
        payload,
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )
    logger.debug("access_token_created", user_id=user_id[:8])
    return token


def create_refresh_token(user_id: str) -> str:
    """
    Create a long-lived JWT refresh token.
    Expires in JWT_REFRESH_EXPIRE_DAYS (default 7 days).
    Used only to issue new access tokens — not for API access.
    """
    settings = _get_settings()
    expire = datetime.now(timezone.utc) + timedelta(
        days=settings.jwt_refresh_expire_days
    )
    payload = {
        "sub": user_id,
        "type": "refresh",      # ← different type, can't be used as access
        "exp": expire,
        "iat": datetime.now(timezone.utc),
    }
    token = jwt.encode(
        payload,
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )
    logger.debug("refresh_token_created", user_id=user_id[:8])
    return token


def decode_token(
    token: str,
    expected_type: Literal["access", "refresh"] = "access",
) -> dict:
    """
    Decode and validate a JWT token.

    Validates:
    - Signature (using JWT_SECRET_KEY)
    - Expiry (raises if expired)
    - Token type (access vs refresh — prevents refresh tokens
      being used as access tokens and vice versa)

    Returns the full payload dict on success.
    Raises ValueError with a safe message on any failure.
    """
    settings = _get_settings()
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
        )

        # Enforce token type — critical security check
        token_type = payload.get("type")
        if token_type != expected_type:
            raise ValueError(
                f"Invalid token type. Expected '{expected_type}', got '{token_type}'."
            )

        return payload

    except JWTError as e:
        logger.warning("jwt_decode_failed", error=str(e))
        raise ValueError(f"Token invalid or expired: {str(e)}")


def get_user_id_from_token(token: str) -> str:
    """
    Extract user_id (sub claim) from a valid access token.
    This is the primary function called by FastAPI dependencies.
    """
    payload = decode_token(token, expected_type="access")
    user_id = payload.get("sub")
    if not user_id:
        raise ValueError("Token missing subject claim.")
    return user_id