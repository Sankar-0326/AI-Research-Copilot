import json
import asyncio
from contextlib import asynccontextmanager
from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_core.tools import BaseTool
from research_copilot.logging import get_logger
from research_copilot.config import get_settings

logger = get_logger("mcp_client")


class ResearchMCPClient:
    """
    Agent-facing MCP client.

    Wraps MultiServerMCPClient to provide:
    - Tool discovery (list what's available)
    - Typed tool execution
    - Result normalization into strings for LLM context
    """

    def __init__(self):
        self._tools: list[BaseTool] | None = None
        self._tool_map: dict[str, BaseTool] = {}

    def _get_server_config(self) -> dict:
        """
        Server config for MultiServerMCPClient.
        Points to our local MCP server process via stdio.
        """
        return {
            "research-tools": {
                "command": "python",
                "args": ["-m", "research_copilot.mcp.server"],
                "transport": "stdio",
            }
        }

    async def _load_tools(self) -> list[BaseTool]:
        """Lazily load tools from the MCP server."""
        if self._tools is not None:
            return self._tools

        async with MultiServerMCPClient(self._get_server_config()) as client:
            self._tools = client.get_tools()
            self._tool_map = {tool.name: tool for tool in self._tools}
            logger.info(
                "mcp_tools_loaded",
                count=len(self._tools),
                tools=[t.name for t in self._tools],
            )
        return self._tools

    def get_available_tools(self) -> list[dict]:
        """
        Return a list of available tools with name + description.
        Used by the Planner Agent to decide which tools to invoke.
        """
        tools = asyncio.run(self._load_tools())
        return [
            {"name": t.name, "description": t.description}
            for t in tools
        ]

    def execute_tool(self, tool_name: str, **kwargs) -> str:
        """
        Execute a named tool with given arguments.
        Returns a string result suitable for LLM context injection.
        """
        async def _run():
            tools = await self._load_tools()
            tool = self._tool_map.get(tool_name)

            if not tool:
                available = [t.name for t in tools]
                raise ValueError(
                    f"Tool '{tool_name}' not found. "
                    f"Available tools: {available}"
                )

            logger.info("mcp_tool_executing", tool=tool_name, args=list(kwargs.keys()))
            result = await tool.ainvoke(kwargs)

            # Normalize result to string
            if isinstance(result, str):
                return result
            elif isinstance(result, list):
                return json.dumps(result, indent=2)
            elif isinstance(result, dict):
                return json.dumps(result, indent=2)
            return str(result)

        return asyncio.run(_run())

    def execute_tools_batch(
        self,
        tool_calls: list[dict],
    ) -> dict[str, str]:
        """
        Execute multiple tools concurrently.

        Args:
            tool_calls: List of {"tool": "tool_name", "args": {...}}

        Returns:
            Dict mapping tool_name → result string
        """
        async def _run_all():
            tasks = []
            for call in tool_calls:
                tool_name = call["tool"]
                args = call.get("args", {})
                tool = self._tool_map.get(tool_name)
                if tool:
                    tasks.append((tool_name, tool.ainvoke(args)))
                else:
                    logger.warning("mcp_tool_not_found", tool=tool_name)

            results = {}
            for tool_name, coro in tasks:
                try:
                    result = await coro
                    results[tool_name] = (
                        result if isinstance(result, str)
                        else json.dumps(result, indent=2)
                    )
                except Exception as e:
                    logger.error("mcp_tool_failed", tool=tool_name, error=str(e))
                    results[tool_name] = f"Tool execution failed: {str(e)}"

            return results

        asyncio.run(self._load_tools())
        return asyncio.run(_run_all())


# Module-level singleton
_mcp_client: ResearchMCPClient | None = None


def get_mcp_client() -> ResearchMCPClient:
    global _mcp_client
    if _mcp_client is None:
        _mcp_client = ResearchMCPClient()
    return _mcp_client