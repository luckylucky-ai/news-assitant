"""Reddit 数据源 —— 使用 PRAW（同步）包装为 async 接口。"""

from __future__ import annotations

import asyncio
import logging
from typing import List

import praw
from praw.models import Subreddit

import config
from sources.base import BaseSource, NewsItem

logger = logging.getLogger(__name__)

# 关注的 subreddit（按话题）
SUBREDDITS = {
    "政治": ["politics", "worldnews", "geopolitics"],
    "AI": ["artificial", "MachineLearning", "LocalLLaMA", "ChatGPT"],
    "投资": ["investing", "stocks", "CryptoCurrency", "wallstreetbets"],
}


class RedditSource(BaseSource):
    name = "Reddit"

    def __init__(self) -> None:
        self.reddit = praw.Reddit(
            client_id=config.REDDIT_CLIENT_ID,
            client_secret=config.REDDIT_CLIENT_SECRET,
            user_agent=config.REDDIT_USER_AGENT,
        )

    def _fetch_sync(self, queries: List[str]) -> List[NewsItem]:
        items: List[NewsItem] = []
        seen_urls: set[str] = set()

        for category, subs in SUBREDDITS.items():
            for sub_name in subs:
                try:
                    subreddit: Subreddit = self.reddit.subreddit(sub_name)
                    for post in subreddit.hot(limit=5):
                        if post.stickied:
                            continue
                        url = f"https://www.reddit.com{post.permalink}"
                        if url in seen_urls:
                            continue
                        seen_urls.add(url)
                        items.append(
                            NewsItem(
                                title=post.title,
                                url=url,
                                source=self.name,
                                summary=(post.selftext or "")[:300],
                                author=str(post.author),
                                published_at=str(post.created_utc),
                                category=category,
                                extra={
                                    "score": post.score,
                                    "num_comments": post.num_comments,
                                    "subreddit": sub_name,
                                },
                            )
                        )
                except Exception:
                    logger.exception("Failed to fetch subreddit r/%s", sub_name)
        return items

    async def fetch(self, queries: List[str]) -> List[NewsItem]:
        return await asyncio.to_thread(self._fetch_sync, queries)
