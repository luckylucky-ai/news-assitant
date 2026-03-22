"""每日简报助手 —— 主入口。

通过 MCP Server 抓取 X、YouTube、Reddit 内容，
结合 NewsAPI 新闻，生成飞书文档并推送消息。

运行模式（RUN_MODE 环境变量）：
    schedule  - 持续运行，每天定时执行
    cron      - 执行一次后退出（适合 Railway Cron Job）
    server    - 启动 HTTP 服务，通过 POST /trigger 手动触发
"""

from __future__ import annotations

import argparse
import asyncio
import logging
from collections import defaultdict
from datetime import datetime
from typing import List

import os

import config
from sources.base import NewsItem
from sources.reddit_source import RedditSource
from sources.youtube_source import YouTubeSource
from sources.x_source import XSource
from sources.news_source import NewsSource
from feishu.docs import create_daily_doc
from feishu.message import send_digest_message
from translate import translate_items

logging.basicConfig(
    level=getattr(logging, config.LOG_LEVEL, logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("daily-digest")


async def collect_news() -> dict[str, List[NewsItem]]:
    """从所有数据源并发抓取新闻，按分类整理。"""
    sources = []

    # Reddit MCP 无需 API Key 也能用（匿名模式）
    sources.append(RedditSource())

    if config.YOUTUBE_API_KEY:
        sources.append(YouTubeSource())
    if config.X_API_KEY:
        sources.append(XSource())
    if config.NEWSAPI_KEY:
        sources.append(NewsSource())

    logger.info("Fetching from %d sources: %s",
                len(sources), [s.name for s in sources])

    # 并发抓取，传入分类关键词
    tasks = [source.fetch(config.SEARCH_QUERIES) for source in sources]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    # 按分类整理
    items_by_category: dict[str, List[NewsItem]] = defaultdict(list)
    for result in results:
        if isinstance(result, Exception):
            logger.error("Source fetch failed: %s", result)
            continue
        for item in result:
            # 过滤掉标题为空的条目
            if not item.title or not item.title.strip():
                continue
            cat = item.category or "其他"
            items_by_category[cat].append(item)

    # 按热度排序
    for cat in items_by_category:
        items_by_category[cat].sort(
            key=lambda x: x.extra.get("score", x.extra.get("views", 0)),
            reverse=True,
        )

    total = sum(len(v) for v in items_by_category.values())
    logger.info("Collected %d items across %d categories",
                total, len(items_by_category))

    # 翻译所有非中文条目
    all_items = [item for items in items_by_category.values() for item in items]
    if all_items:
        try:
            await translate_items(all_items)
        except Exception:
            logger.exception("Translation step failed, continuing without translations")

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
    from datetime import timedelta

    tz = ZoneInfo(config.TIMEZONE)
    logger.info("Scheduled mode: will run daily at %02d:%02d (%s)",
                hour, minute, config.TIMEZONE)

    while True:
        now = datetime.now(tz)
        target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if target <= now:
            target += timedelta(days=1)

        wait_seconds = (target - now).total_seconds()
        logger.info("Next run at %s (in %.0f seconds)", target, wait_seconds)
        await asyncio.sleep(wait_seconds)
        await run_digest()


async def run_server(port: int = 8080) -> None:
    """启动 HTTP 服务，通过 POST /trigger 手动触发简报。

    同时在后台运行定时任务。适合部署到 Railway 等平台，
    既能定时执行，又能随时手动触发。
    """
    from aiohttp import web

    _running = False

    async def handle_trigger(request: web.Request) -> web.Response:
        nonlocal _running
        if _running:
            return web.json_response({"status": "busy", "message": "简报正在生成中，请稍后"}, status=409)
        _running = True
        try:
            await run_digest()
            return web.json_response({"status": "ok", "message": "简报已生成并推送"})
        except Exception as e:
            logger.exception("Manual trigger failed")
            return web.json_response({"status": "error", "message": str(e)}, status=500)
        finally:
            _running = False

    async def handle_health(request: web.Request) -> web.Response:
        return web.json_response({"status": "healthy"})

    app = web.Application()
    app.router.add_post("/trigger", handle_trigger)
    app.router.add_get("/health", handle_health)
    app.router.add_get("/", handle_health)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    logger.info("HTTP server started on port %d — POST /trigger to run digest", port)

    # 同时运行定时任务
    await run_scheduled(config.SCHEDULE_HOUR, config.SCHEDULE_MINUTE)


def main() -> None:
    parser = argparse.ArgumentParser(description="每日简报助手")
    parser.add_argument(
        "--schedule", action="store_true",
        help="启用定时模式，每天定时自动执行",
    )
    parser.add_argument(
        "--server", action="store_true",
        help="启动 HTTP 服务器模式（含定时 + 手动触发）",
    )
    parser.add_argument(
        "--hour", type=int, default=config.SCHEDULE_HOUR,
        help="定时执行的小时（24h 制，默认 8）",
    )
    parser.add_argument(
        "--minute", type=int, default=config.SCHEDULE_MINUTE,
        help="定时执行的分钟（默认 0）",
    )
    parser.add_argument(
        "--port", type=int, default=int(os.environ.get("PORT", "8080")),
        help="HTTP 服务器端口（默认 8080 或 $PORT）",
    )
    args = parser.parse_args()

    run_mode = config.RUN_MODE
    if args.schedule:
        run_mode = "schedule"
    if args.server:
        run_mode = "server"

    if run_mode == "server":
        asyncio.run(run_server(args.port))
    elif run_mode == "schedule":
        asyncio.run(run_scheduled(args.hour, args.minute))
    else:
        asyncio.run(run_digest())


if __name__ == "__main__":
    main()
