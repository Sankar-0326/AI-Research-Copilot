import bcrypt
from research_copilot.logging import get_logger

logger = get_logger("auth.password")


def hash_password(plain_password: str) -> str:
    """
    Hash a plain text password using bcrypt.
    Returns a string like: $2b$12$...
    Never store plain passwords — only call this on registration.
    """
    password_bytes = plain_password.encode("utf-8")
    salt = bcrypt.gensalt(rounds=12)
    hashed = bcrypt.hashpw(password_bytes, salt)
    return hashed.decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verify a plain text password against a bcrypt hash.
    Timing-safe — prevents timing attacks.
    """
    try:
        return bcrypt.checkpw(
            plain_password.encode("utf-8"),
            hashed_password.encode("utf-8"),
        )
    except Exception as e:
        logger.warning("password_verify_failed", error=str(e))
        return False