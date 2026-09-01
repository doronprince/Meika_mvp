from fastapi import APIRouter, HTTPException, Query, status

from app.schemas.fx import FxRatesResponse
from app.services import fx_service

router = APIRouter(prefix="/fx", tags=["FX"])


@router.get("/rates", response_model=FxRatesResponse)
async def get_fx_rates(
    base: str = Query(default="KRW", min_length=3, max_length=3),
) -> FxRatesResponse:
    base = base.upper()
    if base not in fx_service.SUPPORTED_CURRENCIES:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=f"{base} is not a supported currency")

    try:
        rates = await fx_service.get_rates(base)
    except fx_service.FxRateUnavailableError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc))

    return FxRatesResponse(base=base, rates=rates)
