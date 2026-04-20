from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # OpenAI
    openai_api_key: str 
    openai_model: str = "gpt-4o"
    openai_embedding_model: str = "text-embedding-3-small"

    # Pinecone
    pinecone_api_key: str
    pinecone_index_name: str = "research-copilot"
    pinecone_environment: str = "us-east-1"

    # App
    app_env: str = "development"
    chunk_size: int = 1000
    chunk_overlap: int = 200
    retrieval_top_k: int = 5

    # Tavily
    tavily_api_key: str

    # Hybrid search
    hybrid_alpha: float = 0.5
    bm25_model_path: str = ".cache/bm25/bm25_model.pkl"
    
    # Database
    database_url: str

    # JWT
    jwt_secret_key: str
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 15
    jwt_refresh_expire_days: int = 7

    # Encryption
    fernet_master_key: str

    # Semantic cache
    semantic_cache_threshold: float = 0.95
    semantic_cache_path: str = ".cache/semantic/"


# @lru_cache() - ensures settings are loaded from disk only once and reused across the app — a production pattern.
@lru_cache()
def get_settings() -> Settings:
    return Settings()