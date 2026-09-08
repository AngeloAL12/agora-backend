"""update complaintcategory enum

Revision ID: 8dcac940666d
Revises: a66424802494
Create Date: 2026-04-12 20:03:03.956411

"""

from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "8dcac940666d"
down_revision: Union[str, Sequence[str], None] = "a66424802494"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.get_context().autocommit_block():
        op.execute("ALTER TYPE complaintcategory ADD VALUE IF NOT EXISTS 'MAINTENANCE'")
        op.execute("ALTER TYPE complaintcategory ADD VALUE IF NOT EXISTS 'CLEANING'")
        op.execute("ALTER TYPE complaintcategory ADD VALUE IF NOT EXISTS 'SERVICES'")
        op.execute(
            "ALTER TYPE complaintcategory ADD VALUE IF NOT EXISTS 'INFRASTRUCTURE'"
        )
        op.execute("ALTER TYPE complaintcategory ADD VALUE IF NOT EXISTS 'OTHER'")
        op.execute("ALTER TYPE complaintcategory ADD VALUE IF NOT EXISTS 'GENERAL'")


def downgrade() -> None:
    """Downgrade schema."""
    pass
