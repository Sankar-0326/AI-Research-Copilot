import tempfile
import shutil
from pathlib import Path

from fastapi import APIRouter, UploadFile, File, HTTPException

from research_copilot.ingestion import ingest_paper
from research_copilot.api.schemas import UploadResponse

router = APIRouter(prefix="/papers", tags=["Papers"])

ALLOWED_CONTENT_TYPES = {"application/pdf"}
MAX_FILE_SIZE_MB = 50


@router.post(
    "/upload",
    response_model=UploadResponse,
    summary="Upload and ingest a research paper PDF",
)
async def upload_paper(file: UploadFile = File(...)):
    """
    Upload a PDF research paper.

    - Validates file type and size
    - Extracts text, chunks, embeds, and stores in Pinecone
    - Returns a paper_id for use in /analyze
    """
    # ── Validation ────────────────────────────────────────────────────
    if file.content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Only PDF files are accepted. Got: {file.content_type}",
        )

    # ── Write to temp file (pdfplumber needs a real file path) ────────
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
        try:
            content = await file.read()

            # Size check
            size_mb = len(content) / (1024 * 1024)
            if size_mb > MAX_FILE_SIZE_MB:
                raise HTTPException(
                    status_code=413,
                    detail=f"File too large: {size_mb:.1f}MB. Max is {MAX_FILE_SIZE_MB}MB.",
                )

            tmp.write(content)
            tmp_path = Path(tmp.name)

        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"File read failed: {str(e)}")

    # ── Ingest ────────────────────────────────────────────────────────
    try:
        result = ingest_paper(
            file_path=tmp_path,
            filename=file.filename,
        )
        return UploadResponse(**result)

    except ValueError as e:
        # Raised by pdf_loader for unreadable PDFs
        raise HTTPException(status_code=422, detail=str(e))

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Ingestion failed: {str(e)}",
        )

    finally:
        # Always clean up the temp file
        tmp_path.unlink(missing_ok=True)