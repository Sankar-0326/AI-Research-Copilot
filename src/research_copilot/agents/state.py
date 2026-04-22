from typing import Annotated, Any, TypedDict
from langchain_core.documents import Document
from langgraph.graph.message import add_messages


class ResearchState(TypedDict):
    """
    Shared state object passed between all agents in the LangGraph graph.

    Design principles:
    - All fields are optional with sensible defaults
    - Agents only write to their own output fields
    - `messages` uses LangGraph's add_messages reducer (append-only)
    - `retrieved_docs` accumulates across agents
    """

    # ── Input ─────────────────────────────────────────────────────────
    query: str                          # User's original question / task
    paper_ids: list[str]               # Papers to operate on (empty = all)

    # ── LangGraph message thread (append-only via reducer) ────────────
    messages: Annotated[list[Any], add_messages]

    # ── Retrieval ─────────────────────────────────────────────────────
    retrieved_docs: list[Document]      # Accumulated retrieved chunks
    retrieval_mode: str                 # "single" | "cross" | "hybrid"

    # ── Agent Outputs ─────────────────────────────────────────────────
    summaries: dict[str, str]           # paper_id → summary text
    insights: list[str]                 # Cross-paper insight bullets
    research_gaps: list[str]            # Identified gaps in literature
    future_directions: list[str]        # Suggested next research steps

    # ── Control Flow ──────────────────────────────────────────────────
    current_agent: str                  # Which agent is running now
    errors: list[str]                   # Non-fatal errors (accumulated)
    completed_agents: list[str]         # Which agents have finished

    # ── Final Output ──────────────────────────────────────────────────
    final_report: str                   # Assembled final report
    status: str                         # "running" | "complete" | "failed"

    # ── MCP Layer ─────────────────────────────────────────────────────
    mcp_context: str                    # enriched context from MCP tools

    # ── User context ───────────────────────────────────────────────────
user_context: Any     # UserContext — carries per-user API keys

def create_initial_state(
    query: str,
    paper_ids: list[str],
    retrieval_mode: str = "cross",
    user_context = None,          
) -> ResearchState:
    """
    Create a fully initialized ResearchState with safe defaults.
    Always use this instead of constructing the dict manually.
    """
    return ResearchState(
        query=query,
        paper_ids=paper_ids,
        messages=[],
        retrieved_docs=[],
        retrieval_mode=retrieval_mode,
        summaries={},
        insights=[],
        research_gaps=[],
        future_directions=[],
        current_agent="",
        errors=[],
        completed_agents=[],
        final_report="",
        status="running",
        user_context=user_context,
        mcp_context="",
    )