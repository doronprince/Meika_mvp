import enum

from pydantic import BaseModel


class XAIFactor(BaseModel):
    """One line of explainable-AI reasoning behind a recommendation or score.

    Every field here must be produced by the code that computed the number —
    never hand-typed prose describing what the code "probably" did. See the
    XAI-enforcement guardrail: no directive without the math behind it.
    """

    label: str
    detail: str
    value: float | str | None = None


class PriceTrendResult(str, enum.Enum):
    """Computed from PriceQuote history, never stored — see [[price-history-design]]."""

    RISING = "rising"
    FALLING = "falling"
    STABLE = "stable"
    INSUFFICIENT_DATA = "insufficient_data"


class RiskLevel(str, enum.Enum):
    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"
