"""统计接口: 看板核心指标."""
from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import schemas
from app.database import get_db
from app.models import Incident, IncidentCorrection

router = APIRouter()


@router.get("/stats", response_model=schemas.StatsOut, summary="看板统计指标")
def get_stats(db: Session = Depends(get_db)) -> schemas.StatsOut:
    total = db.scalar(select(func.count()).select_from(Incident)) or 0
    total_loss = db.scalar(
        select(func.coalesce(func.sum(Incident.loss_usd), 0.0))
    ) or 0.0
    confirmed = (
        db.scalar(
            select(func.count())
            .select_from(Incident)
            .where(Incident.status == "已确认")
        )
        or 0
    )
    investigating = (
        db.scalar(
            select(func.count())
            .select_from(Incident)
            .where(Incident.status == "调查中")
        )
        or 0
    )
    corrections = db.scalar(select(func.count()).select_from(IncidentCorrection)) or 0
    last_fetch = db.scalar(select(func.max(Incident.fetched_at)))

    category_rows = db.execute(
        select(Incident.risk_class, func.count()).group_by(Incident.risk_class)
    ).all()
    severity_rows = db.execute(
        select(Incident.severity, func.count()).group_by(Incident.severity)
    ).all()

    return schemas.StatsOut(
        total_incidents=total,
        total_loss_usd=total_loss,
        confirmed_count=confirmed,
        investigating_count=investigating,
        correction_count=corrections,
        category_distribution=[
            schemas.CategoryCount(name=name, count=cnt) for name, cnt in category_rows
        ],
        severity_distribution=[
            schemas.CategoryCount(name=name, count=cnt) for name, cnt in severity_rows
        ],
        last_fetch_at=last_fetch,
    )
