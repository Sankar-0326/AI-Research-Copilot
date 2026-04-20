from research_copilot.mcp.tools.arxiv_search import search_arxiv
from research_copilot.logging import get_logger

logger = get_logger("tool.trends")


def analyze_field_trends(topic: str, years_back: int = 2) -> dict:
    """
    Analyze research trends for a topic by examining recent arXiv papers.

    Args:
        topic:      Research topic or field to analyze
        years_back: How many years of recent papers to consider

    Returns:
        Dict with trending subtopics, active authors, publication patterns
    """
    from datetime import datetime, timedelta

    # Fetch recent papers on the topic
    recent_papers = search_arxiv(
        query=topic,
        max_results=20,
        sort_by="lastUpdatedDate",
    )

    if not recent_papers:
        return {"error": f"No papers found for topic: {topic}"}

    # Extract trending patterns
    all_categories = []
    all_authors = []
    yearly_counts = {}

    for paper in recent_papers:
        all_categories.extend(paper.get("categories", []))
        all_authors.extend(paper.get("authors", []))

        year = paper.get("published", "")[:4]
        if year:
            yearly_counts[year] = yearly_counts.get(year, 0) + 1

    # Find most common categories (subtopics)
    category_freq = {}
    for cat in all_categories:
        category_freq[cat] = category_freq.get(cat, 0) + 1
    top_categories = sorted(
        category_freq.items(), key=lambda x: x[1], reverse=True
    )[:5]

    # Find most active authors
    author_freq = {}
    for author in all_authors:
        author_freq[author] = author_freq.get(author, 0) + 1
    top_authors = sorted(
        author_freq.items(), key=lambda x: x[1], reverse=True
    )[:5]

    # Recent paper titles as signal of trending subtopics
    recent_titles = [p["title"] for p in recent_papers[:5]]

    logger.info("trends_analyzed", topic=topic, papers_analyzed=len(recent_papers))

    return {
        "topic": topic,
        "papers_analyzed": len(recent_papers),
        "top_categories": [c for c, _ in top_categories],
        "top_authors": [a for a, _ in top_authors],
        "publication_by_year": dict(sorted(yearly_counts.items(), reverse=True)),
        "recent_paper_titles": recent_titles,
    }


def format_trends(trends_data: dict) -> str:
    """Format trend analysis into a readable string for LLM context."""
    if "error" in trends_data:
        return f"Trend analysis failed: {trends_data['error']}"

    lines = [
        f"## Field Trends: {trends_data['topic']}",
        f"Analyzed {trends_data['papers_analyzed']} recent papers",
        "",
        "### Active Research Categories:",
        *[f"- {cat}" for cat in trends_data["top_categories"]],
        "",
        "### Most Active Authors:",
        *[f"- {author}" for author in trends_data["top_authors"]],
        "",
        "### Publication Volume by Year:",
        *[f"- {year}: {count} papers"
          for year, count in trends_data["publication_by_year"].items()],
        "",
        "### Recent Paper Titles (signal of trending subtopics):",
        *[f"- {title}" for title in trends_data["recent_paper_titles"]],
    ]

    return "\n".join(lines)