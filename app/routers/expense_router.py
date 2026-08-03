from fastapi import APIRouter
from app.services.expense_tracker import add_new_expense, list_expenses
from app.models import ExpenseCreate, ExpenseResponse
from typing import List

router = APIRouter(prefix="/api/expenses", tags=["Expense Tracker"])

@router.post("", response_model=ExpenseResponse)
def create_expense(expense: ExpenseCreate):
    return add_new_expense(expense)

@router.get("", response_model=List[dict])
def get_recent_expenses(limit: int = 20):
    return list_expenses(limit=limit)
