from fastapi import APIRouter, Query
from app.services.price_finder import search_prices
from app.models import PriceSearchResponse

router = APIRouter(prefix="/api/price-finder", tags=["Price Finder"])

@router.get("/search", response_model=PriceSearchResponse)
def search_product(q: str = Query(..., min_length=1, description="Product query e.g. 'Rice' or 'Milk'")):
    return search_prices(query=q)
