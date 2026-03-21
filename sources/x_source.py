"""X (Twitter) 数据源 —— 通过 twitter-mcp MCP Server 获取推文。

MCP Server: @enescinar/twitter-mcp
工具: search_tweets
"""

from __future__ import annotations

import logging
import os
from typing import List

import config
from sources.base import BaseSource, NewsItem
from sources.mcp_client import call_mcp_tool, mcp_session

logger = logging.getLogger(__name__)


class XSource(BaseSource):
    name = "X"

    async def fetch(self, queries: dict[str, list[str]]) -> List[NewsItem]:
        if not config.X_API_KEY:
            logger.warning("X API keys not set, skipping X source")
            return []

        env = {
            **os.environ,
            "API_KEY": config.X_API_KEY,
            "API_SECRET_KEY": config.X_API_SECRET_KEY,
            "ACCESS_TOKEN": config.X_ACCESS_TOKEN,
            "ACCESS_TOKEN_SECRET": config.X_ACCESS_TOKEN_SECRET,
        }

        items: List[NewsItem] = []
        try:
            async with mcp_session("npx", ["-y", "@enescinar/twitter-mcp"], env=env) as session:
                for category, keywords in queries.items():
                    query = " OR ".join(keywords[:2])
                    try:
                        results = await call_mcp_tool(
                            session, "search_tweets", {"query": query, "count": 10}
                        )
                        for tweet in results:
                            # 跳过错误响应（如 401 认证失败）
                            if "error" in tweet or "Error" in tweet.get("text", ""):
                                logger.warning("Skipping X error item: %s",
                                               tweet.get("error", tweet.get("text", ""))[:100])
                                continue

                            text = tweet.get("text", tweet.get("full_text", ""))
                            if not text:
                                continue

                            tweet_id = tweet.get("id_str", tweet.get("id", ""))
                            user = tweet.get("user", {})
                            screen_name = user.get("screen_name", "")
                            title = text[:80] + ("..." if len(text) > 80 else "")

                            url = f"https://x.com/{screen_name}/status/{tweet_id}" if screen_name else f"https://x.com/i/status/{tweet_id}"
                            items.append(
                                NewsItem(
                                    title=title,
                                    url=url,
                                    source=self.name,
                                    summary=text[:300],
                                    author=f"@{screen_name}" if screen_name else "",
                                    published_at=tweet.get("created_at", ""),
                                    category=category,
                                    extra={
                                        "likes": tweet.get("favorite_count", 0),
                                        "retweets": tweet.get("retweet_count", 0),
                                    },
                                )
                            )
                    except Exception:
                        logger.exception("X MCP search failed for category %s", category)
        except Exception:
            logger.exception("Failed to start X MCP server")

        return items
