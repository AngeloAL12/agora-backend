"""merge multiple heads

Revision ID: 140bbf222fef
Revises: 3f4ac2afbc96, af268a54fcda
Create Date: 2026-04-19 14:50:51.288157

"""

from typing import Sequence, Union


# revision identifiers, used by Alembic.
revision: str = "140bbf222fef"
down_revision: Union[str, Sequence[str], None] = ("3f4ac2afbc96", "af268a54fcda")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
