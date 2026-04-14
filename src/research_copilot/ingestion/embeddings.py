import asyncio
from langchain_openai import OpenAIEmbeddings
from langchain_pinecone import PineconeVectorStore
from pinecone import Pinecone, ServerlessSpec

from research_copilot.config import get_settings
from research_copilot.ingestion.chunker import ChunkedPaper


def _get_pinecone_index():
    """Initialize Pinecone client and ensure the index exists."""
    settings = get_settings()
    pc = Pinecone(api_key= settings.pinecone_api_key)

    existing_indexes = [idx.name for idx in pc.list_indexes()]

    if settings.pinecone_index_name not in existing_indexes:
        print(f"Creating Pinecone index '{settings.pinecone_index_name}'...")
        pc.create_index(
            name= settings.pinecone_index_name,
            dimension=1536,  # text-embedding-3-small dimension
            metric="cosine",
            spec=ServerlessSpec(
                cloud="aws",
                region=settings.pinecone_environment,
            ),
        )
        # Wait for index to be ready
        import time
        time.sleep(5)

    return pc.Index(settings.pinecone_index_name)


def get_vectorstore() -> PineconeVectorStore:
    """Return a LangChain-compatible Pinecone vectorstore."""
    settings = get_settings()
    _get_pinecone_index()  # ensure index exists

    embeddings = OpenAIEmbeddings(
        model= "text-embedding-3-small",
        api_key= settings.openai_api_key,
    )

    return PineconeVectorStore(
        index= settings.pinecone_index_name,
        embedding= embeddings,
        pinecone_api_key= settings.pinecone_api_key,
    )


def embed_and_store(chunked_paper: ChunkedPaper) -> int:
    """
    Embed all chunks and upsert into Pinecone.
    Returns the number of chunks stored.
    """
    vectorstore = get_vectorstore()

    # Use paper_id as the namespace to isolate papers from each other
    vectorstore.add_documents(
        documents=chunked_paper.chunks,
        namespace=chunked_paper.paper_id,
    )

    print(
        f"--- Stored {len(chunked_paper.chunks)} chunks ---"
        f"for paper '{chunked_paper.filename}' "
        f"(namespace: {chunked_paper.paper_id})"
    )

    return len(chunked_paper.chunks)