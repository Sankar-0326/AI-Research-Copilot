import asyncio
import time
import pickle
from pathlib import Path

from langchain.embeddings.base import Embeddings
from langchain_openai import OpenAIEmbeddings
from langchain_pinecone import PineconeVectorStore
from pinecone import Pinecone, ServerlessSpec
from pinecone_text.sparse import BM25Encoder

from research_copilot.config import get_settings
from research_copilot.ingestion.chunker import ChunkedPaper
from research_copilot.logging import get_logger
from research_copilot.cache.embedding_cache import embedding_cache
from research_copilot.utils import retry_pinecone


logger = get_logger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Pinecone Index
# ─────────────────────────────────────────────────────────────────────────────

def _get_pinecone_client() -> Pinecone:
    settings = get_settings()
    return Pinecone(api_key=settings.pinecone_api_key)


def _get_pinecone_index():
    """
    Initialize Pinecone client and ensure a dotproduct index exists.

    IMPORTANT: Hybrid search requires metric='dotproduct'.
    If an existing cosine index is found under the same name,
    it is deleted and recreated automatically.
    """
    settings = get_settings()
    pc = _get_pinecone_client()

    existing = {idx.name: idx for idx in pc.list_indexes()}

    if settings.pinecone_index_name in existing:
        current_metric = existing[settings.pinecone_index_name].metric

        if current_metric != "dotproduct":
            logger.warning(
                "pinecone_index_metric_mismatch",
                current=current_metric,
                required="dotproduct",
                action="deleting_and_recreating",
            )
            pc.delete_index(settings.pinecone_index_name)
            # Fall through to creation below
        else:
            return pc.Index(settings.pinecone_index_name)

    logger.info(
        "pinecone_index_creation_started",
        index_name=settings.pinecone_index_name,
        metric="dotproduct",
    )

    pc.create_index(
        name=settings.pinecone_index_name,
        dimension=1536,          # text-embedding-3-small
        metric="dotproduct",     # required for sparse-dense hybrid
        spec=ServerlessSpec(
            cloud="aws",
            region=settings.pinecone_environment,
        ),
    )
    time.sleep(5)    # wait for index to be ready

    logger.info(
        "pinecone_index_creation_complete",
        index_name=settings.pinecone_index_name,
    )

    return pc.Index(settings.pinecone_index_name)


def get_pinecone_index():
    """
    Public accessor for the raw Pinecone index.
    Used by PineconeHybridSearchRetriever in retriever.py.
    """
    return _get_pinecone_index()


# ─────────────────────────────────────────────────────────────────────────────
# BM25 Encoder management
# ─────────────────────────────────────────────────────────────────────────────

def _get_bm25_model_path() -> Path:
    settings = get_settings()
    path = Path(settings.bm25_model_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _save_bm25_encoder(encoder: BM25Encoder):
    path = _get_bm25_model_path()
    with open(path, "wb") as f:
        pickle.dump(encoder, f)
    logger.info("bm25_encoder_saved", path=str(path))


def _load_bm25_encoder() -> BM25Encoder | None:
    path = _get_bm25_model_path()
    if not path.exists():
        return None
    with open(path, "rb") as f:
        encoder = pickle.load(f)
    logger.info("bm25_encoder_loaded", path=str(path))
    return encoder


def get_bm25_encoder(corpus_texts: list[str] | None = None) -> BM25Encoder:
    """
    Load existing BM25 encoder from disk, or fit a new one.

    Args:
        corpus_texts: If provided and no saved model exists,
                      fits a new BM25 encoder on these texts.
                      If a saved model exists, updates it with new texts.

    BM25 must be fitted on real corpus text before it can generate
    sparse vectors. We persist it so term frequencies accumulate
    across all ingested papers over time.
    """
    existing = _load_bm25_encoder()

    if existing is None:
        if not corpus_texts:
            # No corpus and no saved model — use default pretrained weights
            logger.warning(
                "bm25_no_corpus_no_model",
                action="using_default_pretrained_weights",
            )
            encoder = BM25Encoder().default()
        else:
            logger.info(
                "bm25_fitting_new_encoder",
                corpus_size=len(corpus_texts),
            )
            encoder = BM25Encoder()
            encoder.fit(corpus_texts)
        _save_bm25_encoder(encoder)
        return encoder

    # Model exists — if new texts provided, update and resave
    if corpus_texts:
        logger.info(
            "bm25_updating_existing_encoder",
            new_texts=len(corpus_texts),
        )
        # BM25Encoder doesn't support incremental fit directly,
        # so we merge by re-encoding the params
        # This is a no-op fit to update internal state
        existing.fit(corpus_texts)
        _save_bm25_encoder(existing)

    return existing


# ─────────────────────────────────────────────────────────────────────────────
# Dense embeddings (unchanged from Phase 2)
# ─────────────────────────────────────────────────────────────────────────────

class CachedOpenAIEmbeddings(Embeddings):
    """
    Wraps OpenAIEmbeddings with disk-based caching.
    Cache hits skip the OpenAI API entirely.
    """

    def __init__(self, base_embeddings: OpenAIEmbeddings):
        self._base = base_embeddings

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        results = []
        uncached_texts = []
        uncached_indices = []

        # Separate cached from uncached
        for i, text in enumerate(texts):
            cached = embedding_cache.get(text)
            if cached is not None:
                results.append((i, cached))
            else:
                uncached_texts.append(text)
                uncached_indices.append(i)

        # Batch embed only uncached texts
        if uncached_texts:
            new_embeddings = self._base.embed_documents(uncached_texts)
            for text, embedding, idx in zip(
                uncached_texts, new_embeddings, uncached_indices
            ):
                embedding_cache.set(text, embedding)
                results.append((idx, embedding))

        # Return in original order
        results.sort(key=lambda x: x[0])
        return [emb for _, emb in results]

    def embed_query(self, text: str) -> list[float]:
        cached = embedding_cache.get(text)
        if cached is not None:
            return cached
        embedding = self._base.embed_query(text)
        embedding_cache.set(text, embedding)
        return embedding


def _get_dense_embeddings() -> CachedOpenAIEmbeddings:
    settings = get_settings()
    base = OpenAIEmbeddings(
        model=settings.openai_embedding_model,
        api_key=settings.openai_api_key,
    )
    return CachedOpenAIEmbeddings(base)


def get_vectorstore() -> PineconeVectorStore:
    """
    Return a LangChain-compatible Pinecone vectorstore.
    Kept for any code that uses similarity_search directly.
    NOTE: For hybrid retrieval use PineconeHybridSearchRetriever
    in retriever.py instead.
    """
    settings = get_settings()
    _get_pinecone_index()  # ensure index exists

    return PineconeVectorStore(
        index= settings.pinecone_index_name,
        embedding= _get_dense_embeddings(),
        pinecone_api_key= settings.pinecone_api_key,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Hybrid upsert
# ─────────────────────────────────────────────────────────────────────────────

@retry_pinecone
def embed_and_store(chunked_paper: ChunkedPaper, user_context = None) -> int:
    """
    Generate dense + sparse vectors for all chunks and upsert into Pinecone.

    Flow:
    1. Fit / update BM25 encoder on this paper's chunk texts
    2. Generate sparse vectors (BM25) for all chunks
    3. Generate dense vectors (OpenAI, cached) for all chunks
    4. Upsert both vector types together into the dotproduct index

    Returns the number of chunks stored.
    """
    start_time = time.time()
    settings = get_settings()

    logger.info(
        "hybrid_upsert_started",
        filename=chunked_paper.filename,
        paper_id=chunked_paper.paper_id,
        chunks=len(chunked_paper.chunks),
    )

    chunk_texts = [doc.page_content for doc in chunked_paper.chunks]

    # ── Step 1: Fit / update BM25 on this paper's chunks ─────────────
    bm25 = get_bm25_encoder(corpus_texts=chunk_texts)

    # ── Step 2: Generate sparse vectors ──────────────────────────────
    sparse_vectors = bm25.encode_documents(chunk_texts)

    # ── Step 3: Generate dense vectors (cached) ───────────────────────
    # ── Use per-user OpenAI key if available ──────────────────────────
    if user_context and user_context.openai_api_key:
        from langchain_openai import OpenAIEmbeddings
        from research_copilot.ingestion.embeddings import CachedOpenAIEmbeddings
        base = OpenAIEmbeddings(
            model=settings.openai_embedding_model,
            api_key=user_context.openai_api_key,    # ← per-user key
        )
        dense_embeddings = CachedOpenAIEmbeddings(base)
    else:
        dense_embeddings = _get_dense_embeddings()  # ← fallback to .env
    dense_vectors = dense_embeddings.embed_documents(chunk_texts)

    # ── Step 4: Upsert both vector types into Pinecone ────────────────
    index = _get_pinecone_index()
    batch_size = 100
    total_upserted = 0

    for batch_start in range(0, len(chunked_paper.chunks), batch_size):
        batch_end = min(batch_start + batch_size, len(chunked_paper.chunks))
        batch = chunked_paper.chunks[batch_start:batch_end]

        vectors = []
        for i, (doc, dense, sparse) in enumerate(zip(
            batch,
            dense_vectors[batch_start:batch_end],
            sparse_vectors[batch_start:batch_end],
        )):
            chunk_idx = batch_start + i
            vectors.append({
                "id": f"{chunked_paper.paper_id}_{chunk_idx}",
                "values": dense,
                "sparse_values": {
                    "indices": sparse["indices"],
                    "values": sparse["values"],
                },
                "metadata": {
                    **doc.metadata,
                    "text": doc.page_content,   # stored for retrieval
                },
            })

        index.upsert(
            vectors=vectors,
            namespace=chunked_paper.paper_id,
        )
        total_upserted += len(vectors)

        logger.info(
            "hybrid_upsert_batch_complete",
            batch=f"{batch_start}-{batch_end}",
            paper_id=chunked_paper.paper_id[:8],
        )

    logger.info(
        "hybrid_upsert_complete",
        chunk_count=total_upserted,
        filename=chunked_paper.filename,
        namespace=chunked_paper.paper_id,
        duration_s=round(time.time() - start_time, 2),
    )

    return total_upserted