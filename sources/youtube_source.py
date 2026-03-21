"""YouTube 数据源 —— 使用 YouTube Data API v3。"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import List

from googleapiclient.discovery import build

import config
from sources.base import BaseSource, NewsItem

logger = logging.getLogger(__name__)

# 关注的频道（可按需扩展）
# 格式：(频道名, 频道ID, 分类)
CHANNELS: list[tuple[str, str, str]] = [
    # AI
    ("Two Minute Papers", "UCbfYPyITQ-7l4upoX8nvctg", "AI"),
    ("Yannic Kilcher", "UCZHmQk67mSJgfCCTn7xBfew", "AI"),
    # 投资
    ("Yahoo Finance", "UCEAZeUIeJs0IjQiqTCdVSIg", "投资"),
    # 政治
    ("TLDR News", "UCSMqateX8OA2s1wsOR2EgJA", "政治"),
]


class YouTubeSource(BaseSource):
    name = "YouTube"

    def __init__(self) -> None:
        self.youtube = build("youtube", "v3", developerKey=config.YOUTUBE_API_KEY)

    def _search_sync(self, queries: List[str]) -> List[NewsItem]:
        items: List[NewsItem] = []
        seen: set[str] = set()
        published_after = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()

        # 1) 按关键词搜索最近 24h 的视频
        search_terms = ["AI news", "politics news today", "stock market today", "crypto news"]
        for term in search_terms:
            try:
                resp = (
                    self.youtube.search()
                    .list(
                        q=term,
                        part="snippet",
                        type="video",
                        order="viewCount",
                        publishedAfter=published_after,
                        maxResults=3,
                        relevanceLanguage="en",
                    )
                    .execute()
                )
                for item in resp.get("items", []):
                    vid = item["id"]["videoId"]
                    if vid in seen:
                        continue
                    seen.add(vid)
                    snippet = item["snippet"]
                    category = self._classify(term)
                    items.append(
                        NewsItem(
                            title=snippet["title"],
                            url=f"https://www.youtube.com/watch?v={vid}",
                            source=self.name,
                            summary=snippet.get("description", "")[:300],
                            author=snippet.get("channelTitle", ""),
                            published_at=snippet.get("publishedAt", ""),
                            category=category,
                        )
                    )
            except Exception:
                logger.exception("YouTube search failed for '%s'", term)

        # 2) 从关注频道获取最新视频
        for ch_name, ch_id, category in CHANNELS:
            try:
                resp = (
                    self.youtube.search()
                    .list(
                        channelId=ch_id,
                        part="snippet",
                        type="video",
                        order="date",
                        publishedAfter=published_after,
                        maxResults=2,
                    )
                    .execute()
                )
                for item in resp.get("items", []):
                    vid = item["id"]["videoId"]
                    if vid in seen:
                        continue
                    seen.add(vid)
                    snippet = item["snippet"]
                    items.append(
                        NewsItem(
                            title=snippet["title"],
                            url=f"https://www.youtube.com/watch?v={vid}",
                            source=self.name,
                            summary=snippet.get("description", "")[:300],
                            author=ch_name,
                            published_at=snippet.get("publishedAt", ""),
                            category=category,
                        )
                    )
            except Exception:
                logger.exception("YouTube channel fetch failed for %s", ch_name)

        return items

    @staticmethod
    def _classify(term: str) -> str:
        t = term.lower()
        if any(k in t for k in ("ai", "llm", "machine learning")):
            return "AI"
        if any(k in t for k in ("politic", "election", "geopolitic")):
            return "政治"
        return "投资"

    async def fetch(self, queries: List[str]) -> List[NewsItem]:
        return await asyncio.to_thread(self._search_sync, queries)
