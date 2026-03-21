"""集中管理所有配置项，从环境变量读取。"""

import os
from dotenv import load_dotenv

load_dotenv()


# ---------- 飞书 ----------
FEISHU_APP_ID = os.getenv("FEISHU_APP_ID", "")
FEISHU_APP_SECRET = os.getenv("FEISHU_APP_SECRET", "")
FEISHU_RECEIVE_ID = os.getenv("FEISHU_RECEIVE_ID", "")
FEISHU_RECEIVE_ID_TYPE = os.getenv("FEISHU_RECEIVE_ID_TYPE", "open_id")
FEISHU_FOLDER_TOKEN = os.getenv("FEISHU_FOLDER_TOKEN", "")

# ---------- Reddit ----------
REDDIT_CLIENT_ID = os.getenv("REDDIT_CLIENT_ID", "")
REDDIT_CLIENT_SECRET = os.getenv("REDDIT_CLIENT_SECRET", "")
REDDIT_USER_AGENT = os.getenv("REDDIT_USER_AGENT", "DailyDigestBot/1.0")

# ---------- YouTube ----------
YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY", "")

# ---------- X / Twitter ----------
X_BEARER_TOKEN = os.getenv("X_BEARER_TOKEN", "")

# ---------- NewsAPI ----------
NEWSAPI_KEY = os.getenv("NEWSAPI_KEY", "")

# ---------- 通用 ----------
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
TIMEZONE = os.getenv("TIMEZONE", "Asia/Shanghai")

# ---------- 话题关键词 ----------
TOPICS = {
    "政治": {
        "en": ["politics", "election", "government", "geopolitics", "diplomacy", "sanction"],
        "zh": ["政治", "选举", "外交", "制裁", "地缘政治"],
    },
    "AI": {
        "en": ["artificial intelligence", "AI", "machine learning", "LLM", "GPT", "Claude", "deep learning"],
        "zh": ["人工智能", "大模型", "机器学习", "深度学习"],
    },
    "投资": {
        "en": ["investing", "stock market", "crypto", "bitcoin", "finance", "economy", "Fed", "interest rate"],
        "zh": ["投资", "股市", "加密货币", "比特币", "经济", "美联储", "利率"],
    },
}

# 用于各平台搜索的英文关键词（取每个分类的前两个）
SEARCH_QUERIES = []
for _cat, _kw in TOPICS.items():
    SEARCH_QUERIES.extend(_kw["en"][:3])
