"""X (Twitter) 数据源 —— 使用 Twitter API v2 Bearer Token。"""

from __future__ import annotations

import logging
from typing import List

import httpx

import config
from sources.base import BaseSource, NewsItem

logger = logging.getLogger(__name__)

SEARCH_URL = "https://api.twitter.com/2/tweets/search/recent"

# 每个分类的搜索词
CATEGORY_QUERIES = {
    "政治": "(politics OR geopolitics OR election OR diplomacy) lang:en -is:retweet",
    "AI": "(AI OR LLM OR GPT OR Claude OR #ArtificialIntelligence) lang:en -is:retweet",
    "投资": "(investing OR #stocks OR #crypto OR bitcoin OR economy) lang:en -is:retweet",
}


class XSource(BaseSource):
    name = "X"

    async def fetch(self, queries: List[str]) -> List[NewsItem]:
        if not config.X_BEARER_TOKEN:
            logger.warning("X_BEARER_TOKEN not set, skipping X source")
            return []

        items: List[NewsItem] = []
        headers = {"Authorization": f"Bearer {config.X_BEARER_TOKEN}"}

        async with httpx.AsyncClient(timeout=30) as client:
            for category, query in CATEGORY_QUERIES.items():
                try:
                    resp = await client.get(
                        SEARCH_URL,
                        headers=headers,
                        params={
                            "query": query,
                            "max_results": 10,
                            "sort_order": "relevancy",
                            "tweet.fields": "author_id,created_at,public_metrics,text",
                        },
                    )
                    resp.raise_for_status()
                    data = resp.json()

                    for tweet in data.get("data", []):
                        tweet_id = tweet["id"]
                        author = tweet.get("author_id", "")
                        metrics = tweet.get("public_metrics", {})
                        text = tweet.get("text", "")
                        title = text[:80] + ("..." if len(text) > 80 else "")

                        items.append(
                            NewsItem(
                                title=title,
                                url=f"https://x.com/i/status/{tweet_id}",
                                source=self.name,
                                summary=text[:300],
                                author=author,
                                published_at=tweet.get("created_at", ""),
                                category=category,
                                extra={
                                    "likes": metrics.get("like_count", 0),
                                    "retweets": metrics.get("retweet_count", 0),
                                    "replies": metrics.get("reply_count", 0),
                                },
                            )
                        )
                except Exception:
                    logger.exception("X search failed for category %s", category)

        return items
