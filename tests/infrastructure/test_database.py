from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from app.core.database import get_session
from sqlalchemy.ext.asyncio import AsyncSession


@pytest.mark.asyncio
async def test_get_session_closes_session() -> None:
    session = AsyncMock(spec=AsyncSession)

    context_manager = MagicMock()
    context_manager.__aenter__ = AsyncMock(return_value=session)
    context_manager.__aexit__ = AsyncMock(return_value=None)

    with patch(
        "app.core.database.AsyncSessionFactory",
        return_value=context_manager,
    ):
        session_generator = get_session()

        yielded_session = await anext(session_generator)

        assert yielded_session is session

        with pytest.raises(StopAsyncIteration):
            await anext(session_generator)

    context_manager.__aexit__.assert_awaited_once()
