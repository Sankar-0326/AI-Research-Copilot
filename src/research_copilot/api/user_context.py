from dataclasses import dataclass
from research_copilot.config import get_settings


@dataclass
class UserContext:
    """
    Carries decrypted per-user API keys through the pipeline.
    Created at the API layer from the JWT + DB lookup,
    passed into agents so they never touch global settings directly.

    Falls back to .env values if a user key is not provided —
    useful for development and testing without a DB.
    """
    user_id: str
    openai_api_key: str
    pinecone_api_key: str
    tavily_api_key: str

    @classmethod
    def from_api_keys(cls, user_id: str, keys: dict[str, str]) -> "UserContext":
        """
        Build a UserContext from decrypted keys dict returned
        by the get_user_api_keys dependency.
        Falls back to .env for any missing key.
        """
        settings = get_settings()
        return cls(
            user_id=user_id,
            openai_api_key=keys.get("openai") or settings.openai_api_key,
            pinecone_api_key=keys.get("pinecone") or settings.pinecone_api_key,
            tavily_api_key=keys.get("tavily") or settings.tavily_api_key,
        )

    @classmethod
    def from_settings(cls) -> "UserContext":
        """
        Build a UserContext purely from .env settings.
        Used in tests and CLI runs where there's no authenticated user.
        """
        settings = get_settings()
        return cls(
            user_id="system",
            openai_api_key=settings.openai_api_key,
            pinecone_api_key=settings.pinecone_api_key,
            tavily_api_key=settings.tavily_api_key,
        )