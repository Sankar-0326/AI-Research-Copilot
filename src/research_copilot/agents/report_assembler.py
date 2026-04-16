from research_copilot.agents.state import ResearchState


def report_assembler(state: ResearchState) -> ResearchState:
    """
    Final node — assembles all agent outputs into a clean report.
    No LLM call needed here, pure formatting logic.
    """
    sections = []

    # Header
    sections.append("# AI Research Copilot — Analysis Report")
    sections.append(f"**Query:** {state['query']}\n")
    sections.append(f"**Papers Analyzed:** {len(state['paper_ids'])}")
    sections.append(f"**Agents Run:** {', '.join(state['completed_agents'])}\n")
    sections.append("---")

    # Summaries
    if state.get("summaries"):
        sections.append("## Paper Summaries\n")
        for paper_id, summary in state["summaries"].items():
            sections.append(f"### Paper `{paper_id[:8]}...`\n{summary}\n")

    # Insights
    if state.get("insights"):
        sections.append("## Cross-Paper Insights\n")
        for insight_block in state["insights"]:
            sections.append(insight_block)

    # Gaps
    if state.get("research_gaps"):
        sections.append("\n## Research Gaps & Future Directions\n")
        for gap_block in state["research_gaps"]:
            sections.append(gap_block)

    # Errors (if any)
    if state.get("errors"):
        sections.append("\n## Warnings\n")
        for err in state["errors"]:
            sections.append(f"- {err}")

    final_report = "\n\n".join(sections)

    return {
        **state,
        "final_report": final_report,
        "status": "complete",
        "current_agent": "done",
    }