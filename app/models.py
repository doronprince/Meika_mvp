from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any

class ExpenseCreate(BaseModel):
    title: str
    category: str
    amount_krw: float
    store_name: Optional[str] = "General Store"
    transit_cost_krw: Optional[float] = 0.0
    date: str
    notes: Optional[str] = ""

class ExpenseResponse(ExpenseCreate):
    id: int
    total_economic_cost_krw: float

class ProductComparisonItem(BaseModel):
    id: int
    product_name: str
    category: str
    store_name: str
    store_type: str
    price_krw: float
    transit_cost_krw: float
    transit_mode: str
    total_economic_cost_krw: float
    location: str
    in_stock: bool
    rating: float
    price_trend: str
    is_best_value: bool = False

class PriceSearchResponse(BaseModel):
    query: str
    user_location: str
    best_option: Optional[ProductComparisonItem] = None
    online_best: Optional[ProductComparisonItem] = None
    local_best: Optional[ProductComparisonItem] = None
    traditional_market_best: Optional[ProductComparisonItem] = None
    all_results: List[ProductComparisonItem]
    xai_recommendation: str
    xai_reasoning: List[str]

class ChatRequest(BaseModel):
    message: str

class ChatResponse(BaseModel):
    reply: str
    xai_factors: List[str]
    suggested_action: Optional[str] = None

class DashboardSummary(BaseModel):
    total_monthly_spend_krw: float
    predicted_month_end_krw: float
    savings_identified_krw: float
    financial_clarity_score: int  # 0 to 100
    risk_level: str  # "Low", "Moderate", "High"
    category_breakdown: Dict[str, float]
    recent_expenses: List[Dict[str, Any]]
    xai_insights: List[str]
