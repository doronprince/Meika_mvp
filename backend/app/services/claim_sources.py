"""Claim parsing and per-source scoring for claim check. Pure and
deterministic: regex and hand-written lexicons, no model, no network.

Every number here is a named constant with its reasoning next to it, so a
reviewer can disagree with a specific value and rerun, rather than being
asked to trust a black box. English-only lexicons; see the module
limitations in claim_check_service.
"""

import enum
import re
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from urllib.parse import urlsplit

# ---------------------------------------------------------------- domains

# Suffixes where the registrable domain has three labels (bbc.co.uk,
# kaist.ac.kr). Hand-coded instead of tldextract, which downloads the Public
# Suffix List on first use and would break graceful offline degradation.
MULTI_LABEL_SUFFIXES = {
    "co.uk", "ac.uk", "gov.uk", "org.uk", "co.kr", "ac.kr", "or.kr", "go.kr", "ne.kr", "co.jp", "ac.jp",
    "go.jp", "or.jp", "ne.jp", "com.au", "edu.au", "gov.au", "co.nz", "com.sg", "com.hk", "com.my", "co.th",
    "com.ph", "co.id", "com.cn", "edu.cn", "gov.cn", "co.in", "gov.in", "com.br", "com.mx", "co.za", "com.tr",
    "com.tw",
}


def registrable_domain(url: str) -> str:
    host = urlsplit(url).hostname if "://" in url else url
    host = (host or "").lower().removeprefix("www.")
    labels = [label for label in host.split(".") if label]
    if len(labels) >= 3 and ".".join(labels[-2:]) in MULTI_LABEL_SUFFIXES:
        return ".".join(labels[-3:])
    return ".".join(labels[-2:])


class Tier(str, enum.Enum):
    REGULATOR = "regulator_or_official"
    ACADEMIC = "academic"
    FINANCIAL_MEDIA = "established_financial_media"
    GENERAL_MEDIA = "general_media"
    AGGREGATOR = "comparison_aggregator"
    VENDOR = "vendor_or_issuer"
    COMMUNITY = "community_ugc"
    UNKNOWN = "unknown"


# Prior credibility by kind of source. A regulator publishes primary
# documents under a legal duty of accuracy; academic work is vetted but rarely
# current on product terms; financial media carry corrections policies and
# specialisation, general media the policy without the specialisation.
# Comparison sites are commission-funded, so their prior is discounted (the
# page-level conflict markers below are separate evidence, not double
# counting). A vendor is authoritative on its own terms but has no standing
# on "best". User-generated content has no verification layer. An unknown
# domain is unverified, not presumed bad, so it sits above UGC.
TIER_BASE: dict[Tier, int] = {
    Tier.REGULATOR: 85,
    Tier.ACADEMIC: 78,
    Tier.FINANCIAL_MEDIA: 70,
    Tier.GENERAL_MEDIA: 58,
    Tier.AGGREGATOR: 45,
    Tier.VENDOR: 42,
    Tier.UNKNOWN: 35,
    Tier.COMMUNITY: 25,
}


def _tier(tier: Tier, *domains: str) -> dict[str, Tier]:
    return {domain: tier for domain in domains}


# Hand-curated and finite, skewed to English-language and Korean finance
# sources. Committed as data so a reviewer can argue with any entry.
SOURCE_REGISTRY: dict[str, Tier] = {
    **_tier(
        Tier.REGULATOR,
        "sec.gov", "investor.gov", "finra.org", "fca.org.uk", "fss.or.kr", "fsc.go.kr", "bok.or.kr",
        "federalreserve.gov", "ecb.europa.eu", "esma.europa.eu", "consumerfinance.gov", "fdic.gov",
        "bankofengland.co.uk", "rbi.org.in", "sebi.gov.in", "mas.gov.sg", "asic.gov.au", "moneysmart.gov.au",
        "imf.org", "bis.org", "oecd.org",
    ),
    **_tier(Tier.ACADEMIC, "nber.org", "ssrn.com", "jstor.org", "arxiv.org"),
    **_tier(
        Tier.FINANCIAL_MEDIA,
        "reuters.com", "bloomberg.com", "ft.com", "wsj.com", "economist.com", "apnews.com", "cnbc.com",
        "marketwatch.com", "barrons.com", "koreaherald.com", "koreatimes.co.kr", "yna.co.kr", "joins.com",
        "livemint.com", "nikkei.com",
    ),
    **_tier(
        Tier.GENERAL_MEDIA,
        "bbc.co.uk", "bbc.com", "cnn.com", "theguardian.com", "nytimes.com", "washingtonpost.com", "forbes.com",
        "businessinsider.com", "yahoo.com", "time.com", "npr.org", "aljazeera.com", "indiatimes.com",
    ),
    **_tier(
        Tier.AGGREGATOR,
        "nerdwallet.com", "bankrate.com", "moneysupermarket.com", "investopedia.com", "thebalancemoney.com",
        "finder.com", "comparethemarket.com", "creditkarma.com", "fool.com", "moneysavingexpert.com",
        "valuepenguin.com", "banksalad.com", "paisabazaar.com", "bankbazaar.com",
    ),
    **_tier(
        Tier.VENDOR,
        "chase.com", "bankofamerica.com", "wellsfargo.com", "citi.com", "hsbc.com", "barclays.co.uk",
        "kbstar.com", "shinhan.com", "wooribank.com", "hanabank.com", "kakaobank.com", "tossbank.com", "toss.im",
        "robinhood.com", "coinbase.com", "binance.com", "upbit.com", "bithumb.com", "fidelity.com", "schwab.com",
        "vanguard.com", "etrade.com", "revolut.com", "wise.com", "paypal.com", "sofi.com", "marcus.com", "ally.com",
        "americanexpress.com", "capitalone.com", "kiwoom.com", "miraeasset.com", "hdfcbank.com", "icicibank.com",
        "zerodha.com", "groww.in",
    ),
    **_tier(
        Tier.COMMUNITY,
        "reddit.com", "quora.com", "medium.com", "youtube.com", "tiktok.com", "x.com", "twitter.com",
        "seekingalpha.com", "facebook.com", "instagram.com", "substack.com", "tistory.com", "stocktwits.com",
        "t.me",
    ),
}

# Host-suffix rules for domains not in the registry.
TIER_SUFFIX_RULES: tuple[tuple[str, Tier], ...] = (
    ("gov", Tier.REGULATOR), ("gov.uk", Tier.REGULATOR), ("go.kr", Tier.REGULATOR), ("gov.in", Tier.REGULATOR),
    ("gov.sg", Tier.REGULATOR), ("gov.au", Tier.REGULATOR), ("europa.eu", Tier.REGULATOR),
    ("edu", Tier.ACADEMIC), ("ac.uk", Tier.ACADEMIC), ("ac.kr", Tier.ACADEMIC), ("ac.jp", Tier.ACADEMIC),
    ("edu.au", Tier.ACADEMIC), ("edu.cn", Tier.ACADEMIC),
)


def tier_for(url: str) -> Tier:
    domain = registrable_domain(url)
    if domain in SOURCE_REGISTRY:
        return SOURCE_REGISTRY[domain]
    host = ((urlsplit(url).hostname if "://" in url else url) or "").lower()
    for suffix, tier in TIER_SUFFIX_RULES:
        if host == suffix or host.endswith("." + suffix):
            return tier
    return Tier.UNKNOWN


# ------------------------------------------------------------------ claims


class ClaimType(str, enum.Enum):
    SAFETY_GUARANTEE = "safety_guarantee"
    RETURN_PREDICTION = "return_prediction"
    TIMING = "timing"
    SUPERLATIVE = "superlative"
    FACTUAL_RATE = "factual_rate"
    UNCLASSIFIED = "unclassified"


# Caution points for how checkable the claim is at all. No evidence can
# settle a guarantee or a future return in advance, so they take the full
# 25; "best" is comparative on unstated criteria (12); a stated rate can be
# checked against a primary source (4); not knowing is mild evidence (10).
UNFALSIFIABILITY_POINTS: dict[ClaimType, int] = {
    ClaimType.SAFETY_GUARANTEE: 25,
    ClaimType.RETURN_PREDICTION: 25,
    ClaimType.TIMING: 18,
    ClaimType.SUPERLATIVE: 12,
    ClaimType.FACTUAL_RATE: 4,
    ClaimType.UNCLASSIFIED: 10,
}

LEAD_INS = (
    "is it true that ", "i heard that ", "someone said ", "my friend said ", "people say ", "they say ",
    "should i ", "i heard ", "is ",
)

SAFETY_TERMS = (
    "guaranteed", "guarantee", "risk-free", "risk free", "no risk", "can't lose", "cannot lose", "zero risk",
    "100% safe", "principal protected",
)
RETURN_TERMS = (
    "will double", "will triple", "will go up", "will rise", "will hit", "will reach", "is going to",
    "set to soar", "to the moon", "10x",
)
RETURN_CONTEXT = ("return", "returns", "gain", "gains", "profit", "profits", "in a year")
TIMING_TERMS = (
    "buy now", "act now", "before it's too late", "last chance", "limited time", "don't miss",
    "while you still can", "right now",
)
SUPERLATIVE_TERMS = (
    "best", "top", "#1", "number one", "highest", "cheapest", "greatest", "unbeatable", "better than any",
    "no one beats",
)
RATE_CONTEXT = ("apy", "apr", "interest", "rate", "fee", "fees", "cashback", "savings account", "deposit")

PCT = re.compile(r"(\d+(?:\.\d+)?)\s*%")
MULT = re.compile(r"\b(\d+(?:\.\d+)?)\s*x\b|\b(double|triple)\b")
MONEY = re.compile(r"(?:[$₩€£¥]|\busd|\bkrw|\beur|\bgbp|\bjpy)\s?(\d[\d,]*(?:\.\d+)?)")

STOPWORDS = frozenset(
    """a about above after again against all also am an and any are as at be because been before being below
    between both but by can could did do does doing down during each few for from further had has have having he
    her here hers herself him himself his how i if in into is it its itself just me more most my myself no nor
    not now of off on once only or other our ours ourselves out over own same she should so some such than that
    the their theirs them themselves then there these they this those through to too under until up very was we
    were what when where which while who whom why will with would you your yours yourself yourselves really
    true heard said people someone friend going get gets make makes much many every year years month months
    week weeks day days thing things good better best""".split()
)


def _has(text: str, phrase: str) -> bool:
    return re.search(r"(?<![a-z0-9])" + re.escape(phrase) + r"(?![a-z0-9])", text) is not None


def _has_any(text: str, phrases) -> bool:
    return any(_has(text, phrase) for phrase in phrases)


@dataclass(frozen=True)
class ParsedClaim:
    text: str
    normalized_query: str
    claim_type: ClaimType
    key_terms: frozenset[str]
    numbers: tuple[str, ...]
    money_mentions: tuple[str, ...]


def normalize_claim(text: str) -> str:
    lowered = " ".join(text.casefold().split())
    for lead_in in sorted(LEAD_INS, key=len, reverse=True):
        if lowered.startswith(lead_in):
            lowered = lowered[len(lead_in):]
            break
    return lowered.rstrip("?.! ").strip()[:200]


def classify(text: str) -> ClaimType:
    """First match wins, strongest red flag first, so "guaranteed best
    returns" is a guarantee, not a superlative."""
    t = text.casefold()
    if _has_any(t, SAFETY_TERMS):
        return ClaimType.SAFETY_GUARANTEE
    if _has_any(t, RETURN_TERMS) or MULT.search(t) or (PCT.search(t) and _has_any(t, RETURN_CONTEXT)):
        return ClaimType.RETURN_PREDICTION
    if _has_any(t, TIMING_TERMS):
        return ClaimType.TIMING
    if _has_any(t, SUPERLATIVE_TERMS):
        return ClaimType.SUPERLATIVE
    if PCT.search(t) and _has_any(t, RATE_CONTEXT):
        return ClaimType.FACTUAL_RATE
    return ClaimType.UNCLASSIFIED


def parse_claim(text: str) -> ParsedClaim:
    normalized = normalize_claim(text)
    t = text.casefold()
    numbers = [m.group(1) for m in PCT.finditer(t)]
    numbers += [m.group(1) for m in MULT.finditer(t) if m.group(1)]
    money = [m.group(1).replace(",", "") for m in MONEY.finditer(t)]
    terms = {tok for tok in re.findall(r"[a-z0-9]+", normalized) if len(tok) >= 4 and tok not in STOPWORDS}
    for quoted in re.findall(r'"([^"]+)"', text):
        terms.update(re.findall(r"[a-z0-9]+", quoted.casefold()))
    return ParsedClaim(
        text=text,
        normalized_query=normalized,
        claim_type=classify(text),
        key_terms=frozenset(terms),
        numbers=tuple(dict.fromkeys(numbers + money)),
        money_mentions=tuple(money),
    )


def entity_match(key_terms: frozenset[str], url: str) -> bool:
    """Does the claim name the site's own brand? Token containment against the
    registrable domain's first label ("kbstar" for kbstar.com). Crude and
    deterministic; its failure modes are listed in the module limitations."""
    label = registrable_domain(url).split(".")[0]
    if len(label) < 4:
        return any(term == label for term in key_terms)
    return any(term == label or (len(term) >= 4 and (term in label or label in term)) for term in key_terms)


# ----------------------------------------------------------------- sources

SPONSORED_MARKERS = (
    "sponsored", "paid partnership", "in partnership with", "advertisement", "promoted post", "#ad",
    "paid content", "advertorial",
)
AFFILIATE_PARAMS = ("tag=", "ref=", "aff=", "affid", "affiliate", "partner=", "clickid", "irclickid", "utm_medium=affiliate")
AFFILIATE_HOSTS = {"shareasale.com", "awin1.com", "cj.com", "impact.com", "skimlinks.com", "amzn.to", "redirectingat.com"}
COMMISSION_MARKERS = (
    "we may earn a commission", "affiliate links", "commission when you", "compensation may impact",
    "we are compensated",
)
URGENCY_MARKERS = ("act now", "limited time", "don't miss", "hurry", "exclusive offer", "get rich", "secret", "life-changing")

# Independence penalties, ordered by how directly money flows to the page
# from the thing being claimed about: a stake in the product itself, then
# disclosed paid placement, an affiliate link, a sitewide commission
# disclosure, the business model alone, and finally rhetoric (style, not money).
VENDOR_IS_SUBJECT_PENALTY = 45
SPONSORED_PENALTY = 40
AFFILIATE_PENALTY = 35
COMMISSION_PENALTY = 25
AGGREGATOR_PENALTY = 20
URGENCY_PENALTY = 15

PRIMARY_SOURCE_BONUS = 20  # a bank's own page IS the primary source for its own advertised rate
RECENT_BONUS = 6  # published within a year
STALE_PENALTY = -10  # more than 3 years old
UNDATED_PENALTY = -4  # recency can't be verified
SPECIFICITY_BONUS = 4  # restates the claim's own figure, so it's at least on topic

SUPPORT_CUES = {"best", "top", "highest", "outperform", "outperforms", "recommend", "recommended", "winner", "beats", "leading", "excellent"}
SUPPORT_PHRASES = ("strong buy",)
DISPUTE_CUES = {
    "not", "isn't", "avoid", "worst", "myth", "scam", "warning", "beware", "misleading", "overrated", "penalty",
    "lawsuit", "downgrade", "fell", "losses", "complaint", "complaints", "risky", "bubble", "fraud",
}
DISPUTE_PHRASES = ("hidden fee", "hidden fees")
NEGATORS = {"not", "no", "never", "isn't", "aren't", "hardly", "without", "doesn't", "don't"}
NEGATION_WINDOW = 3

ECHO_JACCARD = 0.80  # near-verbatim republication only; survives a different headline or truncation
ECHO_DISCOUNT = 0.25  # a syndicating outlet still chose to run it, but it isn't independent corroboration


@dataclass(frozen=True)
class SearchHit:
    position: int
    title: str
    link: str
    snippet: str = ""
    date_text: str | None = None


@dataclass
class SourceScore:
    position: int
    title: str
    link: str
    domain: str
    tier: Tier
    credibility: int
    credibility_parts: list[tuple[str, int]]
    independence: int
    conflict_signals: list[tuple[str, int]]
    date_known: bool
    age_days: int | None
    relevant: bool
    stance: str
    support_hits: int
    dispute_hits: int
    dedup: float = 1.0
    echo_of: int | None = None
    snippet_tokens: frozenset[str] = field(default_factory=frozenset)


def parse_result_date(text: str | None, reference: date) -> date | None:
    if not text:
        return None
    cleaned = text.strip()
    for fmt in ("%b %d, %Y", "%B %d, %Y", "%d %b %Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(cleaned, fmt).date()
        except ValueError:
            pass
    match = re.match(r"(\d+)\s+(day|week|month|year)s?\s+ago", cleaned.lower())
    if match:
        days = int(match.group(1)) * {"day": 1, "week": 7, "month": 30, "year": 365}[match.group(2)]
        return reference - timedelta(days=days)
    return None


def _is_affiliate(url: str) -> bool:
    parts = urlsplit(url)
    host = (parts.hostname or "").lower()
    if any(host == h or host.endswith("." + h) for h in AFFILIATE_HOSTS):
        return True
    query = parts.query.lower()
    return any(marker in query for marker in AFFILIATE_PARAMS)


def _stance(text: str, key_terms: frozenset[str]) -> tuple[bool, str, int, int]:
    tokens = re.findall(r"[a-z0-9']+|#\w+", text)
    if not set(tokens) & key_terms:
        return False, "neutral", 0, 0
    support = dispute = 0
    for i, token in enumerate(tokens):
        if token in SUPPORT_CUES:
            if any(t in NEGATORS for t in tokens[max(0, i - NEGATION_WINDOW):i]):
                dispute += 1  # "not the best" counts against, not for
            else:
                support += 1
        elif token in DISPUTE_CUES:
            dispute += 1
    support += sum(1 for p in SUPPORT_PHRASES if _has(text, p))
    dispute += sum(1 for p in DISPUTE_PHRASES if _has(text, p))
    if support > dispute and support >= 1:
        stance = "supports"
    elif dispute > support:
        stance = "disputes"
    else:
        stance = "neutral"
    return True, stance, support, dispute


def score_source(hit: SearchHit, claim: ParsedClaim, reference: date) -> SourceScore:
    tier = tier_for(hit.link)
    domain = registrable_domain(hit.link)
    names_brand = entity_match(claim.key_terms, hit.link)
    text = f"{hit.title} {hit.snippet}".casefold()
    snippet = hit.snippet.casefold()

    parts: list[tuple[str, int]] = [(f"{tier.value.replace('_', ' ')} base", TIER_BASE[tier])]
    if claim.claim_type == ClaimType.FACTUAL_RATE and names_brand:
        parts.append(("primary source for its own rate", PRIMARY_SOURCE_BONUS))
    published = parse_result_date(hit.date_text, reference)
    age = (reference - published).days if published else None
    if age is None:
        parts.append(("no publication date", UNDATED_PENALTY))
    elif age <= 365:
        parts.append(("published within a year", RECENT_BONUS))
    elif age > 1095:
        parts.append(("more than 3 years old", STALE_PENALTY))
    snippet_numbers = set(re.findall(r"\d+(?:\.\d+)?", snippet.replace(",", "")))
    if claim.numbers and snippet_numbers & set(claim.numbers):
        parts.append(("restates the claim's figure", SPECIFICITY_BONUS))
    credibility = max(0, min(100, sum(points for _, points in parts)))

    signals: list[tuple[str, int]] = []
    if tier == Tier.VENDOR and names_brand:
        signals.append(("sells the product in question", VENDOR_IS_SUBJECT_PENALTY))
    if _has_any(text, SPONSORED_MARKERS):
        signals.append(("sponsored or paid placement", SPONSORED_PENALTY))
    if _is_affiliate(hit.link):
        signals.append(("affiliate link", AFFILIATE_PENALTY))
    if _has_any(snippet, COMMISSION_MARKERS):
        signals.append(("discloses commissions", COMMISSION_PENALTY))
    if tier == Tier.AGGREGATOR:
        signals.append(("commission-funded comparison site", AGGREGATOR_PENALTY))
    if _has_any(text, URGENCY_MARKERS):
        signals.append(("promotional urgency", URGENCY_PENALTY))
    independence = max(0, 100 - sum(p for _, p in signals))

    relevant, stance, support, dispute = _stance(text, claim.key_terms)
    tokens = frozenset(t for t in re.findall(r"[a-z0-9]+", snippet) if len(t) >= 3 and t not in STOPWORDS)
    return SourceScore(
        position=hit.position,
        title=hit.title,
        link=hit.link,
        domain=domain,
        tier=tier,
        credibility=credibility,
        credibility_parts=parts,
        independence=independence,
        conflict_signals=signals,
        date_known=published is not None,
        age_days=age,
        relevant=relevant,
        stance=stance,
        support_hits=support,
        dispute_hits=dispute,
        snippet_tokens=tokens,
    )


def collapse_echoes(sources: list[SourceScore]) -> None:
    """Ten outlets republishing one press release is one source, not ten.
    Groups sources that share a registrable domain or have near-identical
    snippets; the most credible member (earliest result on a tie) keeps full
    weight and the others are discounted. Mutates in place."""
    parent = list(range(len(sources)))

    def find(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    for i in range(len(sources)):
        for j in range(i + 1, len(sources)):
            a, b = sources[i], sources[j]
            union = a.snippet_tokens | b.snippet_tokens
            jaccard = len(a.snippet_tokens & b.snippet_tokens) / len(union) if union else 0.0
            if a.domain == b.domain or jaccard >= ECHO_JACCARD:
                parent[find(j)] = find(i)

    groups: dict[int, list[SourceScore]] = {}
    for i, source in enumerate(sources):
        groups.setdefault(find(i), []).append(source)
    for members in groups.values():
        representative = max(members, key=lambda s: (s.credibility, -s.position))
        for member in members:
            if member is not representative:
                member.dedup = ECHO_DISCOUNT
                member.echo_of = representative.position
