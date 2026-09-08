"""merge club_message head

Revision ID: 1a83bf85c513
Revises: 140bbf222fef, 6f3f3fb31d8b
Create Date: 2026-04-22 20:36:38.844694

"""

from typing import Sequence, Union


# revision identifiers, used by Alembic.
revision: str = "1a83bf85c513"
down_revision: Union[str, Sequence[str], None] = ("140bbf222fef", "6f3f3fb31d8b")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
