import uuid
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user_id
from app.db.session import get_db
from app.schemas.exposure import ExposureInsightReport, ExposureSessionCreate, ExposureSessionRead
from app.services import exposure_service

router = APIRouter(prefix="/exposure", tags=["Exposure & Spending"])


@router.post("/sessions", response_model=ExposureSessionRead, status_code=status.HTTP_201_CREATED)
async def log_session(
    payload: ExposureSessionCreate,
    db: AsyncSession = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
) -> ExposureSessionRead:
    if payload.occurred_on > date.today():
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="occurred_on cannot be in the future")
    session = await exposure_service.create_session(db, user_id, payload)
    return ExposureSessionRead.model_validate(session)


@router.get("/sessions", response_model=list[ExposureSessionRead])
async def list_sessions(
    days: int = Query(default=90, ge=1, le=365),
    db: AsyncSession = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
) -> list[ExposureSessionRead]:
    sessions = await exposure_service.list_sessions(db, user_id, days=days)
    return [ExposureSessionRead.model_validate(s) for s in sessions]


@router.delete("/sessions/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_session(
    session_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
) -> None:
    if not await exposure_service.delete_session(db, user_id, session_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Exposure session not found")


@router.get("/insights", response_model=ExposureInsightReport)
async def get_insights(
    as_of: date | None = Query(default=None, description="Replay the analysis for a past day."),
    db: AsyncSession = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
) -> ExposureInsightReport:
    if as_of is not None and as_of > date.today():
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="as_of cannot be in the future")
    report = await exposure_service.insights_for_user(db, user_id, as_of=as_of)
    if report is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return report
