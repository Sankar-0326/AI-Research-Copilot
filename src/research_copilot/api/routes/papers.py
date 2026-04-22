import tempfile
from pathlib import Path

from fastapi import APIRouter, UploadFile, File, HTTPException, Depends

from research_copilot.ingestion import ingest_paper
from research_copilot.api.schemas import UploadResponse
from research_copilot.api.user_context import UserContext
from research_copilot.auth.dependencies import get_current_user, require_api_keys
from research_copilot.db.models.user import User
from research_copilot.logging import get_logger

logger = get_logger("routes.papers")
router = APIRouter(prefix="/papers", tags=["Papers"])

ALLOWED_CONTENT_TYPES = {"application/pdf"}
MAX_FILE_SIZE_MB = 50


@router.post(
    "/upload",
    response_model=UploadResponse,
    summary="Upload and ingest a research paper PDF",
)
async def upload_paper(
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),     # ← auth required
    keys: dict = Depends(require_api_keys),     # ← keys required
):
    """
    Upload a PDF research paper.

    - Validates file type and size
    - Extracts text, chunks, embeds using the user's own API keys
    - Stores in Pinecone under the user's namespace
    - Returns a paper_id for use in /analyze
    """
    # ── Validation ────────────────────────────────────────────────────
    if file.content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Only PDF files are accepted. Got: {file.content_type}",
        )

    # ── Build user context from decrypted keys ────────────────────────
    user_context = UserContext.from_api_keys(
        user_id=str(user.id),
        keys=keys,
    )

    # ── Write to temp file (pdfplumber needs a real file path) ────────
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
        try:
            content = await file.read()

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
            user_context=user_context,          # ← per-user keys injected
        )

        logger.info(
            "paper_ingested",
            user_id=str(user.id)[:8],
            paper_id=result["paper_id"],
            chunks=result["chunks_stored"],
        )

        return UploadResponse(**result)

    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Ingestion failed: {str(e)}",
        )

    finally:
        tmp_path.unlink(missing_ok=True)