from langgraph.graph import StateGraph, END

from research_copilot.agents.state import ResearchState
from research_copilot.agents.planner import planner_agent 
from research_copilot.agents.summarization import summarization_agent
from research_copilot.agents.insight import insight_agent
from research_copilot.agents.gap_detection import gap_detection_agent
from research_copilot.agents.report_assembler import report_assembler
from research_copilot.logging import get_logger


logger = get_logger(__name__)


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
        logger.error(
            "summarization_failed_all",
            paper_count=len(paper_ids),
        )
        return "hard_fail"

    if len(summaries) < len(paper_ids):
        # Partial success — warn but continue
        failed_count = len(paper_ids) - len(summaries)
        logger.warning(
            "summarization_partial_success",
            total_papers=len(paper_ids),
            successful=len(summaries),
            failed=failed_count,
        )

    logger.info(
        "summarization_sufficient_for_insight",
        summaries=len(summaries),
    )

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
        logger.error(
            "insight_stage_failed",
            reason="upstream_failure",
        )
        return "hard_fail"
    
    logger.info("proceed_to_gap_detection")

    return "run_gap_detection"


def mark_failed(state: ResearchState) -> ResearchState:
    """
    Hard failure node — pipeline couldn't produce meaningful output.
    Sets status to 'failed' and assembles an error report.
    """
    error_summary = "\n".join(f"- {e}" for e in state.get("errors", []))
    errors = state.get("errors", [])

    logger.error(
        "pipeline_failed",
        error_count=len(errors),
        query=state.get("query"),
    )

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
    graph.add_node("planner", planner_agent)
    graph.add_node("summarization", summarization_agent)
    graph.add_node("insight", insight_agent)
    graph.add_node("gap_detection", gap_detection_agent)
    graph.add_node("report_assembler", report_assembler)
    graph.add_node("mark_failed", mark_failed) 

    # ── Entry point — planner runs first now ─────────────────────────
    graph.set_entry_point("planner")                        

    # ── Planner always continues to summarization ─────────────────────
    graph.add_edge("planner", "summarization")              

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

    logger.info("research_graph_compiled")

    return graph.compile()


# Module-level compiled graph — import this everywhere
research_graph = build_research_graph()