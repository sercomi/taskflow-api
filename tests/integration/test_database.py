from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


async def test_database_connection(db_session: AsyncSession) -> None:
    result = await db_session.execute(text("SELECT current_database()"))

    assert result.scalar_one() == "taskflow_test"
