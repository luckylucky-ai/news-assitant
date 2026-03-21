"""统一的 MCP 客户端管理器 —— 启动 MCP Server 子进程并调用工具。"""

from __future__ import annotations

import json
import logging
from contextlib import asynccontextmanager
from typing import Any

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

logger = logging.getLogger(__name__)


@asynccontextmanager
async def mcp_session(
    command: str,
    args: list[str],
    env: dict[str, str] | None = None,
):
    """启动一个 MCP Server 并返回可用的 ClientSession。

    用法:
        async with mcp_session("npx", ["-y", "@enescinar/twitter-mcp"], env={...}) as session:
            result = await session.call_tool("search_tweets", {"query": "AI"})
    """
    server_params = StdioServerParameters(
        command=command,
        args=args,
        env=env,
    )

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            logger.info("MCP session initialized: %s %s", command, " ".join(args))
            yield session


async def call_mcp_tool(
    session: ClientSession,
    tool_name: str,
    arguments: dict[str, Any],
) -> list[dict]:
    """调用 MCP 工具并解析返回结果为字典列表。"""
    logger.info("Calling MCP tool: %s(%s)", tool_name, arguments)

    result = await session.call_tool(tool_name, arguments)

    items = []
    for content in result.content:
        if hasattr(content, "text"):
            try:
                parsed = json.loads(content.text)
                if isinstance(parsed, list):
                    items.extend(parsed)
                elif isinstance(parsed, dict):
                    items.append(parsed)
                else:
                    items.append({"text": content.text})
            except json.JSONDecodeError:
                items.append({"text": content.text})
    return items
