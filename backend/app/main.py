"""FastAPI 应用入口."""
import logging
import threading
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api import corrections, extension, fetch, incidents, stats
from app.config import settings
from app.database import Base, SessionLocal, engine
from app.logging_config import setup_logging
from app.services.scheduler import start_scheduler, stop_scheduler
from app.services.seed import seed_incidents
from app.services.migrate import add_missing_columns, backfill_occurred_at_safe

setup_logging()
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Render 上数据库可能在启动瞬间不可达 (DNS 未就绪 / 免费实例睡眠唤醒).
    # lifespan yield 前完全不碰数据库 —— 让 uvicorn 立刻开始监听端口, Render 健康检查能通过.
    # create_all / 加列 / seed / 后台任务 全部放到后台线程执行.

    # 1. 启动定时抓取调度器 (纯内存操作, 不碰数据库)
    start_scheduler()

    # 2. 后台线程: 所有数据库操作 + 同步网络请求
    # 任何一步失败都 try/except, 不让线程崩溃
    def _run_bootstrap_and_checks():
        from app.database import Base, engine, SessionLocal

        # 2a. 建表 (首次连接数据库)
        try:
            Base.metadata.create_all(bind=engine)
            logger.info("[bootstrap] create_all 成功")
        except Exception as exc:  # noqa: BLE001
            logger.warning("[bootstrap] create_all 失败 (数据库暂不可达): %s", exc)
            return  # 后面的数据库操作也没必要做了

        # 2b. 快速加列
        try:
            add_missing_columns(engine)
        except Exception as exc:  # noqa: BLE001
            logger.warning("[bootstrap] 加列失败: %s", exc)

        # 2c. 首次启动填充历史事件
        try:
            db = SessionLocal()
            try:
                from app.config import settings as _s
                if _s.SEED_ON_STARTUP:
                    from app.services.seed import seed_incidents
                    created = seed_incidents(db)
                    if created:
                        logger.info("[bootstrap] 已初始化 %s 起历史安全事件", created)
            finally:
                db.close()
        except Exception as exc:  # noqa: BLE001
            logger.warning("[bootstrap] seed 失败: %s", exc)

        # 2d. backfill_occurred_at (60s network)
        try:
            backfill_occurred_at_safe()
        except Exception as exc:  # noqa: BLE001
            logger.warning("[bootstrap] backfill 失败: %s", exc)

        # 2e. 数据源自检 (~50s network)
        try:
            from app.services.fetcher import check_source_reachability
            logger.info("[bootstrap] 数据源自检结果: %s", check_source_reachability())
        except Exception as exc:  # noqa: BLE001
            logger.warning("[bootstrap] 数据源自检异常: %s", exc)

        # 2f. 合约捕捉路径巡检 (~0s)
        try:
            from app.database import SessionLocal as _AuditSessionLocal
            from app.services.contract_path import audit_contract_paths, audit_summary_text
            _db = _AuditSessionLocal()
            try:
                logger.info("[bootstrap] %s", audit_summary_text(audit_contract_paths(_db)))
            finally:
                _db.close()
        except Exception as exc:  # noqa: BLE001
            logger.warning("[bootstrap] 合约捕捉路径巡检异常: %s", exc)

    threading.Thread(target=_run_bootstrap_and_checks, daemon=True).start()
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
    # Chrome 扩展 (chrome-extension://<id>) 来源用正则放行, 不能写在 allow_origins 通配
    allow_origin_regex=r"chrome-extension://.*",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(incidents.router, prefix=settings.API_PREFIX, tags=["incidents"])
app.include_router(extension.router, prefix=settings.API_PREFIX, tags=["extension"])
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
