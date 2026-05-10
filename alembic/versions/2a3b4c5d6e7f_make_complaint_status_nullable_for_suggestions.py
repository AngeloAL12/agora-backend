"""Make complaint status nullable for suggestions

Revision ID: 2a3b4c5d6e7f
Revises: 1c429b08be67
Create Date: 2026-05-09 23:55:00.000000

"""

from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "2a3b4c5d6e7f"
down_revision: Union[str, Sequence[str], None] = "1c429b08be67"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Make status column nullable
    op.alter_column("complaint", "status", nullable=True)


def downgrade() -> None:
    """Downgrade schema."""
    # Make status column not nullable again
    op.alter_column("complaint", "status", nullable=False)
