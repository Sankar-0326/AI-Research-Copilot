from research_copilot.agents.state import ResearchState, create_initial_state
from research_copilot.agents.graph import research_graph
from research_copilot.logging import get_logger


logger = get_logger("agents")


def run_research_pipeline(
    query: str,
    paper_ids: list[str],
    retrieval_mode: str = "hybrid",
) -> ResearchState:
    """
    Entry point for running the full multi-agent research pipeline.

    Returns the final state containing summaries, insights,
    research gaps, and the assembled report.
    """
    initial_state = create_initial_state(
        query=query,
        paper_ids=paper_ids,
        retrieval_mode=retrieval_mode,
    )

    # ── Verify user context is available via contextvars ──────────────
    from research_copilot.api.user_context import get_user_context
    user_ctx = get_user_context()

    if user_ctx:
        logger.info(
            "pipeline_user_context",
            user_id=user_ctx.user_id[:8],
            has_openai=bool(user_ctx.openai_api_key),
            has_pinecone=bool(user_ctx.pinecone_api_key),
            has_tavily=bool(user_ctx.tavily_api_key),
            # ← no key hints logged — security
        )
    else:
        logger.warning("pipeline_no_user_context")

        
    logger.info(
        "pipeline_starting",
        query=query[:60],
        papers=len(paper_ids),
        mode=retrieval_mode,
        user_id=user_ctx.user_id[:8] if user_ctx else "system",
    )

    final_state = research_graph.invoke(initial_state)

    logger.info(
        "pipeline_complete",
        status=final_state["status"],
        agents_run=final_state["completed_agents"],
        warnings=len(final_state.get("errors", [])),
    )

    return final_state