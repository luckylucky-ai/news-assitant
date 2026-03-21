"""Reddit 数据源 —— 通过 reddit-mcp-buddy MCP Server 获取帖子。

MCP Server: reddit-mcp-buddy (npm)
工具: browse_subreddit, search_reddit
特点: 无需 API Key 即可使用（匿名模式 10rpm）
"""

from __future__ import annotations

import logging
import os
from typing import List

import config
from sources.base import BaseSource, NewsItem
from sources.mcp_client import call_mcp_tool, mcp_session

logger = logging.getLogger(__name__)

# 按分类关注的 subreddit（优先使用公开可访问的子版块）
SUBREDDITS = {
    "政治": ["news", "worldnews", "geopolitics"],
    "AI": ["technology", "MachineLearning", "LocalLLaMA"],
    "投资": ["investing", "stocks", "CryptoCurrency"],
}

# search_reddit 回退用的搜索关键词
SEARCH_FALLBACK = {
    "政治": "politics OR geopolitics OR election",
    "AI": "artificial intelligence OR LLM OR machine learning",
    "投资": "stock market OR crypto OR investing",
}


class RedditSource(BaseSource):
    name = "Reddit"

    async def fetch(self, queries: dict[str, list[str]]) -> List[NewsItem]:
        env = {**os.environ}
        if config.REDDIT_CLIENT_ID:
            env["REDDIT_CLIENT_ID"] = config.REDDIT_CLIENT_ID
            env["REDDIT_CLIENT_SECRET"] = config.REDDIT_CLIENT_SECRET

        items: List[NewsItem] = []
        try:
            async with mcp_session("npx", ["-y", "reddit-mcp-buddy"], env=env) as session:
                tools = await session.list_tools()
                tool_names = [t.name for t in tools.tools]
                logger.info("Reddit MCP tools available: %s", tool_names)

                for category, subs in SUBREDDITS.items():
                    category_items: List[NewsItem] = []
                    for sub_name in subs:
                        try:
                            results = await self._browse_subreddit(
                                session, tool_names, sub_name
                            )
                            for post in results:
                                category_items.append(
                                    self._parse_post(post, category, sub_name)
                                )
                        except Exception:
                            logger.warning(
                                "browse_subreddit failed for r/%s, will use search fallback",
                                sub_name,
                            )

                    # 如果 browse 全部失败，用 search_reddit 兜底
                    if not category_items and "search_reddit" in tool_names:
                        query = SEARCH_FALLBACK.get(category, category)
                        logger.info("Falling back to search_reddit for %s: %s", category, query)
                        try:
                            results = await call_mcp_tool(
                                session,
                                "search_reddit",
                                {"query": query, "limit": 10},
                            )
                            for post in results:
                                category_items.append(
                                    self._parse_post(post, category, "search")
                                )
                        except Exception:
                            logger.exception("search_reddit failed for %s", category)

                    items.extend(category_items)
        except Exception:
            logger.exception("Failed to start Reddit MCP server")

        return items

    @staticmethod
    async def _browse_subreddit(session, tool_names, sub_name) -> list:
        if "browse_subreddit" in tool_names:
            return await call_mcp_tool(
                session,
                "browse_subreddit",
                {"subreddit": sub_name, "sort": "hot", "limit": 5},
            )
        elif "get_subreddit_posts" in tool_names:
            return await call_mcp_tool(
                session,
                "get_subreddit_posts",
                {"subreddit": sub_name, "sort": "hot", "limit": 5},
            )
        return []

    @staticmethod
    def _parse_post(post: dict, category: str, sub_name: str) -> NewsItem:
        title = post.get("title", "")
        permalink = post.get("permalink", "")
        url = (
            f"https://www.reddit.com{permalink}"
            if permalink.startswith("/")
            else post.get("url", permalink)
        )
        return NewsItem(
            title=title,
            url=url,
            source="Reddit",
            summary=post.get("selftext", post.get("body", ""))[:300],
            author=post.get("author", ""),
            published_at=str(post.get("created_utc", "")),
            category=category,
            extra={
                "score": post.get("score", post.get("ups", 0)),
                "num_comments": post.get("num_comments", 0),
                "subreddit": sub_name,
            },
        )
