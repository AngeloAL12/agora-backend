"""seed default roles

Revision ID: 8f2b1d4c9a7e
Revises: 4332daa82824
Create Date: 2026-03-27 11:10:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "8f2b1d4c9a7e"
down_revision: str | Sequence[str] | None = "4332daa82824"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    bind = op.get_bind()

    for role_name in ("admin", "staff", "user"):
        bind.execute(
            sa.text(
                """
                INSERT INTO role (name)
                VALUES (:role_name)
                ON CONFLICT (name) DO NOTHING
                """
            ),
            {"role_name": role_name},
        )


def downgrade() -> None:
    """Downgrade schema."""
    op.execute(
        sa.text(
            """
            DELETE FROM role
            WHERE name IN ('admin', 'staff', 'user')
              AND NOT EXISTS (
                  SELECT 1 FROM "user" WHERE "user".id_role = role.id
              )
              AND NOT EXISTS (
                  SELECT 1
                  FROM staff_whitelist
                  WHERE staff_whitelist.id_role = role.id
              )
            """
        )
    )
