"""update building image URLs from JPEG/jpg to webp

Revision ID: d1e2f3a4b5c6
Revises: c8d9e0f1a2b3
Create Date: 2026-05-20 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op

revision: str = "d1e2f3a4b5c6"
down_revision: Union[str, Sequence[str], None] = "c8d9e0f1a2b3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Old extensions that need to be replaced with .webp
_OLD_EXTENSIONS = (".JPEG", ".jpeg", ".JPG", ".jpg", ".PNG", ".png")


def _build_update(table: str) -> str:
    """Build a single SQL CASE expression that replaces any known extension with .webp."""
    when_clauses = "\n        ".join(
        f"WHEN url LIKE '%{ext}' THEN CONCAT(LEFT(url, LENGTH(url) - {len(ext)}), '.webp')"
        for ext in _OLD_EXTENSIONS
    )
    return f"""
        UPDATE {table}
        SET url = CASE
        {when_clauses}
        ELSE url
        END
        WHERE {" OR ".join(f"url LIKE '%{ext}'" for ext in _OLD_EXTENSIONS)}
    """


def upgrade() -> None:
    op.execute(_build_update("building_image"))
    op.execute(_build_update("building_360"))
    op.execute(_build_update("point_of_interest_image"))
    op.execute(_build_update("point_of_interest_360"))


def downgrade() -> None:
    # Restore .webp → .JPEG for building_image and .jpg for building_360 / 360 tables
    # (mirrors the original seed: normal images were .JPEG, 360s were .jpg)
    op.execute("""
        UPDATE building_image
        SET url = CONCAT(LEFT(url, LENGTH(url) - 5), '.JPEG')
        WHERE url LIKE '%.webp'
    """)
    op.execute("""
        UPDATE building_360
        SET url = CONCAT(LEFT(url, LENGTH(url) - 5), '.jpg')
        WHERE url LIKE '%.webp'
    """)
    op.execute("""
        UPDATE point_of_interest_image
        SET url = CONCAT(LEFT(url, LENGTH(url) - 5), '.JPEG')
        WHERE url LIKE '%.webp'
    """)
    op.execute("""
        UPDATE point_of_interest_360
        SET url = CONCAT(LEFT(url, LENGTH(url) - 5), '.jpg')
        WHERE url LIKE '%.webp'
    """)
