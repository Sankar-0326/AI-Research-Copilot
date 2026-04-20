import arxiv
from langchain_core.documents import Document
from research_copilot.logging import get_logger

logger = get_logger("tool.arxiv_search")


def search_arxiv(
    query: str,
    max_results: int = 5,
    sort_by: str = "relevance",
) -> list[dict]:
    """
    Search arXiv for papers matching a query.

    Args:
        query:       Search string (topic, title keywords, author)
        max_results: Max papers to return (default 5, max 20)
        sort_by:     'relevance' | 'lastUpdatedDate' | 'submittedDate'

    Returns:
        List of paper dicts with title, authors, abstract, url, published date
    """
    sort_map = {
        "relevance": arxiv.SortCriterion.Relevance,
        "lastUpdatedDate": arxiv.SortCriterion.LastUpdatedDate,
        "submittedDate": arxiv.SortCriterion.SubmittedDate,
    }

    client = arxiv.Client()
    search = arxiv.Search(
        query=query,
        max_results=min(max_results, 20),
        sort_by=sort_map.get(sort_by, arxiv.SortCriterion.Relevance),
    )

    results = []
    for paper in client.results(search):
        results.append({
            "arxiv_id": paper.entry_id.split("/")[-1],
            "title": paper.title,
            "authors": [a.name for a in paper.authors[:5]],
            "abstract": paper.summary[:500] + "..." if len(paper.summary) > 500 else paper.summary,
            "url": paper.pdf_url,
            "published": paper.published.strftime("%Y-%m-%d"),
            "categories": paper.categories,
            "source": "arxiv",
        })

    logger.info("arxiv_search_complete", query=query, results=len(results))
    return results


def arxiv_results_to_documents(results: list[dict]) -> list[Document]:
    """Convert arXiv search results to LangChain Documents."""
    return [
        Document(
            page_content=f"{r['title']}\n\n{r['abstract']}",
            metadata={
                "source": r["url"],
                "title": r["title"],
                "authors": ", ".join(r["authors"]),
                "published": r["published"],
                "arxiv_id": r["arxiv_id"],
                "retrieval_type": "arxiv",
            }
        )
        for r in results
    ]