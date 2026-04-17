import uuid
from typing import Optional
from research_copilot.agents.state import ResearchState
from research_copilot.api.schemas import PipelineStatus


"""
Since analysis runs async, you need somewhere to store job state
between the POST (start job) and GET (fetch results) calls.
"""

class Job:
    """Represents a single analysis job."""
    def __init__(self, job_id: str, query: str, paper_ids: list[str]):
        self.job_id = job_id
        self.query = query
        self.paper_ids = paper_ids
        self.status: PipelineStatus = PipelineStatus.pending
        self.result: Optional[ResearchState] = None
        self.error: Optional[str] = None


class InMemoryJobStore:
    """
    Simple in-memory job store for Phase 1.
    In Phase 2 (stabilization) this gets replaced with Redis.
    """
    def __init__(self):
        self._jobs: dict[str, Job] = {}

    def create(self, query: str, paper_ids: list[str]) -> Job:
        job_id = str(uuid.uuid4())
        job = Job(job_id=job_id, query=query, paper_ids=paper_ids)
        self._jobs[job_id] = job
        return job

    def get(self, job_id: str) -> Optional[Job]:
        return self._jobs.get(job_id)

    def update_status(self, job_id: str, status: PipelineStatus):
        if job := self._jobs.get(job_id):
            job.status = status

    def update_result(self, job_id: str, result: ResearchState):
        if job := self._jobs.get(job_id):
            job.result = result
            job.status = PipelineStatus.complete

    def update_error(self, job_id: str, error: str):
        if job := self._jobs.get(job_id):
            job.error = error
            job.status = PipelineStatus.failed


# Module-level singleton
job_store = InMemoryJobStore()