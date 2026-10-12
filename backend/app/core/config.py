from functools import lru_cache
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from pydantic_settings import BaseSettings, SettingsConfigDict


# libpq spellings that mean "use TLS". asyncpg doesn't understand any of
# them: it takes an `ssl` connect argument instead, so they are stripped
# from the URL here and turned into that flag (see app/db/session.py).
_TLS_SSLMODES = {"require", "verify-ca", "verify-full"}
_LIBPQ_ONLY_PARAMS = {"channel_binding", "sslmode", "ssl"}


def normalize_database_url(raw: str) -> tuple[str, bool]:
    """A hosted provider hands out a libpq URL (`postgresql://...?sslmode=require`,
    and Neon adds `channel_binding`). Return it as an asyncpg URL plus whether
    TLS was asked for. Without this the app boots locally and dies in
    production on `connect() got an unexpected keyword argument 'sslmode'`."""
    parts = urlsplit(raw)
    scheme = parts.scheme
    if scheme in ("postgres", "postgresql"):
        scheme = "postgresql+asyncpg"

    requires_tls = False
    kept: list[tuple[str, str]] = []
    for key, value in parse_qsl(parts.query, keep_blank_values=True):
        if key == "sslmode":
            requires_tls = value in _TLS_SSLMODES
        elif key == "ssl":
            requires_tls = value.lower() in {"1", "true", "require", "verify-ca", "verify-full"}
        elif key in _LIBPQ_ONLY_PARAMS:
            continue
        else:
            kept.append((key, value))
    return urlunsplit((scheme, parts.netloc, parts.path, urlencode(kept), parts.fragment)), requires_tls


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
            return normalize_database_url(self.database_url)[0]
        return (
            f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def database_requires_tls(self) -> bool:
        """True when the configured URL asked for TLS, as every hosted
        Postgres does and a local docker-compose one does not."""
        return bool(self.database_url) and normalize_database_url(self.database_url)[1]

    @property
    def cors_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
