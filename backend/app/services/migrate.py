"""数据库迁移: 幂等地为 incidents 表补充 occurred_at 列并回填存量数据.

create_all 不会给已存在的表加列, 需在启动时显式迁移:
1. 检查 incidents 是否已有 occurred_at 列, 没有则 ALTER TABLE 添加.
2. 对 occurred_at 为 NULL 的存量行, 从 DefiLlama 全量数据按 external_id 匹配回填真实事件发生时间.

仅当存在缺失时执行, 不影响后续冷启动耗时.
"""
import logging
from datetime import datetime, timezone

from sqlalchemy import func, inspect, select, text
from sqlalchemy.orm import Session

from app.config import settings
from app.models import Incident

logger = logging.getLogger(__name__)


def ensure_occurred_at_column(engine) -> None:
    """若 incidents 表缺少 occurred_at 列则添加 (幂等)."""
    dialect = engine.dialect.name
    cols = {c["name"] for c in inspect(engine).get_columns("incidents")}
    if "occurred_at" in cols:
        return
    sql = "ALTER TABLE incidents ADD COLUMN occurred_at TIMESTAMP"
    if dialect == "sqlite":
        sql = "ALTER TABLE incidents ADD COLUMN occurred_at TIMESTAMP"
    with engine.begin() as conn:
        conn.execute(text(sql))
    logger.info("[migrate] incidents 表已新增 occurred_at 列")


def backfill_occurred_at(db: Session) -> int:
    """从 DefiLlama 按 external_id 回填 occurred_at, 返回更新的行数 (仅处理 NULL 行).

    真实事件发生时间来源: api.llama.fi/hacks 每条记录中的 date (Unix 秒级时间戳).
    """
    missing = db.scalar(
        select(func.count()).select_from(Incident).where(Incident.occurred_at.is_(None))
    ) or 0
    if missing == 0:
        return 0

    import json
    import urllib.request

    req = urllib.request.Request(
        settings.DEFILLAMA_HACKS_URL,
        headers={"User-Agent": "Web3SecurityDashboard/1.0", "Accept": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        payload = json.loads(resp.read().decode("utf-8"))

    date_by_ext: dict[str, datetime] = {}
    for row in payload:
        date_ts = row.get("date")
        if not date_ts:
            continue
        ext_id = row.get("defillamaId") or row.get("name")
        if not ext_id:
            continue
        occurred = datetime.fromtimestamp(int(date_ts), tz=timezone.utc)
        # 与入库时的 external_id 格式保持一致
        date_by_ext[f"defillama-{ext_id}"] = occurred

    updated = 0
    rows = db.scalars(
        select(Incident).where(Incident.occurred_at.is_(None))
    ).all()
    for inc in rows:
        occurred = date_by_ext.get(inc.external_id)
        if occurred is None:
            continue
        inc.occurred_at = occurred
        updated += 1
    db.commit()
    logger.info("[migrate] 已回填 %s 起存量事件的 occurred_at", updated)
    return updated


def run_migrate(engine) -> None:
    """启动时一次性迁移入口: 加列 + 回填. 全程幂等, 不阻断启动."""
    try:
        ensure_occurred_at_column(engine)
    except Exception as exc:  # noqa: BLE001 - 迁移失败不阻断启动
        logger.warning("[migrate] 加列失败: %s", exc)
        return
    db = None
    try:
        from app.database import SessionLocal

        db = SessionLocal()
        backfill_occurred_at(db)
    except Exception as exc:  # noqa: BLE001
        logger.warning("[migrate] 回填失败: %s", exc)
    finally:
        if db is not None:
            db.close()