"""rename building 360 photos to descriptive webp names

Revision ID: d1e2f3a4b5c6
Revises: c8d9e0f1a2b3
Create Date: 2026-05-31 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "d1e2f3a4b5c6"
down_revision: Union[str, Sequence[str], None] = "c8d9e0f1a2b3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


BUILDING_360_RENAMES: list[tuple[str, str]] = [
    (
        "buildings/Edificio A/360/EdifA_ENTRADA.jpg",
        "buildings/Edificio A/360/EdifA_Entrada.webp",
    ),
    (
        "buildings/Edificio B/360/EdifB_ARRIBA.jpg",
        "buildings/Edificio B/360/EdifB_ARRIBA_Escaleras.webp",
    ),
    (
        "buildings/Edificio B/360/EdifB_BIBLIOTECA.jpg",
        "buildings/Edificio B/360/EdifB_Biblioteca.webp",
    ),
    (
        "buildings/Edificio B/360/EdifB_BIBLIOTECA_DER.jpg",
        "buildings/Edificio B/360/EdifB_Biblioteca_Der.webp",
    ),
    (
        "buildings/Edificio B/360/EdifB_BIBLIOTECA_IZQ.jpg",
        "buildings/Edificio B/360/EdifB_Biblioteca_Izq.webp",
    ),
    (
        "buildings/Edificio B/360/EdifB_ENTRADA.jpg",
        "buildings/Edificio B/360/EdifB_Entrada.webp",
    ),
    (
        "buildings/Edificio D/360/EdifD_ABAJOESCALERAS.jpg",
        "buildings/Edificio D/360/EdifD_ABAJO_Escaleras.webp",
    ),
    (
        "buildings/Edificio D/360/EdifD_ABAJOPUERTA.jpg",
        "buildings/Edificio D/360/EdifD_ABAJO_Puerta.webp",
    ),
    (
        "buildings/Edificio D/360/EdifD_ARRIBAESCALERAS.jpg",
        "buildings/Edificio D/360/EdifD_ARRIBA_Escaleras.webp",
    ),
    (
        "buildings/Edificio E/360/EdifE_PASILLOS.jpg",
        "buildings/Edificio E/360/EdifE_Pasillo.webp",
    ),
    (
        "buildings/Edificio F/360/EdifF_ABAJOESCALERAS.jpg",
        "buildings/Edificio F/360/EdifF_ABAJO_Escaleras.webp",
    ),
    (
        "buildings/Edificio F/360/EdifF_ABAJOPUERTA.jpg",
        "buildings/Edificio F/360/EdifF_ABAJO_Puerta.webp",
    ),
    (
        "buildings/Edificio F/360/EdifF_ARRIBAESCALERAS.jpg",
        "buildings/Edificio F/360/EdifF_ARRIBA_Escaleras.webp",
    ),
    (
        "buildings/Edificio G/360/EdifG_ABAJOLABS.jpg",
        "buildings/Edificio G/360/EdifG_ABAJO_Laboratorios.webp",
    ),
    (
        "buildings/Edificio G/360/EdifG_ABAJOPUERTA.jpg",
        "buildings/Edificio G/360/EdifG_ABAJO_Puerta.webp",
    ),
    (
        "buildings/Edificio G/360/EdifG_ARRIBAESCALERAS.jpg",
        "buildings/Edificio G/360/EdifG_ARRIBA_Escaleras.webp",
    ),
    (
        "buildings/Edificio G/360/EdifG_ARRIBAPUERTA.jpg",
        "buildings/Edificio G/360/EdifG_ARRIBA_Puerta.webp",
    ),
    (
        "buildings/Edificio J/360/EdifJ_BAÑOS.jpg",
        "buildings/Edificio J/360/EdifJ_Banos.webp",
    ),
    (
        "buildings/Edificio J/360/EdifJ_DIRECCION.jpg",
        "buildings/Edificio J/360/EdifJ_Direccion.webp",
    ),
    (
        "buildings/Edificio J/360/EdifJ_PUERTA.jpg",
        "buildings/Edificio J/360/EdifJ_Puerta.webp",
    ),
    (
        "buildings/Edificio L/360/EdifL_ABAJOPAPELERIA.jpg",
        "buildings/Edificio L/360/EdifL_ABAJO_Papeleria.webp",
    ),
    (
        "buildings/Edificio L/360/EdifL_ABAJOPUERTA.jpg",
        "buildings/Edificio L/360/EdifL_ABAJO_Puerta.webp",
    ),
    (
        "buildings/Edificio L/360/EdifL_ARIBAESCALERAS.jpg",
        "buildings/Edificio L/360/EdifL_ARRIBA_Escaleras.webp",
    ),
    (
        "buildings/Edificio M/360/EdifM_LABS.jpg",
        "buildings/Edificio M/360/EdifM_Laboratorios.webp",
    ),
    (
        "buildings/Edificio M/360/EdifM_PASILLO.jpg",
        "buildings/Edificio M/360/EdifM_Pasillo.webp",
    ),
    (
        "buildings/Edificio M/360/EdifM_SALIDA.jpg",
        "buildings/Edificio M/360/EdifM_Salida.webp",
    ),
    (
        "buildings/Edificio N/360/Nodo_ARRIBA.jpg",
        "buildings/Edificio N/360/Nodo_ARRIBA_Salon.webp",
    ),
    (
        "buildings/Edificio N/360/Nodo_ENTRADA_ATRAS.jpg",
        "buildings/Edificio N/360/Nodo_Entrada_Atras.webp",
    ),
    (
        "buildings/Edificio N/360/Nodo_ENTRADA_FRENTE.jpg",
        "buildings/Edificio N/360/Nodo_Entrada_Frente.webp",
    ),
    (
        "buildings/Edificio Q/360/EdifQ_PASILLO.jpg",
        "buildings/Edificio Q/360/EdifQ_Pasillo.webp",
    ),
    (
        "buildings/Edificio U/360/EdifU_ABAJO_DER.jpg",
        "buildings/Edificio U/360/EdifU_ABAJO_Der.webp",
    ),
    (
        "buildings/Edificio U/360/EdifU_ABAJO_IZQ.jpg",
        "buildings/Edificio U/360/EdifU_ABAJO_Izq.webp",
    ),
    (
        "buildings/Edificio U/360/EdifU_ARRIBA.jpg",
        "buildings/Edificio U/360/EdifU_ARRIBA_Principal.webp",
    ),
    (
        "buildings/Edificio U/360/EdifU_ARRIBA_DER.jpg",
        "buildings/Edificio U/360/EdifU_ARRIBA_Der.webp",
    ),
    (
        "buildings/Edificio U/360/EdifU_ARRIBA_IZQ.jpg",
        "buildings/Edificio U/360/EdifU_ARRIBA_Izq.webp",
    ),
    (
        "buildings/Edificio U/360/EdifU_ENTRADA_ATRAS.jpg",
        "buildings/Edificio U/360/EdifU_Entrada_Atras.webp",
    ),
    (
        "buildings/Edificio U/360/EdifU_ENTRADA_FRENTE.jpg",
        "buildings/Edificio U/360/EdifU_Entrada_Frente.webp",
    ),
    (
        "buildings/Edificio U/360/EdifU_TRAILAS1.jpg",
        "buildings/Edificio U/360/EdifU_Trailas_1.webp",
    ),
    (
        "buildings/Edificio U/360/EdifU_TRAILAS2.jpg",
        "buildings/Edificio U/360/EdifU_Trailas_2.webp",
    ),
    (
        "buildings/Edificio V/360/EdifV_PASILLO.jpg",
        "buildings/Edificio V/360/EdifV_Pasillo.webp",
    ),
    (
        "buildings/Edificio V/360/EdifV_PUERTA.jpg",
        "buildings/Edificio V/360/EdifV_Puerta.webp",
    ),
    (
        "buildings/Edificio X/360/EdifX_PASILLO.jpg",
        "buildings/Edificio X/360/EdifX_Pasillo.webp",
    ),
    (
        "buildings/Edificio X/360/EdifX_PUERTA.jpg",
        "buildings/Edificio X/360/EdifX_Puerta.webp",
    ),
    (
        "buildings/Cafeteria/360/Cafetería_ENTRADA.jpg",
        "buildings/Cafeteria/360/Cafe_Entrada.webp",
    ),
    (
        "buildings/Cafeteria/360/Cafetería_PASILLO.jpg",
        "buildings/Cafeteria/360/Cafe_Pasillo.webp",
    ),
]

POI_360_RENAMES: list[tuple[str, str]] = [
    (
        "buildings/Puntos de interes/360/BASKETG.jpg",
        "buildings/Puntos de interes/360/Basketball.webp",
    ),
    (
        "buildings/Puntos de interes/360/FUTBOLG.jpg",
        "buildings/Puntos de interes/360/Futbol.webp",
    ),
    (
        "buildings/Puntos de interes/360/PARKINGL.jpg",
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
