from langgraph.graph import StateGraph, END

from research_copilot.agents.state import ResearchState
from research_copilot.agents.summarization import summarization_agent
from research_copilot.agents.insight import insight_agent
from research_copilot.agents.gap_detection import gap_detection_agent
from research_copilot.agents.report_assembler import report_assembler


def should_run_insight(state: ResearchState) -> str:
    """
    After summarization:
    - If ALL papers failed → hard fail, go to report with failed status
    - If SOME papers succeeded → proceed with what we have
    - If ALL succeeded → normal flow
    """
    summaries = state.get("summaries", {})
    paper_ids = state.get("paper_ids", [])

    if not summaries:
        # Zero summaries produced — nothing useful to synthesize
        print("--- No summaries produced — marking pipeline as failed ---")
        return "hard_fail"

    if len(summaries) < len(paper_ids):
        # Partial success — warn but continue
        failed_count = len(paper_ids) - len(summaries)
        print(f"--- {failed_count}/{len(paper_ids)} papers failed summarization — continuing with partial results ---")

    return "run_insight"


def should_run_gap_detection(state: ResearchState) -> str:
    """
    After insight:
    - If insight produced nothing → still run gap detection
      because gap detection has its own retrieval and can work
      from summaries alone
    - Never skip gap detection unless we're already in failed state
    """
    if state.get("status") == "failed":
        return "hard_fail"
    return "run_gap_detection"


def mark_failed(state: ResearchState) -> ResearchState:
    """
    Hard failure node — pipeline couldn't produce meaningful output.
    Sets status to 'failed' and assembles an error report.
    """
    error_summary = "\n".join(f"- {e}" for e in state.get("errors", []))

    return {
        **state,
        "status": "failed",
        "final_report": (
            f"# Research Pipeline Failed\n\n"
            f"**Query:** {state['query']}\n\n"
            f"## Errors\n{error_summary or '- Unknown failure'}\n\n"
            f"## Suggestion\n"
            f"- Verify paper_ids exist in Pinecone\n"
            f"- Re-ingest papers using `/upload-paper`\n"
            f"- Check API keys in `.env`"
        ),
        "current_agent": "done",
    }


def build_research_graph() -> StateGraph:
    """
    Build and compile the LangGraph multi-agent workflow.

    Flow:
    summarization → insight → gap_detection → report_assembler → END

    With conditional shortcuts to report_assembler on failure.
    """
    graph = StateGraph(ResearchState)

    # ── Register nodes ──────────────────────────────────────────────
    graph.add_node("summarization", summarization_agent)
    graph.add_node("insight", insight_agent)
    graph.add_node("gap_detection", gap_detection_agent)
    graph.add_node("report_assembler", report_assembler)
    graph.add_node("mark_failed", mark_failed) 

    # ── Entry point ─────────────────────────────────────────────────
    graph.set_entry_point("summarization")

    # ── Conditional edges ───────────────────────────────────────────
    graph.add_conditional_edges(
        "summarization",
        should_run_insight,
        {
            "run_insight": "insight",
            "hard_fail": "mark_failed",
        }
    )

    graph.add_conditional_edges(
        "insight",
        should_run_gap_detection,
        {
            "run_gap_detection": "gap_detection",
            "hard_fail": "mark_failed",
        }
    )

    # ── Linear edges ────────────────────────────────────────────────
    graph.add_edge("gap_detection", "report_assembler")
    graph.add_edge("report_assembler", END)
    graph.add_edge("mark_failed", END)

    return graph.compile()


# Module-level compiled graph — import this everywhere
research_graph = build_research_graph()