"""纠错接口: 提交社区纠错 / 查询事件纠错记录."""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session
from starlette import status as http_status

from app import schemas
from app.database import get_db
from app.models import Incident, IncidentCorrection

router = APIRouter()


@router.post(
    "/incidents/{incident_id}/corrections",
    response_model=schemas.CorrectionOut,
    status_code=http_status.HTTP_201_CREATED,
    summary="提交社区纠错",
)
def create_correction(
    incident_id: int,
    payload: schemas.CorrectionCreate,
    db: Session = Depends(get_db),
) -> IncidentCorrection:
    incident = db.get(Incident, incident_id)
    if incident is None:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND, detail="事件不存在"
        )
    correction = IncidentCorrection(incident_id=incident_id, **payload.model_dump())
    db.add(correction)
    db.commit()
    db.refresh(correction)
    return correction


@router.get(
    "/incidents/{incident_id}/corrections",
    response_model=list[schemas.CorrectionOut],
    summary="查询事件的纠错记录",
)
def list_corrections(
    incident_id: int,
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
) -> list[IncidentCorrection]:
    if db.get(Incident, incident_id) is None:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND, detail="事件不存在"
        )
    return db.scalars(
        select(IncidentCorrection)
        .where(IncidentCorrection.incident_id == incident_id)
        .order_by(IncidentCorrection.id.desc())
        .limit(limit)
    ).all()
