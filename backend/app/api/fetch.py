"""抓取接口: 手动触发一次抓取 + 查询定时任务执行状态 (最近日志/下次执行)."""
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from starlette import status as http_status

from app import schemas
from app.database import get_db
from app.services import scheduler
from app.services.fetcher import get_last_source_error, run_fetch

router = APIRouter()


@router.post(
    "/admin/fetch-trigger",
    response_model=schemas.FetchResult,
    status_code=http_status.HTTP_200_OK,
    summary="手动触发一次抓取 (真实数据源/调试用)",
)
def trigger_fetch(db: Session = Depends(get_db)):
    incident, inserted_count, source = run_fetch(db)
    scheduler.mark_run(
        status="ok",
        detail=f"{source}: 新入库 {inserted_count} 起, 代表事件 {incident.external_id}",
    )
    return schemas.FetchResult(
        inserted_count=inserted_count,
        source=source,
        incident=incident,
        source_error=None if source == "defillama" else get_last_source_error(),
    )


@router.get(
    "/admin/fetch-status",
    response_model=schemas.FetchStatusOut,
    summary="定时任务执行状态 (最近执行日志 / 下次执行时间)",
)
def fetch_status():
    return scheduler.status_snapshot()


@router.get(
    "/admin/contract-path-audit",
    response_model=schemas.ContractPathAuditOut,
    summary="合约地址捕捉路径巡检 (按链正确解析, 报告正确/错配/缺失)",
)
def contract_path_audit(
    chain: Optional[str] = Query(default=None, description="按事件 chain 关键词过滤(可含多链)",
),
    db: Session = Depends(get_db),
):
    from app.services.contract_path import audit_contract_paths

    return audit_contract_paths(db, chain=chain)
