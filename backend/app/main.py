"""FastAPI 应用入口."""
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api import corrections, fetch, incidents, stats
from app.config import settings
from app.database import Base, SessionLocal, engine
from app.logging_config import setup_logging
from app.services.scheduler import start_scheduler, stop_scheduler
from app.services.seed import seed_incidents

setup_logging()
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 1. 建表
    Base.metadata.create_all(bind=engine)
    # 2. 首次启动填充历史事件
    db = SessionLocal()
    try:
        if settings.SEED_ON_STARTUP:
            created = seed_incidents(db)
            if created:
                logger.info("[startup] 已初始化 %s 起历史安全事件", created)
    finally:
        db.close()
    # 3. 启动每小时定时抓取
    start_scheduler()
    # 4. 数据源自检 (诊断真实源可达性, 不阻断启动)
    try:
        from app.services.fetcher import check_source_reachability
        logger.info("[startup] 数据源自检结果: %s", check_source_reachability())
    except Exception as exc:  # noqa: BLE001 - 自检失败不影响启动
        logger.warning("[startup] 数据源自检异常: %s", exc)
    yield
    stop_scheduler()


app = FastAPI(
    title=settings.APP_NAME,
    version="1.0.0",
    description="Web3 全网安全事件抓取与分析平台后端",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(incidents.router, prefix=settings.API_PREFIX, tags=["incidents"])
app.include_router(corrections.router, prefix=settings.API_PREFIX, tags=["corrections"])
app.include_router(stats.router, prefix=settings.API_PREFIX, tags=["stats"])
app.include_router(fetch.router, prefix=settings.API_PREFIX, tags=["fetch"])


@app.get("/health", tags=["meta"])
def health() -> dict:
    return {"status": "ok"}


# 挂载前端静态资源 (必须放在最后: 兜底 "/" 路由, 不影响已注册的 /api/* 路由)
_static_dir = Path(settings.FRONTEND_DIR)
if _static_dir.is_dir():
    app.mount("/", StaticFiles(directory=str(_static_dir), html=True), name="static")
    logger.info("[static] 前端页面挂载: %s", _static_dir)
else:
    logger.warning("[static] 未找到前端目录 %s, 跳过静态挂载", _static_dir)
