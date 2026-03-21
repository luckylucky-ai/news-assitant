FROM python:3.12-slim

# 安装 Node.js（MCP Server 需要 npx）
RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y --no-install-recommends nodejs \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 预安装 MCP Server npm 包，避免每次运行时下载
RUN npx -y @enescinar/twitter-mcp --help 2>/dev/null || true \
    && npx -y reddit-mcp-buddy --help 2>/dev/null || true \
    && npx -y @kirbah/mcp-youtube --help 2>/dev/null || true

COPY . .

CMD ["python", "main.py", "--schedule"]
