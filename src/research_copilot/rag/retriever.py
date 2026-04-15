from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_pinecone import PineconeVectorStore
from langchain_core.documents import Document
from langchain_tavily import TavilySearch

from research_copilot.config import get_settings
from research_copilot.ingestion.embeddings import get_vectorstore


class ResearchRetriever:
    """
    Unified retriever supporting:
    - Single-paper scoped retrieval (namespace-specific)
    - Cross-paper retrieval (all namespaces)
    - Hybrid retrieval (vector + Tavily web search)
    """

    def __init__(self):
        self.settings = get_settings()
        self.vectorstore = get_vectorstore()
        self._tavily = None  # lazy init

    # ------------------------------------------------------------------
    # Core retrieval methods
    # ------------------------------------------------------------------

    def retrieve_from_paper(
            self,
            query: str,
            paper_id: str,
            top_k: int | None = None,
    ) -> list[Document]:
        """Retrieve chunks scoped to a single paper via its Pinecone namespace."""
        k = top_k or self.settings.retrieval_top_k

        results = self.vectorstore.similarity_search(
            query= query,
            k= k,
            namespace= paper_id
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
        """
        k = top_k or self.settings.retrieval_top_k

        results = self.vectorstore.similarity_search(
            query=query,
            k=k,
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
                tavily_api_key= self.settings.tavily_api_key,
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
        Combine vector retrieval + Tavily web search.
        Deduplicates by source URL / content hash.
        Returns vector results first, web results appended.
        """
        # Vector side
        if paper_ids:
            vector_docs = []
            for pid in paper_ids :
                vector_docs.extend(
                    self.retrieve_from_paper(query, pid, top_k= top_k)
                )
        else:
            vector_docs = self.retrieve_cross_paper(query, top_k= top_k)

        # Web Side
        web_docs = self.retrieve_from_web(query, max_results= web_results)

        # Tag vector docs with retrieval type
        for doc in vector_docs:
            doc.metadata["retrieval_type"] = "vector"

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