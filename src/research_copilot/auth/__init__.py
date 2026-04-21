# src/research_copilot/auth/__init__.py
from research_copilot.auth.password import hash_password, verify_password
from research_copilot.auth.encryption import encrypt_api_key, decrypt_api_key, get_key_hint
from research_copilot.auth.jwt_handler import (
    create_access_token,
    create_refresh_token,
    decode_token,
    get_user_id_from_token,
)
from research_copilot.auth.dependencies import (
    get_current_user,
    get_user_api_keys,
    require_api_keys,
)

__all__ = [
    "hash_password",
    "verify_password",
    "encrypt_api_key",
    "decrypt_api_key",
    "get_key_hint",
    "create_access_token",
    "create_refresh_token",
    "decode_token",
    "get_user_id_from_token",
    "get_current_user",
    "get_user_api_keys",
    "require_api_keys",
]