import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user_id
from app.db.session import get_db
from app.schemas.income import IncomeStreamCreate, IncomeStreamRead, IncomeStreamUpdate
from app.services import fx_service, income_service

router = APIRouter(prefix="/income-streams", tags=["Income"])


@router.post("", response_model=IncomeStreamRead, status_code=status.HTTP_201_CREATED)
async def create_income_stream(
    payload: IncomeStreamCreate,
    db: AsyncSession = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
) -> IncomeStreamRead:
    try:
        stream = await income_service.create_income_stream(db, user_id, payload)
    except income_service.UnsupportedCurrencyError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc))
    except fx_service.FxRateUnavailableError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc))
    return IncomeStreamRead.model_validate(stream)


@router.get("", response_model=list[IncomeStreamRead])
async def list_income_streams(
    db: AsyncSession = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
) -> list[IncomeStreamRead]:
    streams = await income_service.list_income_streams(db, user_id)
    return [IncomeStreamRead.model_validate(stream) for stream in streams]


@router.patch("/{stream_id}", response_model=IncomeStreamRead)
async def update_income_stream(
    stream_id: uuid.UUID,
    payload: IncomeStreamUpdate,
    db: AsyncSession = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
) -> IncomeStreamRead:
    try:
        stream = await income_service.update_income_stream(db, user_id, stream_id, payload)
    except income_service.UnsupportedCurrencyError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc))
    except fx_service.FxRateUnavailableError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc))
    if stream is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Income stream not found")
    return IncomeStreamRead.model_validate(stream)


@router.delete("/{stream_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_income_stream(
    stream_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
) -> None:
    deleted = await income_service.delete_income_stream(db, user_id, stream_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Income stream not found")
