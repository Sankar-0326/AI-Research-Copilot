from dataclasses import dataclass, field


@dataclass
class EvaluationResult:
    """
    Scores for a single agent output.
    All scores are 0.0 → 1.0.
    """
    agent: str
    query: str
    paper_id: str | None

    # Core RAG metrics
    faithfulness: float = 0.0        # Is the output grounded in retrieved context?
    context_relevance: float = 0.0   # Are retrieved chunks relevant to the query?
    answer_relevance: float = 0.0    # Does the output actually answer the query?

    # Metadata
    context_chunks_used: int = 0
    latency_seconds: float = 0.0
    from_cache: bool = False
    warnings: list[str] = field(default_factory=list)

    @property
    def overall_score(self) -> float:
        """Weighted average of the three core metrics."""
        return round(
            (self.faithfulness * 0.4)
            + (self.context_relevance * 0.35)
            + (self.answer_relevance * 0.25),
            3,
        )

    def to_dict(self) -> dict:
        return {
            "agent": self.agent,
            "query": self.query[:60],
            "paper_id": self.paper_id,
            "faithfulness": self.faithfulness,
            "context_relevance": self.context_relevance,
            "answer_relevance": self.answer_relevance,
            "overall_score": self.overall_score,
            "chunks_used": self.context_chunks_used,
            "latency_s": round(self.latency_seconds, 2),
            "from_cache": self.from_cache,
        }