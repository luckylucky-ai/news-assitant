"""飞书消息推送模块 —— 发送每日简报摘要到飞书。"""

from __future__ import annotations

import json
import logging
from typing import List

import httpx

import config
from feishu.auth import get_tenant_token
from sources.base import NewsItem

logger = logging.getLogger(__name__)

SEND_MSG_URL = "https://open.feishu.cn/open-apis/im/v1/messages"


async def send_digest_message(
    items_by_category: dict[str, List[NewsItem]],
    doc_url: str,
    date_str: str,
) -> None:
    """发送每日简报卡片消息到飞书。"""
    token = await get_tenant_token()
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }

    card = _build_card(items_by_category, doc_url, date_str)

    receive_ids = [
        rid.strip()
        for rid in config.FEISHU_RECEIVE_ID.split(",")
        if rid.strip()
    ]

    async with httpx.AsyncClient(timeout=30) as client:
        for receive_id in receive_ids:
            body = {
                "receive_id": receive_id,
                "msg_type": "interactive",
                "content": json.dumps(card),
            }
            resp = await client.post(
                SEND_MSG_URL,
                headers=headers,
                params={"receive_id_type": config.FEISHU_RECEIVE_ID_TYPE},
                json=body,
            )
            resp.raise_for_status()
            result = resp.json()
            if result.get("code") != 0:
                logger.error(
                    "Send message failed for %s: %s", receive_id, result
                )
            else:
                logger.info("Message sent to %s", receive_id)


def _build_card(
    items_by_category: dict[str, List[NewsItem]],
    doc_url: str,
    date_str: str,
) -> dict:
    """构建飞书交互卡片。"""
    elements: list[dict] = []

    category_icons = {"政治": "📌", "AI": "🤖", "投资": "📈"}

    for category in ["政治", "AI", "投资"]:
        items = items_by_category.get(category, [])
        if not items:
            continue

        icon = category_icons.get(category, "📄")
        # 分类标题
        elements.append({
            "tag": "markdown",
            "content": f"**{icon} {category}**",
        })

        # 列出前 5 条（简报消息只展示标题和链接）
        lines = []
        for item in items[:5]:
            lines.append(f"• [{item.title[:60]}]({item.url})")
        elements.append({
            "tag": "markdown",
            "content": "\n".join(lines),
        })

        elements.append({"tag": "hr"})

    # 底部：查看完整文档的按钮
    elements.append({
        "tag": "action",
        "actions": [
            {
                "tag": "button",
                "text": {"tag": "plain_text", "content": "📄 查看完整简报文档"},
                "url": doc_url,
                "type": "primary",
            }
        ],
    })

    card = {
        "config": {"wide_screen_mode": True},
        "header": {
            "title": {
                "tag": "plain_text",
                "content": f"📰 每日简报 - {date_str}",
            },
            "template": "blue",
        },
        "elements": elements,
    }
    return card
