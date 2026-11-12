import pytest
from sqlalchemy.engine import make_url

from app.core.config import Settings


@pytest.mark.parametrize(
    "database_url",
    [
        "postgresql://test_user:p%40ss%3Aword@localhost:5432/test_db",
        "postgresql+psycopg2://test_user:p%40ss%3Aword@localhost:5432/test_db",
    ],
)
def test_postgresql_urls_use_psycopg3_and_preserve_password(database_url):
    settings = Settings(_env_file=None, POSTGRES_PASSWORD="local-test-password", DATABASE_URL=database_url)

    url = make_url(settings.effective_database_url)

    assert url.drivername == "postgresql+psycopg"
    assert url.password == "p@ss:word"


def test_postgresql_url_is_built_with_psycopg3():
    settings = Settings(
        _env_file=None,
        POSTGRES_USER="test_user",
        POSTGRES_PASSWORD="p@ss:word",
        POSTGRES_DB="test_db",
    )

    url = make_url(settings.effective_database_url)

    assert url.drivername == "postgresql+psycopg"
    assert url.password == "p@ss:word"


def test_missing_password_does_not_fall_back_to_a_hardcoded_credential():
    settings = Settings(_env_file=None)

    assert make_url(settings.effective_database_url).password == ""
