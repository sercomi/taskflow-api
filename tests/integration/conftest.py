import os
from collections.abc import AsyncGenerator, Callable
from pathlib import Path

import httpx2
import pytest
import pytest_asyncio
from alembic import command
from alembic.config import Config
from app.core.database import get_session
from app.core.security import create_access_token
from app.main import create_application
from app.models.user import User
from sqlalchemy.engine import URL, make_url
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    create_async_engine,
)


@pytest.fixture(scope="session")
def test_database_url() -> URL:
    raw_url = os.getenv("TEST_DATABASE_URL")

    if not raw_url:
        pytest.fail("TEST_DATABASE_URL is required for integration tests")

    url = make_url(raw_url)

    if (
        url.drivername != "postgresql+asyncpg"
        or url.database != "taskflow_test"
        or url.username != "taskflow_test"
        or url.host not in {"localhost", "127.0.0.1"}
        or url.port != 5433
    ):
        pytest.fail(
            "Unsafe TEST_DATABASE_URL. Expected taskflow_test "
            "on localhost:5433 with user taskflow_test."
        )

    return url


@pytest.fixture(scope="session")
def migrated_test_database(test_database_url: URL) -> URL:
    project_root = Path(__file__).resolve().parents[2]
    alembic_config = Config(str(project_root / "alembic.ini"))

    # Alembic env.py reads this variable and overrides sqlalchemy.url.
    os.environ["TEST_DATABASE_URL"] = test_database_url.render_as_string(hide_password=False)

    command.upgrade(alembic_config, "head")

    return test_database_url


@pytest_asyncio.fixture(scope="function", loop_scope="function")
async def test_engine(
    migrated_test_database: URL,
) -> AsyncGenerator[AsyncEngine, None]:
    engine = create_async_engine(
        migrated_test_database,
        pool_pre_ping=True,
    )

    yield engine

    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(
    test_engine: AsyncEngine,
) -> AsyncGenerator[AsyncSession, None]:
    async with test_engine.connect() as connection:
        transaction = await connection.begin()

        session = AsyncSession(
            bind=connection,
            expire_on_commit=False,
            join_transaction_mode="create_savepoint",
        )

        try:
            yield session
        finally:
            await session.close()
            await transaction.rollback()


@pytest_asyncio.fixture
async def api_client(
    db_session: AsyncSession,
) -> AsyncGenerator[httpx2.AsyncClient, None]:
    application = create_application()

    async def override_get_session() -> AsyncGenerator[AsyncSession, None]:
        yield db_session

    application.dependency_overrides[get_session] = override_get_session

    transport = httpx2.ASGITransport(app=application)

    async with httpx2.AsyncClient(
        transport=transport,
        base_url="http://test",
    ) as client:
        yield client

    application.dependency_overrides.clear()


@pytest.fixture
def auth_headers() -> Callable[[User], dict[str, str]]:
    def create_headers(user: User) -> dict[str, str]:
        token = create_access_token(subject=str(user.id))
        return {"Authorization": f"Bearer {token}"}

    return create_headers
