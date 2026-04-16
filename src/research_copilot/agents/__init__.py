from research_copilot.agents.state import ResearchState, create_initial_state
from research_copilot.agents.graph import research_graph


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

    print(f"\n Starting research pipeline")
    print(f"   Query: {query}")
    print(f"   Papers: {len(paper_ids)}")
    print(f"   Mode: {retrieval_mode}\n")

    final_state = research_graph.invoke(initial_state)

    print(f"\n Pipeline complete — status: {final_state['status']}")
    print(f"   Agents run: {', '.join(final_state['completed_agents'])}")
    if final_state.get("errors"):
        print(f"   Warnings: {len(final_state['errors'])}")

    return final_state