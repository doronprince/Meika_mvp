import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user_id
from app.db.session import get_db
from app.schemas.survival import ShockPreset, SurvivalReport, SurvivalSimulationRequest
from app.services import survival_service

router = APIRouter(prefix="/survival", tags=["Survival Runway"])


@router.post("/simulate", response_model=SurvivalReport)
async def simulate_survival(
    payload: SurvivalSimulationRequest,
    db: AsyncSession = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
) -> SurvivalReport:
    try:
        report = await survival_service.simulate_for_user(db, user_id, payload)
    except survival_service.UnknownIncomeStreamError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc))
    if report is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return report


@router.get("/presets", response_model=list[ShockPreset])
async def get_shock_presets(
    db: AsyncSession = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
) -> list[ShockPreset]:
    presets = await survival_service.presets_for_user(db, user_id)
    if presets is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return presets
