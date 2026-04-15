from research_copilot.rag.retriever import ResearchRetriever

# Module-level singleton — shared across all agents
_retriever: ResearchRetriever | None = None


def get_retriever() -> ResearchRetriever:
    """Return the shared retriever instance (lazy init)."""
    global _retriever
    if _retriever is None:
        _retriever = ResearchRetriever()
    return _retriever


# Using a singleton here is intentional — ResearchRetriever.__init__ calls get_vectorstore() which connects to Pinecone. 
# You don't want that happening on every agent call.