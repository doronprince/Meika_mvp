"""Seed a demo account for tax & compliance foresight.

The main dev account (scripts/seed_dev_user.py) only has this month's
expenses, which is too little history for these rules to say anything —
every rule would honestly report "needs more history". This account carries
14 months of a plausible international student's spending, so the Foresight
screen has real flags to show: transfers home that add up over a rolling
year, education costs without receipts, rent that runs past the tax-year
end, and spending in several currencies.

Idempotent: re-running replaces this account's expenses, receipts, rule
overrides and tax-year settings, with dates relative to today.

Usage:
    cd backend
    python -m scripts.seed_tax_demo
"""

import asyncio
import uuid
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import delete

from app.core.security import hash_password
from app.db.session import AsyncSessionLocal
from app.models.compliance import ComplianceRuleOverride, ExpenseTaxAnnotation, UserComplianceProfile
from app.models.enums import ExpenseCategory, TransitMode
from app.models.expense import Expense
from app.models.user import User

TAX_DEMO_USER_ID = uuid.UUID("00000000-0000-0000-0000-00000000007a")
TAX_DEMO_EMAIL = "tax@meika.example"
TAX_DEMO_PASSWORD = "MeikaTax123!"
MONTHS = 14


def _expense(day: date, title: str, category: ExpenseCategory, amount: str, **kw) -> Expense:
    return Expense(
        user_id=TAX_DEMO_USER_ID,
        title=title,
        category=category,
        amount_krw=Decimal(amount),
        transit_mode=TransitMode.WALK,
        occurred_on=day,
        **kw,
    )


def _ledger(today: date) -> list[tuple[Expense, bool]]:
    """(expense, has_receipt) pairs."""
    start = today - timedelta(days=30 * MONTHS)
    rows: list[tuple[Expense, bool]] = []
    for month in range(MONTHS):
        base = start + timedelta(days=30 * month)
        # Monthly transfer home: ₩1.15M x 12 = ₩13.8M, past the assumed USD 10,000 in a rolling year.
        rows.append((_expense(base + timedelta(days=2), "Wise transfer home", ExpenseCategory.OTHER, "1150000",
                              store_name="Wise"), False))
        rows.append((_expense(base + timedelta(days=4), "Rent", ExpenseCategory.HOUSING_AND_UTILITIES, "650000",
                              store_name="Sinchon Studio"), month % 3 == 0))
        rows.append((_expense(base + timedelta(days=9), "Groceries", ExpenseCategory.GROCERIES, "180000",
                              store_name="Emart"), False))
        rows.append((_expense(base + timedelta(days=15), "Books and materials", ExpenseCategory.EDUCATION, "85000",
                              store_name="Kyobo"), False))
    # Tuition instalments this tax year, one with a receipt recorded.
    for i, offset in enumerate((200, 170, 60)):
        rows.append((_expense(today - timedelta(days=offset), "Tuition instalment", ExpenseCategory.EDUCATION,
                              "1400000", store_name="Yonsei KLI"), i == 0))
    # A trip to Japan and a summer in Europe, logged in local currency.
    for d in range(5):
        rows.append((_expense(today - timedelta(days=120 - d), "Meals in Osaka", ExpenseCategory.CAFES_AND_DINING,
                              "95000", original_currency="JPY", original_amount=Decimal("10300")), False))
    for d in range(0, 60, 6):
        rows.append((_expense(today - timedelta(days=90 - d), "Food in Berlin", ExpenseCategory.CAFES_AND_DINING,
                              "160000", original_currency="EUR", original_amount=Decimal("108")), False))
    # One large transfer, a little short of the assumed USD 3,000.
    rows.append((_expense(today - timedelta(days=45), "Western Union to parents", ExpenseCategory.OTHER, "3900000"),
                 False))
    return rows


async def seed() -> None:
    today = date.today()
    async with AsyncSessionLocal() as session:
        user = await session.get(User, TAX_DEMO_USER_ID)
        if user is None:
            user = User(id=TAX_DEMO_USER_ID, email=TAX_DEMO_EMAIL, hashed_password=hash_password(TAX_DEMO_PASSWORD))
            session.add(user)
        else:
            user.email = TAX_DEMO_EMAIL
            user.hashed_password = hash_password(TAX_DEMO_PASSWORD)
        user.full_name = "Tax demo"

        for model in (ExpenseTaxAnnotation, ComplianceRuleOverride, UserComplianceProfile, Expense):
            await session.execute(delete(model).where(model.user_id == TAX_DEMO_USER_ID))
        await session.flush()

        rows = _ledger(today)
        for expense, _ in rows:
            session.add(expense)
        await session.flush()
        for expense, has_receipt in rows:
            if has_receipt:
                session.add(ExpenseTaxAnnotation(user_id=TAX_DEMO_USER_ID, expense_id=expense.id,
                                                 has_documentation=True, annotated_on=today))
        await session.commit()

    print(f"Seeded {TAX_DEMO_EMAIL} with {len(rows)} expenses over {MONTHS} months.")
    print(f"Log in with: email={TAX_DEMO_EMAIL}  password={TAX_DEMO_PASSWORD}")


if __name__ == "__main__":
    asyncio.run(seed())
