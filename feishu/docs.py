"""飞书文档模块 —— 使用 lark-oapi SDK 创建文档并写入内容。"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import List

import lark_oapi as lark
from lark_oapi.api.docx.v1 import *

import config
from feishu.auth import get_client
from sources.base import NewsItem

logger = logging.getLogger(__name__)


async def create_daily_doc(
    items_by_category: dict[str, List[NewsItem]],
    date_str: str | None = None,
) -> tuple[str, str]:
    """创建每日简报文档。Returns (document_id, document_url)。"""
    if date_str is None:
        date_str = datetime.now().strftime("%Y-%m-%d")

    title = f"每日简报 - {date_str}"
    client = get_client()

    # 1) 创建空文档
    create_req = CreateDocumentRequest.builder() \
        .request_body(
            CreateDocumentRequestBody.builder()
            .title(title)
            .folder_token(config.FEISHU_FOLDER_TOKEN or None)
            .build()
        ).build()

    create_resp = client.docx.v1.document.create(create_req)
    if not create_resp.success():
        raise RuntimeError(
            f"Create doc failed: code={create_resp.code}, msg={create_resp.msg}"
        )

    document = create_resp.data.document
    document_id = document.document_id
    document_url = f"https://feishu.cn/docx/{document_id}"
    logger.info("Created Feishu doc: %s (%s)", title, document_url)

    # 2) 写入内容
    blocks = _build_content_blocks(items_by_category, date_str)
    _batch_create_blocks(client, document_id, document_id, blocks)

    return document_id, document_url


def _build_content_blocks(
    items_by_category: dict[str, List[NewsItem]],
    date_str: str,
) -> list[dict]:
    """构建飞书文档 block 列表（使用原始 dict，SDK 会自动转为 Block 对象）。"""
    blocks: list[dict] = []

    # 日期副标题 (heading2 = block_type 4)
    blocks.append(_heading_block(f"日期：{date_str}  |  自动生成", level=2))

    category_icons = {"政治": "📌", "AI": "🤖", "投资": "📈"}
    for category in ["政治", "AI", "投资"]:
        items = items_by_category.get(category, [])
        if not items:
            continue

        icon = category_icons.get(category, "📄")
        blocks.append(_heading_block(f"{icon} {category}", level=3))

        for idx, item in enumerate(items, 1):
            encoded_url = _encode_url(item.url)
            # 标题（带链接 + 粗体）
            blocks.append({
                "block_type": 2,
                "text": {
                    "style": {},
                    "elements": [{
                        "text_run": {
                            "content": f"{idx}. {item.title}",
                            "text_element_style": {
                                "link": {"url": encoded_url},
                                "bold": True,
                            },
                        },
                    }],
                },
            })

            if item.summary:
                blocks.append(_text_block(f"   {item.summary[:200]}"))

            source_line = f"   来源: {item.source}"
            if item.author:
                source_line += f" | 作者: {item.author}"
            blocks.append(_text_block(source_line))

            # 原文链接
            blocks.append({
                "block_type": 2,
                "text": {
                    "style": {},
                    "elements": [{
                        "text_run": {
                            "content": "   🔗 查看原文",
                            "text_element_style": {"link": {"url": encoded_url}},
                        },
                    }],
                },
            })

        blocks.append({"block_type": 22, "divider": {}})

    return blocks


# 飞书 heading block_type: 3=h1, 4=h2, 5=h3, ..., 11=h9
_HEADING_BLOCK_TYPE = {1: 3, 2: 4, 3: 5, 4: 6, 5: 7, 6: 8, 7: 9, 8: 10, 9: 11}
_HEADING_KEY = {1: "heading1", 2: "heading2", 3: "heading3", 4: "heading4",
                5: "heading5", 6: "heading6", 7: "heading7", 8: "heading8", 9: "heading9"}


def _heading_block(text: str, level: int = 2) -> dict:
    block_type = _HEADING_BLOCK_TYPE.get(level, 4)
    key = _HEADING_KEY.get(level, "heading2")
    return {
        "block_type": block_type,
        key: {
            "elements": [{
                "text_run": {
                    "content": text,
                    "text_element_style": {},
                },
            }],
        },
    }


def _text_block(text: str) -> dict:
    return {
        "block_type": 2,
        "text": {
            "style": {},
            "elements": [{
                "text_run": {
                    "content": text,
                    "text_element_style": {},
                },
            }],
        },
    }


def _encode_url(url: str) -> str:
    """飞书 API 要求 URL 进行 percent-encoding。"""
    from urllib.parse import quote
    return quote(url, safe=":/?=&#")


def _batch_create_blocks(
    client: lark.Client,
    document_id: str,
    parent_block_id: str,
    blocks: list[dict],
) -> None:
    """分批向文档写入 blocks（飞书限制每次最多 50 个）。"""
    batch_size = 50
    for i in range(0, len(blocks), batch_size):
        batch = blocks[i : i + batch_size]
        # 使用原始 API 调用，因为 SDK 的 block builder 对嵌套结构支持有限
        req = CreateDocumentBlockChildrenRequest.builder() \
            .document_id(document_id) \
            .block_id(parent_block_id) \
            .request_body(
                CreateDocumentBlockChildrenRequestBody.builder()
                .children(batch)
                .build()
            ).build()

        resp = client.docx.v1.document_block_children.create(req)
        if not resp.success():
            logger.error("Batch create blocks failed: code=%s, msg=%s", resp.code, resp.msg)
