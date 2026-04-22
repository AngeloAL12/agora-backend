"""add club_message table

Revision ID: 6f3f3fb31d8b
Revises: af268a54fcda
Create Date: 2026-04-21 10:30:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "6f3f3fb31d8b"
down_revision: Union[str, Sequence[str], None] = "af268a54fcda"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "club_message",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("id_club", sa.Integer(), nullable=False),
        sa.Column("id_user", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["id_club"], ["club.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["id_user"], ["user.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_club_message_id_club"), "club_message", ["id_club"], unique=False
    )
    op.create_index(
        op.f("ix_club_message_id_user"), "club_message", ["id_user"], unique=False
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f("ix_club_message_id_user"), table_name="club_message")
    op.drop_index(op.f("ix_club_message_id_club"), table_name="club_message")
    op.drop_table("club_message")
