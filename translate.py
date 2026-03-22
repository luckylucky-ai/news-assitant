"""轻量级翻译模块 —— 使用 Google 免费翻译 API 将英文翻译为中文。

无需 API Key，使用 httpx（已有依赖）直接调用。
"""

from __future__ import annotations

import asyncio
import logging
from typing import List
from urllib.parse import quote

import httpx

from sources.base import NewsItem

logger = logging.getLogger(__name__)

_TRANSLATE_URL = "https://translate.googleapis.com/translate_a/single"


async def _translate_text(
    client: httpx.AsyncClient, text: str, src: str = "en", dest: str = "zh-CN"
) -> str:
    """翻译单段文本。"""
    if not text or not text.strip():
        return ""

    try:
        resp = await client.get(
            _TRANSLATE_URL,
            params={
                "client": "gtx",
                "sl": src,
                "tl": dest,
                "dt": "t",
                "q": text,
            },
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
        # 响应格式: [[["翻译结果","原文",null,null,10],...],null,"en",...]
        translated = "".join(seg[0] for seg in data[0] if seg[0])
        return translated
    except Exception:
        logger.warning("Translation failed for: %s", text[:60])
        return ""


def _is_chinese(text: str) -> bool:
    """检查文本是否已经主要是中文。"""
    chinese_chars = sum(1 for c in text if "\u4e00" <= c <= "\u9fff")
    return chinese_chars > len(text) * 0.3


async def translate_items(items: List[NewsItem]) -> None:
    """批量翻译 NewsItem 的 title 和 summary，结果写入 title_zh / summary_zh。

    已经是中文的内容会跳过。为避免速率限制，请求间有短暂延迟。
    """
    to_translate: list[tuple[int, str, str]] = []  # (index, field, text)

    for i, item in enumerate(items):
        if not _is_chinese(item.title) and item.title.strip():
            to_translate.append((i, "title", item.title))
        else:
            item.title_zh = item.title  # 已经是中文

        if not _is_chinese(item.summary) and item.summary.strip():
            to_translate.append((i, "summary", item.summary[:200]))
        else:
            item.summary_zh = item.summary

    if not to_translate:
        logger.info("No items need translation")
        return

    logger.info("Translating %d texts...", len(to_translate))

    async with httpx.AsyncClient() as client:
        for idx, field_name, text in to_translate:
            translated = await _translate_text(client, text)
            if field_name == "title":
                items[idx].title_zh = translated
            else:
                items[idx].summary_zh = translated
            # 避免请求过快被限流
            await asyncio.sleep(0.3)

    translated_count = sum(
        1 for item in items if item.title_zh and item.title_zh != item.title
    )
    logger.info("Translation done: %d/%d items translated", translated_count, len(items))
