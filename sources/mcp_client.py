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

    # 检查 MCP 层面的错误
    if getattr(result, "isError", False):
        error_text = ""
        for content in result.content:
            if hasattr(content, "text"):
                error_text += content.text
        raise RuntimeError(f"MCP tool {tool_name} returned error: {error_text}")

    items = []
    for content in result.content:
        if hasattr(content, "text"):
            try:
                parsed = json.loads(content.text)
                if isinstance(parsed, list):
                    items.extend(parsed)
                elif isinstance(parsed, dict):
                    # 处理嵌套格式：{posts: [...]} 或 {data: [...]} 等
                    unwrapped = _unwrap_nested(parsed)
                    if unwrapped is not None:
                        items.extend(unwrapped)
                    else:
                        items.append(parsed)
                else:
                    items.append({"text": content.text})
            except json.JSONDecodeError:
                items.append({"text": content.text})

    logger.debug("MCP tool %s returned %d items", tool_name, len(items))
    return items


def _unwrap_nested(d: dict) -> list[dict] | None:
    """尝试从嵌套 dict 中提取列表数据。

    很多 MCP 服务返回 {posts: [...], subreddit: "..."} 这样的格式，
    这里自动解包最大的 list 字段。
    """
    # 常见的嵌套键名
    for key in ("posts", "data", "results", "items", "tweets", "videos"):
        if key in d and isinstance(d[key], list):
            return d[key]
    # 回退：找第一个 list 类型的值
    for val in d.values():
        if isinstance(val, list) and val and isinstance(val[0], dict):
            return val
    return None
