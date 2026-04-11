"""create campus models

Revision ID: dad232aa3c23
Revises: 1592935c8aeb
Create Date: 2026-04-11 13:06:16.105634

"""

from typing import Sequence, Union
from datetime import datetime

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "dad232aa3c23"
down_revision: Union[str, Sequence[str], None] = "1592935c8aeb"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    building_table = op.create_table(
        "building",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "building_image",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("id_building", sa.Integer(), nullable=False),
        sa.Column("url", sa.String(length=255), nullable=False),
        sa.Column("floor", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["id_building"], ["building.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "building_360",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("id_building", sa.Integer(), nullable=False),
        sa.Column("url", sa.String(length=255), nullable=False),
        sa.Column("floor", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["id_building"], ["building.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )

    point_of_interest_table = op.create_table(
        "point_of_interest",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("latitude", sa.Float(), nullable=True),
        sa.Column("longitude", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "point_of_interest_image",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("id_point", sa.Integer(), nullable=False),
        sa.Column("url", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["id_point"], ["point_of_interest.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "point_of_interest_360",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("id_point", sa.Integer(), nullable=False),
        sa.Column("url", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["id_point"], ["point_of_interest.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    # Seed data
    now = datetime.utcnow()
    op.bulk_insert(
        building_table,
        [
            {"name": n, "created_at": now}
            for n in [
                "B",
                "L",
                "U",
                "C",
                "G",
                "I",
                "J",
                "F",
                "E",
                "H",
                "A",
                "V",
                "Q",
                "M",
                "X",
                "D",
                "Nodo",
                "Extraescolares",
            ]
        ],
    )
    op.bulk_insert(
        point_of_interest_table,
        [
            {"name": "Plaza Bicentenario", "created_at": now},
            {"name": "Cancha Basketball", "created_at": now},
        ],
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("point_of_interest_360")
    op.drop_table("point_of_interest_image")
    op.drop_table("point_of_interest")
    op.drop_table("building_360")
    op.drop_table("building_image")
    op.drop_table("building")
