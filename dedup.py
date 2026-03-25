"""简单的跨天去重模块 —— 记录最近推送过的 URL，避免连续多天推送相同内容。

使用本地 JSON 文件存储，保留最近 7 天的记录。
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import List

from sources.base import NewsItem

logger = logging.getLogger(__name__)

_DEDUP_FILE = Path("/tmp/news-digest-dedup.json")
_KEEP_DAYS = 7


def _load_history() -> dict[str, str]:
    """加载历史 URL 记录。格式: {url: date_str}"""
    if not _DEDUP_FILE.exists():
        return {}
    try:
        data = json.loads(_DEDUP_FILE.read_text())
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _save_history(history: dict[str, str]) -> None:
    """保存历史记录，清理超过 _KEEP_DAYS 天的旧记录。"""
    cutoff = (datetime.now() - timedelta(days=_KEEP_DAYS)).strftime("%Y-%m-%d")
    cleaned = {url: date for url, date in history.items() if date >= cutoff}
    try:
        _DEDUP_FILE.write_text(json.dumps(cleaned, ensure_ascii=False))
    except Exception:
        logger.warning("Failed to save dedup history")


def dedup_items(items: List[NewsItem]) -> List[NewsItem]:
    """过滤掉最近已推送过的条目，并将新条目记录到历史中。"""
    history = _load_history()
    today = datetime.now().strftime("%Y-%m-%d")

    new_items: List[NewsItem] = []
    for item in items:
        if item.url in history:
            continue
        new_items.append(item)
        history[item.url] = today

    removed = len(items) - len(new_items)
    if removed > 0:
        logger.info("Dedup: removed %d repeated items, %d remaining", removed, len(new_items))

    _save_history(history)
    return new_items
