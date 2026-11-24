from unittest.mock import AsyncMock, MagicMock

import pytest
from app.models.user import User
from app.services.user import get_user_by_email


@pytest.mark.parametrize(
    "email",
    [
        "test@example.com",
        "TEST@EXAMPLE.COM",
        "Test@Example.com",
    ],
)
async def test_get_user_by_email_case_insensitive(
    mock_session: AsyncMock,
    email: str,
) -> None:
    user = User(
        id=1,
        email="test@example.com",
        hashed_password="hashed-password",
        is_active=True,
    )

    result = MagicMock()
    result.scalar_one_or_none.return_value = user
    mock_session.execute.return_value = result

    found_user = await get_user_by_email(mock_session, email)

    assert found_user is user
    mock_session.execute.assert_awaited_once()
