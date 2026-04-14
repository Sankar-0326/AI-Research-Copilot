from pathlib import Path

from research_copilot.ingestion.pdf_loader import load_pdf, ParsedPaper
from research_copilot.ingestion.chunker import chunk_paper, ChunkedPaper
from research_copilot.ingestion.embeddings import embed_and_store


def ingest_paper(file_path: str | Path, filename: str | None = None) -> dict:
    """
    Full ingestion pipeline:
    PDF → parse → chunk → embed → store in Pinecone.

    Returns a summary dict for API response.
    """
    # Stage 1: Parse
    parsed = load_pdf(file_path= file_path, filename= filename)
    print(f"--- Parsed '{parsed.filename}' — {parsed.page_count} pages ---")

    # Stage 2: Chunk
    chunked = chunk_paper(parsed_paper= parsed)
    print(f"--- Created {len(chunked.chunks)} chunks ---")

    # Stage 3: Embed + Store
    stored_count = embed_and_store(chunked)

    return {
        "paper_id": parsed.paper_id,
        "filename": parsed.filename,
        "page_count": parsed.page_count,
        "chunks_stored": stored_count,
        "status": "ingested",
    }
