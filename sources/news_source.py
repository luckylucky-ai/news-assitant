"""新闻媒体数据源 —— 使用 NewsAPI (newsapi.org)。"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import List

import httpx

import config
from sources.base import BaseSource, NewsItem

logger = logging.getLogger(__name__)

EVERYTHING_URL = "https://newsapi.org/v2/everything"

CATEGORY_QUERIES = {
    "政治": "politics OR geopolitics OR election OR diplomacy OR sanctions",
    "AI": "artificial intelligence OR LLM OR OpenAI OR Google AI OR machine learning",
    "投资": "stock market OR investing OR cryptocurrency OR Federal Reserve OR economy",
}


class NewsSource(BaseSource):
    name = "NewsAPI"

    async def fetch(self, queries: dict[str, list[str]]) -> List[NewsItem]:
        if not config.NEWSAPI_KEY:
            logger.warning("NEWSAPI_KEY not set, skipping NewsAPI source")
            return []

        items: List[NewsItem] = []
        seen: set[str] = set()
        now = datetime.now(timezone.utc)
        from_date = (now - timedelta(days=1)).strftime("%Y-%m-%d")
        to_date = now.strftime("%Y-%m-%d")

        async with httpx.AsyncClient(timeout=30) as client:
            for category, q in CATEGORY_QUERIES.items():
                try:
                    resp = await client.get(
                        EVERYTHING_URL,
                        params={
                            "q": q,
                            "from": from_date,
                            "to": to_date,
                            "sortBy": "publishedAt",
                            "pageSize": 5,
                            "language": "en",
                            "apiKey": config.NEWSAPI_KEY,
                        },
                    )
                    resp.raise_for_status()
                    data = resp.json()

                    for article in data.get("articles", []):
                        url = article.get("url", "")
                        if not url or url in seen:
                            continue
                        seen.add(url)
                        items.append(
                            NewsItem(
                                title=article.get("title", ""),
                                url=url,
                                source=f"NewsAPI - {article.get('source', {}).get('name', '')}",
                                summary=article.get("description", "") or "",
                                author=article.get("author", "") or "",
                                published_at=article.get("publishedAt", ""),
                                category=category,
                            )
                        )
                except Exception:
                    logger.exception("NewsAPI fetch failed for category %s", category)

        return items
