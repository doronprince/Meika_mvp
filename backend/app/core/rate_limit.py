"""Simple in-memory sliding-window rate limiter.

[[rate-limit-scope]]: this is per-process, in-memory state — it resets on
restart and does NOT coordinate across multiple worker processes or
replicas. That's fine for this MVP's single `uvicorn` process; swap for a
Redis-backed limiter before ever running more than one worker.
"""

import time
from collections import defaultdict, deque

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, general_limit: int, auth_limit: int, window_seconds: int = 60):
        super().__init__(app)
        self._general_limit = general_limit
        self._auth_limit = auth_limit
        self._window_seconds = window_seconds
        self._hits: dict[str, deque] = defaultdict(deque)

    async def dispatch(self, request: Request, call_next):
        client_ip = request.client.host if request.client else "unknown"
        is_auth = request.url.path.startswith("/api/v1/auth")
        limit = self._auth_limit if is_auth else self._general_limit
        key = f"{'auth' if is_auth else 'api'}:{client_ip}"

        now = time.monotonic()
        hits = self._hits[key]
        while hits and now - hits[0] > self._window_seconds:
            hits.popleft()

        if len(hits) >= limit:
            return JSONResponse(status_code=429, content={"detail": "Too many requests — slow down and try again."})

        hits.append(now)
        return await call_next(request)
