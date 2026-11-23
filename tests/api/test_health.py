from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock

from app.core.database import get_session
from app.main import create_application
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession


def test_health_check() -> None:
    application = create_application()

    with TestClient(application) as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_readiness_check() -> None:
    application = create_application()

    mock_session = AsyncMock(spec=AsyncSession)

    async def override_get_session() -> AsyncGenerator[AsyncSession, None]:
        yield mock_session

    application.dependency_overrides[get_session] = override_get_session

    try:
        with TestClient(application) as client:
            response = client.get("/health/ready")
    finally:
        application.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "database": "ok",
    }

    mock_session.execute.assert_awaited_once()


def test_readiness_check_database_unavailable() -> None:
    application = create_application()

    mock_session = AsyncMock(spec=AsyncSession)
    mock_session.execute.side_effect = Exception("Database unavailable")

    async def override_get_session() -> AsyncGenerator[AsyncSession, None]:
        yield mock_session

    application.dependency_overrides[get_session] = override_get_session

    try:
        with TestClient(application) as client:
            response = client.get("/health/ready")
    finally:
        application.dependency_overrides.clear()

    assert response.status_code == 503
    assert response.json() == {
        "detail": "Database connection is unavailable",
    }
