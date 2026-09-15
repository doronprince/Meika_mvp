"""Seed a demo account for the Foresight research modules, with months of
history for them to compute from.

Deliberately separate from scripts/seed_dev_user.py: that script rewrites
dev@meika.example's expenses to "this month only" for the dashboard demo,
which would wipe the history the survival baseline (a 90-day ledger
average) needs.

Idempotent: re-running deletes this account's income streams and expenses
and regenerates them relative to today from a fixed random seed, so a given
day always produces the same ledger.

Usage:
    cd backend
    python -m scripts.seed_research_demo
"""

import asyncio
import random
import uuid
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import delete

from app.core.security import hash_password
from app.db.session import AsyncSessionLocal
from app.models.enums import ExpenseCategory, IncomeKind, TransitMode
from app.models.expense import Expense
from app.models.income import IncomeStream
from app.models.user import User
from app.services import fx_service

DEMO_USER_ID = uuid.UUID("00000000-0000-0000-0000-000000000002")
DEMO_USER_EMAIL = "research@meika.example"
DEMO_USER_PASSWORD = "MeikaDemo123!"

HISTORY_DAYS = 120
MONTHLY_BUDGET_KRW = Decimal("1100000.00")
LIQUID_SAVINGS_KRW = Decimal("3200000.00")

# (label, kind, monthly amount, currency the income is paid in)
INCOME_STREAMS = [
    ("Lab assistant (part-time)", IncomeKind.PART_TIME, Decimal("700000"), "KRW"),
    ("Family allowance", IncomeKind.FAMILY_SUPPORT, Decimal("20000"), "INR"),
]


def _expense(day: date, title: str, category: ExpenseCategory, amount: int, store: str | None = None,
             transit: int = 0, mode: TransitMode = TransitMode.WALK) -> Expense:
    return Expense(
        user_id=DEMO_USER_ID,
        title=title,
        category=category,
        amount_krw=Decimal(amount),
        store_name=store,
        transit_cost_krw=Decimal(transit),
        transit_mode=mode,
        occurred_on=day,
    )


def build_ledger(today: date) -> list[Expense]:
    rng = random.Random(20260915)
    rows: list[Expense] = []
    day = today - timedelta(days=HISTORY_DAYS - 1)
    while day <= today:
        if day.day == 1:
            rows.append(_expense(day, "Goshiwon rent", ExpenseCategory.HOUSING_AND_UTILITIES, 450_000))
            rows.append(_expense(day, "Mobile + internet", ExpenseCategory.HOUSING_AND_UTILITIES, 55_000, "KT"))
        if day.day == 3:
            rows.append(_expense(day, "Subway pass top-up", ExpenseCategory.TRANSPORTATION, 55_000))
        if day.weekday() in (1, 4, 6):
            store = rng.choice(["Emart Yeoksam", "Homeplus Jamsil", "Lotte Mart"])
            rows.append(_expense(day, "Groceries", ExpenseCategory.GROCERIES, rng.randint(10, 25) * 1000, store,
                                 1350, TransitMode.SUBWAY_BUS))
        if rng.random() < 0.6:
            store = rng.choice(["Cafe Onion", "Starbucks Gangnam", "Mega Coffee"])
            rows.append(_expense(day, "Coffee", ExpenseCategory.CAFES_AND_DINING, rng.randint(45, 90) * 100, store))
        if day.weekday() == 5 and rng.random() < 0.7:
            rows.append(_expense(day, "Dinner with friends", ExpenseCategory.CAFES_AND_DINING,
                                 rng.randint(15, 35) * 1000, "Hongdae BBQ", 1350, TransitMode.SUBWAY_BUS))
        if rng.random() < 0.04:
            rows.append(_expense(day, "Clothes", ExpenseCategory.APPAREL, rng.randint(25, 90) * 1000, "Uniqlo"))
        if rng.random() < 0.03:
            rows.append(_expense(day, "Electronics", ExpenseCategory.ELECTRONICS, rng.randint(15, 120) * 1000, "Coupang"))
        if day.day == 20 and day.month % 2 == 0:
            rows.append(_expense(day, "Course materials", ExpenseCategory.EDUCATION, 60_000, "Kyobo Bookstore"))
        day += timedelta(days=1)
    return rows


async def seed() -> None:
    today = date.today()

    async with AsyncSessionLocal() as session:
        user = await session.get(User, DEMO_USER_ID)
        if user is None:
            user = User(id=DEMO_USER_ID, email=DEMO_USER_EMAIL, hashed_password=hash_password(DEMO_USER_PASSWORD))
            session.add(user)
        user.email = DEMO_USER_EMAIL
        user.hashed_password = hash_password(DEMO_USER_PASSWORD)
        user.full_name = "Research Demo"
        user.monthly_budget_krw = MONTHLY_BUDGET_KRW
        user.liquid_savings_krw = LIQUID_SAVINGS_KRW
        await session.flush()

        await session.execute(delete(IncomeStream).where(IncomeStream.user_id == DEMO_USER_ID))
        await session.execute(delete(Expense).where(Expense.user_id == DEMO_USER_ID))

        for label, kind, amount, currency in INCOME_STREAMS:
            if currency == "KRW":
                snapshot = amount
            else:
                try:
                    snapshot = await fx_service.convert(amount, currency, "KRW")
                except fx_service.FxRateUnavailableError:
                    print(f"  skipped '{label}': live FX for {currency} is unavailable right now")
                    continue
            session.add(
                IncomeStream(
                    user_id=DEMO_USER_ID,
                    label=label,
                    kind=kind,
                    monthly_amount=amount,
                    currency=currency,
                    monthly_amount_krw_snapshot=snapshot.quantize(Decimal("0.01")),
                )
            )

        ledger = build_ledger(today)
        session.add_all(ledger)
        await session.commit()

    print(f"Seeded research demo user {DEMO_USER_ID} ({DEMO_USER_EMAIL}): {len(ledger)} expenses over "
          f"{HISTORY_DAYS} days, liquid savings {LIQUID_SAVINGS_KRW:,.0f} KRW.")
    print(f"Log in with: email={DEMO_USER_EMAIL}  password={DEMO_USER_PASSWORD}")


if __name__ == "__main__":
    asyncio.run(seed())
