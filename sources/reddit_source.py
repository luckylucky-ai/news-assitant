"""Reddit 数据源 —— 通过 reddit-mcp-buddy MCP Server 获取帖子。

MCP Server: reddit-mcp-buddy (npm)
工具: browse_subreddit, search_reddit
特点: 无需 API Key 即可使用（匿名模式 10rpm）
"""

from __future__ import annotations

import asyncio
import logging
import os
from typing import List

import config
from sources.base import BaseSource, NewsItem
from sources.mcp_client import call_mcp_tool, mcp_session

logger = logging.getLogger(__name__)

# 认证模式下按分类浏览的 subreddit（每个分类只选 1 个最可靠的）
SUBREDDITS = {
    "政治": ["worldnews"],
    "AI": ["technology", "MachineLearning"],
    "投资": ["investing", "CryptoCurrency"],
}

# search_reddit 搜索关键词（匿名模式的主要策略）
SEARCH_QUERIES = {
    "政治": "politics OR geopolitics OR election",
    "AI": "artificial intelligence OR LLM OR machine learning",
    "投资": "stock market OR crypto OR investing",
}


class RedditSource(BaseSource):
    name = "Reddit"

    async def fetch(self, queries: dict[str, list[str]]) -> List[NewsItem]:
        env = {**os.environ}
        has_auth = bool(config.REDDIT_CLIENT_ID)
        if has_auth:
            env["REDDIT_CLIENT_ID"] = config.REDDIT_CLIENT_ID
            env["REDDIT_CLIENT_SECRET"] = config.REDDIT_CLIENT_SECRET

        items: List[NewsItem] = []
        try:
            async with mcp_session("npx", ["-y", "reddit-mcp-buddy"], env=env) as session:
                tools = await session.list_tools()
                tool_names = [t.name for t in tools.tools]
                logger.info("Reddit MCP tools available: %s", tool_names)

                if has_auth:
                    # 认证模式：可以浏览 subreddit（限额更高）
                    items = await self._fetch_authenticated(session, tool_names)
                else:
                    # 匿名模式：只用 search_reddit，节省请求次数（3 次）
                    items = await self._fetch_anonymous(session, tool_names)
        except Exception:
            logger.exception("Failed to start Reddit MCP server")

        return items

    async def _fetch_anonymous(
        self, session, tool_names: list[str]
    ) -> List[NewsItem]:
        """匿名模式：直接用 search_reddit，每个分类 1 次调用。"""
        items: List[NewsItem] = []
        if "search_reddit" not in tool_names:
            logger.warning("search_reddit not available, cannot fetch in anonymous mode")
            return items

        for category, query in SEARCH_QUERIES.items():
            try:
                results = await call_mcp_tool(
                    session,
                    "search_reddit",
                    {"query": query, "sort": "new", "time_filter": "day", "limit": 5},
                )
                for post in results:
                    items.append(self._parse_post(post, category, "search"))
                logger.info("Reddit search for %s returned %d results", category, len(results))
            except Exception:
                logger.exception("search_reddit failed for %s", category)
            # 匿名模式下，在请求之间稍作等待以避免速率限制
            await asyncio.sleep(1)

        return items

    async def _fetch_authenticated(
        self, session, tool_names: list[str]
    ) -> List[NewsItem]:
        """认证模式：浏览 subreddit + search 回退。"""
        items: List[NewsItem] = []

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
                        "browse_subreddit failed for r/%s", sub_name
                    )

            # browse 全部失败时，用 search 兜底
            if not category_items and "search_reddit" in tool_names:
                query = SEARCH_QUERIES.get(category, category)
                logger.info("Falling back to search_reddit for %s: %s", category, query)
                try:
                    results = await call_mcp_tool(
                        session,
                        "search_reddit",
                        {"query": query, "sort": "new", "time_filter": "day", "limit": 10},
                    )
                    for post in results:
                        category_items.append(
                            self._parse_post(post, category, "search")
                        )
                except Exception:
                    logger.exception("search_reddit failed for %s", category)

            items.extend(category_items)

        return items

    @staticmethod
    async def _browse_subreddit(session, tool_names, sub_name) -> list:
        if "browse_subreddit" in tool_names:
            return await call_mcp_tool(
                session,
                "browse_subreddit",
                {"subreddit": sub_name, "sort": "new", "limit": 5},
            )
        elif "get_subreddit_posts" in tool_names:
            return await call_mcp_tool(
                session,
                "get_subreddit_posts",
                {"subreddit": sub_name, "sort": "new", "limit": 5},
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
                "subreddit": post.get("subreddit", sub_name),
            },
        )
