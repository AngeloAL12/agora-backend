"""add ACADEMIC to complaintcategory enum

Revision ID: c1f3a2b4e5d6
Revises: 8dcac940666d
Create Date: 2026-04-13 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "c1f3a2b4e5d6"
down_revision: Union[str, Sequence[str], None] = "8dcac940666d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add ACADEMIC value to complaintcategory enum."""
    with op.get_context().autocommit_block():
        op.execute("ALTER TYPE complaintcategory ADD VALUE IF NOT EXISTS 'ACADEMIC'")


def downgrade() -> None:
    """Downgrade schema.

    NOTE: PostgreSQL does not support removing enum values.
    To fully revert, the enum type would need to be recreated.
    """
    pass
