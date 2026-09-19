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
from app.models.enums import ExpenseCategory, ExposureKind, IncomeKind, TransitMode
from app.models.expense import Expense
from app.models.exposure import ExposureSession
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
        # The last 28 days drift the way the early-warning module looks for:
        # coffee becomes near daily and cheaper per cup, impulse online
        # shopping appears, and a weekly webtoon habit started 6 weeks ago.
        drifting = day > today - timedelta(days=28)
        if rng.random() < (0.95 if drifting else 0.6):
            store = rng.choice(["Cafe Onion", "Starbucks Gangnam", "Mega Coffee"])
            cup = rng.randint(30, 55) * 100 if drifting else rng.randint(45, 90) * 100
            rows.append(_expense(day, "Coffee", ExpenseCategory.CAFES_AND_DINING, cup, store))
        if drifting and rng.random() < 0.12:
            rows.append(_expense(day, "Online shopping", ExpenseCategory.APPAREL, rng.randint(20, 60) * 1000, "Musinsa"))
        if day.weekday() == 6 and day > today - timedelta(days=42):
            rows.append(_expense(day, "Webtoon coins", ExpenseCategory.OTHER, 4_900, "Naver Webtoon"))
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


EXPOSURE_DAYS = 60
# (platform, kind) the demo account logs screen time on.
PLATFORMS = [
    ("Instagram", ExposureKind.SOCIAL_FEED),
    ("Coupang", ExposureKind.SHOPPING_APP),
    ("YouTube", ExposureKind.INFLUENCER_CONTENT),
]


def build_exposure(today: date) -> tuple[list[ExposureSession], list[Expense]]:
    """Demo screen-time log for the exposure module, with a pattern built
    in on purpose: after a long session on a shopping app or influencer
    content, an online purchase often follows the same or next day. This
    is constructed demo data so the screen has something to find; the
    module's real-world behaviour is measured in scripts/eval_exposure.py."""
    rng = random.Random(20260919)
    sessions: list[ExposureSession] = []
    purchases: list[Expense] = []
    for offset in range(EXPOSURE_DAYS):
        day = today - timedelta(days=EXPOSURE_DAYS - 1 - offset)
        if rng.random() < 0.3:
            continue
        platform, kind = rng.choice(PLATFORMS)
        minutes = rng.choice([15, 20, 30, 45, 60, 90, 120, 150])
        sessions.append(
            ExposureSession(user_id=DEMO_USER_ID, occurred_on=day, started_hour=rng.choice([13, 21, 22, 23]),
                            platform=platform, kind=kind, minutes=minutes)
        )
        if kind != ExposureKind.SOCIAL_FEED and minutes >= 90 and rng.random() < 0.75:
            when = min(today, day + timedelta(days=rng.choice([0, 1])))
            purchases.append(_expense(when, "Online order", ExpenseCategory.APPAREL, rng.randint(25, 70) * 1000, platform))
    return sessions, purchases


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
        await session.execute(delete(ExposureSession).where(ExposureSession.user_id == DEMO_USER_ID))

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
        exposure, prompted = build_exposure(today)
        ledger += prompted
        session.add_all(ledger)
        session.add_all(exposure)
        await session.commit()

    print(f"Seeded research demo user {DEMO_USER_ID} ({DEMO_USER_EMAIL}): {len(ledger)} expenses over "
          f"{HISTORY_DAYS} days, liquid savings {LIQUID_SAVINGS_KRW:,.0f} KRW.")
    print(f"Plus {len(exposure)} logged screen-time sessions over the last {EXPOSURE_DAYS} days.")
    print(f"Log in with: email={DEMO_USER_EMAIL}  password={DEMO_USER_PASSWORD}")


if __name__ == "__main__":
    asyncio.run(seed())
