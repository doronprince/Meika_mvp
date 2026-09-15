"""Financial survival time under compound shocks.

Answers "how long would my savings last if several bad things happened at
once — and which of them is doing the damage?" from the user's own rows:

  * users.liquid_savings_krw — the starting balance
  * income_streams — recurring monthly inflows, in the currency actually paid
  * expenses — the last LEDGER_WINDOW_DAYS of logged spend (including transit,
    the same True Economic Cost the dashboard uses), split into essential and
    discretionary by category

The engine is a deterministic month-by-month cash-flow walk — no randomness,
no trained model — so every figure can be recomputed by hand from the
factors it ships with ([[xai-enforcement]]).

Attribution is exact Shapley: with n shocks the engine simulates all 2^n
subsets and credits each shock with its average marginal runway loss over
every order the shocks could arrive in. Unlike leave-one-out, Shapley values
are guaranteed to sum to the joint loss (efficiency); the report computes
and exposes that sum's residual instead of asking the reader to trust it.
The gap between the joint loss and the sum of standalone losses is reported
as the compound interaction: positive when shocks amplify each other,
negative when they overlap (e.g. losing an income stream AND a devaluation
of that same stream — the second shock has less left to destroy).
"""

import math
import uuid
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import ExpenseCategory
from app.models.expense import Expense
from app.models.income import IncomeStream
from app.models.user import User
from app.schemas.common import RiskLevel, XAIFactor
from app.schemas.survival import (
    CategoryBaseline,
    CurrencyDevaluationShock,
    ExpenseIncreaseShock,
    IncomeLossShock,
    InflationShock,
    OneOffExpenseShock,
    Runway,
    ShockAttribution,
    ShockPreset,
    SpendBaseline,
    SurvivalReport,
    SurvivalSimulationRequest,
    SurvivalState,
    TrajectoryPoint,
)
from app.services import fx_service
from app.services.currency_display import DisplayCurrency, resolve_display_currency

LEDGER_WINDOW_DAYS = 90
# Below one rent cycle, a ledger average can miss a monthly bill entirely
# (or catch it and triple it), so the declared monthly budget is used as the
# baseline instead of a number drawn from too little data.
MIN_LEDGER_DAYS = 28
DAYS_PER_MONTH = 365.25 / 12

# The common 3-6 months-of-expenses emergency-fund rule of thumb, applied to
# the shocked runway. A declared heuristic, not a calibrated threshold.
RUNWAY_HIGH_RISK_MONTHS = 3
RUNWAY_MODERATE_RISK_MONTHS = 6

ESSENTIAL_CATEGORIES = frozenset(
    {
        ExpenseCategory.GROCERIES,
        ExpenseCategory.TRANSPORTATION,
        ExpenseCategory.HOUSING_AND_UTILITIES,
        ExpenseCategory.EDUCATION,
    }
)

ASSUMPTIONS = [
    "Month-by-month simulation; within a month, money is assumed to flow evenly, so a partial month "
    "is the fraction of that month's shortfall the remaining savings could cover.",
    "Essential categories: groceries, transportation, housing & utilities, education. Everything "
    "else is discretionary and is the only spending the 'with cuts' scenario reduces.",
    f"Spending baseline is the daily average of the last {LEDGER_WINDOW_DAYS} days of logged expenses "
    f"(including transit), scaled to {DAYS_PER_MONTH:.2f} days per month, once at least "
    f"{MIN_LEDGER_DAYS} days are logged; before that, the monthly budget is used.",
    "Savings earn no interest and no new borrowing is assumed: runway ends when savings reach zero.",
    "A currency devaluation reduces only income streams paid in that currency; savings are held in KRW.",
    "For attribution, a scenario whose savings never run out is scored at the horizon length, so "
    "shocks that don't exhaust savings within the horizon can be under-credited.",
    f"Risk level uses the 3-6 month emergency-fund rule of thumb on the shocked runway: under "
    f"{RUNWAY_HIGH_RISK_MONTHS} months is high, under {RUNWAY_MODERATE_RISK_MONTHS} is moderate.",
]

_CENTS = Decimal("0.01")


def _q2(value: Decimal) -> Decimal:
    return value.quantize(_CENTS, rounding=ROUND_HALF_UP)


def _dec(value: float) -> Decimal:
    return _q2(Decimal(repr(value)))


class UnknownIncomeStreamError(Exception):
    pass


@dataclass(frozen=True)
class IncomeLine:
    stream_id: uuid.UUID | None
    label: str
    currency: str
    monthly_krw: float


@dataclass(frozen=True)
class EngineInputs:
    savings_krw: float
    incomes: tuple[IncomeLine, ...]
    # ExpenseCategory, or None for the unclassified monthly-budget baseline.
    category_monthly_krw: dict
    horizon_months: int


@dataclass(frozen=True)
class SimulationRun:
    balances: tuple[float, ...]  # month-end balance; index 0 is month 1
    runway_months: float | None
    cuts_start_month: int | None


def is_essential(category: ExpenseCategory | None) -> bool:
    return category is None or category in ESSENTIAL_CATEGORIES


def _active(start: int, duration: int | None, month: int) -> bool:
    return month >= start and (duration is None or month < start + duration)


def simulate(
    inputs: EngineInputs,
    shocks: list,
    *,
    cut_pct: float = 0.0,
    cut_trigger_krw: float | None = None,
) -> SimulationRun:
    balance = inputs.savings_krw
    balances: list[float] = []
    runway: float | None = None
    cuts_active = False
    cuts_start: int | None = None

    for month in range(1, inputs.horizon_months + 1):
        if cut_pct > 0 and not cuts_active and cut_trigger_krw is not None and balance < cut_trigger_krw:
            cuts_active = True
            cuts_start = month

        income = 0.0
        for line in inputs.incomes:
            multiplier = 1.0
            for shock in shocks:
                if isinstance(shock, IncomeLossShock):
                    targets_line = shock.income_stream_id is None or shock.income_stream_id == line.stream_id
                    if targets_line and _active(shock.start_month, shock.duration_months, month):
                        multiplier *= 1 - float(shock.pct) / 100
                elif isinstance(shock, CurrencyDevaluationShock):
                    if month >= shock.start_month and shock.currency.upper() == line.currency:
                        multiplier *= 1 - float(shock.pct) / 100
            income += line.monthly_krw * multiplier

        spend = 0.0
        for category, base in inputs.category_monthly_krw.items():
            multiplier = 1.0
            for shock in shocks:
                if isinstance(shock, ExpenseIncreaseShock):
                    applies = shock.category == category if shock.category is not None else is_essential(category)
                    if applies and _active(shock.start_month, shock.duration_months, month):
                        multiplier *= 1 + float(shock.pct) / 100
                elif isinstance(shock, InflationShock):
                    if is_essential(category) and month >= shock.start_month:
                        elapsed_years = (month - shock.start_month + 1) / 12
                        multiplier *= (1 + float(shock.annual_pct) / 100) ** elapsed_years
            if cuts_active and not is_essential(category):
                multiplier *= 1 - cut_pct / 100
            spend += base * multiplier

        one_off = sum(
            float(shock.amount_krw)
            for shock in shocks
            if isinstance(shock, OneOffExpenseShock) and shock.month == month
        )

        new_balance = balance + income - spend - one_off
        if runway is None and new_balance < 0:
            covered_fraction = balance / (balance - new_balance) if balance > 0 else 0.0
            runway = (month - 1) + covered_fraction
        balances.append(new_balance)
        balance = new_balance

    return SimulationRun(balances=tuple(balances), runway_months=runway, cuts_start_month=cuts_start)


def _capped(run: SimulationRun, horizon: int) -> float:
    return float(horizon) if run.runway_months is None else run.runway_months


def shapley_attribution(inputs: EngineInputs, shocks: list) -> tuple[list[float], list[float], float]:
    """(Shapley months lost per shock, standalone months lost per shock, joint months lost)."""
    n = len(shocks)
    horizon = inputs.horizon_months
    baseline = _capped(simulate(inputs, []), horizon)

    loss: dict[int, float] = {}
    for mask in range(1 << n):
        subset = [shocks[i] for i in range(n) if mask >> i & 1]
        loss[mask] = baseline - _capped(simulate(inputs, subset), horizon)

    shapley: list[float] = []
    for i in range(n):
        total = 0.0
        for mask in range(1 << n):
            if mask >> i & 1:
                continue
            k = bin(mask).count("1")
            weight = math.factorial(k) * math.factorial(n - k - 1) / math.factorial(n)
            total += weight * (loss[mask | (1 << i)] - loss[mask])
        shapley.append(total)

    standalone = [loss[1 << i] for i in range(n)]
    return shapley, standalone, loss[(1 << n) - 1]


def _pct(value: Decimal) -> str:
    return f"{value.normalize():f}"


def _category_name(category: ExpenseCategory | None) -> str:
    if category is None:
        return "Essential spending"
    return category.value.replace("_", " ").capitalize()


def shock_label(shock, display: DisplayCurrency, stream_labels: dict[uuid.UUID, str]) -> str:
    if shock.label:
        return shock.label
    if isinstance(shock, IncomeLossShock):
        if shock.income_stream_id is not None:
            text = f"{stream_labels.get(shock.income_stream_id, 'Income stream')} falls {_pct(shock.pct)}%"
        else:
            text = f"Income falls {_pct(shock.pct)}%"
        if shock.duration_months:
            text += f" for {shock.duration_months} month(s)"
    elif isinstance(shock, ExpenseIncreaseShock):
        text = f"{_category_name(shock.category)} costs rise {_pct(shock.pct)}%"
        if shock.duration_months:
            text += f" for {shock.duration_months} month(s)"
    elif isinstance(shock, CurrencyDevaluationShock):
        text = f"{shock.currency.upper()} loses {_pct(shock.pct)}% against KRW"
    elif isinstance(shock, OneOffExpenseShock):
        return f"One-off expense of {display.format(shock.amount_krw)} in month {shock.month}"
    else:
        text = f"Essential prices rise {_pct(shock.annual_pct)}% a year"
    start = getattr(shock, "start_month", 1)
    if start > 1:
        text += f" from month {start}"
    return text


def _runway(run: SimulationRun) -> Runway:
    if run.runway_months is None:
        return Runway(months=None, days=None, sustainable_within_horizon=True)
    return Runway(
        months=round(run.runway_months, 2),
        days=int(round(run.runway_months * DAYS_PER_MONTH)),
        sustainable_within_horizon=False,
    )


def _risk_level(run: SimulationRun) -> RiskLevel:
    if run.runway_months is None or run.runway_months >= RUNWAY_MODERATE_RISK_MONTHS:
        return RiskLevel.LOW
    if run.runway_months >= RUNWAY_HIGH_RISK_MONTHS:
        return RiskLevel.MODERATE
    return RiskLevel.HIGH


def build_report(
    *,
    savings_krw: Decimal | None,
    incomes: list[IncomeLine],
    category_monthly_krw: dict,
    spend_source: str,
    ledger_days: int,
    monthly_budget_krw: Decimal,
    request: SurvivalSimulationRequest,
    display: DisplayCurrency,
    today: date,
    stream_labels: dict[uuid.UUID, str] | None = None,
    fx_snapshot_labels: list[str] | None = None,
) -> SurvivalReport:
    """Pure: everything the report says is derived from these arguments."""
    stream_labels = stream_labels or {}
    fx_snapshot_labels = fx_snapshot_labels or []

    def money(value: float) -> str:
        return display.format(_dec(value))

    monthly_income = sum(line.monthly_krw for line in incomes)
    essential = sum(v for c, v in category_monthly_krw.items() if is_essential(c))
    discretionary = sum(v for c, v in category_monthly_krw.items() if not is_essential(c))
    net = monthly_income - essential - discretionary

    baseline = SpendBaseline(
        monthly_income_krw=_dec(monthly_income),
        monthly_essential_krw=_dec(essential),
        monthly_discretionary_krw=_dec(discretionary),
        monthly_net_krw=_dec(net),
        spend_source=spend_source,
        ledger_days=ledger_days,
        income_streams_counted=len(incomes),
        categories=sorted(
            (
                CategoryBaseline(category=c, monthly_krw=_dec(v), essential=is_essential(c))
                for c, v in category_monthly_krw.items()
            ),
            key=lambda item: item.monthly_krw,
            reverse=True,
        ),
    )

    factors: list[XAIFactor] = []

    if incomes:
        detail = f"{len(incomes)} active income stream(s) totalling {money(monthly_income)} per month"
        if fx_snapshot_labels:
            detail += (
                f"; live exchange rates were unavailable, so {', '.join(fx_snapshot_labels)} "
                "use the rate saved when entered"
            )
        factors.append(XAIFactor(label="Monthly income counted", detail=detail + ".", value=round(monthly_income, 2)))
    else:
        factors.append(
            XAIFactor(
                label="No income recorded",
                detail="Runway assumes zero income. Add your income streams (salary, part-time work, "
                "allowance, scholarship) if you have any.",
                value=0.0,
            )
        )

    if spend_source == "ledger":
        spend_detail = (
            f"{money(essential)} essential + {money(discretionary)} discretionary per month, averaged over "
            f"the last {ledger_days} days of logged expenses (including transit)."
        )
    else:
        split_note = (
            ", split by the category mix logged so far"
            if any(c is not None for c in category_monthly_krw)
            else ", treated as fully essential because no expenses are logged yet"
        )
        spend_detail = (
            f"Only {ledger_days} day(s) of logged expenses (fewer than {MIN_LEDGER_DAYS}), so your monthly "
            f"budget of {display.format(monthly_budget_krw)} is the spending baseline{split_note}."
        )
    factors.append(
        XAIFactor(label="Monthly spending baseline", detail=spend_detail, value=round(essential + discretionary, 2))
    )

    if savings_krw is None:
        factors.append(
            XAIFactor(
                label="Liquid savings not set",
                detail="A runway needs a starting balance. Add your liquid savings (cash and accounts you can "
                "withdraw from immediately) to compute it.",
                value=None,
            )
        )
        return SurvivalReport(
            state=SurvivalState.NEEDS_SAVINGS,
            as_of=today,
            horizon_months=request.horizon_months,
            liquid_savings_krw=None,
            baseline=baseline,
            baseline_runway=None,
            shocked_runway=None,
            shocked_with_cuts_runway=None,
            cuts_start_month=None,
            risk_level=None,
            attributions=[],
            joint_months_lost=None,
            interaction_months=None,
            attribution_residual_months=None,
            trajectory=[],
            factors=factors,
            assumptions=ASSUMPTIONS,
        )

    savings = float(savings_krw)
    inputs = EngineInputs(
        savings_krw=savings,
        incomes=tuple(incomes),
        category_monthly_krw=dict(category_monthly_krw),
        horizon_months=request.horizon_months,
    )
    shocks = list(request.shocks)
    cut_pct = float(request.discretionary_cut_pct)
    cut_trigger = float(request.cut_trigger_buffer_months) * essential
    horizon = request.horizon_months

    baseline_run = simulate(inputs, [])
    shocked_run = simulate(inputs, shocks)
    cuts_run = simulate(inputs, shocks, cut_pct=cut_pct, cut_trigger_krw=cut_trigger)

    factors.insert(
        0,
        XAIFactor(
            label="Starting balance",
            detail=f"Liquid savings of {display.format(savings_krw)} from your profile.",
            value=savings,
        ),
    )

    if baseline_run.runway_months is None:
        factors.append(
            XAIFactor(
                label="Sustainable without shocks",
                detail=f"Income of {money(monthly_income)} per month covers spending of "
                f"{money(essential + discretionary)}, so savings do not run out within {horizon} months.",
                value=round(net, 2),
            )
        )
    else:
        factors.append(
            XAIFactor(
                label="Baseline runway",
                detail=f"With no shock, savings fall by {money(-net)} per month "
                f"({money(monthly_income)} in, {money(essential + discretionary)} out) and last "
                f"{baseline_run.runway_months:.1f} months.",
                value=round(baseline_run.runway_months, 2),
            )
        )

    attributions: list[ShockAttribution] = []
    joint = interaction = residual = None
    if shocks:
        labels = [shock_label(s, display, stream_labels) for s in shocks]
        shapley, standalone, joint = shapley_attribution(inputs, shocks)
        interaction = joint - sum(standalone)
        residual = sum(shapley) - joint

        if shocked_run.runway_months is None:
            factors.append(
                XAIFactor(
                    label="Still sustainable under these shocks",
                    detail=f"Even with all {len(shocks)} shock(s) applied, savings do not run out within "
                    f"{horizon} months.",
                    value=None,
                )
            )
        else:
            factors.append(
                XAIFactor(
                    label="Runway under all selected shocks",
                    detail=f"With all {len(shocks)} shock(s) applied together, savings last "
                    f"{shocked_run.runway_months:.1f} months, {joint:.1f} months less than the baseline"
                    + (f" (baseline capped at the {horizon}-month horizon)" if baseline_run.runway_months is None else "")
                    + ".",
                    value=round(shocked_run.runway_months, 2),
                )
            )

        for index in sorted(range(len(shocks)), key=lambda i: shapley[i], reverse=True):
            share = (shapley[index] / joint * 100) if joint > 1e-9 else None
            attributions.append(
                ShockAttribution(
                    shock_index=index,
                    label=labels[index],
                    kind=shocks[index].kind,
                    months_lost=round(shapley[index], 2),
                    standalone_months_lost=round(standalone[index], 2),
                    share_pct=round(share, 1) if share is not None else None,
                )
            )
            factors.append(
                XAIFactor(
                    label=labels[index],
                    detail=f"Accounts for {shapley[index]:.1f} months of lost runway"
                    + (f" ({share:.0f}% of the total)" if share is not None else "")
                    + f"; on its own it would cost {standalone[index]:.1f} months.",
                    value=round(shapley[index], 2),
                )
            )

        if len(shocks) >= 2:
            standalone_sum = sum(standalone)
            if interaction > 0.05:
                factors.append(
                    XAIFactor(
                        label="Shocks compound each other",
                        detail=f"Together they cost {joint:.1f} months; one at a time they would cost "
                        f"{standalone_sum:.1f} months in total. The extra {interaction:.1f} months is the cost "
                        "of facing them at the same time.",
                        value=round(interaction, 2),
                    )
                )
            elif interaction < -0.05:
                factors.append(
                    XAIFactor(
                        label="Shocks overlap",
                        detail=f"Together they cost {joint:.1f} months, less than the {standalone_sum:.1f} months "
                        "they cost one at a time, because part of their damage lands on the same money (or on "
                        "months past the horizon).",
                        value=round(interaction, 2),
                    )
                )
            else:
                factors.append(
                    XAIFactor(
                        label="Shocks act independently",
                        detail=f"The joint loss of {joint:.1f} months matches the {standalone_sum:.1f} months "
                        "they cost one at a time.",
                        value=round(interaction, 2),
                    )
                )

        factors.append(
            XAIFactor(
                label="Attribution adds up",
                detail=f"Per-shock losses sum to {sum(shapley):.2f} months against a joint loss of {joint:.2f} "
                f"months (residual {residual:.4f}), from exact Shapley values over all {2 ** len(shocks)} "
                "combinations of the selected shocks.",
                value=round(residual, 6),
            )
        )

    if cut_pct > 0:
        if discretionary <= 0:
            factors.append(
                XAIFactor(
                    label="No discretionary spending to cut",
                    detail="All baseline spending is in essential categories, so the 'with cuts' runway equals "
                    "the shocked runway.",
                    value=0.0,
                )
            )
        elif cuts_run.cuts_start_month is None:
            factors.append(
                XAIFactor(
                    label="Spending cuts never triggered",
                    detail=f"Savings stayed above {money(cut_trigger)} "
                    f"({_pct(request.cut_trigger_buffer_months)} months of essential spending) for the whole "
                    "horizon.",
                    value=None,
                )
            )
        else:
            gain = _capped(cuts_run, horizon) - _capped(shocked_run, horizon)
            outcome = (
                "savings no longer run out within the horizon"
                if cuts_run.runway_months is None
                else f"runway becomes {cuts_run.runway_months:.1f} months"
            )
            factors.append(
                XAIFactor(
                    label="Cutting discretionary spending",
                    detail=f"Cutting discretionary spending by {_pct(request.discretionary_cut_pct)}% from month "
                    f"{cuts_run.cuts_start_month}, when savings fall below {money(cut_trigger)}: {outcome} "
                    f"({gain:+.1f} months).",
                    value=round(gain, 2),
                )
            )

    trajectory = [
        TrajectoryPoint(
            month=month,
            baseline_balance_krw=_dec(baseline_run.balances[month - 1]),
            shocked_balance_krw=_dec(shocked_run.balances[month - 1]),
            shocked_with_cuts_balance_krw=_dec(cuts_run.balances[month - 1]),
        )
        for month in range(1, horizon + 1)
    ]

    return SurvivalReport(
        state=SurvivalState.COMPUTED,
        as_of=today,
        horizon_months=horizon,
        liquid_savings_krw=savings_krw,
        baseline=baseline,
        baseline_runway=_runway(baseline_run),
        shocked_runway=_runway(shocked_run),
        shocked_with_cuts_runway=_runway(cuts_run),
        cuts_start_month=cuts_run.cuts_start_month,
        risk_level=_risk_level(shocked_run),
        attributions=attributions,
        joint_months_lost=round(joint, 2) if joint is not None else None,
        interaction_months=round(interaction, 2) if interaction is not None else None,
        attribution_residual_months=round(residual, 6) if residual is not None else None,
        trajectory=trajectory,
        factors=factors,
        assumptions=ASSUMPTIONS,
    )


async def _active_streams(db: AsyncSession, user_id: uuid.UUID) -> list[IncomeStream]:
    result = await db.execute(
        select(IncomeStream).where(IncomeStream.user_id == user_id, IncomeStream.is_active.is_(True))
    )
    return list(result.scalars().all())


async def _income_lines(streams: list[IncomeStream]) -> tuple[list[IncomeLine], list[str]]:
    lines: list[IncomeLine] = []
    snapshot_labels: list[str] = []
    for stream in streams:
        if stream.currency == "KRW":
            krw = stream.monthly_amount
        else:
            try:
                krw = await fx_service.convert(stream.monthly_amount, stream.currency, "KRW")
            except fx_service.FxRateUnavailableError:
                krw = stream.monthly_amount_krw_snapshot
                snapshot_labels.append(stream.label)
        lines.append(
            IncomeLine(stream_id=stream.id, label=stream.label, currency=stream.currency, monthly_krw=float(krw))
        )
    return lines, snapshot_labels


async def _spend_baseline(db: AsyncSession, user: User, today: date) -> tuple[dict, str, int]:
    window_start = today - timedelta(days=LEDGER_WINDOW_DAYS - 1)
    result = await db.execute(
        select(Expense).where(
            Expense.user_id == user.id,
            Expense.occurred_on >= window_start,
            Expense.occurred_on <= today,
        )
    )
    expenses = list(result.scalars().all())

    totals: dict[ExpenseCategory, float] = defaultdict(float)
    for expense in expenses:
        totals[expense.category] += float(expense.amount_krw + expense.transit_cost_krw)
    ledger_days = (today - min(e.occurred_on for e in expenses)).days + 1 if expenses else 0

    if ledger_days >= MIN_LEDGER_DAYS:
        return {c: total / ledger_days * DAYS_PER_MONTH for c, total in totals.items()}, "ledger", ledger_days

    budget = float(user.monthly_budget_krw)
    logged = sum(totals.values())
    if logged > 0:
        return {c: budget * total / logged for c, total in totals.items()}, "monthly_budget", ledger_days
    return {None: budget}, "monthly_budget", ledger_days


async def simulate_for_user(
    db: AsyncSession, user_id: uuid.UUID, request: SurvivalSimulationRequest, *, today: date | None = None
) -> SurvivalReport | None:
    user = await db.get(User, user_id)
    if user is None:
        return None

    today = today or date.today()
    streams = await _active_streams(db, user_id)
    owned_ids = {stream.id for stream in streams}
    for shock in request.shocks:
        if isinstance(shock, IncomeLossShock) and shock.income_stream_id is not None:
            if shock.income_stream_id not in owned_ids:
                raise UnknownIncomeStreamError("income_stream_id does not match any of your active income streams")

    display = await resolve_display_currency(user.preferred_currency)
    incomes, snapshot_labels = await _income_lines(streams)
    categories, source, ledger_days = await _spend_baseline(db, user, today)

    return build_report(
        savings_krw=user.liquid_savings_krw,
        incomes=incomes,
        category_monthly_krw=categories,
        spend_source=source,
        ledger_days=ledger_days,
        monthly_budget_krw=user.monthly_budget_krw,
        request=request,
        display=display,
        today=today,
        stream_labels={stream.id: stream.label for stream in streams},
        fx_snapshot_labels=snapshot_labels,
    )


def build_presets(incomes: list[IncomeLine], category_monthly_krw: dict, display: DisplayCurrency) -> list[ShockPreset]:
    presets: list[ShockPreset] = []

    if incomes:
        largest = max(incomes, key=lambda line: line.monthly_krw)
        presets.append(
            ShockPreset(
                key="lose_largest_income",
                title=f"Lose {largest.label}",
                description=f"Your largest income stream ({display.format(_dec(largest.monthly_krw))}/month) "
                "stops from month 1.",
                shock=IncomeLossShock(pct=Decimal("100"), income_stream_id=largest.stream_id),
            )
        )
        presets.append(
            ShockPreset(
                key="income_drop_30_for_6_months",
                title="Income drops 30% for 6 months",
                description="Fewer shifts, a delayed allowance or a reduced stipend, then recovery.",
                shock=IncomeLossShock(pct=Decimal("30"), duration_months=6),
            )
        )
        foreign = [line for line in incomes if line.currency != "KRW"]
        if foreign:
            biggest_foreign = max(foreign, key=lambda line: line.monthly_krw)
            presets.append(
                ShockPreset(
                    key=f"devalue_{biggest_foreign.currency.lower()}_20",
                    title=f"{biggest_foreign.currency} loses 20% against KRW",
                    description=f"Money arriving in {biggest_foreign.currency} buys 20% fewer won from month 1.",
                    shock=CurrencyDevaluationShock(currency=biggest_foreign.currency, pct=Decimal("20")),
                )
            )

    if ExpenseCategory.HOUSING_AND_UTILITIES in category_monthly_krw:
        presets.append(
            ShockPreset(
                key="housing_up_10",
                title="Housing costs rise 10%",
                description="A rent or utilities increase from month 1.",
                shock=ExpenseIncreaseShock(pct=Decimal("10"), category=ExpenseCategory.HOUSING_AND_UTILITIES),
            )
        )
    else:
        presets.append(
            ShockPreset(
                key="essentials_up_10",
                title="Essential costs rise 10%",
                description="Every essential category costs 10% more from month 1.",
                shock=ExpenseIncreaseShock(pct=Decimal("10")),
            )
        )

    essential = sum(v for c, v in category_monthly_krw.items() if is_essential(c))
    if essential > 0:
        presets.append(
            ShockPreset(
                key="emergency_one_month_essentials",
                title="Emergency bill",
                description=f"An unplanned bill in month 2, sized at one month of your essential spending "
                f"({display.format(_dec(essential))}). Edit the amount to fit your situation.",
                shock=OneOffExpenseShock(amount_krw=_dec(essential), month=2),
            )
        )

    presets.append(
        ShockPreset(
            key="inflation_5",
            title="Essential prices rise 5% a year",
            description="Compounding price growth on groceries, transport, housing and education.",
            shock=InflationShock(annual_pct=Decimal("5")),
        )
    )
    return presets


async def presets_for_user(
    db: AsyncSession, user_id: uuid.UUID, *, today: date | None = None
) -> list[ShockPreset] | None:
    user = await db.get(User, user_id)
    if user is None:
        return None
    today = today or date.today()
    display = await resolve_display_currency(user.preferred_currency)
    incomes, _ = await _income_lines(await _active_streams(db, user_id))
    categories, _, _ = await _spend_baseline(db, user, today)
    return build_presets(incomes, categories, display)
