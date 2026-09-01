from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.rate_limit import RateLimitMiddleware
from app.routers import auth, chat, dashboard, expense, fx, health, price_finder, users, ws_copilot


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield


def create_application() -> FastAPI:
    application = FastAPI(
        title=settings.project_name,
        description=(
            "Meika API — AI Financial Copilot for international students. "
            "Decoupled JSON/WebSocket backend serving the Flutter client."
        ),
        version="0.1.0",
        lifespan=lifespan,
    )

    # Order matters: Starlette makes the LAST-added middleware outermost, so
    # CORS is added last to ensure even a 429 from the rate limiter carries
    # proper CORS headers back to the browser.
    application.add_middleware(
        RateLimitMiddleware,
        general_limit=settings.rate_limit_per_minute,
        auth_limit=settings.auth_rate_limit_per_minute,
    )
    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    application.include_router(health.router, prefix=settings.api_v1_prefix)
    application.include_router(auth.router, prefix=settings.api_v1_prefix)
    application.include_router(users.router, prefix=settings.api_v1_prefix)
    application.include_router(expense.router, prefix=settings.api_v1_prefix)
    application.include_router(dashboard.router, prefix=settings.api_v1_prefix)
    application.include_router(price_finder.router, prefix=settings.api_v1_prefix)
    application.include_router(fx.router, prefix=settings.api_v1_prefix)
    application.include_router(chat.router, prefix=settings.api_v1_prefix)
    application.include_router(ws_copilot.router, prefix="/ws")

    return application


app = create_application()
