from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate

from research_copilot.agents.state import ResearchState
from research_copilot.config import get_settings
from research_copilot.rag import get_retriever
from research_copilot.logging import get_logger
from research_copilot.cache.response_cache import response_cache


logger = get_logger("gap_detection_agent")


GAP_DETECTION_PROMPT = ChatPromptTemplate.from_messages([
    (
        "system", 
        """
            You are an expert in research methodology and scientific 
            literature analysis. Your goal is to identify genuine gaps in the research 
            landscape based on a corpus of papers and the current state of the field.

            A "research gap" must be:
            - Something NOT addressed by the provided papers
            - Supported by evidence (not just speculation)
            - Actionable (a researcher could pursue it)

            Structure your output EXACTLY as:

            ## Research Gaps
            (numbered list — each gap on its own line with a brief explanation)

            ## Unanswered Questions
            (questions the papers raise but do not answer)

            ## Underexplored Populations / Domains
            (contexts where findings haven't been validated)

            ## Methodological Weaknesses
            (limitations in how the field currently studies this topic)

            ## Future Research Directions
            (concrete, specific suggestions for follow-up work — be actionable)

            Be critical and rigorous. Vague gaps like "more research is needed" are not acceptable.
            """
    ),
    (
        "human", 
        """
            Research Query: {query}

            Paper Summaries:
            {summaries}

            Cross-Paper Insights:
            {insights}

            Supporting Context (papers + web):
            {context}

            Identify research gaps and future directions now.
            """
    )
])


def gap_detection_agent(state: ResearchState) -> ResearchState:
    """
    Gap Detection Agent Node.

    - Uses summaries + insights from previous agents as context
    - Fetches additional web context to understand field state
    - Identifies gaps, unanswered questions, future directions
    """
    settings = get_settings()
    retriever = get_retriever()
    llm = ChatOpenAI(
        model=settings.openai_model,
        api_key=settings.openai_api_key,
        temperature=0.2,
    )

    chain = GAP_DETECTION_PROMPT | llm
    errors = list(state.get("errors", []))
    accumulated_docs = list(state.get("retrieved_docs", []))

    try:
        # ── Cache check ───────────────────────────────────────────────
        cached = response_cache.get(
            agent="gap_detection",
            query=state["query"],          # raw query — not the modified one
            paper_ids=state["paper_ids"],
        )
        if cached:
            logger.info("gap_detection_from_cache", paper_ids_count=len(state["paper_ids"]))
            completed = list(state.get("completed_agents", []))
            completed.append("gap_detection")
            return {
                **state,
                "research_gaps": [cached],
                "future_directions": [],
                "completed_agents": completed,
                "current_agent": "report_assembler",
            }

        # ── Retrieval ─────────────────────────────────────────────────
        # Use more web results here — gap detection benefits from knowing
        # what the broader field looks like beyond just the uploaded papers
        docs = retriever.retrieve_hybrid(
            query=f"limitations and future work: {state['query']}",
            paper_ids=state["paper_ids"] if state["paper_ids"] else None,
            top_k=5,
            web_results=5,
        )
        accumulated_docs.extend(docs)
        context = retriever.format_context(docs)

        summaries_block = "\n\n".join([
            f"### Paper {pid[:8]}...\n{summary}"
            for pid, summary in state.get("summaries", {}).items()
        ]) or "No summaries available."

        insights_block = "\n\n".join(state.get("insights", [])) or "No insights available."

        response = chain.invoke({
            "query": state["query"],
            "summaries": summaries_block,
            "insights": insights_block,
            "context": context,
        })

        # ── Cache set ─────────────────────────────────────────────────
        response_cache.set(
            agent="gap_detection",
            query=state["query"],          # consistent with cache check above
            paper_ids=state["paper_ids"],
            response=response.content,
        )

        # Split into gaps vs future directions
        full_response = response.content
        research_gaps = [full_response]   # stored as structured block
        future_directions = []            # extracted in report assembler

        logger.info("gap_detection_completed")

    except Exception as e:
        error_msg = f"Gap detection failed: {str(e)}"
        errors.append(error_msg)
        research_gaps = []
        future_directions = []
        logger.error(
            "gap_detection_failed",
            error=error_msg,
            )

    completed = list(state.get("completed_agents", []))
    completed.append("gap_detection")

    return {
        **state,
        "research_gaps": research_gaps,
        "future_directions": future_directions,
        "retrieved_docs": accumulated_docs,
        "errors": errors,
        "completed_agents": completed,
        "current_agent": "report_assembler",
    }