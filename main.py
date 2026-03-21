"""每日简报助手 —— 主入口。

功能：
1. 并发抓取 X、YouTube、Reddit、新闻媒体的热点内容
2. 按 政治 / AI / 投资 分类整理
3. 创建飞书文档，写入详细内容（含原文链接）
4. 推送飞书卡片消息，附带文档链接

用法：
    python main.py            # 立即执行一次
    python main.py --schedule # 每天早上 8:00 自动执行
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from collections import defaultdict
from datetime import datetime
from typing import List

import config
from sources.base import NewsItem
from sources.reddit_source import RedditSource
from sources.youtube_source import YouTubeSource
from sources.x_source import XSource
from sources.news_source import NewsSource
from feishu.docs import create_daily_doc
from feishu.message import send_digest_message

logging.basicConfig(
    level=getattr(logging, config.LOG_LEVEL, logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("daily-digest")


async def collect_news() -> dict[str, List[NewsItem]]:
    """从所有数据源并发抓取新闻，按分类整理。"""
    sources = []

    if config.REDDIT_CLIENT_ID:
        sources.append(RedditSource())
    if config.YOUTUBE_API_KEY:
        sources.append(YouTubeSource())
    if config.X_BEARER_TOKEN:
        sources.append(XSource())
    if config.NEWSAPI_KEY:
        sources.append(NewsSource())

    if not sources:
        logger.error(
            "No data sources configured! Please set API keys in .env file."
        )
        return {}

    logger.info("Fetching from %d sources: %s",
                len(sources), [s.name for s in sources])

    # 并发抓取
    tasks = [source.fetch(config.SEARCH_QUERIES) for source in sources]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    # 按分类整理
    items_by_category: dict[str, List[NewsItem]] = defaultdict(list)
    for result in results:
        if isinstance(result, Exception):
            logger.error("Source fetch failed: %s", result)
            continue
        for item in result:
            cat = item.category or "其他"
            items_by_category[cat].append(item)

    # 每个分类按热度/时间排序（优先看 extra 里的 score）
    for cat in items_by_category:
        items_by_category[cat].sort(
            key=lambda x: x.extra.get("score", 0), reverse=True
        )

    total = sum(len(v) for v in items_by_category.values())
    logger.info("Collected %d items across %d categories",
                total, len(items_by_category))
    return dict(items_by_category)


async def run_digest() -> None:
    """执行一次完整的每日简报流程。"""
    date_str = datetime.now().strftime("%Y-%m-%d")
    logger.info("===== 每日简报 %s =====", date_str)

    # 1. 抓取新闻
    items_by_category = await collect_news()
    if not items_by_category:
        logger.warning("No news items collected, aborting.")
        return

    # 2. 创建飞书文档
    try:
        doc_id, doc_url = await create_daily_doc(items_by_category, date_str)
        logger.info("Document created: %s", doc_url)
    except Exception:
        logger.exception("Failed to create Feishu document")
        return

    # 3. 推送飞书消息
    try:
        await send_digest_message(items_by_category, doc_url, date_str)
        logger.info("Digest message sent successfully!")
    except Exception:
        logger.exception("Failed to send Feishu message")

    logger.info("===== 简报完成 =====")


async def run_scheduled(hour: int = 8, minute: int = 0) -> None:
    """定时执行，每天指定时间运行。"""
    from zoneinfo import ZoneInfo

    tz = ZoneInfo(config.TIMEZONE)
    logger.info("Scheduled mode: will run daily at %02d:%02d (%s)",
                hour, minute, config.TIMEZONE)

    while True:
        now = datetime.now(tz)
        target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if target <= now:
            # 已过今天的时间，等到明天
            from datetime import timedelta
            target += timedelta(days=1)

        wait_seconds = (target - now).total_seconds()
        logger.info("Next run at %s (in %.0f seconds)", target, wait_seconds)
        await asyncio.sleep(wait_seconds)
        await run_digest()


def main() -> None:
    parser = argparse.ArgumentParser(description="每日简报助手")
    parser.add_argument(
        "--schedule", action="store_true",
        help="启用定时模式，每天早上 8:00 自动执行",
    )
    parser.add_argument(
        "--hour", type=int, default=8,
        help="定时执行的小时（24h 制，默认 8）",
    )
    parser.add_argument(
        "--minute", type=int, default=0,
        help="定时执行的分钟（默认 0）",
    )
    args = parser.parse_args()

    if args.schedule:
        asyncio.run(run_scheduled(args.hour, args.minute))
    else:
        asyncio.run(run_digest())


if __name__ == "__main__":
    main()
