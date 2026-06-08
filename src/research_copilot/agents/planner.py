import json
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate

from research_copilot.agents.state import ResearchState
from research_copilot.config import get_settings
from research_copilot.mcp import get_mcp_client
from research_copilot.logging import get_logger
from research_copilot.utils import retry_openai, timed


logger = get_logger("planner_agent")


PLANNER_PROMPT = ChatPromptTemplate.from_messages([
    (
        "system", 
        """
        You are a research planning agent. Given a user query and a list
        of available tools, your job is to decide WHICH tools to call and with WHAT 
        arguments to best enrich the analysis before the research agents begin.

        Available tools:
        {available_tools}

        Rules:
        - Only select tools that are genuinely useful for this specific query
        - Do not call a tool if the query doesn't require it
        - For get_paper_citations, always use paper_title with the ACTUAL TITLE of the paper
          (e.g. "Attention Is All You Need"), NEVER a hash ID like "80b9f349564a7f42"
          If you only have a hash ID, use search_papers first to discover the title
        - For trend analysis, extract the core topic from the query
        - Prefer focused queries over broad ones

        Respond ONLY with a valid JSON array of tool calls:
        [
        {{"tool": "tool_name", "args": {{"arg1": "value1"}}}},
        ...
        ]

        If no tools are needed, respond with an empty array: []
        """
    ),
    (
        "human", 
        """
        User Query: {query}

        Uploaded Paper IDs: {paper_ids}

        Decide which tools to call now.
        """
    )
])


@retry_openai
@timed("summarization_llm")
def _call_llm(chain, inputs: dict) -> str:
    return chain.invoke(inputs)


def planner_agent(state: ResearchState) -> ResearchState:
    """
    Planner Agent Node — runs FIRST in the graph.

    1. Discovers available MCP tools
    2. Asks GPT-4o which tools are relevant for this query
    3. Executes selected tools concurrently via MCP client
    4. Injects results into state as additional context
    """
    settings = get_settings()
    mcp_client = get_mcp_client()
    errors = list(state.get("errors", []))

    user_context = state.get("user_context")
    openai_key = (
        user_context.openai_api_key
        if user_context and user_context.openai_api_key
        else settings.openai_api_key
    )
    llm = ChatOpenAI(
        model=settings.openai_model,
        api_key=openai_key,
        temperature=0,   # deterministic planning
    )

    try:
        # ── Step 1: Discover tools ────────────────────────────────────
        available_tools = mcp_client.get_available_tools()

        tools_description = "\n".join([
            f"- {t['name']}: {t['description']}"
            for t in available_tools
        ])

        logger.info(
            "planner_tools_discovered",
            count=len(available_tools),
            tools=[t["name"] for t in available_tools],
        )

        # ── Step 2: Ask LLM which tools to invoke ────────────────────
        chain = PLANNER_PROMPT | llm
        
        response = _call_llm(chain= chain, 
                                 inputs= {
                                    "query": state["query"],
                                    "paper_ids": state["paper_ids"],
                                    "available_tools": tools_description,
                                 })

        # Parse the tool call plan
        try:
            raw = response.content.strip()
            # Strip markdown code fences if present
            if raw.startswith("```"):
                raw = raw.split("```")[1]
                if raw.startswith("json"):
                    raw = raw[4:]
                raw = raw.strip()
            tool_calls = json.loads(raw)
            if not isinstance(tool_calls, list):
                tool_calls = []
        except (json.JSONDecodeError, IndexError):
            logger.warning(
                "planner_parse_failed",
                raw_response=response.content[:200],
            )
            tool_calls = []

        if not tool_calls:
            logger.info("planner_no_tools_needed")
            completed = list(state.get("completed_agents", []))
            completed.append("planner")
            return {
                **state,
                "completed_agents": completed,
                "current_agent": "summarization",
            }

        # ── Step 3: Execute tools concurrently ────────────────────────
        tool_results = mcp_client.execute_tools_batch(tool_calls)

        # ── Step 4: Format results as context ─────────────────────────
        context_blocks = []
        for tool_name, result in tool_results.items():
            context_blocks.append(
                f"### MCP Tool Result: {tool_name}\n{result}"
            )

        mcp_context = "\n\n".join(context_blocks)

        logger.info(
            "planner_complete",
            tools_executed=len(tool_results),
            context_length=len(mcp_context),
        )

    except Exception as e:
        error_msg = f"Planner agent failed: {str(e)}"
        errors.append(error_msg)
        mcp_context = ""
        logger.error("planner_failed", error=error_msg)

    completed = list(state.get("completed_agents", []))
    completed.append("planner")

    return {
        **state,
        "mcp_context": mcp_context,        # ← new state field
        "errors": errors,
        "completed_agents": completed,
        "current_agent": "summarization",
    }