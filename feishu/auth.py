"""飞书鉴权 —— 使用 lark-oapi SDK 创建全局 Client。"""

from __future__ import annotations

import lark_oapi as lark

import config

_client: lark.Client | None = None


def get_client() -> lark.Client:
    """获取飞书 SDK Client 单例。"""
    global _client
    if _client is None:
        _client = lark.Client.builder() \
            .app_id(config.FEISHU_APP_ID) \
            .app_secret(config.FEISHU_APP_SECRET) \
            .log_level(lark.LogLevel.INFO) \
            .build()
    return _client
