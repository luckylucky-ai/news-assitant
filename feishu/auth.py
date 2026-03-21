"""飞书鉴权 —— 获取 tenant_access_token。"""

from __future__ import annotations

import logging
import time

import httpx

import config

logger = logging.getLogger(__name__)

TOKEN_URL = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"

_cached_token: str = ""
_cached_expire: float = 0


async def get_tenant_token() -> str:
    """获取 tenant_access_token，带简单缓存。"""
    global _cached_token, _cached_expire

    if _cached_token and time.time() < _cached_expire - 60:
        return _cached_token

    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(
            TOKEN_URL,
            json={
                "app_id": config.FEISHU_APP_ID,
                "app_secret": config.FEISHU_APP_SECRET,
            },
        )
        resp.raise_for_status()
        data = resp.json()

    if data.get("code") != 0:
        raise RuntimeError(f"Failed to get tenant token: {data}")

    _cached_token = data["tenant_access_token"]
    _cached_expire = time.time() + data.get("expire", 7200)
    logger.info("Refreshed Feishu tenant_access_token")
    return _cached_token
