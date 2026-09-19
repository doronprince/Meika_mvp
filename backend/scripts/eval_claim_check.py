"""Check the claim-check engine's measurable properties.

Honest scope: there is no labelled ground truth for "was this claim worth
acting on", and building an annotated corpus would need human annotators
and more live searches than the free SerpApi quota allows. So this script
does NOT report accuracy or F1. It verifies the four properties that can be
measured without either, over a grid of claims, fixed synthetic search
results and stakes, using the real engine (build_report):

  1. Determinism: evaluating the same inputs twice gives identical reports.
  2. Non-assertion: no generated text says a claim is true, false, correct
     or wrong ([[never-asserts-truth]]).
  3. Exposure monotonicity: a larger stake never lowers the caution score.
  4. Degradation: with no sources the score is null (not 0), the personal
     context is still computed, and the missing-stake band is always
     [score, score + 15].

Usage:
    cd backend
    python -m scripts.eval_claim_check
"""

import re
from datetime import datetime, timezone
from decimal import Decimal

from app.services.claim_check_service import Personal, build_report
from app.services.claim_sources import SearchHit, parse_claim, score_source
from app.services.currency_display import DisplayCurrency

KRW = DisplayCurrency("KRW", Decimal("1"))
NOW = datetime(2026, 9, 19, tzinfo=timezone.utc)

CLAIMS = [
    "This savings account is guaranteed and risk-free",
    "Bitcoin will double by the end of the year",
    "Buy now before it's too late, prices only go up",
    "KakaoBank has the best savings account for students",
    "Toss Bank pays 3.5% interest on deposits",
    "Index funds beat most active managers",
    "This credit card gives 5% cashback on everything",
    "Gold is the safest investment right now",
]

HIT_SETS = {
    "none": None,
    "one_source": [SearchHit(1, "Explainer", "https://www.reuters.com/a", "What to know about savings, rates and returns.", "Sep 1, 2026")],
    "mixed": [
        SearchHit(1, "Best picks", "https://www.nerdwallet.com/best?tag=x", "We may earn a commission. The best savings account, top rates, recommended.", "Sep 1, 2026"),
        SearchHit(2, "Official", "https://www.fss.or.kr/eng", "Consumer warning: guaranteed returns claims are misleading.", "Aug 20, 2026"),
        SearchHit(3, "Forum", "https://www.reddit.com/r/x", "Not the best, hidden fees, avoid.", None),
        SearchHit(4, "News", "https://www.bloomberg.com/y", "Savings rates fell for students this month.", "Sep 5, 2026"),
    ],
    "promotional": [
        SearchHit(i, f"Sponsored {i}", f"https://promo{i}.io/x?ref=aff", "Sponsored: act now, the best returns, guaranteed!", "Sep 1, 2026")
        for i in range(1, 6)
    ],
}

PERSONAS = {
    "comfortable": Personal(Decimal("1200000"), Decimal("500000"), "projection", Decimal("700000"), Decimal("15000"), Decimal("5000000"), 85),
    "stretched": Personal(Decimal("800000"), Decimal("-50000"), "projection", Decimal("100000"), Decimal("30000"), None, 35),
    "new_user": Personal(Decimal("600000"), Decimal("600000"), "spend_to_date", Decimal("600000"), Decimal("0"), None, 100),
}

STAKES = [None, Decimal("10000"), Decimal("100000"), Decimal("500000"), Decimal("3000000")]
FORBIDDEN = re.compile(r"\b(claim|it) is (true|false|correct|accurate|wrong|a lie)\b|\bthis is (true|false)\b", re.I)


def evaluate(claim_text, hits, persona, stake):
    claim = parse_claim(claim_text)
    sources = [score_source(h, claim, NOW.date()) for h in hits] if hits else []
    return build_report(
        claim, sources, evidence_status="live" if hits else "unavailable", evidence_fetched_at=NOW if hits else None,
        now=NOW, country="kr", personal=persona, stake_krw=stake, stake_original=None, display=KRW,
    )


def main() -> None:
    runs = deterministic = assertion_violations = monotonic_failures = degradation_failures = 0
    for claim_text in CLAIMS:
        for hit_name, hits in HIT_SETS.items():
            for persona in PERSONAS.values():
                previous = None
                for stake in STAKES:
                    a = evaluate(claim_text, hits, persona, stake)
                    b = evaluate(claim_text, hits, persona, stake)
                    runs += 1
                    deterministic += a.model_dump() == b.model_dump()
                    text = " ".join([f.label + " " + f.detail for f in a.factors] + [a.disclaimer])
                    assertion_violations += bool(FORBIDDEN.search(text))
                    if hits is None:
                        degradation_failures += not (a.caution_score is None and a.personal is not None)
                    elif stake is None:
                        degradation_failures += a.caution_score_upper != min(100, a.caution_score + 15)
                    else:
                        if previous is not None and a.caution_score < previous:
                            monotonic_failures += 1
                        previous = a.caution_score

    print(f"{runs} evaluations: {len(CLAIMS)} claims x {len(HIT_SETS)} evidence sets x {len(PERSONAS)} personas x "
          f"{len(STAKES)} stakes (synthetic search results, real engine).\n")
    print("| property | result |")
    print("|---|---|")
    print(f"| determinism (identical reports on re-run) | {deterministic}/{runs} |")
    print(f"| non-assertion (texts claiming true/false) | {assertion_violations} violations |")
    print(f"| exposure monotonicity (score fell as stake rose) | {monotonic_failures} failures |")
    print(f"| degradation (null score without sources; band = score + 15 without a stake) | {degradation_failures} failures |")


if __name__ == "__main__":
    main()
