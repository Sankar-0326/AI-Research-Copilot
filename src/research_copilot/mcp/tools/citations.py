import httpx
from research_copilot.logging import get_logger

logger = get_logger("tool.citations")

SEMANTIC_SCHOLAR_BASE = "https://api.semanticscholar.org/graph/v1"


def get_citations(
    paper_title: str,
    limit: int = 10,
) -> dict:
    """
    Fetch citation data for a paper from Semantic Scholar.

    Args:
        paper_title: Title of the paper to look up
        limit:       Max citations/references to return

    Returns:
        Dict with paper details, citations (papers that cite this),
        and references (papers this cites)
    """
    try:
        # Step 1 — search for the paper
        search_url = f"{SEMANTIC_SCHOLAR_BASE}/paper/search"
        search_resp = httpx.get(
            search_url,
            params={
                "query": paper_title,
                "limit": 1,
                "fields": "paperId,title,year,authors",
            },
            timeout=10,
        )
        search_resp.raise_for_status()
        search_data = search_resp.json()

        if not search_data.get("data"):
            return {"error": f"Paper not found: {paper_title}"}

        paper_id = search_data["data"][0]["paperId"]
        found_title = search_data["data"][0]["title"]

        # Step 2 — fetch citations and references
        detail_url = f"{SEMANTIC_SCHOLAR_BASE}/paper/{paper_id}"
        detail_resp = httpx.get(
            detail_url,
            params={
                "fields": "title,year,authors,citationCount,"
                          "citations.title,citations.year,citations.authors,"
                          "references.title,references.year,references.authors",
            },
            timeout=10,
        )
        detail_resp.raise_for_status()
        detail = detail_resp.json()

        citations = [
            {
                "title": c.get("title", "Unknown"),
                "year": c.get("year"),
                "authors": [a["name"] for a in c.get("authors", [])[:3]],
            }
            for c in detail.get("citations", [])[:limit]
        ]

        references = [
            {
                "title": r.get("title", "Unknown"),
                "year": r.get("year"),
                "authors": [a["name"] for a in r.get("authors", [])[:3]],
            }
            for r in detail.get("references", [])[:limit]
        ]

        logger.info(
            "citations_fetched",
            paper=found_title[:50],
            citations=len(citations),
            references=len(references),
        )

        return {
            "paper_id": paper_id,
            "title": found_title,
            "citation_count": detail.get("citationCount", 0),
            "citations": citations,
            "references": references,
        }

    except httpx.HTTPError as e:
        logger.error("citations_fetch_failed", error=str(e))
        return {"error": f"HTTP error: {str(e)}"}


def format_citation_graph(citation_data: dict) -> str:
    """Format citation data into a readable string for LLM context."""
    if "error" in citation_data:
        return f"Citation lookup failed: {citation_data['error']}"

    lines = [
        f"## Citation Graph: {citation_data['title']}",
        f"Total citations: {citation_data['citation_count']}",
        "",
        "### Papers that cite this work:",
    ]

    for c in citation_data["citations"][:5]:
        authors = ", ".join(c["authors"]) if c["authors"] else "Unknown"
        lines.append(f"- {c['title']} ({c['year']}) — {authors}")

    lines += ["", "### Papers this work references:"]
    for r in citation_data["references"][:5]:
        authors = ", ".join(r["authors"]) if r["authors"] else "Unknown"
        lines.append(f"- {r['title']} ({r['year']}) — {authors}")

    return "\n".join(lines)