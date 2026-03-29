"""merge heads

Revision ID: ddd4803ec953
Revises: 8bd48f2cf7a1, 8f2b1d4c9a7e
Create Date: 2026-03-29 12:27:58.196720

"""

from typing import Sequence, Union


# revision identifiers, used by Alembic.
revision: str = "ddd4803ec953"
down_revision: Union[str, Sequence[str], None] = ("8bd48f2cf7a1", "8f2b1d4c9a7e")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
