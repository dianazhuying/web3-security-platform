"""数据库查询封装."""
from typing import Optional

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.models import Incident


def list_incidents(
    db: Session,
    *,
    category: str = "ALL",
    status: str = "ALL",
    q: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
) -> tuple[int, list[Incident]]:
    """联合筛选: 风险大类 + 事件状态 + 关键词搜索, 按抓取时间倒序分页."""
    filters = []
    if category and category != "ALL":
        filters.append(Incident.risk_class == category)
    if status and status != "ALL":
        filters.append(Incident.status == status)
    if q:
        pattern = f"%{q.strip()}%"
        filters.append(
            or_(
                Incident.title.ilike(pattern),
                Incident.project_name.ilike(pattern),
                Incident.chain.ilike(pattern),
            )
        )

    total = db.scalar(
        select(func.count()).select_from(Incident).where(*filters)
    ) or 0

    items = db.scalars(
        select(Incident)
        .where(*filters)
        .order_by(Incident.fetched_at.desc(), Incident.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()

    return total, items
