from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_pinecone import PineconeVectorStore
from langchain_core.documents import Document
from langchain_tavily import TavilySearch
from langchain_community.retrievers import PineconeHybridSearchRetriever

from research_copilot.config import get_settings
from research_copilot.logging import get_logger


logger = get_logger(__name__)


class ResearchRetriever:
    """
   Unified retriever supporting:
    - Single-paper scoped retrieval (namespace-specific, hybrid BM25 + dense)
    - Cross-paper retrieval (all namespaces, hybrid BM25 + dense)
    - Web retrieval (Tavily)
    - Combined hybrid retrieval (vector + web)
    """

    def __init__(self, pinecone_api_key: str | None = None, tavily_api_key: str | None = None,):
        self.settings = get_settings()
        self._tavily = None     # lazy init
        self._retriever = None  # lazy init — built on first retrieval call
        self._pinecone_key = pinecone_api_key
        self._tavily_key = tavily_api_key

    def _get_hybrid_retriever(self) -> PineconeHybridSearchRetriever:
        """
        Lazily build the PineconeHybridSearchRetriever.
        Called on first retrieval — not in __init__ — so startup
        doesn't pay the Pinecone + BM25 init cost if retriever
        is never used in that process.
        Build retriever using provided key or fall back to global settings.
        """
        if self._retriever is not None and not self._pinecone_key:
            return self._retriever

        from research_copilot.ingestion.embeddings import (
            get_pinecone_index,
            _get_pinecone_index_with_key,
            get_bm25_encoder,
            _get_dense_embeddings,
        )

        settings = get_settings()
        index = (
            _get_pinecone_index_with_key(self._pinecone_key)
            if self._pinecone_key
            else get_pinecone_index()
        )
        bm25 = get_bm25_encoder()
        embeddings = _get_dense_embeddings()

        retriever = PineconeHybridSearchRetriever(
            index=index,
            sparse_encoder=bm25,
            embeddings=embeddings,
            alpha=settings.hybrid_alpha,
        )

        logger.info(
            "hybrid_retriever_initialized",
            alpha=settings.hybrid_alpha,
            key_source="user" if self._pinecone_key else "env",
        )

        if not self._pinecone_key:
            self._retriever = retriever

        return retriever

    # ------------------------------------------------------------------
    # Core retrieval methods
    # ------------------------------------------------------------------

    def retrieve_from_paper(
        self,
        query: str,
        paper_id: str,
        top_k: int | None = None,
    ) -> list[Document]:
        """
        Retrieve chunks scoped to a single paper via its Pinecone namespace.
        Uses hybrid BM25 + dense retrieval.
        """
        k = top_k if top_k else self.settings.retrieval_top_k
        retriever = self._get_hybrid_retriever()

        # ── Set per-call params as attributes — not as invoke() kwargs ────
        retriever.top_k = k
        retriever.namespace = paper_id

        # PineconeHybridSearchRetriever accepts namespace at call time
        results = retriever.invoke(query)

        logger.info(
            "retrieve_from_paper",
            paper_id=paper_id[:8],
            query=query[:60],
            results=len(results),
        )

        return results
    
    def retrieve_cross_paper(
        self,
        query: str,
        top_k: int | None = None,
    ) -> list[Document]:
        """
        Retrieve across ALL papers (no namespace filter).
        Used by Insight Agent and Gap Detection Agent.
        Uses hybrid BM25 + dense retrieval.
        """
        k = top_k if top_k else self.settings.retrieval_top_k
        retriever = self._get_hybrid_retriever()

        # ── Clear namespace for cross-paper search ────────────────────────
        retriever.top_k = k
        retriever.namespace = ""    # empty string = no namespace filter

        # No namespace = search across all papers
        results = retriever.invoke(query)

        logger.info(
            "retrieve_cross_paper",
            query=query[:60],
            results=len(results),
        )

        return results

    def retrieve_from_web(
            self, 
            query: str, 
            max_results: int = 5
            ) -> list[Document]:
        """
        Fetch recent web results via Tavily.
        Wraps results as LangChain Documents for uniform handling.
        """
        if self._tavily is None:
            self._tavily = TavilySearch(
                tavily_api_key= self._tavily_key,
                max_results= max_results,
                )
            
        raw_results = self._tavily.invoke(query)

        # Normalize Tavily results into LangChain Documents
        documents = []
        for item in raw_results.get("results", []):
            documents.append(
                Document(
                    page_content=item.get("content", ""),
                    metadata={
                        "source": item.get("url", "web"),
                        "title": item.get("title", ""),
                        "score": item.get("score", 0.0),
                        "retrieval_type": "web",
                    },
                )
            )
        return documents
    
    def retrieve_hybrid(
            self,
            query: str,
            paper_ids: list[str] | None = None,
            top_k: int | None = None,
            web_results: int = 3,
    ) -> list[Document]:
        """
        Combine Pinecone hybrid retrieval (BM25 + dense) + Tavily web search.
        Returns vector results first, web results appended.
        Returns vector results first, web results appended.
        """
        # ── Vector side (now hybrid BM25 + dense) ────────────────────
        k = top_k if top_k else self.settings.retrieval_top_k
        if paper_ids:
            vector_docs = []
            for pid in paper_ids :
                vector_docs.extend(
                    self.retrieve_from_paper(query, pid, top_k= k)
                )
        else:
            vector_docs = self.retrieve_cross_paper(query, top_k= k)

        # ── Web side ──────────────────────────────────────────────────
        web_docs = self.retrieve_from_web(query, max_results= web_results)

        # Tag vector docs with retrieval type
        for doc in vector_docs:
            doc.metadata["retrieval_type"] = "vector"

        logger.info(
            "retrieve_hybrid_complete",
            vector_docs=len(vector_docs),
            web_docs=len(web_docs),
            query=query[:60],
        )

        return vector_docs + web_docs
    
    # ------------------------------------------------------------------
    # Utility
    # ------------------------------------------------------------------

    def format_context(self, documents: list[Document]) -> str:
        """
        Format retrieved documents into a clean string context block
        for injection into LLM prompts.
        """
        if not documents:
            return "No relevant context found."
        
        sections = []
        for i, doc in enumerate(documents, 1):
            source = doc.metadata.get("source", "unknown")
            r_type = doc.metadata.get("retrieval_type", "vector")
            paper_id = doc.metadata.get("paper_id", "")

            header = f"[{i}] Source: {source}"
            if paper_id:
                header += f" | Paper ID: {paper_id[:8]}..."
            header += f" | Type: {r_type}"

            sections.append(f"{header}\n{doc.page_content}")

        return "\n\n---\n\n".join(sections)