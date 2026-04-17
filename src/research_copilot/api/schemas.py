from pydantic import BaseModel, Field
from typing import Optional 
from enum import Enum


class RetrievalMode(str, Enum):
    single = "single"
    cross = "cross"
    hybrid = "hybrid"


class PipelineStatus(str, Enum):
    pending = "pending"
    running = "running"
    complete = "complete"
    failed = "failed"


# ── Upload ────────────────────────────────────────────────────────────

class UploadResponse(BaseModel):
    paper_id: str
    filename: str
    page_count: int
    chunks_stored: int
    status: str


# ── Analysis ─────────────────────────────────────────────────────────

class AnalyzeRequest(BaseModel):
    query: str = Field(
        ...,
        min_length=10,
        description="Research question or analysis task",
        examples=["What are the key contributions and limitations of these papers?"]
    )
    paper_ids: list[str] = Field(
        ...,
        min_length=1,
        description="List of paper IDs returned from /upload-paper"
    )
    retrieval_mode: RetrievalMode = Field(
        default=RetrievalMode.hybrid,
        description="Retrieval strategy: single | cross | hybrid"
    )


class AnalyzeResponse(BaseModel):
    job_id: str
    status: PipelineStatus
    message: str


# ── Results ───────────────────────────────────────────────────────────

class SummaryResponse(BaseModel):
    paper_id: str
    summary: str
    status: PipelineStatus


class InsightsResponse(BaseModel):
    job_id: str
    insights: list[str]
    status: PipelineStatus


class ResearchGapsResponse(BaseModel):
    job_id: str
    research_gaps: list[str]
    future_directions: list[str]
    status: PipelineStatus


class FullReportResponse(BaseModel):
    job_id: str
    query: str
    paper_ids: list[str]
    summaries: dict[str, str]
    insights: list[str]
    research_gaps: list[str]
    future_directions: list[str]
    final_report: str
    completed_agents: list[str]
    errors: list[str]
    status: PipelineStatus


# ── Error ─────────────────────────────────────────────────────────────

class ErrorResponse(BaseModel):
    detail: str
    code: Optional[str] = None