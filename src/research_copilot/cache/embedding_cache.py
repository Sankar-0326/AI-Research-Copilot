import hashlib
import diskcache
from pathlib import Path
from research_copilot.logging import get_logger

logger = get_logger("embedding_cache")
CACHE_DIR = Path(".cache/embeddings")


class EmbeddingCache:
    """
    Persistent disk cache for embeddings.
    Key: SHA256 of chunk text
    Value: embedding vector (list[float])
    """

    def __init__(self):
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        self._cache = diskcache.Cache(str(CACHE_DIR), size_limit=2 ** 30)  # 1GB

    def _key(self, text: str) -> str:
        return hashlib.sha256(text.encode()).hexdigest()

    def get(self, text: str) -> list[float] | None:
        key = self._key(text)
        result = self._cache.get(key)
        if result is not None:
            logger.debug("embedding_cache_hit", key=key[:8])
        return result

    def set(self, text: str, embedding: list[float]):
        key = self._key(text)
        self._cache.set(key, embedding)
        logger.debug("embedding_cache_set", key=key[:8])

    def clear(self):
        self._cache.clear()
        logger.info("embedding_cache_cleared")

    @property
    def size(self) -> int:
        return len(self._cache)


embedding_cache = EmbeddingCache()