from unittest.mock import AsyncMock, patch

from app.main import create_application
from fastapi.testclient import TestClient


def test_database_connection_is_closed_on_shutdown() -> None:
    with patch(
        "app.main.close_database_connection",
        new_callable=AsyncMock,
    ) as mock_close:
        application = create_application()

        with TestClient(application):
            mock_close.assert_not_awaited()

        mock_close.assert_awaited_once()
