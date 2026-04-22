from pathlib import Path

from research_copilot.ingestion.pdf_loader import load_pdf, ParsedPaper
from research_copilot.ingestion.chunker import chunk_paper, ChunkedPaper
from research_copilot.ingestion.embeddings import embed_and_store
from research_copilot.logging import get_logger


logger = get_logger("ingestion")


def ingest_paper(
        file_path: str | Path, 
        filename: str | None = None,
        user_context = None,
    ) -> dict:
    """
    Full ingestion pipeline:
    PDF → parse → chunk → embed → store in Pinecone.

    Returns a summary dict for API response.
    """
    # Stage 1: Parse
    parsed = load_pdf(file_path= file_path, filename= filename)
    logger.info(
        "pdf_parsed",
        filename=parsed.filename,
        pages=parsed.page_count,
    )

    # Stage 2: Chunk
    chunked = chunk_paper(parsed_paper= parsed)
    logger.info("chunks_created", count=len(chunked.chunks))

    # Stage 3: Embed + Store
    stored_count = embed_and_store(chunked, user_context=user_context)

    return {
        "paper_id": parsed.paper_id,
        "filename": parsed.filename,
        "page_count": parsed.page_count,
        "chunks_stored": stored_count,
        "status": "ingested",
    }
