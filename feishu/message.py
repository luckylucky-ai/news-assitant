"""飞书消息推送模块 —— 通过机器人发送每日简报到群聊。"""

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
BOT_CHATS_URL = "https://open.feishu.cn/open-apis/im/v1/chats"


async def _get_bot_chat_ids() -> list[str]:
    """获取机器人所在的所有群聊 chat_id。"""
    # 如果配置了指定的 chat_id，直接用
    if config.FEISHU_CHAT_ID:
        return [cid.strip() for cid in config.FEISHU_CHAT_ID.split(",") if cid.strip()]

    # 否则自动获取机器人加入的群列表
    token = await get_tenant_token()
    headers = {"Authorization": f"Bearer {token}"}

    chat_ids: list[str] = []
    page_token = ""

    async with httpx.AsyncClient(timeout=30) as client:
        while True:
            params: dict = {"page_size": 50}
            if page_token:
                params["page_token"] = page_token

            resp = await client.get(BOT_CHATS_URL, headers=headers, params=params)
            resp.raise_for_status()
            data = resp.json()

            if data.get("code") != 0:
                logger.error("Failed to list bot chats: %s", data)
                break

            for item in data.get("data", {}).get("items", []):
                chat_ids.append(item["chat_id"])

            page_token = data.get("data", {}).get("page_token", "")
            if not data.get("data", {}).get("has_more"):
                break

    logger.info("Found %d chat(s) for bot", len(chat_ids))
    return chat_ids


async def send_digest_message(
    items_by_category: dict[str, List[NewsItem]],
    doc_url: str,
    date_str: str,
) -> None:
    """发送每日简报卡片消息到机器人所在的群聊。"""
    token = await get_tenant_token()
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }

    card = _build_card(items_by_category, doc_url, date_str)
    chat_ids = await _get_bot_chat_ids()

    if not chat_ids:
        logger.warning("Bot is not in any chat group. Please add the bot to a group first.")
        return

    async with httpx.AsyncClient(timeout=30) as client:
        for chat_id in chat_ids:
            body = {
                "receive_id": chat_id,
                "msg_type": "interactive",
                "content": json.dumps(card),
            }
            resp = await client.post(
                SEND_MSG_URL,
                headers=headers,
                params={"receive_id_type": "chat_id"},
                json=body,
            )
            resp.raise_for_status()
            result = resp.json()
            if result.get("code") != 0:
                logger.error("Send message failed for chat %s: %s", chat_id, result)
            else:
                logger.info("Message sent to chat %s", chat_id)


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
        elements.append({
            "tag": "markdown",
            "content": f"**{icon} {category}**",
        })

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
