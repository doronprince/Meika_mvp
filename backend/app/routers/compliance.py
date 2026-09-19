import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user_id
from app.db.session import get_db
from app.schemas.compliance import (
    ComplianceForesightResult,
    ComplianceRuleOverrideUpdate,
    ComplianceRuleView,
    ComplianceSettingsRead,
    ComplianceSettingsUpdate,
    ExpenseTaxAnnotationRead,
    ExpenseTaxAnnotationUpsert,
)
from app.services import compliance_service

router = APIRouter(prefix="/compliance", tags=["Tax & Compliance Foresight"])

_USER_NOT_FOUND = HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")


@router.get("/foresight", response_model=ComplianceForesightResult)
async def get_foresight(
    db: AsyncSession = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
) -> ComplianceForesightResult:
    result = await compliance_service.get_foresight(db, user_id)
    if result is None:
        raise _USER_NOT_FOUND
    return result


@router.get("/rules", response_model=list[ComplianceRuleView])
async def get_rules(
    db: AsyncSession = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
) -> list[ComplianceRuleView]:
    rules = await compliance_service.get_rules(db, user_id)
    if rules is None:
        raise _USER_NOT_FOUND
    return rules


@router.put("/rules/{rule_key}/override", response_model=ComplianceRuleView)
async def set_rule_override(
    rule_key: str,
    payload: ComplianceRuleOverrideUpdate,
    db: AsyncSession = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
) -> ComplianceRuleView:
    try:
        view = await compliance_service.set_rule_override(db, user_id, rule_key, payload)
    except compliance_service.RuleNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Rule not found")
    except compliance_service.InvalidOverrideError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc))
    if view is None:
        raise _USER_NOT_FOUND
    return view


@router.delete("/rules/{rule_key}/override", status_code=status.HTTP_204_NO_CONTENT)
async def delete_rule_override(
    rule_key: str,
    db: AsyncSession = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
) -> None:
    # Idempotent: deleting nothing is the requested end state.
    try:
        await compliance_service.delete_rule_override(db, user_id, rule_key)
    except compliance_service.RuleNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Rule not found")


@router.get("/settings", response_model=ComplianceSettingsRead)
async def get_settings(
    db: AsyncSession = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
) -> ComplianceSettingsRead:
    settings_read = await compliance_service.get_settings(db, user_id)
    if settings_read is None:
        raise _USER_NOT_FOUND
    return settings_read


@router.put("/settings", response_model=ComplianceSettingsRead)
async def update_settings(
    payload: ComplianceSettingsUpdate,
    db: AsyncSession = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
) -> ComplianceSettingsRead:
    settings_read = await compliance_service.update_settings(db, user_id, payload)
    if settings_read is None:
        raise _USER_NOT_FOUND
    return settings_read


@router.post("/annotations", response_model=ExpenseTaxAnnotationRead)
async def upsert_annotation(
    payload: ExpenseTaxAnnotationUpsert,
    db: AsyncSession = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
) -> ExpenseTaxAnnotationRead:
    try:
        return await compliance_service.upsert_annotation(db, user_id, payload)
    except compliance_service.ExpenseNotFoundError:
        # 404, never 403: another user's expense id is indistinguishable from
        # one that doesn't exist.
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Expense not found")


@router.delete("/annotations/{expense_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_annotation(
    expense_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
) -> None:
    try:
        await compliance_service.delete_annotation(db, user_id, expense_id)
    except compliance_service.ExpenseNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Expense not found")
