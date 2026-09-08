"""seed building photos from R2 bucket

Revision ID: c8d9e0f1a2b3
Revises: f2adf8fdec5d
Create Date: 2026-05-17 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "c8d9e0f1a2b3"
down_revision: Union[str, Sequence[str], None] = "f2adf8fdec5d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# ---------------------------------------------------------------------------
# Data – R2 object keys as stored in the DB (the router generates presigned URLs
# from these at request time via storage_service.get_presigned_url).
# Building names match the `name` column in the `building` table.
# ---------------------------------------------------------------------------

BUILDING_IMAGES: dict[str, list[str]] = {
    "A": [
        "buildings/Edificio A/normal/EdifA_FachadaFrontal01.JPEG",
        "buildings/Edificio A/normal/EdifA_FachadaFrontal02.JPEG",
        "buildings/Edificio A/normal/EdifA_Lobby.JPEG",
        "buildings/Edificio A/normal/EdifA_RRHH.JPEG",
    ],
    "B": [
        "buildings/Edificio B/normal/0.jpg",
        "buildings/Edificio B/normal/EdifB_Casilleros.JPEG",
        "buildings/Edificio B/normal/EdifB_FachadaFrontal.jpeg",
        "buildings/Edificio B/normal/EdifB_Lab.jpeg",
        "buildings/Edificio B/normal/EdifB_Mesas.jpeg",
    ],
    "C": [
        "buildings/Edificio C/normal/EdifC_Fachada.JPEG",
    ],
    "D": [
        "buildings/Edificio D/normal/EdifD_FachadaFrontal01.JPEG",
        "buildings/Edificio D/normal/EdifD_FachadaFrontal02.JPEG",
        "buildings/Edificio D/normal/EdifD_PlantaAlta.JPEG",
        "buildings/Edificio D/normal/EdifD_PlantaBaja.JPEG",
        "buildings/Edificio D/normal/EdifD_SalaMaestros.JPEG",
    ],
    "E": [
        "buildings/Edificio E/normal/EdifE_Departamento.JPEG",
        "buildings/Edificio E/normal/EdifE_FachadaFrontal.JPEG",
        "buildings/Edificio E/normal/EdifE_PasilloDer.JPEG",
        "buildings/Edificio E/normal/EdifE_PasilloIzq.JPEG",
    ],
    "F": [
        "buildings/Edificio F/normal/EdifF_FachadaFrontal01.JPEG",
        "buildings/Edificio F/normal/EdifF_FachadaFrontal02.JPEG",
        "buildings/Edificio F/normal/EdifF_Mesas.JPEG",
        "buildings/Edificio F/normal/EdifF_PlantaBajaIzq.JPEG",
        "buildings/Edificio F/normal/EdifF_SalaMaestrosL.JPEG",
        "buildings/Edificio F/normal/EdifF_SalaMaestrosR.JPEG",
        "buildings/Edificio F/normal/EdifF_Secretaria.JPEG",
    ],
    "G": [
        "buildings/Edificio G/normal/EdifG_FachadaFrontal.JPEG",
        "buildings/Edificio G/normal/EdifG_FachadaTrasera01.JPEG",
        "buildings/Edificio G/normal/EdifG_FachadaTrasera02.JPEG",
        "buildings/Edificio G/normal/EdifG_PlantaAlta.JPEG",
        "buildings/Edificio G/normal/EdifG_PlantaBaja.JPEG",
    ],
    "H": [
        "buildings/Edificio H/normal/EdifH_Entrada.JPEG",
        "buildings/Edificio H/normal/EdifH_Fachada.JPEG",
    ],
    "I": [
        "buildings/Edificio I/normal/EdifI_Fachada.JPEG",
        "buildings/Edificio I/normal/EdifI_Laboratorio.JPEG",
    ],
    "J": [
        "buildings/Edificio J/normal/EdifJ_Direccion.JPEG",
        "buildings/Edificio J/normal/EdifJ_FachadaFrontal.JPEG",
        "buildings/Edificio J/normal/EdifJ_Libreria.JPEG",
        "buildings/Edificio J/normal/EdifJ_Pasillo01.JPEG",
        "buildings/Edificio J/normal/EdifJ_Pasillo02.JPEG",
    ],
    "L": [
        "buildings/Edificio L/normal/EdifL_FachadaFrontal01.JPEG",
        "buildings/Edificio L/normal/EdifL_FachadaFrontal02.JPEG",
        "buildings/Edificio L/normal/EdifL_Papeleria.JPEG",
        "buildings/Edificio L/normal/EdifL_Pintura.JPEG",
        "buildings/Edificio L/normal/EdifL_PlantaAlta.JPEG",
        "buildings/Edificio L/normal/EdifL_SalaMaestros01.JPEG",
        "buildings/Edificio L/normal/EdifL_SalaMaestros02.JPEG",
        "buildings/Edificio L/normal/EdifL_SalaMaestros03.JPEG",
    ],
    "M": [
        "buildings/Edificio M/normal/EdifM_FachadaFrontal01.JPEG",
        "buildings/Edificio M/normal/EdifM_FachadaFrontal02.JPEG",
        "buildings/Edificio M/normal/EdifM_Pasillo.JPEG",
        "buildings/Edificio M/normal/EdifM_PasilloIzq.JPEG",
    ],
    "U": [
        "buildings/Edificio U/normal/EdifU_CienciasBasicas.JPEG",
        "buildings/Edificio U/normal/EdifU_Fachada.JPEG",
        "buildings/Edificio U/normal/EdifU_Mesas.JPEG",
        "buildings/Edificio U/normal/EdifU_Palmera.JPEG",
        "buildings/Edificio U/normal/EdifU_PlantaAlta01.JPEG",
        "buildings/Edificio U/normal/EdifU_PlantaAlta02.JPEG",
        "buildings/Edificio U/normal/EdifU_PlantaBaja.JPEG",
        "buildings/Edificio U/normal/EdifU_Rotonda.JPEG",
        "buildings/Edificio U/normal/EdifU_Trailas.JPEG",
    ],
    "V": [
        "buildings/Edificio V/normal/EdifV_Coordinacion.JPEG",
        "buildings/Edificio V/normal/EdifV_DesAcademico.JPEG",
        "buildings/Edificio V/normal/EdifV_Escolares01.JPEG",
        "buildings/Edificio V/normal/EdifV_Escolares02.JPEG",
        "buildings/Edificio V/normal/EdifV_FachadaFrontal.JPEG",
        "buildings/Edificio V/normal/EdifV_FachadaTrasera01.JPEG",
        "buildings/Edificio V/normal/EdifV_LabLogistica.JPEG",
        "buildings/Edificio V/normal/EdifV_Mascaras01.JPEG",
        "buildings/Edificio V/normal/EdifV_Mascaras02.JPEG",
        "buildings/Edificio V/normal/EdifV_Quimica.JPEG",
    ],
    "X": [
        "buildings/Edificio X/normal/EdifX_FachadaFrontal01.JPEG",
        "buildings/Edificio X/normal/EdifX_FachadaFrontal02.JPEG",
        "buildings/Edificio X/normal/EdifX_Pasillo.JPEG",
        "buildings/Edificio X/normal/EdifX_SalaMaestros.JPEG",
        "buildings/Edificio X/normal/EdifX_Salones.JPEG",
    ],
}

BUILDING_360: dict[str, list[str]] = {
    "A": [
        "buildings/Edificio A/360/EdifA_Entrada.webp",
    ],
    "B": [
        "buildings/Edificio B/360/EdifB_ARRIBA_Escaleras.webp",
        "buildings/Edificio B/360/EdifB_Biblioteca.webp",
        "buildings/Edificio B/360/EdifB_Biblioteca_Der.webp",
        "buildings/Edificio B/360/EdifB_Biblioteca_Izq.webp",
        "buildings/Edificio B/360/EdifB_Entrada.webp",
    ],
    "D": [
        "buildings/Edificio D/360/EdifD_ABAJO_Escaleras.webp",
        "buildings/Edificio D/360/EdifD_ABAJO_Puerta.webp",
        "buildings/Edificio D/360/EdifD_ARRIBA_Escaleras.webp",
    ],
    "E": [
        "buildings/Edificio E/360/EdifE_Pasillo.webp",
    ],
    "F": [
        "buildings/Edificio F/360/EdifF_ABAJO_Escaleras.webp",
        "buildings/Edificio F/360/EdifF_ABAJO_Puerta.webp",
        "buildings/Edificio F/360/EdifF_ARRIBA_Escaleras.webp",
    ],
    "G": [
        "buildings/Edificio G/360/EdifG_ABAJO_Laboratorios.webp",
        "buildings/Edificio G/360/EdifG_ABAJO_Puerta.webp",
        "buildings/Edificio G/360/EdifG_ARRIBA_Escaleras.webp",
        "buildings/Edificio G/360/EdifG_ARRIBA_Puerta.webp",
    ],
    "J": [
        "buildings/Edificio J/360/EdifJ_Banos.webp",
        "buildings/Edificio J/360/EdifJ_Direccion.webp",
        "buildings/Edificio J/360/EdifJ_Puerta.webp",
    ],
    "L": [
        "buildings/Edificio L/360/EdifL_ABAJO_Papeleria.webp",
        "buildings/Edificio L/360/EdifL_ABAJO_Puerta.webp",
        "buildings/Edificio L/360/EdifL_ARRIBA_Escaleras.webp",
    ],
    "M": [
        "buildings/Edificio M/360/EdifM_Laboratorios.webp",
        "buildings/Edificio M/360/EdifM_Pasillo.webp",
        "buildings/Edificio M/360/EdifM_Salida.webp",
    ],
    "Nodo": [
        "buildings/Edificio N/360/Nodo_ARRIBA_Salon.webp",
        "buildings/Edificio N/360/Nodo_Entrada_Atras.webp",
        "buildings/Edificio N/360/Nodo_Entrada_Frente.webp",
    ],
    "Q": [
        "buildings/Edificio Q/360/EdifQ_Pasillo.webp",
    ],
    "U": [
        "buildings/Edificio U/360/EdifU_ABAJO_Der.webp",
        "buildings/Edificio U/360/EdifU_ABAJO_Izq.webp",
        "buildings/Edificio U/360/EdifU_ARRIBA_Principal.webp",
        "buildings/Edificio U/360/EdifU_ARRIBA_Der.webp",
        "buildings/Edificio U/360/EdifU_ARRIBA_Izq.webp",
        "buildings/Edificio U/360/EdifU_Entrada_Atras.webp",
        "buildings/Edificio U/360/EdifU_Entrada_Frente.webp",
        "buildings/Edificio U/360/EdifU_Trailas_1.webp",
        "buildings/Edificio U/360/EdifU_Trailas_2.webp",
    ],
    "V": [
        "buildings/Edificio V/360/EdifV_Pasillo.webp",
        "buildings/Edificio V/360/EdifV_Puerta.webp",
    ],
    "X": [
        "buildings/Edificio X/360/EdifX_Pasillo.webp",
        "buildings/Edificio X/360/EdifX_Puerta.webp",
    ],
    "Cafeteria": [
        "buildings/Cafeteria/360/Cafe_Entrada.webp",
        "buildings/Cafeteria/360/Cafe_Pasillo.webp",
    ],
}

# POI names must match the `name` column in `point_of_interest`.
# "Cancha Fútbol" and "Estacionamiento" are inserted in this migration.
POI_360: dict[str, list[str]] = {
    "Cancha Basketball": [
        "buildings/Puntos de interes/360/Basketball.webp",
    ],
    "Cancha Fútbol": [
        "buildings/Puntos de interes/360/Futbol.webp",
    ],
    "Estacionamiento": [
        "buildings/Puntos de interes/360/Parking.webp",
    ],
}


def _esc(s: str) -> str:
    return s.replace("'", "''")


def upgrade() -> None:
    # New building not present in original seed
    op.execute("INSERT INTO building (name, created_at) VALUES ('Cafeteria', NOW())")

    # New points of interest
    op.execute(
        "INSERT INTO point_of_interest (name, created_at) VALUES "
        "('Cancha Fútbol', NOW()), ('Estacionamiento', NOW())"
    )

    # Normal photos for buildings
    for building_name, urls in BUILDING_IMAGES.items():
        vals = ", ".join(
            f"((SELECT id FROM building WHERE name = '{_esc(building_name)}'), '{_esc(url)}', 0, NOW())"
            for url in urls
        )
        op.execute(
            f"INSERT INTO building_image (id_building, url, floor, created_at) VALUES {vals}"
        )

    # 360 photos for buildings
    for building_name, urls in BUILDING_360.items():
        vals = ", ".join(
            f"((SELECT id FROM building WHERE name = '{_esc(building_name)}'), '{_esc(url)}', 0, NOW())"
            for url in urls
        )
        op.execute(
            f"INSERT INTO building_360 (id_building, url, floor, created_at) VALUES {vals}"
        )

    # 360 photos for points of interest
    for poi_name, urls in POI_360.items():
        vals = ", ".join(
            f"((SELECT id FROM point_of_interest WHERE name = '{_esc(poi_name)}'), '{_esc(url)}', NOW())"
            for url in urls
        )
        op.execute(
            f"INSERT INTO point_of_interest_360 (id_point, url, created_at) VALUES {vals}"
        )


def downgrade() -> None:
    op.execute("DELETE FROM building_image WHERE url LIKE 'buildings/%'")
    op.execute("DELETE FROM building_360 WHERE url LIKE 'buildings/%'")
    op.execute(
        "DELETE FROM point_of_interest_360 WHERE url LIKE 'buildings/Puntos de interes/%'"
    )
    op.execute("DELETE FROM building WHERE name = 'Cafeteria'")
    op.execute(
        "DELETE FROM point_of_interest WHERE name IN ('Cancha Fútbol', 'Estacionamiento')"
    )
