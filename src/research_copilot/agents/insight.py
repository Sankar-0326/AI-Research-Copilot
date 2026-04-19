from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate

from research_copilot.agents.state import ResearchState
from research_copilot.config import get_settings
from research_copilot.rag import get_retriever
from research_copilot.logging import get_logger


logger = get_logger("insight_agent")


INSIGHT_PROMPT = ChatPromptTemplate.from_messages([
    (
        "system",
        """
            You are a senior research scientist specializing in cross-paper 
            synthesis. You have access to excerpts from multiple research papers AND recent 
            web search results.

            Your task is to identify NON-OBVIOUS connections, patterns, and insights that 
            emerge only when looking across ALL papers together — not insights that could 
            come from reading any single paper.

            Structure your output as:
            ## Convergent Themes
            (ideas that multiple papers agree on or build toward)

            ## Contradictions & Debates
            (where papers disagree or take opposing stances)

            ## Methodological Patterns
            (common or contrasting approaches across papers)

            ## Emerging Concepts
            (ideas that seem to be gaining traction based on papers + web context)

            ## Key Cross-Paper Insight
            (your single most important synthesized finding — 2-3 sentences)

            Ground every insight in the provided context. Cite paper IDs where relevant.
            """
    ),
    (
        "human",
        """
            Research Query: {query}

            Paper Summaries:
            {summaries}

            Cross-Paper Retrieved Excerpts + Web Context:
            {context}

            Generate cross-paper insights now.
            """
    )
])


def insight_agent(state: ResearchState) -> ResearchState:
    """
    Insight Agent Node.

    - Retrieves cross-paper context using hybrid retrieval
    - Uses existing summaries as additional context
    - Generate
    """
    settings = get_settings()
    retriever = get_retriever()
    llm = ChatOpenAI(
        model= settings.openai_model,
        api_key= settings.openai_api_key,
        temperature= 0.3,  # slightly higher for creative synthesis
    )

    chain = INSIGHT_PROMPT | llm
    errors = list(state.get("errors", []))
    accumulated_docs = list(state.get("retrieved_docs", []))

    try:
        # Use hybrid retrieval — pull from all papers + web
        docs = retriever.retrieve_hybrid(
            query=state["query"],
            paper_ids=state["paper_ids"] if state["paper_ids"] else None,
            top_k=6,
            web_results=3,
        )
        accumulated_docs.extend(docs)
        context = retriever.format_context(docs)

        # Format summaries as context block
        summaries_block = "\n\n".join([
            f"### Paper {pid[:8]}...\n{summary}"
            for pid, summary in state.get("summaries", {}).items()
        ]) or "No summaries available yet."

        response = chain.invoke({
            "query": state["query"],
            "summaries": summaries_block,
            "context": context,
        })

        # Parse response into a list of insight bullets
        raw_insights = response.content
        insights = [raw_insights]  # store as full structured block

        total_docs = len(docs)
        web_docs = sum(1 for d in docs if d.metadata.get("retrieval_type") == "web")
        logger.info(
            "insight_agent_completed",
            total_docs=total_docs,
            web_docs=web_docs
        )
        
    except Exception as e:
        error_msg = f"Insight agent failed: {str(e)}"
        errors.append(error_msg)
        insights = []
        logger.error(
            "insight_failed",
            error=error_msg,
            )

    completed = list(state.get("completed_agents", []))
    completed.append("insight")

    return {
        **state,
        "insights": insights,
        "retrieved_docs": accumulated_docs,
        "errors": errors,
        "completed_agents": completed,
        "current_agent": "gap_detection",
    }