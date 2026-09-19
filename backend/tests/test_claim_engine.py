"""Pure tests for the caution-score engine (no database, no network)."""

import re
from datetime import datetime, timezone
from decimal import Decimal

from app.services.claim_check_service import Personal, build_report
from app.services.claim_sources import SearchHit, parse_claim, score_source
from app.services.currency_display import DisplayCurrency

KRW = DisplayCurrency("KRW", Decimal("1"))
NOW = datetime(2026, 9, 19, 12, 0, tzinfo=timezone.utc)
PERSONAL = Personal(
    monthly_budget_krw=Decimal("1000000"),
    headroom_krw=Decimal("400000"),
    headroom_basis="projection",
    remaining_budget_krw=Decimal("500000"),
    velocity_krw_per_day=Decimal("20000"),
    liquid_savings_krw=Decimal("3000000"),
    clarity_score=80,
)
CLAIM = parse_claim("KakaoBank has the best savings account for students")
HITS = [
    SearchHit(1, "Best savings accounts", "https://www.nerdwallet.com/best?tag=x", "We may earn a commission. The best savings account for students.", "Sep 1, 2026"),
    SearchHit(2, "KakaoBank savings", "https://www.kakaobank.com/savings", "Our savings account is the best for students.", "Aug 1, 2026"),
    SearchHit(3, "Savings warning", "https://www.reuters.com/savings", "Regulators warn savings account promotions can be misleading.", "Sep 10, 2026"),
    SearchHit(4, "Reddit thread", "https://www.reddit.com/r/korea/savings", "Not the best savings account, hidden fees.", None),
]


def report(hits=HITS, stake=None, status="live"):
    sources = [score_source(h, CLAIM, NOW.date()) for h in hits] if hits else []
    return build_report(
        CLAIM, sources, evidence_status=status, evidence_fetched_at=NOW if hits else None, now=NOW, country="kr",
        personal=PERSONAL, stake_krw=stake, stake_original=None, display=KRW,
    )


def test_no_sources_means_no_score_but_personal_context_still_computed():
    r = report(hits=None, status="unavailable")
    assert r.caution_score is None and r.caution_score_upper is None and r.risk_level is None
    assert r.evidence_stance == "not_applicable"
    assert [c.computable for c in r.components] == [True, False, False, False, False]
    assert r.personal.budget_runway_days == 25.0  # 500,000 / 20,000
    assert r.personal.survival_runway_days == 150.0  # 3,000,000 / 20,000
    assert any(f.label == "No caution score" for f in r.factors)


def test_missing_stake_gives_a_band_and_a_stake_closes_it():
    open_band = report()
    assert open_band.caution_score is not None
    assert open_band.caution_score_upper == min(100, open_band.caution_score + 15)
    closed = report(stake=Decimal("100000"))
    assert closed.caution_score_upper == closed.caution_score


def test_caution_rises_with_the_stake():
    scores = [report(stake=Decimal(s)).caution_score for s in (10_000, 100_000, 400_000, 2_000_000)]
    assert scores == sorted(scores)
    assert scores[-1] > scores[0]


def test_thin_evidence_is_charged_not_ignored():
    r = report(hits=HITS[2:3])
    c4 = next(c for c in r.components if c.key == "c4_disagreement")
    assert r.usable_source_count == 1
    assert c4.points == 10.0  # 15 x (3 - 1) / 3


def test_score_is_the_sum_of_its_components():
    r = report(stake=Decimal("100000"))
    assert r.caution_score == round(sum(c.points for c in r.components))


def test_same_inputs_same_report():
    assert report().model_dump() == report().model_dump()


def test_no_text_asserts_the_claim_is_true_or_false():
    forbidden = re.compile(r"\b(claim|it) is (true|false|correct|accurate|wrong|a lie)\b|\bthis is (true|false)\b", re.I)
    for r in (report(), report(hits=None, status="unavailable"), report(stake=Decimal("5000000"))):
        text = " ".join([f.label + " " + f.detail for f in r.factors] + [r.disclaimer])
        assert not forbidden.search(text)
        assert "not a truth score" in r.disclaimer
