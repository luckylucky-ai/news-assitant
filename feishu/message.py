"""飞书消息推送模块 —— 使用 lark-oapi SDK 通过机器人发送消息到群聊。"""

from __future__ import annotations

import json
import logging
from typing import List

import lark_oapi as lark
from lark_oapi.api.im.v1 import *

import config
from feishu.auth import get_client
from sources.base import NewsItem

logger = logging.getLogger(__name__)


def _get_bot_chat_ids(client: lark.Client) -> list[str]:
    """获取机器人所在的所有群聊 chat_id。"""
    if config.FEISHU_CHAT_ID:
        return [cid.strip() for cid in config.FEISHU_CHAT_ID.split(",") if cid.strip()]

    chat_ids: list[str] = []
    page_token = ""

    while True:
        req_builder = ListChatRequest.builder().page_size(50)
        if page_token:
            req_builder = req_builder.page_token(page_token)
        req = req_builder.build()

        resp = client.im.v1.chat.list(req)
        if not resp.success():
            logger.error("Failed to list bot chats: code=%s, msg=%s", resp.code, resp.msg)
            break

        if resp.data and resp.data.items:
            for item in resp.data.items:
                chat_ids.append(item.chat_id)

        if not resp.data or not resp.data.has_more:
            break
        page_token = resp.data.page_token or ""

    logger.info("Found %d chat(s) for bot", len(chat_ids))
    return chat_ids


async def send_digest_message(
    items_by_category: dict[str, List[NewsItem]],
    doc_url: str,
    date_str: str,
) -> None:
    """发送每日简报卡片消息到机器人所在的群聊。"""
    client = get_client()
    card = _build_card(items_by_category, doc_url, date_str)
    chat_ids = _get_bot_chat_ids(client)

    if not chat_ids:
        logger.warning("Bot is not in any chat group. Please add the bot to a group first.")
        return

    for chat_id in chat_ids:
        req = CreateMessageRequest.builder() \
            .receive_id_type("chat_id") \
            .request_body(
                CreateMessageRequestBody.builder()
                .receive_id(chat_id)
                .msg_type("interactive")
                .content(json.dumps(card))
                .build()
            ).build()

        resp = client.im.v1.message.create(req)
        if not resp.success():
            logger.error("Send message failed for chat %s: code=%s, msg=%s",
                         chat_id, resp.code, resp.msg)
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
        elements.append({"tag": "markdown", "content": f"**{icon} {category}**"})

        lines = []
        for item in items[:5]:
            title_display = item.title[:60]
            # 如果有中文翻译且与原文不同，显示翻译
            if item.title_zh and item.title_zh != item.title:
                lines.append(f"• [{title_display}]({item.url})\n  {item.title_zh[:60]}")
            else:
                lines.append(f"• [{title_display}]({item.url})")
        elements.append({"tag": "markdown", "content": "\n".join(lines)})
        elements.append({"tag": "hr"})

    elements.append({
        "tag": "action",
        "actions": [{
            "tag": "button",
            "text": {"tag": "plain_text", "content": "📄 查看完整简报文档"},
            "url": doc_url,
            "type": "primary",
        }],
    })

    return {
        "config": {"wide_screen_mode": True},
        "header": {
            "title": {"tag": "plain_text", "content": f"📰 每日简报 - {date_str}"},
            "template": "blue",
        },
        "elements": elements,
    }
