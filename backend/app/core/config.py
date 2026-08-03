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
