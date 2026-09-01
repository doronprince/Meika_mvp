import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_optional_user_id
from app.db.session import get_db
from app.schemas.price_finder import PriceFinderResult
from app.services import price_finder_service

router = APIRouter(prefix="/price-finder", tags=["Price-Finder"])


@router.get("/search", response_model=list[PriceFinderResult])
async def search_price_comparisons(
    q: str | None = Query(default=None, min_length=1, max_length=255),
    db: AsyncSession = Depends(get_db),
    user_id: uuid.UUID | None = Depends(get_optional_user_id),
) -> list[PriceFinderResult]:
    return await price_finder_service.search_price_comparisons(db, q, user_id)
