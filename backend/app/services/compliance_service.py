"""Database side of tax & compliance foresight: loads the user's ledger,
profile and overrides, then hands everything to the pure engine in
app/services/compliance_engine.py.

[[no-tax-advice]]: nothing here states law or gives advice. The module flags
POSSIBLE questions from arithmetic on logged expenses, always against an
assumed figure the user can change, and always refers the user to a
qualified professional. The Copilot never sends a tax question to Gemini —
see the routing branch in app/ai/copilot_service.py.

No external service is involved. With no network at all the module still
works; only the prose falls back to KRW when live FX is down.
"""

import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.compliance import ComplianceRuleOverride, ExpenseTaxAnnotation, UserComplianceProfile
from app.models.enums import AssumptionSource
from app.models.expense import Expense
from app.models.user import User
from app.schemas.compliance import (
    ComplianceForesightResult,
    ComplianceRuleOverrideUpdate,
    ComplianceRuleView,
    ComplianceSettingsRead,
    ComplianceSettingsUpdate,
    ExpenseTaxAnnotationRead,
    ExpenseTaxAnnotationUpsert,
)
from app.services import compliance_detectors as det
from app.services.compliance_engine import effective_rule, evaluate_ledger
from app.services.compliance_rules import ComplianceRuleSpec, load_ruleset
from app.services.currency_display import resolve_display_currency


class RuleNotFoundError(Exception):
    pass


class ExpenseNotFoundError(Exception):
    pass


class InvalidOverrideError(Exception):
    pass


async def get_foresight(
    db: AsyncSession, user_id: uuid.UUID, *, today: date | None = None, bands: det.BandConfig = det.DEFAULT_BANDS
) -> ComplianceForesightResult | None:
    user = await db.get(User, user_id)
    if user is None:
        return None

    today = today or date.today()
    display = await resolve_display_currency(user.preferred_currency)
    profile = await _profile(db, user_id)
    fiscal = det.fiscal_window(
        today,
        profile.fiscal_year_start_month if profile else 1,
        profile.fiscal_year_start_day if profile else 1,
        is_default=profile is None,
    )

    first_day = await db.scalar(
        select(func.min(Expense.occurred_on)).where(Expense.user_id == user_id, Expense.occurred_on <= today)
    )
    expense_count = await db.scalar(
        select(func.count()).select_from(Expense).where(Expense.user_id == user_id, Expense.occurred_on <= today)
    )
    lookback_start = min(fiscal.start, today - timedelta(days=det.MAX_LOOKBACK_DAYS))
    expenses = (
        await db.execute(
            select(Expense).where(
                Expense.user_id == user_id, Expense.occurred_on >= lookback_start, Expense.occurred_on <= today
            )
        )
    ).scalars().all()
    documented = dict(
        (
            await db.execute(
                select(ExpenseTaxAnnotation.expense_id, ExpenseTaxAnnotation.has_documentation).where(
                    ExpenseTaxAnnotation.user_id == user_id
                )
            )
        ).all()
    )
    lines = [
        det.LedgerLine(
            occurred_on=e.occurred_on,
            title=e.title,
            category=e.category,
            amount_krw=e.amount_krw,
            transit_cost_krw=e.transit_cost_krw,
            store_name=e.store_name,
            notes=e.notes,
            original_currency=e.original_currency,
            original_amount=e.original_amount,
            has_documentation=bool(documented.get(e.id, False)),
            expense_id=e.id,
        )
        for e in expenses
    ]

    return evaluate_ledger(
        lines=lines,
        ctx=det.EvalContext(today=today, fiscal=fiscal, ledger_first_day=first_day),
        ruleset=load_ruleset(),
        overrides=await _overrides(db, user_id),
        display=display,
        expense_count=expense_count or 0,
        residence_jurisdiction=profile.residence_jurisdiction if profile else None,
        bands=bands,
    )


async def get_rules(db: AsyncSession, user_id: uuid.UUID) -> list[ComplianceRuleView] | None:
    if await db.get(User, user_id) is None:
        return None
    overrides = await _overrides(db, user_id)
    return [_rule_view(spec, overrides.get(spec.rule_key)) for spec in load_ruleset().rules]


async def set_rule_override(
    db: AsyncSession, user_id: uuid.UUID, rule_key: str, data: ComplianceRuleOverrideUpdate
) -> ComplianceRuleView | None:
    spec = load_ruleset().get(rule_key)
    if spec is None:
        raise RuleNotFoundError(rule_key)
    if await db.get(User, user_id) is None:
        return None

    changes = data.model_dump(exclude_unset=True)
    if changes.get("threshold_amount_krw") is not None and spec.threshold is None:
        raise InvalidOverrideError("This rule has no amount to change; it looks for a pattern, not a figure.")

    row = (await _overrides(db, user_id)).get(rule_key)
    if row is None:
        row = ComplianceRuleOverride(user_id=user_id, rule_key=rule_key, is_enabled=True)
        db.add(row)

    if "threshold_amount_krw" in changes:
        row.threshold_amount_krw = changes["threshold_amount_krw"]
    if "is_enabled" in changes:
        row.is_enabled = changes["is_enabled"]

    if "assumption_source" in changes:
        source = changes["assumption_source"]
    elif "threshold_amount_krw" in changes:
        # Typing your own figure makes it yours; clearing it goes back to Meika's default.
        source = (
            AssumptionSource.USER_SET
            if changes["threshold_amount_krw"] is not None
            else AssumptionSource.UNVERIFIED_DEFAULT
        )
    else:
        source = row.assumption_source or AssumptionSource.UNVERIFIED_DEFAULT
    row.assumption_source = source
    if source == AssumptionSource.USER_VERIFIED:
        row.verified_at = datetime.now(timezone.utc)
        row.verified_note = changes.get("verified_note", row.verified_note)
    else:
        row.verified_at = None
        row.verified_note = None

    await db.commit()
    await db.refresh(row)
    return _rule_view(spec, row)


async def delete_rule_override(db: AsyncSession, user_id: uuid.UUID, rule_key: str) -> None:
    if load_ruleset().get(rule_key) is None:
        raise RuleNotFoundError(rule_key)
    await db.execute(
        delete(ComplianceRuleOverride).where(
            ComplianceRuleOverride.user_id == user_id, ComplianceRuleOverride.rule_key == rule_key
        )
    )
    await db.commit()


async def get_settings(db: AsyncSession, user_id: uuid.UUID) -> ComplianceSettingsRead | None:
    if await db.get(User, user_id) is None:
        return None
    return _settings_read(await _profile(db, user_id))


async def update_settings(
    db: AsyncSession, user_id: uuid.UUID, data: ComplianceSettingsUpdate
) -> ComplianceSettingsRead | None:
    if await db.get(User, user_id) is None:
        return None
    profile = await _profile(db, user_id)
    if profile is None:
        profile = UserComplianceProfile(user_id=user_id, fiscal_year_start_month=1, fiscal_year_start_day=1)
        db.add(profile)
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(profile, field, value)
    profile.jurisdiction_confirmed_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(profile)
    return _settings_read(profile)


async def upsert_annotation(
    db: AsyncSession, user_id: uuid.UUID, data: ExpenseTaxAnnotationUpsert, *, today: date | None = None
) -> ExpenseTaxAnnotationRead:
    await _require_own_expense(db, user_id, data.expense_id)
    row = (
        await db.execute(
            select(ExpenseTaxAnnotation).where(
                ExpenseTaxAnnotation.user_id == user_id, ExpenseTaxAnnotation.expense_id == data.expense_id
            )
        )
    ).scalar_one_or_none()
    if row is None:
        row = ExpenseTaxAnnotation(user_id=user_id, expense_id=data.expense_id)
        db.add(row)
    row.has_documentation = data.has_documentation
    row.document_ref = data.document_ref
    row.annotated_on = today or date.today()
    await db.commit()
    await db.refresh(row)
    return ExpenseTaxAnnotationRead.model_validate(row)


async def delete_annotation(db: AsyncSession, user_id: uuid.UUID, expense_id: uuid.UUID) -> None:
    await _require_own_expense(db, user_id, expense_id)
    await db.execute(
        delete(ExpenseTaxAnnotation).where(
            ExpenseTaxAnnotation.user_id == user_id, ExpenseTaxAnnotation.expense_id == expense_id
        )
    )
    await db.commit()


async def _require_own_expense(db: AsyncSession, user_id: uuid.UUID, expense_id: uuid.UUID) -> None:
    # The annotation's own user_id column can't stand in for this check: a
    # caller could otherwise annotate another tenant's expense id and the
    # row would look perfectly well-formed.
    owned = await db.scalar(select(Expense.id).where(Expense.id == expense_id, Expense.user_id == user_id))
    if owned is None:
        raise ExpenseNotFoundError(str(expense_id))


async def _profile(db: AsyncSession, user_id: uuid.UUID) -> UserComplianceProfile | None:
    return (
        await db.execute(select(UserComplianceProfile).where(UserComplianceProfile.user_id == user_id))
    ).scalar_one_or_none()


async def _overrides(db: AsyncSession, user_id: uuid.UUID) -> dict[str, ComplianceRuleOverride]:
    rows = (
        await db.execute(select(ComplianceRuleOverride).where(ComplianceRuleOverride.user_id == user_id))
    ).scalars().all()
    return {row.rule_key: row for row in rows}


def _settings_read(profile: UserComplianceProfile | None) -> ComplianceSettingsRead:
    if profile is None:
        return ComplianceSettingsRead(
            residence_jurisdiction=None,
            home_jurisdiction=None,
            fiscal_year_start_month=1,
            fiscal_year_start_day=1,
            is_default=True,
        )
    return ComplianceSettingsRead(
        residence_jurisdiction=profile.residence_jurisdiction,
        home_jurisdiction=profile.home_jurisdiction,
        fiscal_year_start_month=profile.fiscal_year_start_month,
        fiscal_year_start_day=profile.fiscal_year_start_day,
        is_default=False,
    )


def _rule_view(spec: ComplianceRuleSpec, override: ComplianceRuleOverride | None) -> ComplianceRuleView:
    rule = effective_rule(spec, override)
    packaged: Decimal | None = spec.threshold.amount_krw if spec.threshold else None
    return ComplianceRuleView(
        rule_key=spec.rule_key,
        title=spec.title,
        question=spec.question,
        detector_kind=spec.detector_kind,
        effective_threshold_krw=rule.threshold_krw,
        packaged_threshold_krw=packaged,
        threshold_basis_note=spec.basis_note if rule.use_basis else None,
        assumption_statement=spec.assumption_statement,
        verification_prompt=spec.verification_prompt,
        source_note=spec.source_note,
        assumption_source=rule.assumption_source,
        is_enabled=rule.is_enabled,
        verified_at=rule.verified_at,
        verified_note=rule.verified_note,
        max_severity=spec.max_severity,
    )
