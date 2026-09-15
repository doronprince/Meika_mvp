import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import GoalType
from app.models.expense import Expense
from app.models.goal import Goal, GoalContribution
from app.models.user import User
from app.schemas.goal import GoalContributionCreate, GoalCreate, GoalRead
from app.services.currency_display import DisplayCurrency, resolve_display_currency
from app.services.goal_forecast import forecast_goal


class NotASavingsGoalError(Exception):
    pass


class ContributionBeforeStartError(Exception):
    pass


async def create_goal(
    db: AsyncSession, user_id: uuid.UUID, data: GoalCreate, *, today: date | None = None
) -> GoalRead | None:
    user = await db.get(User, user_id)
    if user is None:
        return None

    today = today or date.today()
    goal = Goal(user_id=user_id, **data.model_dump(exclude={"start_date"}), start_date=data.start_date or today)
    db.add(goal)
    await db.commit()
    await db.refresh(goal)
    display = await resolve_display_currency(user.preferred_currency)
    return await _to_read(db, goal, display, today)


async def list_goals(db: AsyncSession, user_id: uuid.UUID, *, today: date | None = None) -> list[GoalRead]:
    today = today or date.today()
    result = await db.execute(select(Goal).where(Goal.user_id == user_id).order_by(Goal.target_date))
    goals = list(result.scalars().all())
    display = await _display_for(db, user_id)
    return [await _to_read(db, goal, display, today) for goal in goals]


async def get_goal(
    db: AsyncSession, user_id: uuid.UUID, goal_id: uuid.UUID, *, today: date | None = None
) -> GoalRead | None:
    goal = await _get_owned(db, user_id, goal_id)
    if goal is None:
        return None
    return await _to_read(db, goal, await _display_for(db, user_id), today or date.today())


async def delete_goal(db: AsyncSession, user_id: uuid.UUID, goal_id: uuid.UUID) -> bool:
    result = await db.execute(delete(Goal).where(Goal.id == goal_id, Goal.user_id == user_id))
    await db.commit()
    return result.rowcount > 0


async def add_contribution(
    db: AsyncSession,
    user_id: uuid.UUID,
    goal_id: uuid.UUID,
    data: GoalContributionCreate,
    *,
    today: date | None = None,
) -> GoalRead | None:
    goal = await _get_owned(db, user_id, goal_id)
    if goal is None:
        return None
    if goal.goal_type != GoalType.SAVINGS:
        raise NotASavingsGoalError("Contributions only apply to savings goals — spending caps track expenses")

    today = today or date.today()
    contributed_on = data.contributed_on or today
    if contributed_on < goal.start_date:
        raise ContributionBeforeStartError("Money set aside before the start date belongs in starting_amount_krw")

    db.add(
        GoalContribution(
            user_id=user_id,
            goal_id=goal.id,
            amount_krw=data.amount_krw,
            contributed_on=contributed_on,
            note=data.note,
        )
    )
    await db.commit()
    return await get_goal(db, user_id, goal_id, today=today)


async def list_contributions(
    db: AsyncSession, user_id: uuid.UUID, goal_id: uuid.UUID
) -> list[GoalContribution] | None:
    if await _get_owned(db, user_id, goal_id) is None:
        return None
    result = await db.execute(
        select(GoalContribution)
        .where(GoalContribution.goal_id == goal_id, GoalContribution.user_id == user_id)
        .order_by(GoalContribution.contributed_on.desc())
    )
    return list(result.scalars().all())


async def _get_owned(db: AsyncSession, user_id: uuid.UUID, goal_id: uuid.UUID) -> Goal | None:
    result = await db.execute(select(Goal).where(Goal.id == goal_id, Goal.user_id == user_id))
    return result.scalar_one_or_none()


async def _display_for(db: AsyncSession, user_id: uuid.UUID) -> DisplayCurrency:
    user = await db.get(User, user_id)
    return await resolve_display_currency(user.preferred_currency if user else None)


async def _progress_krw(db: AsyncSession, goal: Goal, today: date) -> Decimal:
    if goal.goal_type == GoalType.SAVINGS:
        contributed = await db.scalar(
            select(func.coalesce(func.sum(GoalContribution.amount_krw), 0)).where(
                GoalContribution.user_id == goal.user_id,
                GoalContribution.goal_id == goal.id,
                GoalContribution.contributed_on <= today,
            )
        )
        return goal.starting_amount_krw + Decimal(contributed)

    # Spending caps count the true economic cost (amount + transit), same as
    # the dashboard, over the goal's window up to today.
    stmt = select(func.coalesce(func.sum(Expense.amount_krw + Expense.transit_cost_krw), 0)).where(
        Expense.user_id == goal.user_id,
        Expense.occurred_on >= goal.start_date,
        Expense.occurred_on <= min(today, goal.target_date),
    )
    if goal.category is not None:
        stmt = stmt.where(Expense.category == goal.category)
    return Decimal(await db.scalar(stmt))


async def _to_read(db: AsyncSession, goal: Goal, display: DisplayCurrency, today: date) -> GoalRead:
    forecast = forecast_goal(
        goal_type=goal.goal_type,
        target_krw=goal.target_amount_krw,
        start_date=goal.start_date,
        target_date=goal.target_date,
        today=today,
        progress_krw=await _progress_krw(db, goal, today),
        display=display,
        starting_krw=goal.starting_amount_krw,
        category=goal.category,
    )
    return GoalRead(
        id=goal.id,
        name=goal.name,
        goal_type=goal.goal_type,
        target_amount_krw=goal.target_amount_krw,
        starting_amount_krw=goal.starting_amount_krw,
        category=goal.category,
        start_date=goal.start_date,
        target_date=goal.target_date,
        created_at=goal.created_at,
        forecast=forecast,
    )
