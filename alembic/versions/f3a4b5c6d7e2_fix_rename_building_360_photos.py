"""fix rename building 360 photos (old migration used .jpg paths, DB already had .webp)

Revision ID: f3a4b5c6d7e2
Revises: e2f3a4b5c6d7
Create Date: 2026-06-01 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op

revision: str = "f3a4b5c6d7e2"
down_revision: Union[str, Sequence[str], None] = "e2f3a4b5c6d7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Prior migration d1e2f3a4b5c6 already converted all .jpg → .webp in the DB,
# so e2f3a4b5c6d7's WHERE url = '...old.jpg' matched nothing.
# This migration corrects using the actual DB paths (old basename + .webp extension).
BUILDING_360_RENAMES: list[tuple[str, str]] = [
    (
        "buildings/Edificio A/360/EdifA_ENTRADA.webp",
        "buildings/Edificio A/360/EdifA_Entrada.webp",
    ),
    (
        "buildings/Edificio B/360/EdifB_ARRIBA.webp",
        "buildings/Edificio B/360/EdifB_ARRIBA_Escaleras.webp",
    ),
    (
        "buildings/Edificio B/360/EdifB_BIBLIOTECA.webp",
        "buildings/Edificio B/360/EdifB_Biblioteca.webp",
    ),
    (
        "buildings/Edificio B/360/EdifB_BIBLIOTECA_DER.webp",
        "buildings/Edificio B/360/EdifB_Biblioteca_Der.webp",
    ),
    (
        "buildings/Edificio B/360/EdifB_BIBLIOTECA_IZQ.webp",
        "buildings/Edificio B/360/EdifB_Biblioteca_Izq.webp",
    ),
    (
        "buildings/Edificio B/360/EdifB_ENTRADA.webp",
        "buildings/Edificio B/360/EdifB_Entrada.webp",
    ),
    (
        "buildings/Edificio D/360/EdifD_ABAJOESCALERAS.webp",
        "buildings/Edificio D/360/EdifD_ABAJO_Escaleras.webp",
    ),
    (
        "buildings/Edificio D/360/EdifD_ABAJOPUERTA.webp",
        "buildings/Edificio D/360/EdifD_ABAJO_Puerta.webp",
    ),
    (
        "buildings/Edificio D/360/EdifD_ARRIBAESCALERAS.webp",
        "buildings/Edificio D/360/EdifD_ARRIBA_Escaleras.webp",
    ),
    (
        "buildings/Edificio E/360/EdifE_PASILLOS.webp",
        "buildings/Edificio E/360/EdifE_Pasillo.webp",
    ),
    (
        "buildings/Edificio F/360/EdifF_ABAJOESCALERAS.webp",
        "buildings/Edificio F/360/EdifF_ABAJO_Escaleras.webp",
    ),
    (
        "buildings/Edificio F/360/EdifF_ABAJOPUERTA.webp",
        "buildings/Edificio F/360/EdifF_ABAJO_Puerta.webp",
    ),
    (
        "buildings/Edificio F/360/EdifF_ARRIBAESCALERAS.webp",
        "buildings/Edificio F/360/EdifF_ARRIBA_Escaleras.webp",
    ),
    (
        "buildings/Edificio G/360/EdifG_ABAJOLABS.webp",
        "buildings/Edificio G/360/EdifG_ABAJO_Laboratorios.webp",
    ),
    (
        "buildings/Edificio G/360/EdifG_ABAJOPUERTA.webp",
        "buildings/Edificio G/360/EdifG_ABAJO_Puerta.webp",
    ),
    (
        "buildings/Edificio G/360/EdifG_ARRIBAESCALERAS.webp",
        "buildings/Edificio G/360/EdifG_ARRIBA_Escaleras.webp",
    ),
    (
        "buildings/Edificio G/360/EdifG_ARRIBAPUERTA.webp",
        "buildings/Edificio G/360/EdifG_ARRIBA_Puerta.webp",
    ),
    (
        "buildings/Edificio J/360/EdifJ_BAÑOS.webp",
        "buildings/Edificio J/360/EdifJ_Banos.webp",
    ),
    (
        "buildings/Edificio J/360/EdifJ_DIRECCION.webp",
        "buildings/Edificio J/360/EdifJ_Direccion.webp",
    ),
    (
        "buildings/Edificio J/360/EdifJ_PUERTA.webp",
        "buildings/Edificio J/360/EdifJ_Puerta.webp",
    ),
    (
        "buildings/Edificio L/360/EdifL_ABAJOPAPELERIA.webp",
        "buildings/Edificio L/360/EdifL_ABAJO_Papeleria.webp",
    ),
    (
        "buildings/Edificio L/360/EdifL_ABAJOPUERTA.webp",
        "buildings/Edificio L/360/EdifL_ABAJO_Puerta.webp",
    ),
    (
        "buildings/Edificio L/360/EdifL_ARIBAESCALERAS.webp",
        "buildings/Edificio L/360/EdifL_ARRIBA_Escaleras.webp",
    ),
    (
        "buildings/Edificio M/360/EdifM_LABS.webp",
        "buildings/Edificio M/360/EdifM_Laboratorios.webp",
    ),
    (
        "buildings/Edificio M/360/EdifM_PASILLO.webp",
        "buildings/Edificio M/360/EdifM_Pasillo.webp",
    ),
    (
        "buildings/Edificio M/360/EdifM_SALIDA.webp",
        "buildings/Edificio M/360/EdifM_Salida.webp",
    ),
    (
        "buildings/Edificio N/360/Nodo_ARRIBA.webp",
        "buildings/Edificio N/360/Nodo_ARRIBA_Salon.webp",
    ),
    (
        "buildings/Edificio N/360/Nodo_ENTRADA_ATRAS.webp",
        "buildings/Edificio N/360/Nodo_Entrada_Atras.webp",
    ),
    (
        "buildings/Edificio N/360/Nodo_ENTRADA_FRENTE.webp",
        "buildings/Edificio N/360/Nodo_Entrada_Frente.webp",
    ),
    (
        "buildings/Edificio Q/360/EdifQ_PASILLO.webp",
        "buildings/Edificio Q/360/EdifQ_Pasillo.webp",
    ),
    (
        "buildings/Edificio U/360/EdifU_ABAJO_DER.webp",
        "buildings/Edificio U/360/EdifU_ABAJO_Der.webp",
    ),
    (
        "buildings/Edificio U/360/EdifU_ABAJO_IZQ.webp",
        "buildings/Edificio U/360/EdifU_ABAJO_Izq.webp",
    ),
    (
        "buildings/Edificio U/360/EdifU_ARRIBA.webp",
        "buildings/Edificio U/360/EdifU_ARRIBA_Principal.webp",
    ),
    (
        "buildings/Edificio U/360/EdifU_ARRIBA_DER.webp",
        "buildings/Edificio U/360/EdifU_ARRIBA_Der.webp",
    ),
    (
        "buildings/Edificio U/360/EdifU_ARRIBA_IZQ.webp",
        "buildings/Edificio U/360/EdifU_ARRIBA_Izq.webp",
    ),
    (
        "buildings/Edificio U/360/EdifU_ENTRADA_ATRAS.webp",
        "buildings/Edificio U/360/EdifU_Entrada_Atras.webp",
    ),
    (
        "buildings/Edificio U/360/EdifU_ENTRADA_FRENTE.webp",
        "buildings/Edificio U/360/EdifU_Entrada_Frente.webp",
    ),
    (
        "buildings/Edificio U/360/EdifU_TRAILAS1.webp",
        "buildings/Edificio U/360/EdifU_Trailas_1.webp",
    ),
    (
        "buildings/Edificio U/360/EdifU_TRAILAS2.webp",
        "buildings/Edificio U/360/EdifU_Trailas_2.webp",
    ),
    (
        "buildings/Edificio V/360/EdifV_PASILLO.webp",
        "buildings/Edificio V/360/EdifV_Pasillo.webp",
    ),
    (
        "buildings/Edificio V/360/EdifV_PUERTA.webp",
        "buildings/Edificio V/360/EdifV_Puerta.webp",
    ),
    (
        "buildings/Edificio X/360/EdifX_PASILLO.webp",
        "buildings/Edificio X/360/EdifX_Pasillo.webp",
    ),
    (
        "buildings/Edificio X/360/EdifX_PUERTA.webp",
        "buildings/Edificio X/360/EdifX_Puerta.webp",
    ),
    (
        "buildings/Cafeteria/360/Cafetería_ENTRADA.webp",
        "buildings/Cafeteria/360/Cafe_Entrada.webp",
    ),
    (
        "buildings/Cafeteria/360/Cafetería_PASILLO.webp",
        "buildings/Cafeteria/360/Cafe_Pasillo.webp",
    ),
]

POI_360_RENAMES: list[tuple[str, str]] = [
    (
        "buildings/Puntos de interes/360/BASKETG.webp",
        "buildings/Puntos de interes/360/Basketball.webp",
    ),
    (
        "buildings/Puntos de interes/360/FUTBOLG.webp",
        "buildings/Puntos de interes/360/Futbol.webp",
    ),
    (
        "buildings/Puntos de interes/360/PARKINGL.webp",
        "buildings/Puntos de interes/360/Parking.webp",
    ),
]


def _esc(s: str) -> str:
    return s.replace("'", "''")


def upgrade() -> None:
    for old, new in BUILDING_360_RENAMES:
        op.execute(
            f"UPDATE building_360 SET url = '{_esc(new)}' WHERE url = '{_esc(old)}'"
        )
    for old, new in POI_360_RENAMES:
        op.execute(
            f"UPDATE point_of_interest_360 SET url = '{_esc(new)}' WHERE url = '{_esc(old)}'"
        )


def downgrade() -> None:
    for old, new in BUILDING_360_RENAMES:
        op.execute(
            f"UPDATE building_360 SET url = '{_esc(old)}' WHERE url = '{_esc(new)}'"
        )
    for old, new in POI_360_RENAMES:
        op.execute(
            f"UPDATE point_of_interest_360 SET url = '{_esc(old)}' WHERE url = '{_esc(new)}'"
        )
