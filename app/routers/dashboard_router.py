from fastapi import APIRouter
from app.services.expense_tracker import get_dashboard_summary
from app.models import DashboardSummary

router = APIRouter(prefix="/api/dashboard", tags=["Dashboard"])

@router.get("/summary", response_model=DashboardSummary)
def dashboard_summary():
    return get_dashboard_summary()
