import pytest
from app.core.config import Settings


def test_database_url_is_created_correctly() -> None:
    settings = Settings(
        _env_file=None,
        postgres_user="test_user",
        postgres_password="test_password",
        postgres_host="localhost",
        postgres_port=5432,
        postgres_db="test_db",
    )

    url = settings.database_url

    assert url.drivername == "postgresql+asyncpg"
    assert url.username == "test_user"
    assert url.password == "test_password"
    assert url.host == "localhost"
    assert url.port == 5432
    assert url.database == "test_db"


def test_database_url_requires_password() -> None:
    settings = Settings(
        _env_file=None,
        postgres_password="",
    )

    with pytest.raises(
        ValueError,
        match="POSTGRES_PASSWORD environment variable is required",
    ):
        _ = settings.database_url
