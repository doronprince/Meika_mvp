"""Web search for claim check via SerpApi's Google engine. Mirrors
live_price_service: with no SERPAPI_API_KEY, or on any failure, returns None
(never []), so "search unavailable" and "search ran, found nothing" stay
distinct all the way to the user-facing text ([[serpapi-graceful-degradation]]).
"""

import logging

import httpx

from app.core.config import settings
from app.services.claim_sources import SearchHit
from app.services.live_price_service import SERPAPI_BASE_URL

logger = logging.getLogger(__name__)

# Below the Flutter client's 30s receive timeout even with an FX call in the
# same request (12 + 5 seconds).
SEARCH_TIMEOUT_SECONDS = 12.0
MAX_RESULTS = 10


async def search_sources(query: str, country: str) -> list[SearchHit] | None:
    if not settings.serpapi_api_key:
        return None
    try:
        async with httpx.AsyncClient(timeout=SEARCH_TIMEOUT_SECONDS) as client:
            response = await client.get(
                SERPAPI_BASE_URL,
                params={
                    "engine": "google",
                    "q": query,
                    "gl": country.lower(),
                    "num": MAX_RESULTS,
                    "api_key": settings.serpapi_api_key,
                },
            )
            response.raise_for_status()
            data = response.json()
    except (httpx.HTTPError, ValueError):
        logger.exception("SerpApi claim search failed")
        return None

    if "error" in data:
        # SerpApi reports "no results" as an error string too; that one is a
        # real empty result, not an outage.
        if "hasn't returned any results" in str(data["error"]):
            return []
        logger.warning("SerpApi returned an error: %s", data["error"])
        return None

    hits = []
    for index, item in enumerate((data.get("organic_results") or [])[:MAX_RESULTS]):
        if not item.get("link") or not item.get("title"):
            continue
        hits.append(
            SearchHit(
                position=index + 1,
                title=item["title"],
                link=item["link"],
                snippet=item.get("snippet") or "",
                date_text=item.get("date"),
            )
        )
    return hits
