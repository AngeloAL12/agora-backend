"""add cascade delete to club relations

Revision ID: 7569c1faefc2
Revises: 5c9ec474d14a
Create Date: 2026-04-25 18:25:48.654298

"""

from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "7569c1faefc2"
down_revision: Union[str, Sequence[str], None] = "5c9ec474d14a"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    # club_event -> cascade
    op.drop_constraint("club_event_id_club_fkey", "club_event", type_="foreignkey")
    op.create_foreign_key(
        "club_event_id_club_fkey",
        "club_event",
        "club",
        ["id_club"],
        ["id"],
        ondelete="CASCADE",
    )

    # club_member -> cascade
    op.drop_constraint("club_member_id_club_fkey", "club_member", type_="foreignkey")
    op.create_foreign_key(
        "club_member_id_club_fkey",
        "club_member",
        "club",
        ["id_club"],
        ["id"],
        ondelete="CASCADE",
    )


def downgrade():
    # revert club_event
    op.drop_constraint("club_event_id_club_fkey", "club_event", type_="foreignkey")
    op.create_foreign_key(
        "club_event_id_club_fkey",
        "club_event",
        "club",
        ["id_club"],
        ["id"],
    )

    # revert club_member
    op.drop_constraint("club_member_id_club_fkey", "club_member", type_="foreignkey")
    op.create_foreign_key(
        "club_member_id_club_fkey",
        "club_member",
        "club",
        ["id_club"],
        ["id"],
    )
