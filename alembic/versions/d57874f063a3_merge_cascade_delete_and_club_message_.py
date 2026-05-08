"""merge cascade_delete and club_message heads

Revision ID: d57874f063a3
Revises: 1a83bf85c513, 7569c1faefc2
Create Date: 2026-05-07 22:03:32.984822

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd57874f063a3'
down_revision: Union[str, Sequence[str], None] = ('1a83bf85c513', '7569c1faefc2')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
