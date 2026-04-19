from dataclasses import dataclass
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.documents import Document

from research_copilot.config import get_settings
from research_copilot.ingestion.pdf_loader import ParsedPaper
from research_copilot.logging import get_logger


logger = get_logger(__name__)


@dataclass
class ChunkedPaper:
    paper_id: str
    filename: str
    chunks: list[Document]


def chunk_paper(parsed_paper: ParsedPaper) -> ChunkedPaper:
    """
    Split a parsed paper into overlapping chunks for vector embedding.
    Uses recursive character splitting — respects paragraph/sentence boundaries.
    """
    settings = get_settings()

    logger.info(
        "chunking_started",
        paper_id=parsed_paper.paper_id,
        filename=parsed_paper.filename,
        chunk_size=settings.chunk_size,
        chunk_overlap=settings.chunk_overlap,
        input_characters=len(parsed_paper.full_text),
    )

    splitter = RecursiveCharacterTextSplitter(
        chunk_size = settings.chunk_size,
        chunk_overlap = settings.chunk_overlap,
        separators= ["\n\n", "\n", ". ", " ", ""],
        length_function= len,
    )

    raw_chunks = splitter.split_text(parsed_paper.full_text)

    documents = [
        Document(
            page_content= chunk,
            metadata = {
                **parsed_paper.metadata,    # Each chunk gets a paper_id and chunk_index in its metadata
                "paper_id": parsed_paper.paper_id,
                "chunk_index": i,
                "total_chunks": len(raw_chunks),
            },
        )
        for i, chunk in enumerate(raw_chunks)
    ]

    logger.info(
        "chunking_completed",
        paper_id=parsed_paper.paper_id,
        filename=parsed_paper.filename,
        total_chunks=len(raw_chunks),
    )

    return ChunkedPaper(
        paper_id= parsed_paper.paper_id,
        filename= parsed_paper.filename,
        chunks= documents,
    )