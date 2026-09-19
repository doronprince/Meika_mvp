import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user_id
from app.db.session import get_db
from app.schemas.claim import ClaimEvaluationRead, ClaimEvaluationRequest, ClaimEvaluationSummary
from app.services import claim_check_service, fx_service

router = APIRouter(prefix="/claim-check", tags=["Claim Check"])


@router.post("/evaluate", response_model=ClaimEvaluationRead, status_code=status.HTTP_201_CREATED)
async def evaluate_claim(
    payload: ClaimEvaluationRequest,
    db: AsyncSession = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
) -> ClaimEvaluationRead:
    try:
        report = await claim_check_service.evaluate_claim(db, user_id, payload)
    except claim_check_service.UnsupportedCurrencyError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc))
    except fx_service.FxRateUnavailableError as exc:
        # A stake in a currency that can't be converted can't be compared with
        # a KRW budget, so this is the one path that can't degrade.
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc))
    if report is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return report


@router.get("/history", response_model=list[ClaimEvaluationSummary])
async def history(
    limit: int = Query(default=20, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
) -> list[ClaimEvaluationSummary]:
    return await claim_check_service.list_evaluations(db, user_id, limit=limit)


@router.get("/{evaluation_id}", response_model=ClaimEvaluationRead)
async def get_evaluation(
    evaluation_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
) -> ClaimEvaluationRead:
    report = await claim_check_service.get_evaluation(db, user_id, evaluation_id)
    if report is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Evaluation not found")
    return report


@router.delete("/{evaluation_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_evaluation(
    evaluation_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
) -> None:
    if not await claim_check_service.delete_evaluation(db, user_id, evaluation_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Evaluation not found")
