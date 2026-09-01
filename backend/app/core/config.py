from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Central runtime configuration, sourced from environment variables / .env.

    Values fall back to safe local-dev defaults so the app can boot without a
    .env file present, but production deployments MUST override every secret
    (POSTGRES_PASSWORD, GEMINI_API_KEY) via real environment variables.
    """

    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    project_name: str = "Meika AI Financial Copilot"
    env: str = "development"
    api_v1_prefix: str = "/api/v1"

    postgres_user: str = "meika"
    postgres_password: str = "meika"
    postgres_db: str = "meika"
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    database_url: str | None = None

    cors_origins: str = "http://localhost:3000,http://localhost:8080"

    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.0-flash"

    # Live Price-Finder search (Google Shopping via SerpApi). Empty by
    # default — search falls back to the seeded demo catalog until a real
    # key is set. Free tier: 100 searches/month, no card required.
    serpapi_api_key: str = ""

    # Dev-only default so the app boots without a .env file (see class
    # docstring). Production MUST override this via a real environment
    # variable — a guessable secret defeats JWT signing entirely.
    jwt_secret_key: str = "dev-only-insecure-secret-change-me"
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 60 * 24

    rate_limit_per_minute: int = 60
    auth_rate_limit_per_minute: int = 10

    @property
    def sqlalchemy_database_url(self) -> str:
        if self.database_url:
            return self.database_url
        return (
            f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def cors_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
