"""add content safety models

Revision ID: b7c8d9e0f1a2
Revises: f3a4b5c6d7e2
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "b7c8d9e0f1a2"
down_revision: str | Sequence[str] | None = "f3a4b5c6d7e2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

target_type = sa.Enum("POST", "COMMENT", "MESSAGE", name="contenttargettype")
report_reason = sa.Enum(
    "HARASSMENT",
    "HATE_SPEECH",
    "SEXUAL_CONTENT",
    "VIOLENCE",
    "SPAM",
    "PERSONAL_INFORMATION",
    "OTHER",
    name="contentreportreason",
)
report_status = sa.Enum(
    "PENDING", "IN_REVIEW", "RESOLVED", "DISMISSED", name="contentreportstatus"
)
moderation_action = sa.Enum(
    "NONE",
    "REMOVE_CONTENT",
    "SUSPEND_USER",
    "REMOVE_AND_SUSPEND",
    name="moderationaction",
)


def _add_removal_columns(table_name: str) -> None:
    op.add_column(
        table_name,
        sa.Column(
            "is_removed", sa.Boolean(), nullable=False, server_default=sa.false()
        ),
    )
    op.add_column(table_name, sa.Column("removed_at", sa.DateTime(timezone=True)))
    op.add_column(table_name, sa.Column("removed_by_admin_id", sa.Integer()))
    op.add_column(table_name, sa.Column("removed_reason", sa.Text()))
    op.create_foreign_key(
        f"fk_{table_name}_removed_by_admin_id_user",
        table_name,
        "user",
        ["removed_by_admin_id"],
        ["id"],
        ondelete="SET NULL",
    )


def upgrade() -> None:
    _add_removal_columns("club_post")
    _add_removal_columns("club_post_comment")
    _add_removal_columns("club_message")

    op.create_table(
        "content_report",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("reporter_id", sa.Integer(), nullable=False),
        sa.Column("reported_user_id", sa.Integer(), nullable=False),
        sa.Column("moderator_id", sa.Integer()),
        sa.Column("target_type", target_type, nullable=False),
        sa.Column("target_id", sa.Integer(), nullable=False),
        sa.Column("club_id", sa.Integer(), nullable=False),
        sa.Column("reason", report_reason, nullable=False),
        sa.Column("details", sa.Text()),
        sa.Column("content_snapshot", sa.Text(), nullable=False),
        sa.Column(
            "status",
            report_status,
            nullable=False,
            server_default="PENDING",
        ),
        sa.Column(
            "action_taken",
            moderation_action,
            nullable=False,
            server_default="NONE",
        ),
        sa.Column("moderator_comment", sa.Text()),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("reviewed_at", sa.DateTime(timezone=True)),
        sa.ForeignKeyConstraint(["reporter_id"], ["user.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["reported_user_id"], ["user.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["moderator_id"], ["user.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["club_id"], ["club.id"], ondelete="CASCADE"),
        sa.UniqueConstraint(
            "reporter_id",
            "target_type",
            "target_id",
            name="uq_content_report_reporter_target",
        ),
    )
    for column in (
        "reporter_id",
        "reported_user_id",
        "target_type",
        "target_id",
        "club_id",
        "status",
    ):
        op.create_index(f"ix_content_report_{column}", "content_report", [column])

    op.create_table(
        "user_block",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("blocker_id", sa.Integer(), nullable=False),
        sa.Column("blocked_id", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(["blocker_id"], ["user.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["blocked_id"], ["user.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("blocker_id", "blocked_id", name="uq_user_block_pair"),
    )
    op.create_index("ix_user_block_blocker_id", "user_block", ["blocker_id"])
    op.create_index("ix_user_block_blocked_id", "user_block", ["blocked_id"])


def downgrade() -> None:
    op.drop_index("ix_user_block_blocked_id", table_name="user_block")
    op.drop_index("ix_user_block_blocker_id", table_name="user_block")
    op.drop_table("user_block")

    for column in (
        "status",
        "club_id",
        "target_id",
        "target_type",
        "reported_user_id",
        "reporter_id",
    ):
        op.drop_index(f"ix_content_report_{column}", table_name="content_report")
    op.drop_table("content_report")

    for table_name in ("club_message", "club_post_comment", "club_post"):
        op.drop_constraint(
            f"fk_{table_name}_removed_by_admin_id_user",
            table_name,
            type_="foreignkey",
        )
        op.drop_column(table_name, "removed_reason")
        op.drop_column(table_name, "removed_by_admin_id")
        op.drop_column(table_name, "removed_at")
        op.drop_column(table_name, "is_removed")

    bind = op.get_bind()
    moderation_action.drop(bind, checkfirst=True)
    report_status.drop(bind, checkfirst=True)
    report_reason.drop(bind, checkfirst=True)
    target_type.drop(bind, checkfirst=True)
