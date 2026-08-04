from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.routers import expense, health


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

    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    application.include_router(health.router, prefix=settings.api_v1_prefix)
    application.include_router(expense.router, prefix=settings.api_v1_prefix)

    return application


app = create_application()
