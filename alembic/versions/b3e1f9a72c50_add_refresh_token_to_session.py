"""add refresh_token to session

Revision ID: b3e1f9a72c50
Revises: a66424802494, c1f3a2b4e5d6
Create Date: 2026-04-14 00:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b3e1f9a72c50"
down_revision: Union[str, Sequence[str], None] = ("a66424802494", "c1f3a2b4e5d6")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "session",
        sa.Column("refresh_token", sa.String(512), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("session", "refresh_token")
