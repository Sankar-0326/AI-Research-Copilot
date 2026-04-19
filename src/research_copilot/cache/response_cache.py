import hashlib
import json
import diskcache
from pathlib import Path
from research_copilot.logging import get_logger

logger = get_logger("response_cache")
CACHE_DIR = Path(".cache/responses")


class ResponseCache:
    """
    Persistent disk cache for LLM agent responses.
    Key: hash of (agent, query, paper_ids)
    Value: agent output string
    TTL: 24 hours by default
    """
    DEFAULT_TTL = 60 * 60 * 24  # 24h in seconds

    def __init__(self):
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        self._cache = diskcache.Cache(str(CACHE_DIR), size_limit=2 ** 29)  # 512MB

    def _key(self, agent: str, query: str, paper_ids: list[str]) -> str:
        payload = json.dumps(
            {"agent": agent, "query": query, "paper_ids": sorted(paper_ids)},
            sort_keys=True,
        )
        return hashlib.sha256(payload.encode()).hexdigest()

    def get(self, agent: str, query: str, paper_ids: list[str]) -> str | None:
        key = self._key(agent, query, paper_ids)
        result = self._cache.get(key)
        if result:
            logger.info("response_cache_hit", agent=agent, key=key[:8])
        return result

    def set(
        self,
        agent: str,
        query: str,
        paper_ids: list[str],
        response: str,
        ttl: int = DEFAULT_TTL,
    ):
        key = self._key(agent, query, paper_ids)
        self._cache.set(key, response, expire=ttl)
        logger.info("response_cache_set", agent=agent, key=key[:8], ttl=ttl)

    def invalidate(self, agent: str, query: str, paper_ids: list[str]):
        key = self._key(agent, query, paper_ids)
        self._cache.delete(key)


response_cache = ResponseCache()