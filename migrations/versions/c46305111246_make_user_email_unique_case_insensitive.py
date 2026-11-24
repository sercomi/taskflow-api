"""make user email unique case insensitive

Revision ID: c46305111246
Revises: 362b299f8ccf
Create Date: 2026-11-24 06:54:47.986116

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c46305111246"
down_revision: str | Sequence[str] | None = "362b299f8ccf"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_index("ix_users_email", table_name="users")

    op.create_index(
        "ix_users_email",
        "users",
        [sa.text("lower(email)")],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("ix_users_email", table_name="users")

    op.create_index(
        "ix_users_email",
        "users",
        ["email"],
        unique=True,
    )
