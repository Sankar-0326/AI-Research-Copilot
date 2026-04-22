import asyncio
from fastapi import APIRouter, HTTPException, BackgroundTasks, Depends

from research_copilot.agents import run_research_pipeline
from research_copilot.api.schemas import (
    AnalyzeRequest,
    AnalyzeResponse,
    FullReportResponse,
    SummaryResponse,
    InsightsResponse,
    ResearchGapsResponse,
    PipelineStatus,
)
from research_copilot.api.job_store import job_store
from research_copilot.api.user_context import UserContext
from research_copilot.auth.dependencies import get_current_user, require_api_keys
from research_copilot.db.models.user import User
from research_copilot.logging import get_logger

logger = get_logger("routes.analysis")
router = APIRouter(prefix="/analysis", tags=["Analysis"])


# ── Background task ───────────────────────────────────────────────────

def _run_pipeline_task(
    job_id: str,
    request: AnalyzeRequest,
    user_context: UserContext,          # ← per-user keys injected here
):
    """
    Runs in a background thread via FastAPI's BackgroundTasks.
    Updates job store on completion or failure.
    """
    job_store.update_status(job_id, PipelineStatus.running)
    try:
        final_state = run_research_pipeline(
            query=request.query,
            paper_ids=request.paper_ids,
            retrieval_mode=request.retrieval_mode.value,
            user_context=user_context,  # ← passed into pipeline
        )

        if final_state.get("status") == "failed":
            job_store.update_error(
                job_id,
                error="\n".join(final_state.get("errors", ["Unknown failure"])),
            )
        else:
            job_store.update_result(job_id, final_state)

    except Exception as e:
        logger.error("pipeline_task_failed", job_id=job_id, error=str(e))
        job_store.update_error(job_id, error=str(e))


# ── Endpoints ─────────────────────────────────────────────────────────

@router.post(
    "/analyze",
    response_model=AnalyzeResponse,
    status_code=202,
    summary="Trigger multi-agent analysis on uploaded papers",
)
async def analyze(
    request: AnalyzeRequest,
    background_tasks: BackgroundTasks,
    user: User = Depends(get_current_user),         # ← auth required
    keys: dict = Depends(require_api_keys),         # ← keys required
):
    """
    Start an async analysis job using the authenticated user's API keys.
    Returns a job_id immediately.
    Poll GET /analysis/report/{job_id} for results.
    """
    # Build UserContext from decrypted keys
    user_context = UserContext.from_api_keys(
        user_id=str(user.id),
        keys=keys,
    )

    job = job_store.create(
        query=request.query,
        paper_ids=request.paper_ids,
    )

    background_tasks.add_task(
        _run_pipeline_task,
        job.job_id,
        request,
        user_context,                               # ← passed to background task
    )

    logger.info(
        "analysis_job_created",
        job_id=job.job_id,
        user_id=str(user.id)[:8],
        papers=len(request.paper_ids),
    )

    return AnalyzeResponse(
        job_id=job.job_id,
        status=PipelineStatus.pending,
        message=f"Analysis started. Poll /analysis/report/{job.job_id} for results.",
    )


@router.get(
    "/report/{job_id}",
    response_model=FullReportResponse,
    summary="Get full analysis report for a job",
)
async def get_report(
    job_id: str,
    user: User = Depends(get_current_user),         # ← auth required
):
    job = job_store.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found.")

    if job.status in (PipelineStatus.pending, PipelineStatus.running):
        raise HTTPException(
            status_code=202,
            detail=f"Job is still {job.status.value}. Try again shortly.",
        )

    if job.status == PipelineStatus.failed:
        raise HTTPException(
            status_code=500,
            detail=f"Pipeline failed: {job.error}",
        )

    state = job.result
    return FullReportResponse(
        job_id=job_id,
        query=state["query"],
        paper_ids=state["paper_ids"],
        summaries=state.get("summaries", {}),
        insights=state.get("insights", []),
        research_gaps=state.get("research_gaps", []),
        future_directions=state.get("future_directions", []),
        final_report=state.get("final_report", ""),
        completed_agents=state.get("completed_agents", []),
        errors=state.get("errors", []),
        status=PipelineStatus(state.get("status", "complete")),
    )


@router.get(
    "/summary/{paper_id}",
    response_model=SummaryResponse,
    summary="Get summary for a specific paper from a job",
)
async def get_summary(
    paper_id: str,
    job_id: str,
    user: User = Depends(get_current_user),         # ← auth required
):
    job = job_store.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found.")

    if job.status != PipelineStatus.complete:
        raise HTTPException(
            status_code=400,
            detail=f"Job not complete yet. Current status: {job.status.value}",
        )

    summary = job.result.get("summaries", {}).get(paper_id)
    if not summary:
        raise HTTPException(
            status_code=404,
            detail=f"No summary found for paper_id '{paper_id}' in job '{job_id}'",
        )

    return SummaryResponse(
        paper_id=paper_id,
        summary=summary,
        status=PipelineStatus.complete,
    )


@router.get(
    "/insights/{job_id}",
    response_model=InsightsResponse,
    summary="Get cross-paper insights from a completed job",
)
async def get_insights(
    job_id: str,
    user: User = Depends(get_current_user),         # ← auth required
):
    job = job_store.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found.")
    if job.status != PipelineStatus.complete:
        raise HTTPException(status_code=400, detail=f"Job status: {job.status.value}")

    return InsightsResponse(
        job_id=job_id,
        insights=job.result.get("insights", []),
        status=PipelineStatus.complete,
    )


@router.get(
    "/gaps/{job_id}",
    response_model=ResearchGapsResponse,
    summary="Get research gaps and future directions from a completed job",
)
async def get_gaps(
    job_id: str,
    user: User = Depends(get_current_user),         # ← auth required
):
    job = job_store.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found.")
    if job.status != PipelineStatus.complete:
        raise HTTPException(status_code=400, detail=f"Job status: {job.status.value}")

    return ResearchGapsResponse(
        job_id=job_id,
        research_gaps=job.result.get("research_gaps", []),
        future_directions=job.result.get("future_directions", []),
        status=PipelineStatus.complete,
    )