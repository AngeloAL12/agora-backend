"""rename club image to profile_image and add cover_image

Revision ID: 3f4ac2afbc96
Revises: e7c2d1f8a349
Create Date: 2026-04-17 17:44:18.375253

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "3f4ac2afbc96"
down_revision: Union[str, Sequence[str], None] = "2448c427c791"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Renombrar columna image -> profile_image
    op.alter_column("club", "image", new_column_name="profile_image")

    # Agregar cover_image
    op.add_column(
        "club",
        sa.Column("cover_image", sa.String(length=500), nullable=True),
    )


def downgrade() -> None:
    # Quitar cover_image
    op.drop_column("club", "cover_image")

    # Regresar profile_image -> image
    op.alter_column("club", "profile_image", new_column_name="image")
