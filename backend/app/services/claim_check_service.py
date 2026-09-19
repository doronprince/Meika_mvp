"""Claim check: weigh a money claim seen online against real sources and the
user's own numbers.

Question: can an AI system evaluate financial claims from online sources,
flag uncertainty and conflicts of interest, and put them in the context of
one person's finances?

Pipeline (engine v1, deterministic — no LLM in any scoring path):
  1. Parse the claim (claim_sources.parse_claim): its type decides how
     checkable it is at all.
  2. Retrieve sources: 7-day shared cache, else a live SerpApi search within
     a per-user daily budget, else none. Every path is disclosed.
  3. Score each source for credibility (a domain-tier prior plus recency and
     specificity) and independence (conflict-of-interest markers), collapse
     echoes of the same story, and read its stance lexically.
  4. Personal context from dashboard_service: budget headroom, how long this
     month's budget lasts, how long savings last, and what the stake would
     be against those.
  5. A 0-100 CAUTION score from five capped components (unfalsifiability 25,
     source quality 25, conflicts 20, disagreement or thin evidence 15,
     personal exposure 15). With no stake given, exposure is undefined and a
     band [score, score + 15] is reported instead of a guess. With no sources
     at all, source quality and conflicts are 0/0 — the score does not exist
     and is returned as null, while the personal context is still computed.

[[never-asserts-truth]]: nothing here says a claim is true or false. A low
caution score means weak grounds for worry given what was retrievable, not
an endorsement. scripts/eval_claim_check.py audits the generated text for
this.
"""

import hashlib
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import delete, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.claim import ClaimEvaluation, ClaimEvidenceCache
from app.models.user import User
from app.schemas.claim import (
    CautionComponent,
    ClaimEvaluationRead,
    ClaimEvaluationReport,
    ClaimEvaluationRequest,
    ClaimEvaluationSummary,
    PersonalContext,
    ScorePart,
    SourceAssessment,
)
from app.schemas.common import RiskLevel, XAIFactor
from app.services import claim_search, dashboard_service, fx_service
from app.services.claim_sources import (
    UNFALSIFIABILITY_POINTS,
    ClaimType,
    ParsedClaim,
    SearchHit,
    SourceScore,
    collapse_echoes,
    parse_claim,
    score_source,
)
from app.services.currency_display import DisplayCurrency, resolve_display_currency
from app.services.live_price_service import country_for_currency

ENGINE_VERSION = "v1"
CACHE_TTL_DAYS = 7  # deposit rates and product terms move over weeks; the age is always shown
# SerpApi's free tier (100/month) is shared with Price-Finder and the Copilot.
# Counted from persisted evaluations, so it survives a restart.
LIVE_SEARCHES_PER_USER_PER_DAY = 5
MIN_SOURCES_FOR_DISAGREEMENT = 3
STANCE_DOMINANCE = 2  # sources must lean 2:1 before Meika names a side
EXPOSURE_REFERENCE_DAYS = 30  # one budget cycle, the period every dashboard figure uses
RISK_HIGH = 60  # the Clarity Score's 70/40 boundaries mirrored for an inverted scale
RISK_MODERATE = 30

DISCLAIMER = (
    "This is a caution score, not a truth score. Meika does not fact-check claims; it weighs "
    "where the claim's support comes from and what acting on it would mean for your budget. This is not "
    "financial advice."
)

LIMITATIONS = [
    "It does not check facts. It can tell you a page is commission-funded and that other sources disagree, not "
    "whether a stated rate or figure is real.",
    "Stance is keyword matching over a search snippet, not a reading of the page. It misses sarcasm, "
    "conditionals and comparisons, and abstains often by design.",
    "Everything is read from search titles, snippets and URLs. Conflicts of interest that don't show there (a "
    "disclosure further down the page, a link added by script) are invisible.",
    "The domain list is hand-curated, finite and English/Korean-leaning. Unlisted sites count as unknown, so "
    "claims about regional products mostly reflect Meika's ignorance of the sources.",
    "Brand matching compares claim words with the site's domain name. It misses brands whose domain doesn't "
    "contain the name and can fire on generic words.",
    "Echo collapse catches republication of the same text, not coordinated campaigns in different words.",
    "Guarantees and predictions about the future can't be settled by any source, so they always carry the full "
    "unfalsifiability penalty.",
    "Personal context is this month's spending, your budget and (if you entered it) your savings. Meika doesn't "
    "know your income, debts or portfolio, so this is decision support, not a suitability assessment.",
    "Search results change over time and by country; each evaluation freezes the evidence it used.",
    "Every threshold is an argued design choice, not fitted to outcomes (there is no ground truth for 'was this "
    "worth acting on'), so the score is not calibrated.",
    "English lexicons only: a claim in Korean will mostly be unclassified and most sources will read as neutral.",
]

_CENTS = Decimal("0.01")


def _q2(value: Decimal) -> Decimal:
    return value.quantize(_CENTS, rounding=ROUND_HALF_UP)


def _round1(value: Decimal) -> float:
    return float(value.quantize(Decimal("0.1"), rounding=ROUND_HALF_UP))


class UnsupportedCurrencyError(Exception):
    pass


@dataclass(frozen=True)
class Personal:
    monthly_budget_krw: Decimal
    headroom_krw: Decimal
    headroom_basis: str
    remaining_budget_krw: Decimal
    velocity_krw_per_day: Decimal
    liquid_savings_krw: Decimal | None
    clarity_score: int | None


def _evidence_stance(support: float, dispute: float, status: str, source_count: int) -> str:
    if source_count == 0:
        return "not_applicable"
    if support + dispute == 0:
        return "no_directional_language"
    if support >= STANCE_DOMINANCE * dispute and support > 0:
        return "sources_lean_supporting"
    if dispute >= STANCE_DOMINANCE * support and dispute > 0:
        return "sources_lean_disputing"
    return "sources_disagree"


def _risk(score: int | None) -> RiskLevel | None:
    if score is None:
        return None
    if score >= RISK_HIGH:
        return RiskLevel.HIGH
    if score >= RISK_MODERATE:
        return RiskLevel.MODERATE
    return RiskLevel.LOW


def build_report(
    claim: ParsedClaim,
    sources: list[SourceScore] | None,
    *,
    evidence_status: str,
    evidence_fetched_at: datetime | None,
    now: datetime,
    country: str,
    personal: Personal,
    stake_krw: Decimal | None,
    stake_original: tuple[str, Decimal] | None,
    display: DisplayCurrency,
) -> ClaimEvaluationReport:
    """Pure: same inputs, same report."""
    sources = list(sources or [])
    collapse_echoes(sources)
    usable = [s for s in sources if s.relevant]

    def c(s: SourceScore) -> float:  # effective credibility weight
        return s.credibility / 100 * s.dedup

    def w(s: SourceScore) -> float:  # full evidence weight
        return c(s) * s.independence / 100

    q = coi = disagreement = None
    if sources:
        q = sum(s.credibility * s.dedup for s in sources) / (100 * sum(s.dedup for s in sources))
        total_c = sum(c(s) for s in sources)
        coi = sum((1 - s.independence / 100) * c(s) for s in sources) / total_c if total_c > 0 else 0.0
    support = sum(w(s) for s in usable if s.stance == "supports")
    dispute = sum(w(s) for s in usable if s.stance == "disputes")
    if support + dispute > 0:
        disagreement = 2 * min(support, dispute) / (support + dispute)
    stance = _evidence_stance(support, dispute, evidence_status, len(sources))

    # Personal context.
    v = personal.velocity_krw_per_day
    headroom_eff = max(personal.headroom_krw, Decimal("0"))
    budget_runway = _round1(max(personal.remaining_budget_krw, Decimal("0")) / v) if v > 0 else None
    survival_runway = (
        _round1(personal.liquid_savings_krw / v) if personal.liquid_savings_krw is not None and v > 0 else None
    )
    exposure = None
    if stake_krw is not None:
        e_headroom = 1.0 if headroom_eff == 0 else min(1.0, float(stake_krw / headroom_eff))
        e_runway = min(1.0, float(stake_krw / v) / EXPOSURE_REFERENCE_DAYS) if v > 0 else None
        exposure = max(x for x in (e_headroom, e_runway) if x is not None)

    # Caution components.
    c1 = float(UNFALSIFIABILITY_POINTS[claim.claim_type])
    type_name = claim.claim_type.value.replace("_", " ")
    components = [
        CautionComponent(
            key="c1_unfalsifiability", name="How checkable the claim is", cap=25, points=c1, computable=True,
            detail=f"Read as a {type_name} claim, which carries {c1:.0f} of 25 points: "
            + {
                ClaimType.SAFETY_GUARANTEE: "no source can settle a guarantee in advance.",
                ClaimType.RETURN_PREDICTION: "no source can settle a future return in advance.",
                ClaimType.TIMING: "urgency is a sales technique, and whether 'now' is right can't be checked.",
                ClaimType.SUPERLATIVE: "'best' depends on criteria the claim doesn't state.",
                ClaimType.FACTUAL_RATE: "a stated rate can in principle be checked against the provider.",
                ClaimType.UNCLASSIFIED: "Meika couldn't tell what kind of claim this is.",
            }[claim.claim_type],
        )
    ]
    c2 = c3 = c4 = None
    if sources:
        c2 = 25 * (1 - q)
        c3 = 20 * coi
        if len(usable) >= MIN_SOURCES_FOR_DISAGREEMENT:
            c4 = 15 * (disagreement or 0.0)
            c4_detail = (
                f"{len(usable)} on-topic sources; weighted disagreement {disagreement:.2f} on a 0-1 scale gives "
                f"{c4:.1f} of 15 points."
                if disagreement is not None
                else f"{len(usable)} on-topic sources, none using directional language, so 0 of 15 points."
            )
        else:
            c4 = 15 * (MIN_SOURCES_FOR_DISAGREEMENT - len(usable)) / MIN_SOURCES_FOR_DISAGREEMENT
            c4_detail = (
                f"Only {len(usable)} on-topic source(s), too few to judge agreement, so thin evidence adds "
                f"{c4:.0f} of 15 points. (On a caution scale, less evidence can't count as reassurance.)"
            )
        flagged = sum(1 for s in sources if s.conflict_signals)
        components += [
            CautionComponent(
                key="c2_source_quality", name="Source quality", cap=25, points=round(c2, 2), computable=True,
                detail=f"Echo-adjusted average credibility {q * 100:.0f}/100 across {len(sources)} source(s) gives "
                f"{c2:.1f} of 25 points.",
            ),
            CautionComponent(
                key="c3_conflicts", name="Conflicts of interest", cap=20, points=round(c3, 2), computable=True,
                detail=f"{flagged} of {len(sources)} source(s) show a conflict-of-interest marker; credibility-"
                f"weighted dependence {coi:.2f} gives {c3:.1f} of 20 points.",
            ),
            CautionComponent(
                key="c4_disagreement", name="Disagreement or thin evidence", cap=15, points=round(c4, 2),
                computable=True, detail=c4_detail,
            ),
        ]
    else:
        reason = "No sources were retrieved, so this can't be computed."
        components += [
            CautionComponent(key="c2_source_quality", name="Source quality", cap=25, points=None, computable=False, detail=reason),
            CautionComponent(key="c3_conflicts", name="Conflicts of interest", cap=20, points=None, computable=False, detail=reason),
            CautionComponent(key="c4_disagreement", name="Disagreement or thin evidence", cap=15, points=None, computable=False, detail=reason),
        ]
    c5 = 15 * exposure if exposure is not None else None
    if c5 is not None:
        c5_detail = f"The stake uses {exposure * 100:.0f}% of the relevant cushion, giving {c5:.1f} of 15 points."
    else:
        c5_detail = "No amount given, so this can't be computed; the score is shown as a range instead."
    components.append(
        CautionComponent(
            key="c5_personal_exposure", name="What it would mean for you", cap=15,
            points=None if c5 is None else round(c5, 2), computable=c5 is not None, detail=c5_detail,
        )
    )

    score = upper = None
    if sources:
        defined = c1 + c2 + c3 + c4
        score = max(0, min(100, round(defined + (c5 or 0.0))))
        upper = score if c5 is not None else max(0, min(100, round(defined + 15)))

    factors = _factors(
        claim=claim, sources=sources, usable=usable, evidence_status=evidence_status,
        evidence_fetched_at=evidence_fetched_at, now=now, stance=stance, q=q, coi=coi, score=score, upper=upper,
        components=components, personal=personal, budget_runway=budget_runway, survival_runway=survival_runway,
        stake_krw=stake_krw, exposure=exposure, display=display,
    )

    age_days = (now - evidence_fetched_at).days if evidence_fetched_at else None
    return ClaimEvaluationReport(
        claim_text=claim.text,
        normalized_query=claim.normalized_query,
        country=country,
        claim_type=claim.claim_type.value,
        evidence_status=evidence_status,
        evidence_fetched_at=evidence_fetched_at,
        evidence_age_days=age_days,
        evidence_stance=stance,
        caution_score=score,
        caution_score_upper=upper,
        risk_level=_risk(score),
        source_count=len(sources),
        usable_source_count=len(usable),
        weighted_credibility=None if q is None else round(q * 100, 2),
        coi_density=None if coi is None else round(coi, 4),
        disagreement_index=None if disagreement is None else round(disagreement, 4),
        stake_amount_krw=stake_krw,
        stake_original_currency=stake_original[0] if stake_original else None,
        stake_original_amount=stake_original[1] if stake_original else None,
        personal=PersonalContext(
            monthly_budget_krw=personal.monthly_budget_krw,
            budget_headroom_krw=_q2(personal.headroom_krw),
            headroom_basis=personal.headroom_basis,
            spending_velocity_krw_per_day=_q2(v),
            budget_runway_days=budget_runway,
            liquid_savings_krw=personal.liquid_savings_krw,
            survival_runway_days=survival_runway,
            exposure=None if exposure is None else round(exposure, 4),
        ),
        components=components,
        sources=[
            SourceAssessment(
                position=s.position, title=s.title, link=s.link, domain=s.domain, tier=s.tier.value,
                credibility=s.credibility,
                credibility_parts=[ScorePart(label=label, points=p) for label, p in s.credibility_parts],
                independence=s.independence,
                conflict_signals=[ScorePart(label=label, points=p) for label, p in s.conflict_signals],
                date_known=s.date_known, age_days=s.age_days, relevant=s.relevant, stance=s.stance,
                echo_of=s.echo_of, weight=round(w(s), 4),
            )
            for s in sorted(sources, key=lambda s: s.position)
        ],
        factors=factors,
        limitations=LIMITATIONS,
        disclaimer=DISCLAIMER,
        engine_version=ENGINE_VERSION,
    )


def _factors(**k) -> list[XAIFactor]:
    claim: ParsedClaim = k["claim"]
    display: DisplayCurrency = k["display"]
    personal: Personal = k["personal"]
    sources: list[SourceScore] = k["sources"]
    components: list[CautionComponent] = k["components"]
    factors = [XAIFactor(label="What kind of claim this is", detail=components[0].detail, value=components[0].points)]

    status = k["evidence_status"]
    fetched = k["evidence_fetched_at"]
    age = (k["now"] - fetched).days if fetched else None
    evidence_detail = {
        "live": f"A live web search for \"{claim.normalized_query}\" returned {len(sources)} source(s).",
        "cached": f"Used {len(sources)} source(s) from a search for the same claim {age} day(s) ago.",
        "live_empty": f"A live web search for \"{claim.normalized_query}\" returned no results. That is not evidence "
        "for or against the claim, only an absence of sources.",
        "quota_exhausted": f"The daily limit of {LIVE_SEARCHES_PER_USER_PER_DAY} live searches is used up, so "
        + (f"sources from a search {age} day(s) ago were used." if sources else "no sources could be retrieved."),
        "unavailable": "Live search isn't available right now (not configured, or the request failed), so no "
        "sources were retrieved. The personal context below still applies.",
    }[status]
    factors.append(XAIFactor(label="Where the evidence came from", detail=evidence_detail, value=float(len(sources))))

    if sources:
        factors.append(XAIFactor(label="Source quality", detail=components[1].detail, value=components[1].points))
        factors.append(XAIFactor(label="Conflicts of interest", detail=components[2].detail, value=components[2].points))
        stance_text = {
            "sources_lean_supporting": "Sources mostly use language that backs the claim",
            "sources_lean_disputing": "Sources mostly use language that pushes back on the claim",
            "sources_disagree": "Sources are split",
            "no_directional_language": "No source used clearly supportive or critical language",
        }[k["stance"]]
        factors.append(
            XAIFactor(
                label="What the sources say",
                detail=f"{stance_text} (keyword reading of search snippets, not of the pages). {components[3].detail}",
                value=components[3].points,
            )
        )

    headroom_basis = (
        "at your projected month-end spend"
        if personal.headroom_basis == "projection"
        else "based on spending so far (a month-end projection needs 7 days of data)"
    )
    context = f"Budget headroom this month is {display.format(_q2(personal.headroom_krw))} {headroom_basis}."
    if k["budget_runway"] is not None:
        context += f" At your current pace, this month's budget lasts about {k['budget_runway']:.0f} more day(s)."
    else:
        context += " No spending is recorded this month, so no budget runway can be computed."
    if k["survival_runway"] is not None:
        context += f" Your savings would cover about {k['survival_runway']:.0f} day(s) of spending at that pace."
    elif personal.liquid_savings_krw is None:
        context += " Add your liquid savings to see how long they would last."
    factors.append(XAIFactor(label="Your financial cushion", detail=context, value=float(_q2(personal.headroom_krw))))

    if k["stake_krw"] is not None:
        factors.append(
            XAIFactor(
                label="What the stake would mean for you",
                detail=f"{display.format(k['stake_krw'])} against that cushion. {components[4].detail}",
                value=components[4].points,
            )
        )

    score, upper = k["score"], k["upper"]
    if score is None:
        factors.append(
            XAIFactor(
                label="No caution score",
                detail="Without any sources, source quality and conflicts of interest are undefined, so no score is "
                "given rather than a partial one.",
                value=None,
            )
        )
    else:
        parts = " + ".join(f"{c.points:.1f}" for c in components if c.points is not None)
        band = "" if upper == score else f" It could be as high as {upper} once you say how much you'd put in."
        factors.append(
            XAIFactor(
                label=f"Caution {score}/100",
                detail=f"{score} = {parts} (components listed above, rounded). Higher means more reason for caution; it says "
                f"nothing about whether the claim holds.{band}",
                value=float(score),
            )
        )
    return factors


def _query_hash(country: str, normalized: str) -> str:
    return hashlib.sha256(f"{country}|{normalized}".encode()).hexdigest()


def _hits_from_json(rows: list) -> list[SearchHit]:
    return [SearchHit(**row) for row in rows]


async def _personal_context(db: AsyncSession, user: User) -> Personal:
    summary = await dashboard_service.get_dashboard_summary(db, user.id)
    if summary.projected_month_end_spend_krw is not None:
        headroom, basis = summary.monthly_budget_krw - summary.projected_month_end_spend_krw, "projection"
    else:
        headroom, basis = summary.remaining_budget_krw, "spend_to_date"
    return Personal(
        monthly_budget_krw=summary.monthly_budget_krw,
        headroom_krw=headroom,
        headroom_basis=basis,
        remaining_budget_krw=summary.remaining_budget_krw,
        velocity_krw_per_day=summary.spending_velocity_krw_per_day,
        liquid_savings_krw=user.liquid_savings_krw,
        clarity_score=summary.clarity_score.value,
    )


async def _gather_evidence(
    db: AsyncSession, user_id: uuid.UUID, claim: ParsedClaim, country: str, now: datetime
) -> tuple[str, list[SearchHit] | None, datetime | None]:
    query_hash = _query_hash(country, claim.normalized_query)
    cached = (
        await db.execute(select(ClaimEvidenceCache).where(ClaimEvidenceCache.query_hash == query_hash))
    ).scalar_one_or_none()
    if cached and now - cached.fetched_at < timedelta(days=CACHE_TTL_DAYS):
        return "cached", _hits_from_json(cached.results), cached.fetched_at

    live_today = (
        await db.execute(
            select(func.count())
            .select_from(ClaimEvaluation)
            .where(
                ClaimEvaluation.user_id == user_id,
                ClaimEvaluation.evidence_status == "live",
                ClaimEvaluation.created_at > now - timedelta(days=1),
            )
        )
    ).scalar_one()
    if live_today >= LIVE_SEARCHES_PER_USER_PER_DAY:
        if cached:
            return "quota_exhausted", _hits_from_json(cached.results), cached.fetched_at
        return "quota_exhausted", None, None

    hits = await claim_search.search_sources(claim.normalized_query, country)
    if hits is None:
        return "unavailable", None, None
    if not hits:
        return "live_empty", [], now
    rows = [hit.__dict__ for hit in hits]
    await db.execute(
        insert(ClaimEvidenceCache)
        .values(
            id=uuid.uuid4(), query_hash=query_hash, normalized_query=claim.normalized_query, country=country,
            results=rows, fetched_at=now,
        )
        .on_conflict_do_update(index_elements=["query_hash"], set_={"results": rows, "fetched_at": now})
    )
    return "live", hits, now


async def evaluate_claim(
    db: AsyncSession, user_id: uuid.UUID, request: ClaimEvaluationRequest, *, now: datetime | None = None
) -> ClaimEvaluationRead | None:
    user = await db.get(User, user_id)
    if user is None:
        return None
    now = now or datetime.now(timezone.utc)
    display = await resolve_display_currency(user.preferred_currency)

    stake_krw = stake_original = None
    if request.stake_amount is not None:
        currency = (request.stake_currency or user.preferred_currency or "KRW").upper()
        if currency not in fx_service.SUPPORTED_CURRENCIES:
            raise UnsupportedCurrencyError(f"{currency} is not a supported currency")
        stake_krw = _q2(await fx_service.convert(request.stake_amount, currency, "KRW"))
        stake_original = (currency, request.stake_amount)

    claim = parse_claim(request.claim_text)
    country = (request.country or country_for_currency(user.preferred_currency)).lower()
    status, hits, fetched_at = await _gather_evidence(db, user_id, claim, country, now)
    sources = [score_source(hit, claim, now.date()) for hit in hits] if hits else []
    personal = await _personal_context(db, user)

    report = build_report(
        claim, sources, evidence_status=status, evidence_fetched_at=fetched_at, now=now, country=country,
        personal=personal, stake_krw=stake_krw, stake_original=stake_original, display=display,
    )
    row = ClaimEvaluation(
        user_id=user_id,
        claim_text=claim.text,
        normalized_query=claim.normalized_query,
        query_hash=_query_hash(country, claim.normalized_query),
        country=country,
        claim_type=report.claim_type,
        evidence_status=report.evidence_status,
        evidence_stance=report.evidence_stance,
        caution_score=report.caution_score,
        caution_score_upper=report.caution_score_upper,
        source_count=report.source_count,
        stake_amount_krw=stake_krw,
        evidence_fetched_at=fetched_at,
        engine_version=ENGINE_VERSION,
        report=report.model_dump(mode="json"),
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return ClaimEvaluationRead(id=row.id, created_at=row.created_at, **report.model_dump())


async def list_evaluations(db: AsyncSession, user_id: uuid.UUID, *, limit: int = 20) -> list[ClaimEvaluationSummary]:
    result = await db.execute(
        select(ClaimEvaluation)
        .where(ClaimEvaluation.user_id == user_id)
        .order_by(ClaimEvaluation.created_at.desc())
        .limit(limit)
    )
    return [
        ClaimEvaluationSummary(
            id=row.id, created_at=row.created_at, claim_text=row.claim_text, claim_type=row.claim_type,
            evidence_stance=row.evidence_stance, caution_score=row.caution_score,
            caution_score_upper=row.caution_score_upper, risk_level=_risk(row.caution_score),
            source_count=row.source_count,
        )
        for row in result.scalars()
    ]


async def get_evaluation(db: AsyncSession, user_id: uuid.UUID, evaluation_id: uuid.UUID) -> ClaimEvaluationRead | None:
    row = (
        await db.execute(
            select(ClaimEvaluation).where(ClaimEvaluation.id == evaluation_id, ClaimEvaluation.user_id == user_id)
        )
    ).scalar_one_or_none()
    if row is None:
        return None
    return ClaimEvaluationRead(id=row.id, created_at=row.created_at, **row.report)


async def delete_evaluation(db: AsyncSession, user_id: uuid.UUID, evaluation_id: uuid.UUID) -> bool:
    result = await db.execute(
        delete(ClaimEvaluation).where(ClaimEvaluation.id == evaluation_id, ClaimEvaluation.user_id == user_id)
    )
    await db.commit()
    return result.rowcount > 0
