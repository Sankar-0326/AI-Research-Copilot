from cryptography.fernet import Fernet, InvalidToken

from research_copilot.config import get_settings
from research_copilot.logging import get_logger

logger = get_logger("auth.encryption")


def _get_fernet() -> Fernet:
    """
    Build a Fernet instance from the master key in .env.
    Called fresh each time — never cached at module level
    so key rotation only requires updating .env.
    """
    settings = get_settings()
    return Fernet(settings.fernet_master_key.encode())


def encrypt_api_key(plain_key: str) -> str:
    """
    Encrypt a plain API key using Fernet symmetric encryption.

    Fernet guarantees:
    - AES-128-CBC encryption
    - HMAC-SHA256 authentication
    - Timestamp embedded in token (enables TTL if needed later)

    Returns a URL-safe base64 encoded string safe to store in PostgreSQL.
    Never stored in logs — only the encrypted form and key_hint are persisted.
    """
    fernet = _get_fernet()
    encrypted = fernet.encrypt(plain_key.encode("utf-8"))
    logger.debug("api_key_encrypted")
    return encrypted.decode("utf-8")


def decrypt_api_key(encrypted_key: str) -> str:
    """
    Decrypt a Fernet-encrypted API key back to plain text.

    Raises ValueError if:
    - The master key has changed (token invalid)
    - The token has been tampered with (HMAC fails)
    - The token is malformed

    The plain key is returned directly to the caller and
    injected into the request context — never logged.
    """
    fernet = _get_fernet()
    try:
        decrypted = fernet.decrypt(encrypted_key.encode("utf-8"))
        logger.debug("api_key_decrypted")
        return decrypted.decode("utf-8")
    except InvalidToken:
        logger.error(
            "api_key_decrypt_failed",
            reason="invalid_token_or_wrong_master_key",
        )
        raise ValueError(
            "Could not decrypt API key. "
            "The master key may have changed or the token is corrupted."
        )


def get_key_hint(plain_key: str) -> str:
    """
    Extract the last 4 characters of a plain API key.
    Stored in DB and shown in UI so users can identify which key is stored
    without ever exposing the full key.

    e.g. 'sk-abc123xyz' → '...xyz'  (shown as '...xyz' in UI)
    """
    if len(plain_key) < 4:
        return "***"
    return plain_key[-4:]