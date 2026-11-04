"""
Base agent class providing MCP connectivity and Claude tool-use loop.
All domain agents inherit from this class.
"""
from __future__ import annotations

import json
import logging
import sys
from typing import Any

import anthropic
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

sys.path.insert(0, __import__("pathlib").Path(__file__).parent.parent.__str__())
from config import ANTHROPIC_API_KEY, LLM_MAX_TOKENS, LLM_MODEL

logger = logging.getLogger(__name__)


class BaseAgent:
    """
    Abstract base for all domain agents.
    Connects to an MCP server via stdio, discovers tools, and drives a
    Claude tool-use loop until the model emits a JSON result block.
    Uses AsyncAnthropic so the event loop is never blocked.
    """

    def __init__(
        self,
        mcp_server_script: str,
        agent_name: str,
        system_prompt: str,
    ) -> None:
        self.mcp_server_script = mcp_server_script
        self.agent_name = agent_name
        self.system_prompt = system_prompt
        # AsyncAnthropic keeps the FastAPI event loop free during API calls
        self._client = anthropic.AsyncAnthropic(api_key=ANTHROPIC_API_KEY)

    async def run(self, user_prompt: str) -> dict[str, Any]:
        """
        Start the MCP server as a subprocess, run the agent loop,
        and return the parsed JSON result.
        """
        logger.info("[%s] Starting agent with server: %s", self.agent_name, self.mcp_server_script)

        server_params = StdioServerParameters(
            command=sys.executable,
            args=[self.mcp_server_script],
        )

        try:
            async with stdio_client(server_params) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    tools = await self._discover_tools(session)
                    logger.debug("[%s] Discovered %d tools", self.agent_name, len(tools))
                    result = await self._agent_loop(session, user_prompt, tools)
                    logger.info("[%s] Agent completed successfully", self.agent_name)
                    return result
        except Exception as exc:
            logger.error("[%s] Agent failed: %s", self.agent_name, exc)
            raise

    async def _discover_tools(self, session: ClientSession) -> list[dict]:
        tools_response = await session.list_tools()
        return [
            {
                "name": tool.name,
                "description": tool.description or "",
                "input_schema": tool.input_schema,
            }
            for tool in tools_response.tools
        ]

    async def _agent_loop(
        self,
        session: ClientSession,
        user_prompt: str,
        tools: list[dict],
    ) -> dict[str, Any]:
        messages = [{"role": "user", "content": user_prompt}]
        max_iterations = 10

        for iteration in range(max_iterations):
            logger.debug("[%s] Agent loop iteration %d", self.agent_name, iteration + 1)

            create_kwargs: dict[str, Any] = {
                "model": LLM_MODEL,
                "max_tokens": LLM_MAX_TOKENS,
                "system": self.system_prompt,
                "messages": messages,
            }
            if tools:
                create_kwargs["tools"] = tools

            # Async call — does not block the event loop
            response = await self._client.messages.create(**create_kwargs)

            if response.stop_reason == "end_turn":
                return self._extract_json_result(response)

            if response.stop_reason == "tool_use":
                tool_results = []
                for block in response.content:
                    if block.type == "tool_use":
                        tool_result_content = await self._call_mcp_tool(
                            session, block.name, block.input or {}
                        )
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": tool_result_content,
                        })

                messages.append({"role": "assistant", "content": response.content})
                messages.append({"role": "user", "content": tool_results})
                continue

            return self._extract_json_result(response)

        raise RuntimeError(
            f"[{self.agent_name}] Agent loop exceeded {max_iterations} iterations"
        )

    async def _call_mcp_tool(
        self, session: ClientSession, tool_name: str, tool_input: dict
    ) -> str:
        logger.debug("[%s] Calling MCP tool: %s", self.agent_name, tool_name)
        try:
            result = await session.call_tool(tool_name, tool_input)
            parts = []
            for content_block in result.content:
                if hasattr(content_block, "text"):
                    parts.append(content_block.text)
            return "\n".join(parts) if parts else "Tool returned no output"
        except Exception as exc:
            logger.error("[%s] Tool call failed: %s — %s", self.agent_name, tool_name, exc)
            return json.dumps({"error": str(exc), "tool": tool_name})

    def _extract_json_result(self, response) -> dict[str, Any]:
        """
        Extract the final JSON block from the model's response.
        Falls back to wrapping the text in a dict if no JSON is found.
        """
        full_text = ""
        for block in response.content:
            if hasattr(block, "text"):
                full_text += block.text

        import re
        json_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", full_text, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group(1))
            except json.JSONDecodeError:
                pass

        stripped = full_text.strip()
        if stripped.startswith("{"):
            try:
                return json.loads(stripped)
            except json.JSONDecodeError:
                pass

        json_objects = re.findall(r"\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}", full_text, re.DOTALL)
        for candidate in reversed(json_objects):
            try:
                return json.loads(candidate)
            except json.JSONDecodeError:
                continue

        logger.warning("[%s] No JSON found in response — wrapping raw text", self.agent_name)
        return {"raw_response": full_text, "agent": self.agent_name}
