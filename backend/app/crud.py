"""数据库查询封装."""
from typing import Optional

from sqlalchemy import extract, func, or_, select
from sqlalchemy.orm import Session

from app.models import Incident, IncidentTraceLink

# 追溯报告完整度筛选: 按 L1-L4 中存在可点击链接(url非空)的等级数 (0-4)
VALID_REPORT = {"none": 0, "g1": 1, "g2": 2, "g3": 3, "g4": 4}


def list_incidents(
    db: Session,
    *,
    category: str = "ALL",
    status: str = "ALL",
    q: Optional[str] = None,
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
