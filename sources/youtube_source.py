"""YouTube 数据源 —— 通过 mcp-youtube MCP Server 搜索视频。

MCP Server: @kirbah/mcp-youtube
工具: search_videos
"""

from __future__ import annotations

import logging
import os
from typing import List

import config
from sources.base import BaseSource, NewsItem
from sources.mcp_client import call_mcp_tool, mcp_session

logger = logging.getLogger(__name__)

# 每个分类的搜索词
SEARCH_TERMS = {
    "政治": "politics news today",
    "AI": "AI artificial intelligence news",
    "投资": "stock market crypto investing news",
}


class YouTubeSource(BaseSource):
    name = "YouTube"

    async def fetch(self, queries: dict[str, list[str]]) -> List[NewsItem]:
        if not config.YOUTUBE_API_KEY:
            logger.warning("YOUTUBE_API_KEY not set, skipping YouTube source")
            return []

        env = {
            **os.environ,
            "YOUTUBE_API_KEY": config.YOUTUBE_API_KEY,
        }

        items: List[NewsItem] = []
        try:
            async with mcp_session("npx", ["-y", "@kirbah/mcp-youtube"], env=env) as session:
                tools = await session.list_tools()
                tool_names = [t.name for t in tools.tools]
                logger.info("YouTube MCP tools available: %s", tool_names)

                # 找到搜索工具
                search_tool = None
                for name in ["search_videos", "searchVideos", "search"]:
                    if name in tool_names:
                        search_tool = name
                        break
                if not search_tool:
                    search_tool = tool_names[0] if tool_names else None
                    logger.warning("Using fallback YouTube tool: %s", search_tool)

                if not search_tool:
                    logger.error("No YouTube MCP tools found")
                    return []

                for category, term in SEARCH_TERMS.items():
                    try:
                        results = await call_mcp_tool(
                            session,
                            search_tool,
                            {"query": term, "maxResults": 5},
                        )
                        for video in results:
                            vid = video.get("videoId", video.get("id", ""))
                            title = video.get("title", "")
                            url = f"https://www.youtube.com/watch?v={vid}" if vid else video.get("url", "")
                            items.append(
                                NewsItem(
                                    title=title,
                                    url=url,
                                    source=self.name,
                                    summary=video.get("description", "")[:300],
                                    author=video.get("channelTitle", video.get("channel", "")),
                                    published_at=video.get("publishedAt", ""),
                                    category=category,
                                    extra={
                                        "views": video.get("viewCount", video.get("views", 0)),
                                    },
                                )
                            )
                    except Exception:
                        logger.exception("YouTube MCP search failed for %s", category)
        except Exception:
            logger.exception("Failed to start YouTube MCP server")

        return items
