import time
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.documents import Document

from research_copilot.agents.state import ResearchState
from research_copilot.config import get_settings
from research_copilot.rag import get_retriever
from research_copilot.logging import get_logger
from research_copilot.cache.response_cache import response_cache
from research_copilot.evaluation.evaluator import RAGEvaluator
from research_copilot.utils import retry_openai, timed


logger = get_logger("summarization_agent")

evaluator = RAGEvaluator()

@retry_openai
@timed("summarization_llm")
def _call_llm(chain, inputs: dict) -> str:
    return chain.invoke(inputs)


SUMMARIZATION_PROMPT = ChatPromptTemplate.from_messages([
    ("system", 
        """
            You are an expert research analyst. Your task is to produce a 
            structured summary of a research paper based on retrieved excerpts.

            Your summary MUST follow this exact structure:
            ## Title & Authors
            (infer from context if visible)

            ## Problem Statement
            (what problem does this paper solve?)

            ## Key Contributions
            (bullet list of 3-5 main contributions)

            ## Methodology
            (how did they approach the problem?)

            ## Results & Findings
            (key quantitative or qualitative results)

            ## Limitations
            (what are the paper's own stated or implied limitations?)

            Be precise. If information is missing from the context, state "Not found in excerpts." 
            Do NOT hallucinate details.
        """
    ),
    ("human", 
        """
            Paper ID: {paper_id}

            Retrieved Excerpts:
            {context}

            User Query (for focus): {query}

            Generate the structured summary now.
        """
    )
]
)


def summarization_agent(state: ResearchState) -> ResearchState :
    """
    Summarization Agent Node.

    For each paper_id in state:
    - Retrieve top-k chunks from its Pinecone namespace
    - Generate a structured summary via GPT-4o
    - Store result in state['summaries'][paper_id]
    """
    settings = get_settings()
    retriever = get_retriever()
    llm = ChatOpenAI(
        model= settings.openai_model,
        api_key= settings.openai_api_key,
        temperature= 0.1,  # low temp for factual summarization
    )

    chain = SUMMARIZATION_PROMPT | llm
    summaries = dict(state.get("summaries", {}))
    errors = list(state.get("errors", []))
    accumulated_docs = list(state.get("retrieved_docs", []))

    for paper_id in state["paper_ids"] :
        # ── Cache check ───────────────────────────────────────────────
        # Check cache first
        cached = response_cache.get(
            agent="summarization",
            query=state["query"],
            paper_ids=[paper_id],
            )
        
        if cached:
            summaries[paper_id] = cached
            logger.info("summary_from_cache", paper_id=paper_id[:8])
            continue  # skip LLM call entirely

        try:
            # Retrieve chunks scoped to this paper
            docs = retriever.retrieve_from_paper(
                query=state["query"],
                paper_id=paper_id,
                top_k=8,  # more chunks for summaries
            )

            if not docs :
                errors.append(f"No chunks found for paper_id: {paper_id}")
                summaries[paper_id] = "Could not generate summary — no content retrieved."
                continue

            accumulated_docs.extend(docs)
            context = retriever.format_context(docs)

            # ── Timed LLM call ────────────────────────────────────────────
            start_time = time.time()

            response = _call_llm(chain= chain, 
                                 inputs= {
                                    "paper_id": paper_id,
                                    "context": context,
                                    "query": state["query"],
                                 })

            elapsed = time.time() - start_time  # computed immediately after

            # ── Cache set ─────────────────────────────────────────────────
            # Cache the result before storing
            response_cache.set(
                agent="summarization",
                query=state["query"],
                paper_ids=[paper_id],
                response=response.content,
                )
            
            # ── Evaluation ────────────────────────────────────────────────
            eval_result = evaluator.evaluate(
                agent="summarization",
                query=state["query"],
                answer=response.content,
                context_docs=docs,
                paper_id=paper_id,
                latency=elapsed,
            )
            logger.info("eval_result", **eval_result.to_dict())
            
            summaries[paper_id] = response.content
            logger.info("summary_complete", paper_id=paper_id[:8], chunks_used=len(docs))

        except Exception as e:
            error_msg = f"Summarization failed for {paper_id[:8]}: {str(e)}"
            errors.append(error_msg)
            logger.error("operation_failed", error=error_msg, paper_id=paper_id[:8])

    completed = list(state.get("completed_agents", []))
    completed.append("summarization")

    return {
        **state,
        "summaries": summaries,
        "retrieved_docs": accumulated_docs,
        "errors": errors,
        "completed_agents": completed,
        "current_agent": "insight",
    }