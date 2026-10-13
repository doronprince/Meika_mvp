"""Seed ONE demo account that exercises every feature.

The three earlier demo accounts each fed a different part of the app, which
meant signing out and back in to see everything. This builds a single
account with the data all of them needed: 14 months of expenses (so the
tax rules and the early-warning baseline have history), spending this month
(so the dashboard isn't empty), receipts on some costs, a savings goal with
contributions and a spending cap, income and savings for the survival
runway, and screen-time sessions for the exposure module.

Idempotent: re-running deletes this account's rows and regenerates them
relative to today from a fixed seed, so a given day always produces the
same ledger.

Usage:
    cd backend
    python -m scripts.seed_demo
"""

import asyncio
import random
import uuid
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import delete

from app.core.security import hash_password
from app.db.session import AsyncSessionLocal
from app.models.compliance import ComplianceRuleOverride, ExpenseTaxAnnotation, UserComplianceProfile
from app.models.enums import ExpenseCategory, ExposureKind, GoalType, IncomeKind, TransitMode
from app.models.expense import Expense
from app.models.exposure import ExposureSession
from app.models.goal import Goal, GoalContribution
from app.models.income import IncomeStream
from app.models.user import User
from app.services import fx_service

DEMO_USER_ID = uuid.UUID("00000000-0000-0000-0000-0000000000de")
DEMO_EMAIL = "demo@meika.example"
DEMO_PASSWORD = "MeikaDemo123!"

HISTORY_MONTHS = 14
# Set against what this persona actually spends (rent, transfers home,
# tuition months): a budget below the ledger would make the demo open on
# a high-risk score that says more about the fixture than the system.
MONTHLY_BUDGET_KRW = Decimal("2600000.00")
LIQUID_SAVINGS_KRW = Decimal("3200000.00")
RENT_KRW = 650_000
# Used when the live FX API is unreachable: the stored snapshot is only a
# fallback for the survival module, and the canonical figure stays the
# original currency amount.
INR_KRW_FALLBACK = Decimal("16.2")

rng = random.Random(20261013)


def _expense(day: date, title: str, category: ExpenseCategory, amount: int, store: str | None = None,
             transit: int = 0, mode: TransitMode = TransitMode.WALK, currency: str | None = None,
             original: Decimal | None = None) -> Expense:
    return Expense(
        user_id=DEMO_USER_ID,
        title=title,
        category=category,
        amount_krw=Decimal(amount),
        store_name=store,
        transit_cost_krw=Decimal(transit),
        transit_mode=mode,
        occurred_on=day,
        original_currency=currency,
        original_amount=original,
    )


def _ledger(today: date) -> list[tuple[Expense, bool]]:
    """(expense, has_receipt) over the last 14 months, including this one."""
    rows: list[tuple[Expense, bool]] = []
    first_of_this_month = today.replace(day=1)

    month_starts = []
    cursor = first_of_this_month
    for _ in range(HISTORY_MONTHS):
        month_starts.append(cursor)
        cursor = (cursor - timedelta(days=1)).replace(day=1)

    for index, month_start in enumerate(month_starts):
        def day_in_month(day_number: int) -> date:
            try:
                candidate = month_start.replace(day=day_number)
            except ValueError:
                candidate = month_start.replace(day=28)
            return min(candidate, today)

        # Rent: one charge a month, which is what makes the projection
        # treat it as a commitment rather than a daily rate.
        rows.append((_expense(day_in_month(3), "Rent", ExpenseCategory.HOUSING_AND_UTILITIES, RENT_KRW,
                              store="Sinchon Studio"), index % 3 == 0))
        # Money sent home, monthly, which the compliance rules watch.
        rows.append((_expense(day_in_month(6), "Wise transfer home", ExpenseCategory.OTHER, 1_150_000,
                              store="Wise"), False))
        # Weekly-ish groceries and cafés, varied enough to look real.
        for week in range(4):
            groceries_day = day_in_month(2 + week * 7)
            if groceries_day <= today:
                rows.append((_expense(groceries_day, "Groceries", ExpenseCategory.GROCERIES,
                                      rng.randrange(28_000, 52_000), store="Emart",
                                      transit=1_350, mode=TransitMode.SUBWAY_BUS), False))
            cafe_day = day_in_month(4 + week * 7)
            if cafe_day <= today:
                rows.append((_expense(cafe_day, "Coffee and study", ExpenseCategory.CAFES_AND_DINING,
                                      rng.randrange(5_500, 9_500), store="Cafe Onion"), False))
        # Books most months, tuition twice a year.
        rows.append((_expense(day_in_month(12), "Books and materials", ExpenseCategory.EDUCATION,
                              rng.randrange(35_000, 85_000), store="Kyobo"), index % 4 == 0))
        if month_start.month in (3, 9):
            rows.append((_expense(day_in_month(15), "Tuition instalment", ExpenseCategory.EDUCATION, 1_400_000,
                                  store="Yonsei KLI"), True))

    # A trip to Japan and a summer in Europe: spending in several currencies.
    for offset in range(5):
        rows.append((_expense(today - timedelta(days=120 - offset), "Meals in Osaka",
                              ExpenseCategory.CAFES_AND_DINING, 95_000, store="Dotonbori",
                              currency="JPY", original=Decimal("10300")), False))
    for offset in range(0, 48, 6):
        rows.append((_expense(today - timedelta(days=90 - offset), "Food in Berlin",
                              ExpenseCategory.CAFES_AND_DINING, 160_000, store="Markthalle",
                              currency="EUR", original=Decimal("108")), False))
    # One unusually large transfer, a little under the assumed figure.
    rows.append((_expense(today - timedelta(days=45), "Western Union to parents", ExpenseCategory.OTHER,
                          3_900_000, store="Western Union"), False))
    return [(expense, has_receipt) for expense, has_receipt in rows if expense.occurred_on <= today]


def _exposure_sessions(today: date) -> list[ExposureSession]:
    """Screen time over the last 60 days, heavier at weekends — the weekly
    rhythm the exposure module has to control for."""
    sessions = []
    for days_ago in range(60):
        day = today - timedelta(days=days_ago)
        weekend = day.weekday() >= 5
        for _ in range(rng.randint(1, 3) + (1 if weekend else 0)):
            kind = rng.choice([ExposureKind.SOCIAL_FEED, ExposureKind.SHOPPING_APP,
                               ExposureKind.INFLUENCER_CONTENT, ExposureKind.ADS_AND_DEAL_ALERTS])
            sessions.append(ExposureSession(
                user_id=DEMO_USER_ID,
                occurred_on=day,
                started_hour=rng.choice([9, 13, 19, 21, 22, 23]),
                platform=rng.choice(["Instagram", "YouTube", "Coupang", "TikTok"]),
                kind=kind,
                minutes=rng.randrange(15, 95) + (25 if weekend else 0),
            ))
    return sessions


async def _income_streams() -> list[IncomeStream]:
    streams = [
        ("Lab assistant (part-time)", IncomeKind.PART_TIME, Decimal("700000"), "KRW"),
        ("Family allowance", IncomeKind.FAMILY_SUPPORT, Decimal("20000"), "INR"),
    ]
    rows = []
    for label, kind, amount, currency in streams:
        if currency == "KRW":
            snapshot = amount
        else:
            try:
                snapshot = await fx_service.convert(amount, currency, "KRW")
            except Exception:
                snapshot = amount * INR_KRW_FALLBACK
        rows.append(IncomeStream(
            user_id=DEMO_USER_ID,
            label=label,
            kind=kind,
            monthly_amount=amount,
            currency=currency,
            monthly_amount_krw_snapshot=snapshot.quantize(Decimal("0.01")),
            is_active=True,
        ))
    return rows


async def seed() -> None:
    today = date.today()
    async with AsyncSessionLocal() as session:
        user = await session.get(User, DEMO_USER_ID)
        if user is None:
            user = User(id=DEMO_USER_ID, email=DEMO_EMAIL, hashed_password=hash_password(DEMO_PASSWORD))
            session.add(user)
        else:
            user.email = DEMO_EMAIL
            user.hashed_password = hash_password(DEMO_PASSWORD)
        user.full_name = "Meika demo"
        user.monthly_budget_krw = MONTHLY_BUDGET_KRW
        user.liquid_savings_krw = LIQUID_SAVINGS_KRW
        user.preferred_currency = "KRW"

        for model in (ExpenseTaxAnnotation, ComplianceRuleOverride, UserComplianceProfile,
                      GoalContribution, Goal, ExposureSession, IncomeStream, Expense):
            await session.execute(delete(model).where(model.user_id == DEMO_USER_ID))
        await session.flush()

        rows = _ledger(today)
        for expense, _ in rows:
            session.add(expense)
        await session.flush()
        for expense, has_receipt in rows:
            if has_receipt:
                session.add(ExpenseTaxAnnotation(user_id=DEMO_USER_ID, expense_id=expense.id,
                                                 has_documentation=True, annotated_on=today))

        # A savings goal that lands "at risk": a ~23% faster pace closes the gap.
        savings = Goal(
            user_id=DEMO_USER_ID,
            name="Winter trip to Jeju",
            goal_type=GoalType.SAVINGS,
            target_amount_krw=Decimal("450000"),
            starting_amount_krw=Decimal("50000"),
            start_date=today - timedelta(days=20),
            target_date=today + timedelta(days=40),
        )
        session.add(savings)
        await session.flush()
        for days_ago in (20, 13, 6):
            session.add(GoalContribution(user_id=DEMO_USER_ID, goal_id=savings.id,
                                         amount_krw=Decimal("40000"), contributed_on=today - timedelta(days=days_ago)))

        next_month = date(today.year + (today.month == 12), today.month % 12 + 1, 1)
        session.add(Goal(
            user_id=DEMO_USER_ID,
            name="Cafés this month",
            goal_type=GoalType.SPENDING_CAP,
            target_amount_krw=Decimal("80000"),
            category=ExpenseCategory.CAFES_AND_DINING,
            start_date=today.replace(day=1),
            target_date=next_month - timedelta(days=1),
        ))

        for stream in await _income_streams():
            session.add(stream)
        for exposure in _exposure_sessions(today):
            session.add(exposure)

        await session.commit()

    print(f"Seeded {DEMO_EMAIL}: {len(rows)} expenses over {HISTORY_MONTHS} months, 2 goals, "
          f"2 income streams, savings, receipts and screen-time sessions.")
    print(f"Log in with: email={DEMO_EMAIL}  password={DEMO_PASSWORD}")


if __name__ == "__main__":
    asyncio.run(seed())
