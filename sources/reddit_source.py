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

# 按分类关注的 subreddit
SUBREDDITS = {
    "政治": ["politics", "worldnews", "geopolitics"],
    "AI": ["artificial", "MachineLearning", "LocalLLaMA"],
    "投资": ["investing", "stocks", "CryptoCurrency"],
}


class RedditSource(BaseSource):
    name = "Reddit"

    async def fetch(self, queries: dict[str, list[str]]) -> List[NewsItem]:
        env = {**os.environ}
        # 如果配置了 Reddit API Key，传给 MCP Server 提升速率
        if config.REDDIT_CLIENT_ID:
            env["REDDIT_CLIENT_ID"] = config.REDDIT_CLIENT_ID
            env["REDDIT_CLIENT_SECRET"] = config.REDDIT_CLIENT_SECRET

        items: List[NewsItem] = []
        try:
            async with mcp_session("npx", ["-y", "reddit-mcp-buddy"], env=env) as session:
                # 获取可用工具列表
                tools = await session.list_tools()
                tool_names = [t.name for t in tools.tools]
                logger.info("Reddit MCP tools available: %s", tool_names)

                for category, subs in SUBREDDITS.items():
                    for sub_name in subs:
                        try:
                            # 尝试 browse_subreddit 工具
                            if "browse_subreddit" in tool_names:
                                results = await call_mcp_tool(
                                    session,
                                    "browse_subreddit",
                                    {"subreddit": sub_name, "sort": "hot", "limit": 5},
                                )
                            elif "get_subreddit_posts" in tool_names:
                                results = await call_mcp_tool(
                                    session,
                                    "get_subreddit_posts",
                                    {"subreddit": sub_name, "sort": "hot", "limit": 5},
                                )
                            else:
                                logger.warning("No browse tool found, trying search")
                                results = await call_mcp_tool(
                                    session,
                                    tool_names[0],
                                    {"query": sub_name, "limit": 5},
                                )

                            for post in results:
                                title = post.get("title", "")
                                permalink = post.get("permalink", "")
                                url = f"https://www.reddit.com{permalink}" if permalink.startswith("/") else post.get("url", permalink)
                                items.append(
                                    NewsItem(
                                        title=title,
                                        url=url,
                                        source=self.name,
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
                                )
                        except Exception:
                            logger.exception("Reddit MCP failed for r/%s", sub_name)
        except Exception:
            logger.exception("Failed to start Reddit MCP server")

        return items
