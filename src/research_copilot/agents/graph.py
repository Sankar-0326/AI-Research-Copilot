from langgraph.graph import StateGraph, END

from research_copilot.agents.state import ResearchState
from research_copilot.agents.summarization import summarization_agent
from research_copilot.agents.insight import insight_agent
from research_copilot.agents.gap_detection import gap_detection_agent
from research_copilot.agents.report_assembler import report_assembler


def should_run_insight(state: ResearchState) -> str:
    """
    Conditional edge after summarization.
    Skip insight if summarization produced no results.
    """
    if not state.get("summaries"):
        return "skip_to_report"
    return "run_insight"


def should_run_gap_detection(state: ResearchState) -> str:
    """
    Conditional edge after insight.
    Skip gap detection if insight agent failed.
    """
    if not state.get("insights"):
        return "skip_to_report"
    return "run_gap_detection"


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

    # ── Entry point ─────────────────────────────────────────────────
    graph.set_entry_point("summarization")

    # ── Conditional edges ───────────────────────────────────────────
    graph.add_conditional_edges(
        "summarization",
        should_run_insight,
        {
            "run_insight": "insight",
            "skip_to_report": "report_assembler",
        }
    )

    graph.add_conditional_edges(
        "insight",
        should_run_gap_detection,
        {
            "run_gap_detection": "gap_detection",
            "skip_to_report": "report_assembler",
        }
    )

    # ── Linear edges ────────────────────────────────────────────────
    graph.add_edge("gap_detection", "report_assembler")
    graph.add_edge("report_assembler", END)

    return graph.compile()


# Module-level compiled graph — import this everywhere
research_graph = build_research_graph()