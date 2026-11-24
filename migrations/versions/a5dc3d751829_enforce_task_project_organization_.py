"""enforce task project organization integrity

Revision ID: a5dc3d751829
Revises: c46305111246
Create Date: 2026-11-24 10:50:43.422347

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a5dc3d751829"
down_revision: str | Sequence[str] | None = "c46305111246"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Required by PostgreSQL for the composite foreign key.
    op.create_unique_constraint(
        "uq_project_id_organization",
        "projects",
        ["id", "organization_id"],
    )

    # Replace the individual project_id FK with a composite FK.
    op.drop_constraint(
        "tasks_project_id_fkey",
        "tasks",
        type_="foreignkey",
    )

    op.create_foreign_key(
        "fk_task_project_organization",
        "tasks",
        "projects",
        ["project_id", "organization_id"],
        ["id", "organization_id"],
        ondelete="CASCADE",
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_task_project_organization",
        "tasks",
        type_="foreignkey",
    )

    op.create_foreign_key(
        "tasks_project_id_fkey",
        "tasks",
        "projects",
        ["project_id"],
        ["id"],
        ondelete="CASCADE",
    )

    op.drop_constraint(
        "uq_project_id_organization",
        "projects",
        type_="unique",
    )
