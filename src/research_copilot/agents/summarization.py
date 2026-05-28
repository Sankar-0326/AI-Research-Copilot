import time
import asyncio
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.documents import Document

from research_copilot.agents.state import ResearchState
from research_copilot.config import get_settings
from research_copilot.rag import get_retriever
from research_copilot.logging import get_logger
from research_copilot.cache.semantic_cache import response_cache
from research_copilot.evaluation.evaluator import RAGEvaluator
from research_copilot.utils import retry_openai, timed


logger = get_logger("summarization_agent")

evaluator = RAGEvaluator()


SUMMARIZATION_PROMPT = ChatPromptTemplate.from_messages([
    ("system", 
        """
            You are an expert research analyst. Your task is to produce a 
            structured summary of a research paper based on retrieved excerpts.

            Your summary MUST follow this exact structure:
            ## Title & Authors
            (infer from context if visible)

            ## Problem Statement
            (what problem does this paper solve?)

            ## Key Contributions
            (bullet list of 3-5 main contributions)

            ## Methodology
            (how did they approach the problem?)

            ## Results & Findings
            (key quantitative or qualitative results)

            ## Limitations
            (what are the paper's own stated or implied limitations?)

            Be precise. If information is missing from the context, state "Not found in excerpts." 
            Do NOT hallucinate details.
        """
    ),
    ("human", 
        """
            Paper ID: {paper_id}

            Retrieved Excerpts:
            {context}

            User Query (for focus): {query}

            Generate the structured summary now.
        """
    )
]
)


@retry_openai
@timed("summarization_llm")
def _call_llm(chain, inputs: dict) -> str:
    return chain.invoke(inputs)


async def _summarize_single_paper(
    paper_id: str,
    query: str,
    chain,
    retriever,
) -> tuple[str, str | None, list[Document], str | None]:
    """
    Summarize one paper asynchronously.

    Returns:
        (paper_id, summary_or_None, docs_used, error_or_None)

    Returning docs_used lets the caller accumulate retrieved_docs
    correctly even in concurrent execution.
    """
    # ── Cache check ───────────────────────────────────────────────────
    cached = response_cache.get(
        agent= "summarization", 
        query= query, 
        paper_ids= [paper_id]
        )
    if cached:
        logger.info("summary_from_cache", paper_id=paper_id[:8])
        # No docs retrieved — return empty list for accumulation
        return paper_id, cached, [], None

    try:
        # ── Retrieval ─────────────────────────────────────────────────
        docs = retriever.retrieve_from_paper(
            query=query,
            paper_id=paper_id,
            top_k=8,
        )

        if not docs:
            return (
                paper_id,
                "Could not generate summary — no content retrieved.",
                [],
                f"No chunks found for paper_id: {paper_id}",
            )

        context = retriever.format_context(docs)

        # ── Timed LLM call (in thread pool — keeps event loop unblocked) ──
        start_time = time.time()

        response = await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: _call_llm(
                chain=chain,
                inputs={
                    "paper_id": paper_id,
                    "context": context,
                    "query": query,
                }
            )
        )

        elapsed = time.time() - start_time  # computed immediately after

        # ── Cache set ─────────────────────────────────────────────────
        response_cache.set(
            agent="summarization", 
            query=query, 
            paper_ids=[paper_id], 
            response=response.content
            )

        # ── Evaluation ────────────────────────────────────────────────
        eval_result = evaluator.evaluate(
            agent="summarization",
            query=query,
            answer=response.content,
            context_docs=docs,
            paper_id=paper_id,
            latency=elapsed,
        )
        logger.info("eval_result", **eval_result.to_dict())
        logger.info(
            "summary_complete",
            paper_id=paper_id[:8],
            chunks_used=len(docs),
            latency_s=round(elapsed, 3),
        )

        return paper_id, response.content, docs, None

    except Exception as e:
        error_msg = f"Summarization failed for {paper_id[:8]}: {str(e)}"
        logger.error("operation_failed", error=error_msg, paper_id=paper_id[:8])
        return paper_id, None, [], error_msg


def summarization_agent(state: ResearchState) -> ResearchState :
    """
    Summarization Agent Node.

    For each paper_id in state:
    - Retrieve top-k chunks from its Pinecone namespace
    - Generate a structured summary via GPT-4o
    - Store result in state['summaries'][paper_id]

    All papers run concurrently via asyncio.gather.
    """
    settings = get_settings()
    user_context = state.get("user_context")
    retriever = get_retriever(
        pinecone_api_key=user_context.pinecone_api_key if user_context and user_context.pinecone_api_key else settings.pinecone_api_key,
        tavily_api_key=user_context.tavily_api_key if user_context and user_context.tavily_api_key else settings.tavily_api_key
    )
    openai_key = (
        user_context.openai_api_key
        if user_context and user_context.openai_api_key
        else settings.openai_api_key
    )
    llm = ChatOpenAI(
        model= settings.openai_model,
        api_key= openai_key,
        temperature= 0.1,  # low temp for factual summarization
    )

    chain = SUMMARIZATION_PROMPT | llm
    
    # ── Concurrent execution ──────────────────────────────────────────
    async def run_all():
        tasks = [
            _summarize_single_paper(pid, state["query"], chain, retriever)
            for pid in state["paper_ids"]
        ]
        return await asyncio.gather(*tasks)

    results = asyncio.run(run_all())

    # ── Collect results ───────────────────────────────────────────────
    summaries = dict(state.get("summaries", {}))
    errors = list(state.get("errors", []))
    accumulated_docs = list(state.get("retrieved_docs", []))

    for paper_id, summary, docs, error in results:  # ← unpack 4 values
        if summary:
            summaries[paper_id] = summary
        if docs:
            accumulated_docs.extend(docs)           # ← preserved
        if error:
            errors.append(error)

    completed = list(state.get("completed_agents", []))
    completed.append("summarization")

    return {
        **state,
        "summaries": summaries,
        "retrieved_docs": accumulated_docs,
        "errors": errors,
        "completed_agents": completed,
        "current_agent": "insight",
    }