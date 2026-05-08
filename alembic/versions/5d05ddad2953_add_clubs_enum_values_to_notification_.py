"""add clubs enum values to notification enums

Revision ID: 5d05ddad2953
Revises: 29f0ff63081f
Create Date: 2026-05-06 08:32:15.662497

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '5d05ddad2953'
down_revision: Union[str, Sequence[str], None] = '29f0ff63081f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TYPE notificationcategory ADD VALUE IF NOT EXISTS 'CLUBS'")
    op.execute("ALTER TYPE notificationeventtype ADD VALUE IF NOT EXISTS 'CLUB_JOIN_REQUEST'")
    op.execute("ALTER TYPE notificationeventtype ADD VALUE IF NOT EXISTS 'CLUB_JOIN_ACCEPTED'")
    op.execute("ALTER TYPE notificationeventtype ADD VALUE IF NOT EXISTS 'CLUB_JOIN_REJECTED'")


def downgrade() -> None:
    # PostgreSQL does not support removing enum values — requires recreating the type
    pass
