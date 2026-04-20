from fastmcp import FastMCP
from research_copilot.mcp.tools.arxiv_search import search_arxiv
from research_copilot.mcp.tools.citations import get_citations, format_citation_graph
from research_copilot.mcp.tools.trends import analyze_field_trends, format_trends
from research_copilot.logging import get_logger

logger = get_logger("mcp_server")

# Initialize the MCP server
mcp = FastMCP(
    name="research-copilot-tools",
    instructions="""
        You are a research tool server for the AI Research Copilot system.
        You provide tools for searching academic literature, analyzing citations,
        and understanding research trends.
    """,
)


@mcp.tool()
def search_papers(query: str, max_results: int = 5) -> list[dict]:
    """
    Search arXiv for research papers matching a query.
    Use this to find papers related to a topic, author, or concept.

    Args:
        query:       Search query (topic keywords, author name, concept)
        max_results: Number of papers to return (1-20)
    """
    logger.info("mcp_tool_called", tool="search_papers", query=query)
    return search_arxiv(query=query, max_results=max_results)


@mcp.tool()
def get_paper_citations(paper_title: str, limit: int = 10) -> str:
    """
    Get the citation graph for a research paper.
    Returns papers that cite this work AND papers this work references.
    Use this to understand a paper's influence and its intellectual foundations.

    Args:
        paper_title: Full or partial title of the paper
        limit:       Max citations/references to return
    """
    logger.info("mcp_tool_called", tool="get_paper_citations", paper=paper_title[:50])
    citation_data = get_citations(paper_title=paper_title, limit=limit)
    return format_citation_graph(citation_data)


@mcp.tool()
def get_field_trends(topic: str) -> str:
    """
    Analyze current research trends for a topic or field.
    Returns active subtopics, prolific authors, and publication patterns.
    Use this when you need to understand the broader research landscape.

    Args:
        topic: Research field or topic to analyze (e.g. 'retrieval augmented generation')
    """
    logger.info("mcp_tool_called", tool="get_field_trends", topic=topic)
    trends_data = analyze_field_trends(topic=topic)
    return format_trends(trends_data)


@mcp.tool()
def search_recent_papers(topic: str, max_results: int = 5) -> list[dict]:
    """
    Search arXiv for the MOST RECENT papers on a topic.
    Use this specifically when recency matters — finding latest work,
    checking if findings have been updated, or identifying new developments.

    Args:
        topic:       Research topic to search
        max_results: Number of recent papers to return
    """
    logger.info("mcp_tool_called", tool="search_recent_papers", topic=topic)
    return search_arxiv(
        query=topic,
        max_results=max_results,
        sort_by="lastUpdatedDate",
    )


def run_server():
    """Run the MCP server — called from CLI or subprocess."""
    logger.info("mcp_server_starting", name="research-copilot-tools")
    mcp.run()


if __name__ == "__main__":
    run_server()