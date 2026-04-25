"""Add club posts, comments, likes and images tables

Revision ID: 5c9ec474d14a
Revises: af268a54fcda
Create Date: 2026-04-22 17:44:59.270445

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "5c9ec474d14a"
down_revision: Union[str, Sequence[str], None] = "af268a54fcda"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "club_post",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("id_club", sa.Integer(), nullable=False),
        sa.Column("id_author", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["id_author"],
            ["user.id"],
        ),
        sa.ForeignKeyConstraint(
            ["id_club"],
            ["club.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "club_post_comment",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("id_post", sa.Integer(), nullable=False),
        sa.Column("id_user", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["id_post"],
            ["club_post.id"],
        ),
        sa.ForeignKeyConstraint(
            ["id_user"],
            ["user.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "club_post_image",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("url", sa.String(length=500), nullable=False),
        sa.Column("id_post", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["id_post"],
            ["club_post.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "club_post_like",
        sa.Column("id_post", sa.Integer(), nullable=False),
        sa.Column("id_user", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["id_post"],
            ["club_post.id"],
        ),
        sa.ForeignKeyConstraint(
            ["id_user"],
            ["user.id"],
        ),
        sa.PrimaryKeyConstraint("id_post", "id_user"),
    )


def downgrade() -> None:
    op.drop_table("club_post_like")
    op.drop_table("club_post_image")
    op.drop_table("club_post_comment")
    op.drop_table("club_post")
