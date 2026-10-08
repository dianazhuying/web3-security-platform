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


@router.get("/chains", summary="获取事件涉及的独立公链列表 (按事件数倒序, 供筛选下拉)")
def chains(
    limit: int = Query(default=30, ge=1, le=100),
    ecosystem: Optional[str] = Query(default=None, description="仅返回该生态下的公链: EVM / SOLANA / OTHER / ALL"),
    db: Session = Depends(get_db),
) -> list[str]:
    return crud.get_chains(db, limit=limit, ecosystem=ecosystem)


@router.get(
    "/incidents",
    response_model=schemas.IncidentListResponse,
    summary="获取事件列表 (风险大类 + 状态 + 关键词联合筛选)",
)
def list_incidents(
    category: Optional[str] = Query(default=None, description="风险大类, 对应 risk_class, 如: 网络安全运营风险 / 私钥泄露"),
    status: Optional[str] = Query(default=None, description="事件状态: " + " / ".join(STATUSES) + ", 传 ALL 或省略表示全部"),
    q: Optional[str] = Query(default=None, description="关键词, 匹配标题/项目名/公链"),
    chain: Optional[str] = Query(default=None, description="公链筛选, 如 Ethereum/BSC/Solana, 匹配该链或其多链组合成员",),
    ecosystem: Optional[str] = Query(default=None, description="生态筛选: EVM(以太坊生态)/SOLANA(Solana生态)/OTHER(其他生态), 可叠加公链",),
    year: Optional[int] = Query(default=None, ge=2000, le=2100, description="按事件发生年份过滤, e.g. 2023"),
    month: Optional[int] = Query(default=None, ge=1, le=12, description="按事件发生月份过滤, e.g. 5"),
    report: Optional[str] = Query(default=None, description="按可信追溯报告完整度过滤: none=无链接, g1/g2/g3=至少N级, g4=完整4级"),
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
        chain=chain,
        ecosystem=ecosystem,
        year=year,
        month=month,
        report=report,
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
    # 物化 dynamic list 的 trace_sources, 供 response_model 序列化
    incident.trace_sources = incident.trace_sources.all()
    return incident
