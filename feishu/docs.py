"""飞书文档模块 —— 创建文档并写入每日简报内容。

使用飞书文档 API：
- 创建文档 (docx)
- 写入富文本内容（包含原文链接）
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import List

import httpx

import config
from feishu.auth import get_tenant_token
from sources.base import NewsItem

logger = logging.getLogger(__name__)

CREATE_DOC_URL = "https://open.feishu.cn/open-apis/docx/v1/documents"
CREATE_BLOCK_CHILDREN_URL = (
    "https://open.feishu.cn/open-apis/docx/v1/documents/{document_id}"
    "/blocks/{block_id}/children"
)


async def _headers() -> dict:
    token = await get_tenant_token()
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }


async def create_daily_doc(
    items_by_category: dict[str, List[NewsItem]],
    date_str: str | None = None,
) -> tuple[str, str]:
    """创建每日简报文档。

    Returns:
        (document_id, document_url)
    """
    if date_str is None:
        date_str = datetime.now().strftime("%Y-%m-%d")

    title = f"每日简报 - {date_str}"
    headers = await _headers()

    # 1) 创建空文档
    async with httpx.AsyncClient(timeout=30) as client:
        create_params = {"title": title}
        if config.FEISHU_FOLDER_TOKEN:
            create_params["folder_token"] = config.FEISHU_FOLDER_TOKEN

        resp = await client.post(CREATE_DOC_URL, headers=headers, json=create_params)
        resp.raise_for_status()
        doc_data = resp.json()

    if doc_data.get("code") != 0:
        raise RuntimeError(f"Create doc failed: {doc_data}")

    document = doc_data["data"]["document"]
    document_id = document["document_id"]
    document_url = f"https://feishu.cn/docx/{document_id}"
    root_block_id = document_id  # 文档根 block_id 等于 document_id

    logger.info("Created Feishu doc: %s (%s)", title, document_url)

    # 2) 向文档写入内容
    blocks = _build_content_blocks(items_by_category, date_str)
    await _batch_create_blocks(document_id, root_block_id, blocks, headers)

    return document_id, document_url


def _build_content_blocks(
    items_by_category: dict[str, List[NewsItem]],
    date_str: str,
) -> list[dict]:
    """构建飞书文档 block 列表。"""
    blocks: list[dict] = []

    # 日期副标题
    blocks.append(_text_block(f"日期：{date_str}  |  自动生成", heading=2))

    category_order = ["政治", "AI", "投资"]
    for category in category_order:
        items = items_by_category.get(category, [])
        if not items:
            continue

        # 分类标题
        blocks.append(_text_block(f"{'📌' if category == '政治' else '🤖' if category == 'AI' else '📈'} {category}", heading=3))

        for idx, item in enumerate(items, 1):
            # 每条新闻：标题（含链接）+ 摘要 + 来源
            title_elements = [
                {
                    "tag": "textRun",
                    "textRun": {
                        "content": f"{idx}. {item.title}",
                        "textElementStyle": {
                            "link": {"url": item.url},
                            "bold": True,
                        },
                    },
                }
            ]
            blocks.append({
                "block_type": 2,  # text
                "text": {"style": {}, "elements": title_elements},
            })

            # 摘要
            if item.summary:
                summary_text = item.summary[:200]
                blocks.append(_plain_text_block(f"   {summary_text}"))

            # 来源信息
            source_line = f"   来源: {item.source}"
            if item.author:
                source_line += f" | 作者: {item.author}"
            blocks.append(_plain_text_block(source_line))

            # 原文链接（单独一行，方便点击）
            link_elements = [
                {
                    "tag": "textRun",
                    "textRun": {
                        "content": "   🔗 查看原文",
                        "textElementStyle": {
                            "link": {"url": item.url},
                        },
                    },
                }
            ]
            blocks.append({
                "block_type": 2,
                "text": {"style": {}, "elements": link_elements},
            })

        # 分隔线
        blocks.append({"block_type": 22})  # divider

    return blocks


def _text_block(text: str, heading: int = 0) -> dict:
    """创建一个文本/标题 block。"""
    block: dict = {
        "block_type": 3 if heading else 2,  # 3=heading, 2=text
        "text": {
            "style": {},
            "elements": [
                {
                    "tag": "textRun",
                    "textRun": {
                        "content": text,
                        "textElementStyle": {},
                    },
                }
            ],
        },
    }
    if heading:
        block["text"]["style"]["headingLevel"] = heading
    return block


def _plain_text_block(text: str) -> dict:
    return {
        "block_type": 2,
        "text": {
            "style": {},
            "elements": [
                {
                    "tag": "textRun",
                    "textRun": {
                        "content": text,
                        "textElementStyle": {},
                    },
                }
            ],
        },
    }


async def _batch_create_blocks(
    document_id: str,
    parent_block_id: str,
    blocks: list[dict],
    headers: dict,
) -> None:
    """分批向文档写入 blocks（飞书限制每次最多 50 个）。"""
    url = CREATE_BLOCK_CHILDREN_URL.format(
        document_id=document_id, block_id=parent_block_id
    )
    batch_size = 50

    async with httpx.AsyncClient(timeout=30) as client:
        for i in range(0, len(blocks), batch_size):
            batch = blocks[i : i + batch_size]
            resp = await client.post(
                url,
                headers=headers,
                json={"children": batch},
            )
            resp.raise_for_status()
            result = resp.json()
            if result.get("code") != 0:
                logger.error("Batch create blocks failed: %s", result)
