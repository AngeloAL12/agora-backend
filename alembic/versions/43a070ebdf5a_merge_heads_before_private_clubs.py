"""merge heads before private clubs

Revision ID: 43a070ebdf5a
Revises: 1a83bf85c513, 7569c1faefc2
Create Date: 2026-05-06 08:18:57.125759

"""

from typing import Sequence, Union


# revision identifiers, used by Alembic.
revision: str = "43a070ebdf5a"
down_revision: Union[str, Sequence[str], None] = ("1a83bf85c513", "7569c1faefc2")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
