"""事件接口: 列表联合筛选 / 单个详情."""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload
from starlette import status as http_status

from app import crud, schemas
from app.database import get_db
from app.models import Incident
from app.reference_data import STATUSES

router = APIRouter()


@router.get(
    "/incidents",
    response_model=schemas.IncidentListResponse,
    summary="获取事件列表 (风险大类 + 状态 + 关键词联合筛选)",
)
def list_incidents(
    category: Optional[str] = Query(default=None, description="风险大类, 对应 risk_class, 如: 网络安全运营风险 / 私钥泄露"),
    status: Optional[str] = Query(default=None, description="事件状态: " + " / ".join(STATUSES) + ", 传 ALL 或省略表示全部"),
    q: Optional[str] = Query(default=None, description="关键词, 匹配标题/项目名/公链"),
    year: Optional[int] = Query(default=None, ge=2000, le=2100, description="按事件发生年份过滤, e.g. 2023"),
    month: Optional[int] = Query(default=None, ge=1, le=12, description="按事件发生月份过滤, e.g. 5"),
    page: int = Query(default=1, ge=1, description="页码, 从 1 开始"),
    page_size: int = Query(default=20, ge=1, le=100, description="每页数量"),
    db: Session = Depends(get_db),
) -> schemas.IncidentListResponse:
    # 状态白名单校验: 仅允许 5 类状态或 ALL/空, 非法值直接返回 422
    if status is not None and status != "ALL" and status not in STATUSES:
        raise HTTPException(
            status_code=http_status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"无效的事件状态: {status}. 允许值: {STATUSES}",
        )
    total, items = crud.list_incidents(
        db,
        category=category or "ALL",
        status=status or "ALL",
        q=q,
        year=year,
        month=month,
        page=page,
        page_size=page_size,
    )
    return schemas.IncidentListResponse(total=total, total_count=total, page=page, page_size=page_size, items=items)


@router.get(
    "/incidents/{incident_id}",
    response_model=schemas.IncidentOut,
    summary="获取单个事件详情 (含 L1-L4 追溯链接)",
)
def get_incident(incident_id: int, db: Session = Depends(get_db)) -> Incident:
    incident = db.scalar(
        select(Incident)
        .where(Incident.id == incident_id)
        .options(selectinload(Incident.trace_links))
    )
    if incident is None:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND, detail="事件不存在"
        )
    return incident
