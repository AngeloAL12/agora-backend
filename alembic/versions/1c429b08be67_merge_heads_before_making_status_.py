"""Merge heads before making status nullable

Revision ID: 1c429b08be67
Revises: 5d05ddad2953, d57874f063a3
Create Date: 2026-05-09 23:49:37.179446

"""

from typing import Sequence, Union


# revision identifiers, used by Alembic.
revision: str = "1c429b08be67"
down_revision: Union[str, Sequence[str], None] = ("5d05ddad2953", "d57874f063a3")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
