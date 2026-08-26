"""The Wise Guide copilot's reply generation.

Every reply is grounded in numbers this process actually computed — the
dashboard's Financial Clarity Score factors or a Price-Finder recommendation
— never invented, whether or not Gemini is configured. Gemini (when a real
GEMINI_API_KEY is set) only rephrases those numbers conversationally; it is
explicitly instructed not to introduce new ones, and any failure (missing
key, network, bad response) falls back to a deterministic reply built from
the same computed context. See [[xai-enforcement]] guardrail.
"""

import logging
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.schemas.common import XAIFactor
from app.schemas.dashboard import DashboardSummary
from app.schemas.price_finder import PriceFinderResult
from app.services import dashboard_service, price_finder_service

logger = logging.getLogger(__name__)

try:
    from google import genai
except ImportError:  # pragma: no cover - optional dependency
    genai = None


async def generate_reply(db: AsyncSession, user_id: uuid.UUID, user_message: str) -> tuple[str, list[XAIFactor]]:
    summary, price_result = await _gather_context(db, user_id, user_message)
    factors = _extract_factors(summary, price_result)

    if settings.gemini_api_key and genai is not None:
        try:
            content = await _generate_with_gemini(user_message, summary, price_result)
            return content, factors
        except Exception:
            logger.exception("Gemini call failed; falling back to deterministic reply")

    return _deterministic_reply(summary, price_result), factors


async def _gather_context(
    db: AsyncSession, user_id: uuid.UUID, message: str
) -> tuple[DashboardSummary | None, PriceFinderResult | None]:
    summary = await dashboard_service.get_dashboard_summary(db, user_id)

    lower = message.lower()
    all_products = await price_finder_service.search_price_comparisons(db, None)
    matched = next(
        (p for p in all_products if p.product_name.split()[0].lower() in lower),
        None,
    )
    return summary, matched


def _extract_factors(summary: DashboardSummary | None, price_result: PriceFinderResult | None) -> list[XAIFactor]:
    if price_result:
        return [price_result.recommendation]
    if summary:
        return summary.clarity_score.factors
    return []


def _deterministic_reply(summary: DashboardSummary | None, price_result: PriceFinderResult | None) -> str:
    if price_result:
        return f"For {price_result.product_name}: {price_result.recommendation.detail}"

    if summary is None:
        return "I don't have an account to reason about yet — log an expense first so I have real numbers to work with."

    score = summary.clarity_score
    lead = f"Your Financial Clarity Score is {score.value}/100 ({score.risk_level.value} risk) this month."
    top_factor = score.factors[0] if score.factors else None
    return lead + (f" {top_factor.detail}" if top_factor else "")


async def _generate_with_gemini(
    message: str, summary: DashboardSummary | None, price_result: PriceFinderResult | None
) -> str:
    client = genai.Client(api_key=settings.gemini_api_key)
    prompt = _build_prompt(message, summary, price_result)
    response = await client.aio.models.generate_content(model=settings.gemini_model, contents=prompt)
    text = (response.text or "").strip()
    if not text:
        raise ValueError("empty Gemini response")
    return text


def _build_prompt(message: str, summary: DashboardSummary | None, price_result: PriceFinderResult | None) -> str:
    lines = [
        "You are Meika's Wise Guide, an explainable financial copilot for international students in Seoul.",
        "Answer the user's question in 2-3 short, warm sentences.",
        "Base your answer ONLY on the real numbers given below — never invent a number, price, or store name.",
        "",
        f"User question: {message}",
    ]

    if summary:
        lines += [
            "",
            f"This month: spent ₩{summary.total_spent_this_month_krw:,.0f} of a "
            f"₩{summary.monthly_budget_krw:,.0f} budget (day {summary.days_elapsed_this_month} of "
            f"{summary.days_in_month}).",
            f"Financial Clarity Score: {summary.clarity_score.value}/100 "
            f"({summary.clarity_score.risk_level.value} risk).",
        ]
        for factor in summary.clarity_score.factors:
            lines.append(f"- {factor.label}: {factor.detail}")

    if price_result:
        lines.append("")
        lines.append(f"Price comparison for {price_result.product_name}:")
        for c in price_result.comparisons:
            lines.append(
                f"- {c.store_name}: ₩{c.price_krw:,.0f} + ₩{c.transit_cost_krw:,.0f} transit = "
                f"₩{c.true_economic_cost_krw:,.0f} true cost ({c.price_trend.value})"
            )
        lines.append(f"Recommendation: {price_result.recommendation.detail}")

    return "\n".join(lines)
