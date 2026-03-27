"""create career table and add user career fk

Revision ID: 8bd48f2cf7a1
Revises: 4332daa82824
Create Date: 2026-03-27 12:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "8bd48f2cf7a1"
down_revision: str | Sequence[str] | None = "4332daa82824"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "career",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )

    career_table = sa.table("career", sa.column("name", sa.String(length=100)))
    op.bulk_insert(
        career_table,
        [
            {"name": "Ing. Bioquimica"},
            {"name": "Ing. Semiconductores"},
            {"name": "Contador Público"},
            {"name": "Ing. Administracion"},
            {"name": "Ing. Desarrollo de Aplicaciones"},
            {"name": "Ing. Eléctrica"},
            {"name": "Ing. Electrónica"},
            {"name": "Ing. Energías Renovables"},
            {"name": "Ing. Gestión Empresarial"},
            {"name": "Ing. Industrial"},
            {"name": "Ing. Logística"},
            {"name": "Ing. Materiales"},
            {"name": "Ing. Mecatrónica"},
            {"name": "Ing. Mecánica"},
            {"name": "Ing. Química"},
            {"name": "Ing. Sistemas Computacionales"},
        ],
    )

    op.execute(
        sa.text(
            'UPDATE "user" SET id_career = NULL '
            "WHERE id_career IS NOT NULL "
            "AND id_career NOT IN (SELECT id FROM career)"
        )
    )

    op.create_foreign_key(
        "fk_user_id_career_career",
        "user",
        "career",
        ["id_career"],
        ["id"],
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint("fk_user_id_career_career", "user", type_="foreignkey")
    op.drop_table("career")
