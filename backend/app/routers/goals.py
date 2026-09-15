import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user_id
from app.db.session import get_db
from app.schemas.goal import GoalContributionCreate, GoalContributionRead, GoalCreate, GoalRead
from app.services import goal_service

router = APIRouter(prefix="/goals", tags=["Goals"])


@router.post("", response_model=GoalRead, status_code=status.HTTP_201_CREATED)
async def create_goal(
    payload: GoalCreate,
    db: AsyncSession = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
) -> GoalRead:
    goal = await goal_service.create_goal(db, user_id, payload)
    if goal is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return goal


@router.get("", response_model=list[GoalRead])
async def list_goals(
    db: AsyncSession = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
) -> list[GoalRead]:
    return await goal_service.list_goals(db, user_id)


@router.get("/{goal_id}", response_model=GoalRead)
async def get_goal(
    goal_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
) -> GoalRead:
    goal = await goal_service.get_goal(db, user_id, goal_id)
    if goal is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Goal not found")
    return goal


@router.delete("/{goal_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_goal(
    goal_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
) -> None:
    if not await goal_service.delete_goal(db, user_id, goal_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Goal not found")


@router.post("/{goal_id}/contributions", response_model=GoalRead, status_code=status.HTTP_201_CREATED)
async def add_contribution(
    goal_id: uuid.UUID,
    payload: GoalContributionCreate,
    db: AsyncSession = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
) -> GoalRead:
    try:
        goal = await goal_service.add_contribution(db, user_id, goal_id, payload)
    except (goal_service.NotASavingsGoalError, goal_service.ContributionBeforeStartError) as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc))
    if goal is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Goal not found")
    return goal


@router.get("/{goal_id}/contributions", response_model=list[GoalContributionRead])
async def list_contributions(
    goal_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
) -> list[GoalContributionRead]:
    contributions = await goal_service.list_contributions(db, user_id, goal_id)
    if contributions is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Goal not found")
    return [GoalContributionRead.model_validate(c) for c in contributions]
