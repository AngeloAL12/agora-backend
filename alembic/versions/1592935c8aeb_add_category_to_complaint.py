"""add category to complaint

Revision ID: 1592935c8aeb
Revises: a0b652c77c23
Create Date: 2026-04-02 17:14:24.132800

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "1592935c8aeb"
down_revision: Union[str, Sequence[str], None] = "a0b652c77c23"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema - add category column in safe steps."""
    bind = op.get_bind()

    # Step 1: Create ENUM type
    complaintcategory = sa.Enum("ACADEMIC", "SECURITY", name="complaintcategory")
    complaintcategory.create(bind, checkfirst=True)

    # Step 2: Add column as nullable with temporary server default
    op.add_column(
        "complaint",
        sa.Column(
            "category", complaintcategory, nullable=True, server_default="ACADEMIC"
        ),
    )

    # Step 3: Backfill all NULL values with "ACADEMIC"
    bind.execute(
        sa.text("UPDATE complaint SET category = :default WHERE category IS NULL"),
        {"default": "ACADEMIC"},
    )

    # Step 4: Alter column to NOT NULL
    op.alter_column("complaint", "category", nullable=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("complaint", "category")
    sa.Enum(name="complaintcategory").drop(op.get_bind(), checkfirst=True)
