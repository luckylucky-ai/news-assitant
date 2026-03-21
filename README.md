# 每日简报助手 (Daily Digest Assistant)

自动抓取 X、YouTube、Reddit 和新闻媒体上关于 **政治、AI、投资** 的热点内容，生成飞书文档并推送简报消息。

## 功能

- **多源抓取**：X (Twitter)、YouTube、Reddit、NewsAPI
- **三大话题**：政治、AI、投资
- **飞书文档**：自动创建文档，包含详细内容和原文链接
- **飞书消息**：推送卡片消息，包含摘要和文档链接
- **定时执行**：支持每天定时自动运行

## 项目结构

```
news-assitant/
├── main.py                 # 主入口
├── config.py               # 配置管理
├── requirements.txt        # Python 依赖
├── .env.example            # 环境变量模板
├── sources/                # 数据源
│   ├── base.py             # 基类和数据结构
│   ├── reddit_source.py    # Reddit 抓取
│   ├── youtube_source.py   # YouTube 抓取
│   ├── x_source.py         # X/Twitter 抓取
│   └── news_source.py      # 新闻媒体抓取
└── feishu/                 # 飞书集成
    ├── auth.py             # 飞书鉴权
    ├── docs.py             # 飞书文档创建
    └── message.py          # 飞书消息推送
```

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 配置环境变量

```bash
cp .env.example .env
# 编辑 .env 填入你的 API 密钥
```

### 3. 运行

```bash
# 立即执行一次
python main.py

# 定时模式（每天 8:00 自动执行）
python main.py --schedule

# 自定义时间（每天 9:30）
python main.py --schedule --hour 9 --minute 30
```

## API 密钥获取

| 服务 | 获取方式 |
|------|---------|
| 飞书 | [飞书开放平台](https://open.feishu.cn/) 创建应用，开通文档和消息权限 |
| Reddit | [Reddit Apps](https://www.reddit.com/prefs/apps) 创建 script 类型应用 |
| YouTube | [Google Cloud Console](https://console.cloud.google.com/) 启用 YouTube Data API v3 |
| X/Twitter | [Twitter Developer Portal](https://developer.twitter.com/) 获取 Bearer Token |
| NewsAPI | [newsapi.org](https://newsapi.org/) 注册获取 API Key |

## 飞书应用权限

创建飞书应用后，需要开通以下权限：

- `docx:document` - 创建和编辑文档
- `im:message:create` - 发送消息
- `drive:drive` - 访问云空间（如需指定文件夹）

## 注意事项

- 不是所有数据源都必须配置，未配置的会自动跳过
- 建议至少配置一个数据源 + 飞书
- X API 免费版有速率限制，可能需要付费方案
- NewsAPI 免费版仅支持过去 24 小时的内容
