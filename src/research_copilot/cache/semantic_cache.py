import json
import time
import random
import pickle
import hashlib
import numpy as np
import faiss
from pathlib import Path
from dataclasses import dataclass, field

from langchain_openai import OpenAIEmbeddings

from research_copilot.config import get_settings
from research_copilot.logging import get_logger

logger = get_logger("semantic_cache")


# ─────────────────────────────────────────────────────────────────────────────
# Cache Entry
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class CacheEntry:
    """
    A single cached item.
    Stores the response, its embedding, and expiry metadata.
    """
    key: str                    # exact hash key (agent + query + paper_ids)
    response: str               # LLM response text
    embedding: list[float]      # embedding of the query (for similarity search)
    agent: str
    query: str
    paper_ids: list[str]
    created_at: float = field(default_factory=time.time)
    expires_at: float = 0.0     # unix timestamp, 0 = no expiry


# ─────────────────────────────────────────────────────────────────────────────
# Semantic Cache
# ─────────────────────────────────────────────────────────────────────────────

class SemanticCache:
    """
    Two-tier LLM response cache:

    Tier 1 — Exact match (dict lookup, <1ms)
        Hash of (agent + query + paper_ids) → cached response
        Handles identical repeated queries with zero overhead

    Tier 2 — Semantic match (FAISS similarity search, ~5-20ms)
        Embeds incoming query → cosine similarity vs all cached embeddings
        Returns cached response if similarity >= threshold (default 0.95)
        Handles paraphrased queries that mean the same thing

    Tier 3 — Cache miss
        Falls through to LLM call
        Result stored in both tiers for future hits

    Persistence:
        FAISS index + entry metadata saved to disk on every write
        Survives restarts — no cold cache after deployment
    """

    BASE_TTL = 60 * 60 * 24        # 24h base
    TTL_JITTER = 60 * 60 * 2       # ±2h jitter — prevents thundering herd

    def __init__(self):
        settings = get_settings()
        self.threshold = settings.semantic_cache_threshold
        self.cache_dir = Path(settings.semantic_cache_path)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        self._faiss_path = self.cache_dir / "faiss.index"
        self._entries_path = self.cache_dir / "entries.pkl"

        # Tier 1 — exact match store
        self._exact: dict[str, CacheEntry] = {}

        # Tier 2 — semantic index + ordered entries list
        # IndexFlatIP = inner product (cosine sim on normalized vectors)
        self._index: faiss.IndexFlatIP | None = None
        self._entries: list[CacheEntry] = []   # parallel to FAISS index rows

        # Embedding model (lazy init)
        self._embedder: OpenAIEmbeddings | None = None

        # Load persisted state
        self._load()

        logger.info(
            "semantic_cache_initialized",
            threshold=self.threshold,
            entries=len(self._entries),
            cache_dir=str(self.cache_dir),
        )

    # ── Embedding ─────────────────────────────────────────────────────────────

    def _get_embedder(self) -> OpenAIEmbeddings:
        if self._embedder is None:
            settings = get_settings()
            self._embedder = OpenAIEmbeddings(
                model=settings.openai_embedding_model,
                api_key=settings.openai_api_key,
            )
        return self._embedder

    def _embed(self, text: str) -> np.ndarray:
        """
        Embed a string and return a normalized float32 numpy vector.
        Normalization is required for IndexFlatIP to compute cosine similarity.
        """
        embedder = self._get_embedder()
        vector = np.array(embedder.embed_query(text), dtype=np.float32)

        # L2 normalize so inner product == cosine similarity
        norm = np.linalg.norm(vector)
        if norm > 0:
            vector = vector / norm

        return vector

    # ── Key ───────────────────────────────────────────────────────────────────

    def _make_key(
        self,
        agent: str,
        query: str,
        paper_ids: list[str],
    ) -> str:
        """
        Deterministic hash key identical to the old ResponseCache.
        Includes agent name so different agents never share cached responses.
        """
        payload = json.dumps(
            {"agent": agent, "query": query, "paper_ids": sorted(paper_ids)},
            sort_keys=True,
        )
        return hashlib.sha256(payload.encode()).hexdigest()

    # ── TTL ───────────────────────────────────────────────────────────────────

    def _make_expiry(self) -> float:
        """
        TTL with random jitter to prevent thundering herd.
        All entries set at the same time won't expire simultaneously.
        """
        jitter = random.uniform(-self.TTL_JITTER, self.TTL_JITTER)
        return time.time() + self.BASE_TTL + jitter

    def _is_expired(self, entry: CacheEntry) -> bool:
        if entry.expires_at == 0:
            return False
        return time.time() > entry.expires_at

    # ── FAISS index management ────────────────────────────────────────────────

    def _get_or_create_index(self, dimension: int = 1536) -> faiss.IndexFlatIP:
        if self._index is None:
            self._index = faiss.IndexFlatIP(dimension)
        return self._index

    def _add_to_index(self, entry: CacheEntry):
        """Add an entry's embedding to FAISS and append to entries list."""
        vector = np.array(entry.embedding, dtype=np.float32).reshape(1, -1)
        index = self._get_or_create_index(dimension=vector.shape[1])
        index.add(vector)
        self._entries.append(entry)

    # ── Persistence ───────────────────────────────────────────────────────────

    def _save(self):
        """Persist FAISS index and entry metadata to disk."""
        try:
            if self._index is not None and self._index.ntotal > 0:
                faiss.write_index(self._index, str(self._faiss_path))

            with open(self._entries_path, "wb") as f:
                pickle.dump(self._entries, f)

            logger.debug("semantic_cache_saved", entries=len(self._entries))

        except Exception as e:
            logger.error("semantic_cache_save_failed", error=str(e))

    def _load(self):
        """Load persisted FAISS index and entry metadata from disk."""
        try:
            if self._faiss_path.exists():
                self._index = faiss.read_index(str(self._faiss_path))
                logger.info("faiss_index_loaded", vectors=self._index.ntotal)

            if self._entries_path.exists():
                with open(self._entries_path, "rb") as f:
                    self._entries = pickle.load(f)

                # Rebuild exact match tier from loaded entries
                for entry in self._entries:
                    if not self._is_expired(entry):
                        self._exact[entry.key] = entry

                logger.info(
                    "semantic_cache_entries_loaded",
                    total=len(self._entries),
                    active=len(self._exact),
                )

        except Exception as e:
            logger.warning("semantic_cache_load_failed", error=str(e))
            # Start fresh — non-fatal
            self._index = None
            self._entries = []
            self._exact = {}

    # ── Public API ────────────────────────────────────────────────────────────

    def get(
        self,
        agent: str,
        query: str,
        paper_ids: list[str],
    ) -> str | None:
        """
        Look up a cached response.

        Tier 1: Exact hash match — returns instantly if found
        Tier 2: Semantic FAISS match — embeds query, searches index
                Returns if cosine similarity >= self.threshold
        Tier 3: Cache miss → returns None
        """
        key = self._make_key(agent, query, paper_ids)

        # ── Tier 1: exact match ───────────────────────────────────────
        if key in self._exact:
            entry = self._exact[key]
            if self._is_expired(entry):
                self._evict(key)
                logger.info("cache_expired", agent=agent, key=key[:8])
            else:
                logger.info(
                    "cache_hit_exact",
                    agent=agent,
                    key=key[:8],
                )
                return entry.response

        # ── Tier 2: semantic match ────────────────────────────────────
        if self._index is None or self._index.ntotal == 0:
            return None

        try:
            query_vector = self._embed(query).reshape(1, -1)

            # Search top-1 most similar cached query
            scores, indices = self._index.search(query_vector, k=1)
            top_score = float(scores[0][0])
            top_idx = int(indices[0][0])

            if top_idx == -1:
                return None

            if top_score >= self.threshold:
                matched_entry = self._entries[top_idx]

                # Only return if same agent (different agents = different responses)
                if matched_entry.agent != agent:
                    return None

                if self._is_expired(matched_entry):
                    logger.info(
                        "semantic_match_expired",
                        score=round(top_score, 4),
                        agent=agent,
                    )
                    return None

                logger.info(
                    "cache_hit_semantic",
                    agent=agent,
                    similarity=round(top_score, 4),
                    threshold=self.threshold,
                )
                return matched_entry.response

            logger.debug(
                "cache_miss_below_threshold",
                agent=agent,
                best_score=round(top_score, 4),
                threshold=self.threshold,
            )

        except Exception as e:
            # Cache failure is never fatal — just log and fall through
            logger.error("semantic_search_failed", error=str(e))

        return None

    def set(
        self,
        agent: str,
        query: str,
        paper_ids: list[str],
        response: str,
        ttl: int | None = None,
    ):
        """
        Store a response in both tiers.

        Embeds the query for semantic search and stores in FAISS.
        Adds to exact match dict.
        Persists both to disk.
        """
        key = self._make_key(agent, query, paper_ids)

        try:
            embedding = self._embed(query)

            entry = CacheEntry(
                key=key,
                response=response,
                embedding=embedding.tolist(),
                agent=agent,
                query=query,
                paper_ids=paper_ids,
                expires_at=self._make_expiry(),
            )

            # Store in both tiers
            self._exact[key] = entry
            self._add_to_index(entry)

            # Persist to disk
            self._save()

            logger.info(
                "cache_set",
                agent=agent,
                key=key[:8],
                expires_in_h=round((entry.expires_at - time.time()) / 3600, 1),
            )

        except Exception as e:
            # Cache write failure is never fatal
            logger.error("cache_set_failed", agent=agent, error=str(e))

    def invalidate(
        self,
        agent: str,
        query: str,
        paper_ids: list[str],
    ):
        """Remove a specific entry from the exact match tier."""
        key = self._make_key(agent, query, paper_ids)
        self._evict(key)

    def _evict(self, key: str):
        """Remove entry from exact match tier."""
        if key in self._exact:
            del self._exact[key]
            logger.info("cache_evicted", key=key[:8])

    def clear(self):
        """Wipe all cache state — in memory and on disk."""
        self._exact.clear()
        self._entries.clear()
        self._index = None

        for path in [self._faiss_path, self._entries_path]:
            if path.exists():
                path.unlink()

        logger.info("semantic_cache_cleared")

    @property
    def stats(self) -> dict:
        """Quick stats for logging and health checks."""
        return {
            "exact_entries": len(self._exact),
            "faiss_vectors": self._index.ntotal if self._index else 0,
            "threshold": self.threshold,
            "cache_dir": str(self.cache_dir),
        }


# Module-level singleton — same usage pattern as old response_cache
response_cache = SemanticCache()