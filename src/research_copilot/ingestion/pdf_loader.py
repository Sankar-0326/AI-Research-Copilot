import hashlib
from pathlib import Path
from dataclasses import dataclass, field

import pdfplumber
# Why pdfplumber over pypdf? Research papers often have multi-column layouts and dense formatting. 
# pdfplumber handles those significantly better for text extraction.

from research_copilot.logging import get_logger
logger = get_logger(__name__)

@dataclass
class ParsedPaper:
    """Represents a fully parsed research paper."""
    paper_id: str
    filename: str
    full_text: str
    page_count: int
    metadata: dict = field(default_factory=dict)



def _generate_paper_id(filename: str, content: bytes) -> str:
    """Deterministic ID based on filename + content hash."""
    hash_input = filename.encode() + content[:1024]
    return hashlib.sha256(hash_input).hexdigest()[:16]  # hashlib.sha256() only accepts bytes not strings


def load_pdf(file_path: str | Path, filename: str | None = None) -> ParsedPaper:
    """
    Extract text from a PDF file using pdfplumber.
    Handles multi-column layouts better than pypdf for research papers.
    """
    logger.info(
        "pdf_load_started",
        filename=filename,
        path=str(file_path),
    )
    file_path = Path(file_path)
    filename = filename or file_path.name

    raw_bytes = file_path.read_bytes()
    paper_id = _generate_paper_id(filename= filename, content= raw_bytes)

    pages_text: list[str] = []

    with pdfplumber.open(file_path) as pdf:
        page_count = len(pdf.pages)
        logger.info(
                "pdf_opened",
                filename=filename,
                paper_id=paper_id,
                page_count=page_count,
            )
        for page_number, page in enumerate(pdf.pages, start=1):
            text = page.extract_text(x_tolerance=2, y_tolerance=3)
            if text:
                pages_text.append(text.strip())
            else:
                    logger.warning(
                        "pdf_page_empty",
                        filename=filename,
                        paper_id=paper_id,
                        page_number=page_number,
                    )

    full_text = "\n\n".join(pages_text)

    if not full_text.strip():
        logger.error(
            "pdf_text_extraction_failed",
            filename=filename,
            paper_id=paper_id,
        )
        raise ValueError(
            f"Could not extract text from '{filename}'. "
            "The PDF may be scanned/image-based and requires OCR."
        )
    
    logger.info(
        "pdf_load_completed",
        filename=filename,
        paper_id=paper_id,
        page_count=page_count,
        extracted_pages=len(pages_text),
        total_characters=len(full_text),
    )

    return ParsedPaper(
        paper_id= paper_id,
        filename= filename,
        full_text= full_text,
        page_count= page_count,
        metadata={
            "source": filename,
            "page_count": page_count,
        },
    )