from research_copilot.rag.retriever import ResearchRetriever

# Module-level singleton — shared across all agents
_retriever: ResearchRetriever | None = None


def get_retriever(
        pinecone_api_key: str | None = None,
        tavily_api_key: str | None = None,
        openai_api_key: str | None = None,  
        ) -> ResearchRetriever:
    """
    Return retriever instance.
    If a per-user key is provided, always build a fresh instance.
    If using global .env key, return the cached singleton.
    """
    global _retriever

    if pinecone_api_key or tavily_api_key or openai_api_key:
        return ResearchRetriever(
            pinecone_api_key=pinecone_api_key,
            tavily_api_key=tavily_api_key,
            openai_api_key=openai_api_key,   
        )
    
    if _retriever is None:
        _retriever = ResearchRetriever()

    return _retriever


# Using a singleton here is intentional — ResearchRetriever.__init__ calls get_vectorstore() which connects to Pinecone. 
# You don't want that happening on every agent call.