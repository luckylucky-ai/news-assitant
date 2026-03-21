"""集中管理所有配置项，从环境变量读取。"""

import os
from dotenv import load_dotenv

load_dotenv()

# ---------- 飞书 ----------
FEISHU_APP_ID = os.getenv("FEISHU_APP_ID", "")
FEISHU_APP_SECRET = os.getenv("FEISHU_APP_SECRET", "")
FEISHU_FOLDER_TOKEN = os.getenv("FEISHU_FOLDER_TOKEN", "")
# 可选：指定群聊 chat_id，不填则自动发送到机器人所在的所有群
FEISHU_CHAT_ID = os.getenv("FEISHU_CHAT_ID", "")

# ---------- X / Twitter (MCP Server 需要) ----------
X_API_KEY = os.getenv("X_API_KEY", "")
X_API_SECRET_KEY = os.getenv("X_API_SECRET_KEY", "")
X_ACCESS_TOKEN = os.getenv("X_ACCESS_TOKEN", "")
X_ACCESS_TOKEN_SECRET = os.getenv("X_ACCESS_TOKEN_SECRET", "")

# ---------- Reddit (MCP Server, 可选) ----------
REDDIT_CLIENT_ID = os.getenv("REDDIT_CLIENT_ID", "")
REDDIT_CLIENT_SECRET = os.getenv("REDDIT_CLIENT_SECRET", "")

# ---------- YouTube (MCP Server 需要) ----------
YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY", "")

# ---------- NewsAPI ----------
NEWSAPI_KEY = os.getenv("NEWSAPI_KEY", "")

# ---------- 通用 ----------
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
TIMEZONE = os.getenv("TIMEZONE", "Asia/Shanghai")
RUN_MODE = os.getenv("RUN_MODE", "server")
SCHEDULE_HOUR = int(os.getenv("SCHEDULE_HOUR", "8"))
SCHEDULE_MINUTE = int(os.getenv("SCHEDULE_MINUTE", "0"))

# ---------- 话题搜索关键词 ----------
SEARCH_QUERIES = {
    "政治": ["politics news today", "geopolitics", "election"],
    "AI": ["artificial intelligence news", "LLM AI", "OpenAI Claude GPT"],
    "投资": ["stock market today", "crypto bitcoin news", "Federal Reserve economy"],
}
