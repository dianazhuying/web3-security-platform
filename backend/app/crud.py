"""数据库查询封装."""
from typing import Optional

from sqlalchemy import extract, func, or_, select
from sqlalchemy.orm import Session

from app.models import Incident, IncidentTraceLink

# 信源等级筛选: 按 L1-L4 中存在可点击链接(url非空)的等级数 (0-4)
# 键 "0"-"4" 对应前端 L0-L4 语义 (L0=无可点击信源/未验证, Ln=达到该等级及以上);
# 旧键 none/g1-g4 保留兼容。
VALID_REPORT = {"none": 0, "g1": 1, "g2": 2, "g3": 3, "g4": 4, "0": 0, "1": 1, "2": 2, "3": 3, "4": 4}


def list_incidents(
    db: Session,
    *,
    category: str = "ALL",
    status: str = "ALL",
    q: Optional[str] = None,
    chain: Optional[str] = None,
    year: Optional[int] = None,
    month: Optional[int] = None,
    report: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
) -> tuple[int, list[Incident]]:
    """联合筛选: 风险大类 + 状态 + 关键词 + 年份/月份 + 追溯报告完整度, 按事件发生时间倒序分页."""
    filters = []
    if category and category != "ALL":
        filters.append(Incident.risk_class == category)
    if status and status != "ALL":
        filters.append(Incident.status == status)
    if year:
        filters.append(extract("year", Incident.occurred_at) == int(year))
    if month:
        filters.append(extract("month", Incident.occurred_at) == int(month))
    if q:
        pattern = f"%{q.strip()}%"
        filters.append(
            or_(
                Incident.title.ilike(pattern),
                Incident.project_name.ilike(pattern),
                Incident.chain.ilike(pattern),
            )
        )
    if chain:
        # 公链筛选: chain 为逗号拼接的多链字符串, 精确等于 或 作为集合成员被包含
        c = chain.strip()
        filters.append(
            or_(
                Incident.chain == c,
                Incident.chain.like(f"{c},%"),
                Incident.chain.like(f"%,{c}"),
                Incident.chain.like(f"%,{c},%"),
            )
        )
    if report:
        target = VALID_REPORT.get(report)
        if target is not None:
            # 该事件有可点击链接的追溯等级数
            report_cnt = (
                select(func.count(func.distinct(IncidentTraceLink.level)))
                .where(
                    IncidentTraceLink.incident_id == Incident.id,
                    IncidentTraceLink.url != "",
                )
                .scalar_subquery()
            )
            filters.append(report_cnt == target if target == 0 else report_cnt >= target)

    total = db.scalar(
        select(func.count()).select_from(Incident).where(*filters)
    ) or 0

    items = db.scalars(
        select(Incident)
        .where(*filters)
        .order_by(Incident.occurred_at.desc().nullslast(), Incident.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()

    return total, items


def get_chains(db: Session, limit: int = 30) -> list[str]:
    """返回事件中涉及的独立公链列表 (按事件数倒序, 取前 limit 条).

    chain 字段为逗号拼接的多链字符串, 需拆分后按单个公链聚合计数.
    """
    rows = db.execute(
        select(func.count().label("cnt"), Incident.chain)
        .where(Incident.chain.isnot(None), Incident.chain != "")
        .group_by(Incident.chain)
        .order_by(func.count().desc())
    ).all()
    counts: dict[str, int] = {}
    for row in rows:
        for part in row.chain.split(","):
            p = part.strip()
            if p:
                counts[p] = counts.get(p, 0) + 1
    top = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
    return [name for name, _n in top[:limit]]
