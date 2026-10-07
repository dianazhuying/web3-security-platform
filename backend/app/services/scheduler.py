"""APScheduler 定时任务: 每小时自动抓取最新安全事件 (含执行日志与状态记录).

失败重试机制:
- 真实数据源层 (fetcher.run_fetch): 指数退避重试, 重试耗尽后回退模拟数据;
- 调度器层: max_instances=1 防止并发, coalesce 合并积压,
  misfire_grace_time 允许错过的执行在窗口内补跑。
"""
import logging
import time
from datetime import datetime, timezone
from typing import Optional

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger

from app.config import settings
from app.database import SessionLocal
from app.services.fetcher import run_fetch

logger = logging.getLogger("app.scheduler")

_scheduler: Optional[BackgroundScheduler] = None
_last_run: dict = {"status": "never", "at": None, "detail": ""}


def run_fetch_job() -> None:
    """定时任务执行体: 独立会话抓取并落库, 记录执行日志与最近执行状态."""
    started = time.perf_counter()
    db = SessionLocal()
    try:
        incident, inserted_count, source = run_fetch(db)
        # 追加可信追溯管道: 抓取/匹配来源 + 智能处置建议收敛 (均不写盖人工纠错)
        trace_detail = ""
        try:
            from app.services.trace.pipeline import run_trace_pipeline
            from app.services.convergence import converge_incidents
            t = run_trace_pipeline(db)
            c = converge_incidents(db)
            trace_detail = (
                f" 追踪:插入源{t['inserted']}/跳过{t['skipped_existing']}"
                f" 收敛:用户建议{c['user_generated']}/项目建议{c['project_generated']}/纠错保护{c['blocked']}"
            )
        except Exception:  # noqa: BLE001 - 追溯/收敛失败不影响抓取主流程
            logger.exception("[scheduler] 追溯管道/收敛引擎执行异常")
        duration = time.perf_counter() - started
        _last_run.update(
            status="ok",
            at=datetime.now(timezone.utc),
            detail=f"{source}: 新入库 {inserted_count} 起, 代表事件 {incident.external_id}{trace_detail}",
        )
        logger.info(
            "[scheduler] 定时抓取完成 source=%s inserted=%s event=%s 耗时=%.1fs",
            source, inserted_count, incident.external_id, duration,
        )
    except Exception:  # noqa: BLE001 - 定时任务必须吞掉异常避免调度器崩溃
        duration = time.perf_counter() - started
        _last_run.update(
            status="failed",
            at=datetime.now(timezone.utc),
            detail="定时抓取执行失败 (已记录异常日志)",
        )
        logger.exception("[scheduler] 定时抓取任务执行失败 耗时=%.1fs", duration)
    finally:
        db.close()


def start_scheduler() -> None:
    """应用启动时启动后台调度器."""
    global _scheduler
    if not settings.ENABLE_SCHEDULER or _scheduler is not None:
        return

    scheduler = BackgroundScheduler(timezone=settings.SCHEDULER_TIMEZONE)
    scheduler.add_job(
        run_fetch_job,
        IntervalTrigger(seconds=settings.FETCH_INTERVAL_SECONDS),
        id="auto_fetch_incidents",
        name="每小时自动抓取最新安全事件",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
        misfire_grace_time=settings.FETCH_INTERVAL_SECONDS,
    )
    scheduler.start()
    _scheduler = scheduler
    logger.info(
        "[scheduler] 定时任务已启动, 间隔 %s 秒, 真实源失败重试 %s 次 (退避 %ss)",
        settings.FETCH_INTERVAL_SECONDS,
        settings.FETCH_RETRY_TIMES,
        settings.FETCH_RETRY_BACKOFF_SECONDS,
    )


def stop_scheduler() -> None:
    """应用关闭时停止调度器."""
    global _scheduler
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        _scheduler = None
        logger.info("[scheduler] 定时任务已停止")


# ===================== 执行状态查询 =====================

def mark_run(status: str, detail: str) -> None:
    """由手动触发等途径记录一次执行状态."""
    _last_run.update(status=status, at=datetime.now(timezone.utc), detail=detail)


def get_last_run() -> dict:
    return dict(_last_run)


def next_run_time():
    if _scheduler is not None:
        job = _scheduler.get_job("auto_fetch_incidents")
        if job is not None:
            return job.next_run_time
    return None


def status_snapshot() -> dict:
    """定时任务状态快照 (供 API 查询最近日志与下次执行时间)."""
    return {
        "scheduler_running": _scheduler is not None and _scheduler.running,
        "fetch_interval_seconds": settings.FETCH_INTERVAL_SECONDS,
        "retry_times": settings.FETCH_RETRY_TIMES,
        "last_run_at": _last_run["at"],
        "last_status": _last_run["status"],
        "last_detail": _last_run["detail"],
        "next_run_at": next_run_time(),
    }
