# Web3 Security Intelligence 后端镜像
# 构建上下文 = 项目根目录 (backend 与 frontend 一起打进镜像, FastAPI 静态托管前端)
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    TZ=Asia/Shanghai

WORKDIR /app

# 依赖层 (利用构建缓存)
COPY backend/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# 应用代码与前端静态资源
COPY backend/app /app/app
COPY backend/run.py /app/run.py
COPY frontend /app/frontend

# 容器内运行环境: SQLite 数据落盘到 /app/data (由 compose 卷持久化), 前端目录指向 /app/frontend
ENV DATABASE_URL=sqlite:////app/data/web3_security.db \
    FRONTEND_DIR=/app/frontend \
    LOG_DIR=/app/logs

# SQLite 数据与日志目录
RUN mkdir -p /app/data /app/logs

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
