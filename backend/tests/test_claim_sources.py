"""Pure tests for claim parsing and per-source scoring."""

from datetime import date

import pytest

from app.services.claim_sources import (
    AFFILIATE_PENALTY,
    AGGREGATOR_PENALTY,
    ECHO_DISCOUNT,
    SPONSORED_PENALTY,
    VENDOR_IS_SUBJECT_PENALTY,
    ClaimType,
    SearchHit,
    Tier,
    classify,
    collapse_echoes,
    entity_match,
    normalize_claim,
    parse_claim,
    registrable_domain,
    score_source,
    tier_for,
)

TODAY = date(2026, 9, 19)


@pytest.mark.parametrize(
    "url, expected",
    [
        ("https://www.bbc.co.uk/news/business", "bbc.co.uk"),
        ("https://kaist.ac.kr/en/", "kaist.ac.kr"),
        ("https://blog.naver.com/some/post", "naver.com"),
        ("https://www.nerdwallet.com/article/banking", "nerdwallet.com"),
        ("https://sub.domain.example.com/x", "example.com"),
    ],
)
def test_registrable_domain(url, expected):
    assert registrable_domain(url) == expected


@pytest.mark.parametrize(
    "url, tier",
    [
        ("https://www.sec.gov/investor", Tier.REGULATOR),
        ("https://www.irs.gov/help", Tier.REGULATOR),
        ("https://www.fsc.go.kr/eng", Tier.REGULATOR),
        ("https://www.stanford.edu/research", Tier.ACADEMIC),
        ("https://www.reuters.com/markets", Tier.FINANCIAL_MEDIA),
        ("https://www.reddit.com/r/personalfinance", Tier.COMMUNITY),
        ("https://some-random-blog.io/post", Tier.UNKNOWN),
    ],
)
def test_tier_lookup(url, tier):
    assert tier_for(url) == tier


@pytest.mark.parametrize(
    "text, claim_type",
    [
        ("This savings product is guaranteed and risk-free", ClaimType.SAFETY_GUARANTEE),
        ("guaranteed best returns anywhere", ClaimType.SAFETY_GUARANTEE),
        ("Tesla stock will double by next year", ClaimType.RETURN_PREDICTION),
        ("This coin gives 40% returns in a year", ClaimType.RETURN_PREDICTION),
        ("Buy now before it's too late, prices are climbing", ClaimType.TIMING),
        ("Kakao Bank has the best savings account for students", ClaimType.SUPERLATIVE),
        ("Toss Bank pays 3.5% interest on deposits", ClaimType.FACTUAL_RATE),
        ("Index funds are boring but fine", ClaimType.UNCLASSIFIED),
    ],
)
def test_claim_type_first_match_wins(text, claim_type):
    assert classify(text) == claim_type


def test_normalization_strips_question_scaffolding():
    assert normalize_claim("Is it true that  KakaoBank pays 4%?") == "kakaobank pays 4%"


def test_brand_match_is_by_domain_label():
    claim = parse_claim("KakaoBank has the best savings account")
    assert entity_match(claim.key_terms, "https://www.kakaobank.com/products")
    assert not entity_match(claim.key_terms, "https://www.nerdwallet.com/savings")
    # A two-letter domain label mustn't match any word that merely contains it.
    assert not entity_match(frozenset({"exchange"}), "https://x.com/post")


def test_vendor_talking_about_itself_loses_independence_but_gains_primary_source_credit_for_rates():
    claim = parse_claim("KakaoBank pays 3.5% interest on savings")
    hit = SearchHit(1, "KakaoBank savings", "https://www.kakaobank.com/savings", "Earn 3.5% interest a year.", "Aug 1, 2026")
    source = score_source(hit, claim, TODAY)
    assert source.tier == Tier.VENDOR
    labels = dict(source.credibility_parts)
    assert labels["primary source for its own rate"] == 20
    assert labels["restates the claim's figure"] == 4
    assert source.independence == 100 - VENDOR_IS_SUBJECT_PENALTY


def test_conflict_markers_stack():
    claim = parse_claim("NerdWallet says this is the best credit card")
    hit = SearchHit(
        1,
        "Sponsored: the best credit card of 2026",
        "https://www.nerdwallet.com/best-card?tag=abc123",
        "We may earn a commission from links on this page. The best credit card for students.",
        "Sep 1, 2026",
    )
    source = score_source(hit, claim, TODAY)
    penalties = dict(source.conflict_signals)
    assert penalties["sponsored or paid placement"] == SPONSORED_PENALTY
    assert penalties["affiliate link"] == AFFILIATE_PENALTY
    assert penalties["commission-funded comparison site"] == AGGREGATOR_PENALTY
    assert "discloses commissions" in penalties
    assert source.independence == 0


def test_stance_negation_and_relevance_gate():
    claim = parse_claim("This is the best savings account")
    supports = score_source(SearchHit(1, "Recommended", "https://a.com", "Recommended: the best savings account this year."), claim, TODAY)
    disputes = score_source(SearchHit(2, "Review", "https://b.com", "Honestly not the best savings account; hidden fees."), claim, TODAY)
    off_topic = score_source(SearchHit(3, "Weather", "https://c.com", "Sunny with light winds tomorrow."), claim, TODAY)
    assert supports.stance == "supports"
    assert disputes.stance == "disputes"
    assert off_topic.relevant is False and off_topic.stance == "neutral"


def test_undated_and_stale_sources_are_marked_down():
    claim = parse_claim("This fund is the best")
    undated = score_source(SearchHit(1, "t", "https://a.com", "best fund"), claim, TODAY)
    stale = score_source(SearchHit(2, "t", "https://b.com", "best fund", "Jan 5, 2020"), claim, TODAY)
    assert dict(undated.credibility_parts)["no publication date"] == -4
    assert dict(stale.credibility_parts)["more than 3 years old"] == -10
    assert stale.age_days > 1095


def test_echoes_of_one_story_are_discounted():
    claim = parse_claim("This savings account is the best")
    text = "Bank launches savings account with the best rate in the market this spring according to the press release"
    sources = [
        score_source(SearchHit(1, "A", "https://www.reuters.com/a", text, "Sep 1, 2026"), claim, TODAY),
        score_source(SearchHit(2, "B", "https://unknown-news.io/b", text, "Sep 1, 2026"), claim, TODAY),
        score_source(SearchHit(3, "C", "https://www.reuters.com/c", "Different story about savings", "Sep 1, 2026"), claim, TODAY),
    ]
    collapse_echoes(sources)
    by_position = {s.position: s for s in sources}
    assert by_position[1].dedup == 1.0  # most credible member keeps full weight
    assert by_position[2].dedup == ECHO_DISCOUNT and by_position[2].echo_of == 1
    assert by_position[3].dedup == ECHO_DISCOUNT  # same domain as 1
