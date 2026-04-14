FROM python:3.11-slim

WORKDIR /app

# 复制依赖文件
COPY requirements.txt .

# 安装依赖
RUN pip install --no-cache-dir -r requirements.txt

# 复制代码
COPY app/ ./app/

# Railway injects $PORT; fall back to 8000 for local dev
ENV PORT=8000

# 暴露 PORT 环境变量指定的端口
EXPOSE ${PORT}

# 启动脚本：Railway injects $PORT，读取它传递给 uvicorn
# 本地默认 8000，Railway 部署时使用 $PORT
COPY start.sh /start.sh
RUN chmod +x /start.sh
CMD ["/start.sh"]
