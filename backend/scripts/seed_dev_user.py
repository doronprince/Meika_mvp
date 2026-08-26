"""Seed a fixed-UUID dev user with sample expenses, for local frontend
testing against the [[tenant-isolation]] guardrail. Logs in through the real
Phase 8 JWT auth flow (POST /api/v1/auth/login) with the credentials printed
below — there's no more X-User-Id shortcut.

Idempotent: re-running replaces the dev user's expenses with a fresh batch
dated relative to today, so dashboard metrics (spending velocity, projected
month-end spend) always reflect "this month" regardless of when it's run.

Usage:
    cd backend
    python -m scripts.seed_dev_user
"""

import asyncio
import uuid
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import delete, select

from app.core.security import hash_password
from app.db.session import AsyncSessionLocal
from app.models.enums import ExpenseCategory, TransitMode
from app.models.expense import Expense
from app.models.user import User

DEV_USER_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")
# .example is ICANN-reserved for documentation/testing (RFC 2606) — unlike
# .local, it passes EmailStr's reserved-domain check on the real /auth/login
# endpoint this user now has to authenticate through.
DEV_USER_EMAIL = "dev@meika.example"
DEV_USER_PASSWORD = "MeikaDemo123!"

# (days_ago, title, category, amount_krw, store_name, transit_cost_krw, transit_mode)
SAMPLE_EXPENSES = [
    (0, "Emart grocery run", ExpenseCategory.GROCERIES, "38500", "Emart Yeoksam", "1350", TransitMode.SUBWAY_BUS),
    (1, "Coffee + study session", ExpenseCategory.CAFES_AND_DINING, "6800", "Cafe Onion", "0", TransitMode.WALK),
    (2, "Monthly subway pass top-up", ExpenseCategory.TRANSPORTATION, "55000", None, "0", TransitMode.SUBWAY_BUS),
    (3, "Textbook", ExpenseCategory.EDUCATION, "42000", "Kyobo Bookstore", "1350", TransitMode.SUBWAY_BUS),
    (4, "Dinner with friends", ExpenseCategory.CAFES_AND_DINING, "24000", "Gangnam BBQ House", "8500", TransitMode.TAXI),
    (5, "Phone case", ExpenseCategory.ELECTRONICS, "15000", "Coupang", "0", TransitMode.WALK),
    (6, "Winter jacket", ExpenseCategory.APPAREL, "89000", "Uniqlo Myeongdong", "1350", TransitMode.SUBWAY_BUS),
]


async def seed() -> None:
    today = date.today()

    async with AsyncSessionLocal() as session:
        user = await session.get(User, DEV_USER_ID)
        if user is None:
            user = User(id=DEV_USER_ID, email=DEV_USER_EMAIL, hashed_password=hash_password(DEV_USER_PASSWORD))
            session.add(user)
        else:
            user.email = DEV_USER_EMAIL
            user.hashed_password = hash_password(DEV_USER_PASSWORD)

        await session.execute(delete(Expense).where(Expense.user_id == DEV_USER_ID))

        for days_ago, title, category, amount, store_name, transit_cost, transit_mode in SAMPLE_EXPENSES:
            occurred_on = today - timedelta(days=days_ago)
            if occurred_on.month != today.month or occurred_on.year != today.year:
                # Keep every sample inside the current month so dashboard
                # metrics never silently drop rows near the 1st.
                occurred_on = date(today.year, today.month, 1)
            session.add(
                Expense(
                    user_id=DEV_USER_ID,
                    title=title,
                    category=category,
                    amount_krw=Decimal(amount),
                    store_name=store_name,
                    transit_cost_krw=Decimal(transit_cost),
                    transit_mode=transit_mode,
                    occurred_on=occurred_on,
                )
            )

        await session.commit()

        count = await session.execute(select(Expense).where(Expense.user_id == DEV_USER_ID))
        n = len(count.scalars().all())
        print(f"Seeded dev user {DEV_USER_ID} ({DEV_USER_EMAIL}) with {n} expenses this month.")
        print(f"Log in with: email={DEV_USER_EMAIL}  password={DEV_USER_PASSWORD}")


if __name__ == "__main__":
    asyncio.run(seed())
