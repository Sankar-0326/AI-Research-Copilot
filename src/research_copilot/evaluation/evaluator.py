import time
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.documents import Document

from research_copilot.config import get_settings
from research_copilot.evaluation.metrics import EvaluationResult
from research_copilot.logging import get_logger

logger = get_logger("evaluator")

# Faithfulness check — does the answer stay grounded in context?
FAITHFULNESS_PROMPT = ChatPromptTemplate.from_messages([
    ("system", """You are an evaluation judge for RAG systems.
Score the FAITHFULNESS of an answer — meaning how well it is grounded 
in the provided context, with no hallucinated facts.

Return ONLY a JSON object: {{"score": <float 0.0-1.0>, "reason": "<one sentence>"}}
1.0 = fully grounded, 0.0 = completely hallucinated"""),
    ("human", """Context:
{context}

Answer:
{answer}

Score the faithfulness now.""")
])

# Context relevance — are the retrieved chunks actually useful?
CONTEXT_RELEVANCE_PROMPT = ChatPromptTemplate.from_messages([
    ("system", """You are an evaluation judge for RAG systems.
Score the CONTEXT RELEVANCE — how relevant the retrieved chunks are 
to answering the given query.

Return ONLY a JSON object: {{"score": <float 0.0-1.0>, "reason": "<one sentence>"}}
1.0 = perfectly relevant, 0.0 = completely irrelevant"""),
    ("human", """Query: {query}

Retrieved Context:
{context}

Score the relevance now.""")
])


class RAGEvaluator:
    """
    Lightweight LLM-as-judge evaluator for RAG pipelines.
    Uses a fast GPT-4o-mini call to score each agent output.
    """

    def __init__(self):
        settings = get_settings()
        # Use mini model for eval — cheaper, fast enough for scoring
        self._llm = ChatOpenAI(
            model="gpt-4o-mini",
            api_key=settings.openai_api_key,
            temperature=0,
        )

    def _score(self, prompt: ChatPromptTemplate, **kwargs) -> tuple[float, str]:
        """Run a scoring prompt and parse the JSON result."""
        import json
        try:
            chain = prompt | self._llm
            response = chain.invoke(kwargs)
            parsed = json.loads(response.content)
            return float(parsed["score"]), parsed.get("reason", "")
        except Exception as e:
            logger.warning("eval_score_failed", error=str(e))
            return 0.0, f"Evaluation failed: {str(e)}"

    def evaluate(
        self,
        agent: str,
        query: str,
        answer: str,
        context_docs: list[Document],
        paper_id: str | None = None,
        latency: float = 0.0,
        from_cache: bool = False,
    ) -> EvaluationResult:
        """
        Score a single agent output on faithfulness and context relevance.
        Answer relevance is approximated as the average of the two.
        """
        from research_copilot.rag.retriever import ResearchRetriever
        retriever = ResearchRetriever()
        context_str = retriever.format_context(context_docs)

        start = time.time()

        faithfulness_score, faith_reason = self._score(
            FAITHFULNESS_PROMPT,
            context=context_str,
            answer=answer,
        )

        relevance_score, rel_reason = self._score(
            CONTEXT_RELEVANCE_PROMPT,
            query=query,
            context=context_str,
        )

        # Answer relevance ≈ geometric mean of the two as a proxy
        answer_relevance = round((faithfulness_score + relevance_score) / 2, 3)
        eval_latency = time.time() - start

        result = EvaluationResult(
            agent=agent,
            query=query,
            paper_id=paper_id,
            faithfulness=faithfulness_score,
            context_relevance=relevance_score,
            answer_relevance=answer_relevance,
            context_chunks_used=len(context_docs),
            latency_seconds=latency,
            from_cache=from_cache,
        )

        logger.info(
            "eval_complete",
            agent=agent,
            overall=result.overall_score,
            faithfulness=faithfulness_score,
            context_relevance=relevance_score,
            eval_latency_ms=round(eval_latency * 1000),
        )

        return result