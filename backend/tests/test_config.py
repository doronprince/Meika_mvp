"""Hosted-database URL handling. A provider hands out a libpq URL; asyncpg
rejects libpq's own parameters, so these are the cases that decide whether
the app boots in production."""

from app.core.config import normalize_database_url


def test_neon_style_url_becomes_asyncpg_and_asks_for_tls():
    url, tls = normalize_database_url(
        "postgresql://user:pw@ep-cool-name-123456.ap-southeast-1.aws.neon.tech/meika"
        "?sslmode=require&channel_binding=require"
    )
    # asyncpg driver, and neither libpq-only parameter survives: passing
    # either one through raises "unexpected keyword argument 'sslmode'".
    assert url == "postgresql+asyncpg://user:pw@ep-cool-name-123456.ap-southeast-1.aws.neon.tech/meika"
    assert tls is True


def test_heroku_style_postgres_scheme_is_upgraded():
    url, tls = normalize_database_url("postgres://user:pw@host:5432/db")
    assert url == "postgresql+asyncpg://user:pw@host:5432/db"
    assert tls is False


def test_local_compose_url_is_left_alone():
    raw = "postgresql+asyncpg://meika:meika@localhost:5432/meika"
    assert normalize_database_url(raw) == (raw, False)


def test_an_explicit_ssl_parameter_is_honoured_and_removed():
    url, tls = normalize_database_url("postgresql://user:pw@host/db?ssl=true&application_name=meika")
    assert tls is True
    # Unrelated parameters are kept.
    assert url == "postgresql+asyncpg://user:pw@host/db?application_name=meika"


def test_sslmode_disable_does_not_request_tls():
    _, tls = normalize_database_url("postgresql://user:pw@host/db?sslmode=disable")
    assert tls is False
