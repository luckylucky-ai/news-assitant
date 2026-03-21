"""所有数据源的基类和通用数据结构。"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import List

logger = logging.getLogger(__name__)


@dataclass
class NewsItem:
    """一条新闻/帖子的通用表示。"""
    title: str
    url: str
    source: str  # e.g. "Reddit", "X", "YouTube", "NewsAPI"
    summary: str = ""
    author: str = ""
    published_at: str = ""
    category: str = ""  # 政治 / AI / 投资
    extra: dict = field(default_factory=dict)

    def to_display(self) -> str:
        parts = [f"[{self.source}] {self.title}"]
        if self.summary:
            parts.append(f"  摘要: {self.summary[:120]}")
        parts.append(f"  链接: {self.url}")
        return "\n".join(parts)


class BaseSource:
    """数据源基类。"""

    name: str = "base"

    async def fetch(self, queries: List[str]) -> List[NewsItem]:
        raise NotImplementedError
