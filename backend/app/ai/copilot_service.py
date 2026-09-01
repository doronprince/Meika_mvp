"""The Wise Guide copilot's reply generation.

Every reply is grounded in numbers this process actually computed — the
dashboard's Financial Clarity Score factors or a Price-Finder recommendation
— never invented, whether or not Gemini is configured. Gemini (when a real
GEMINI_API_KEY is set) only rephrases those numbers conversationally; it is
explicitly instructed not to introduce new ones, and any failure (missing
key, network, bad response) falls back to a deterministic reply built from
the same computed context. See [[xai-enforcement]] guardrail.

[[copilot-live-search-quota]]: a price question that doesn't match the
seeded demo catalog falls through to a live SerpApi search — the same one
Price-Finder's search box uses, and the same free-tier quota (100/month).
Only fires when the message actually looks like a price question
(_looks_like_price_question), not on every message, to keep casual chat
from silently burning through it.
"""

import logging
import re
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.user import User
from app.schemas.common import XAIFactor
from app.schemas.dashboard import DashboardSummary
from app.schemas.price_finder import PriceFinderResult
from app.services import dashboard_service, price_finder_service
from app.services.currency_display import DisplayCurrency, resolve_display_currency

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
            display = await _display_currency_for(db, user_id)
            content = await _generate_with_gemini(user_message, summary, price_result, display)
            return content, factors
        except Exception:
            logger.exception("Gemini call failed; falling back to deterministic reply")

    return _deterministic_reply(summary, price_result), factors


async def _display_currency_for(db: AsyncSession, user_id: uuid.UUID) -> DisplayCurrency:
    user = await db.get(User, user_id)
    return await resolve_display_currency(user.preferred_currency if user else None)


_PRICE_QUESTION_KEYWORDS = ("cost", "costs", "price", "prices", "cheap", "expensive", "buy", "how much")

_QUERY_PREFIXES = (
    "how much do ", "how much does ", "how much is ", "how much are ",
    "what does ", "what do ", "what is the price of ", "what's the price of ",
    "price of ", "cost of ", "how much for ",
)
_QUERY_SUFFIXES = (" cost", " costs", " price", " prices")


def _looks_like_price_question(message: str) -> bool:
    lower = message.lower()
    return any(keyword in lower for keyword in _PRICE_QUESTION_KEYWORDS)


def _extract_product_query(message: str) -> str:
    """Rough heuristic, not NLP-grade: strip common question scaffolding so
    "How much do wireless headphones cost?" becomes "wireless headphones"
    for a live search. Good enough for a chat box, not a substitute for the
    Price-Finder search field when precision matters."""
    text = re.sub(r"[?!.]+$", "", message.strip())
    lower = text.lower()
    for prefix in _QUERY_PREFIXES:
        if lower.startswith(prefix):
            text = text[len(prefix):]
            break
    for suffix in _QUERY_SUFFIXES:
        if text.lower().endswith(suffix):
            text = text[: -len(suffix)]
            break
    return text.strip()


async def _gather_context(
    db: AsyncSession, user_id: uuid.UUID, message: str
) -> tuple[DashboardSummary | None, PriceFinderResult | None]:
    summary = await dashboard_service.get_dashboard_summary(db, user_id)

    lower = message.lower()
    catalog_products = await price_finder_service.search_price_comparisons(db, None, user_id)
    matched = next(
        (p for p in catalog_products if p.product_name.split()[0].lower() in lower),
        None,
    )

    if matched is None and _looks_like_price_question(message):
        query = _extract_product_query(message)
        if query:
            live_results = await price_finder_service.search_price_comparisons(db, query, user_id)
            if live_results:
                matched = min(live_results, key=lambda r: r.comparisons[0].true_economic_cost_krw)

    return summary, matched


def _extract_factors(summary: DashboardSummary | None, price_result: PriceFinderResult | None) -> list[XAIFactor]:
    if price_result:
        return [price_result.recommendation]
    if summary:
        return summary.clarity_score.factors
    return []


def _deterministic_reply(summary: DashboardSummary | None, price_result: PriceFinderResult | None) -> str:
    if price_result:
        prefix = "Live result — " if price_result.is_live else ""
        return f"{prefix}For {price_result.product_name}: {price_result.recommendation.detail}"

    if summary is None:
        return "I don't have an account to reason about yet — log an expense first so I have real numbers to work with."

    score = summary.clarity_score
    lead = f"Your Financial Clarity Score is {score.value}/100 ({score.risk_level.value} risk) this month."
    top_factor = score.factors[0] if score.factors else None
    return lead + (f" {top_factor.detail}" if top_factor else "")


async def _generate_with_gemini(
    message: str,
    summary: DashboardSummary | None,
    price_result: PriceFinderResult | None,
    display: DisplayCurrency,
) -> str:
    client = genai.Client(api_key=settings.gemini_api_key)
    prompt = _build_prompt(message, summary, price_result, display)
    response = await client.aio.models.generate_content(model=settings.gemini_model, contents=prompt)
    text = (response.text or "").strip()
    if not text:
        raise ValueError("empty Gemini response")
    return text


def _build_prompt(
    message: str,
    summary: DashboardSummary | None,
    price_result: PriceFinderResult | None,
    display: DisplayCurrency,
) -> str:
    lines = [
        "You are Meika's Wise Guide, an explainable financial copilot for international students in Seoul.",
        "Answer the user's question in 2-3 short, warm sentences.",
        "Base your answer ONLY on the real numbers given below — never invent a number, price, or store name.",
        f"Every figure below is already in the user's currency ({display.code}) — quote them as given, don't relabel or reconvert.",
        "",
        f"User question: {message}",
    ]

    if summary:
        lines += [
            "",
            f"This month: spent {display.format(summary.total_spent_this_month_krw)} of a "
            f"{display.format(summary.monthly_budget_krw)} budget (day {summary.days_elapsed_this_month} of "
            f"{summary.days_in_month}).",
            f"Financial Clarity Score: {summary.clarity_score.value}/100 "
            f"({summary.clarity_score.risk_level.value} risk).",
        ]
        for factor in summary.clarity_score.factors:
            lines.append(f"- {factor.label}: {factor.detail}")

    if price_result:
        lines.append("")
        source_note = " (live search result)" if price_result.is_live else ""
        lines.append(f"Price comparison for {price_result.product_name}{source_note}:")
        for c in price_result.comparisons:
            lines.append(
                f"- {c.store_name}: {display.format(c.price_krw)} + {display.format(c.transit_cost_krw)} transit = "
                f"{display.format(c.true_economic_cost_krw)} true cost ({c.price_trend.value})"
            )
        lines.append(f"Recommendation: {price_result.recommendation.detail}")

    return "\n".join(lines)
