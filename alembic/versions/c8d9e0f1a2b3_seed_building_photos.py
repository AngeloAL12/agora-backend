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
        "buildings/Edificio A/360/EdifA_ENTRADA.jpg",
    ],
    "B": [
        "buildings/Edificio B/360/EdifB_ARRIBA.jpg",
        "buildings/Edificio B/360/EdifB_BIBLIOTECA.jpg",
        "buildings/Edificio B/360/EdifB_BIBLIOTECA_DER.jpg",
        "buildings/Edificio B/360/EdifB_BIBLIOTECA_IZQ.jpg",
        "buildings/Edificio B/360/EdifB_ENTRADA.jpg",
    ],
    "D": [
        "buildings/Edificio D/360/EdifD_ABAJOESCALERAS.jpg",
        "buildings/Edificio D/360/EdifD_ABAJOPUERTA.jpg",
        "buildings/Edificio D/360/EdifD_ARRIBAESCALERAS.jpg",
    ],
    "E": [
        "buildings/Edificio E/360/EdifE_PASILLOS.jpg",
    ],
    "F": [
        "buildings/Edificio F/360/EdifF_ABAJOESCALERAS.jpg",
        "buildings/Edificio F/360/EdifF_ABAJOPUERTA.jpg",
        "buildings/Edificio F/360/EdifF_ARRIBAESCALERAS.jpg",
    ],
    "G": [
        "buildings/Edificio G/360/EdifG_ABAJOLABS.jpg",
        "buildings/Edificio G/360/EdifG_ABAJOPUERTA.jpg",
        "buildings/Edificio G/360/EdifG_ARRIBAESCALERAS.jpg",
        "buildings/Edificio G/360/EdifG_ARRIBAPUERTA.jpg",
    ],
    "J": [
        "buildings/Edificio J/360/EdifJ_BAÑOS.jpg",
        "buildings/Edificio J/360/EdifJ_DIRECCION.jpg",
        "buildings/Edificio J/360/EdifJ_PUERTA.jpg",
    ],
    "L": [
        "buildings/Edificio L/360/EdifL_ABAJOPAPELERIA.jpg",
        "buildings/Edificio L/360/EdifL_ABAJOPUERTA.jpg",
        "buildings/Edificio L/360/EdifL_ARIBAESCALERAS.jpg",
    ],
    "M": [
        "buildings/Edificio M/360/EdifM_LABS.jpg",
        "buildings/Edificio M/360/EdifM_PASILLO.jpg",
        "buildings/Edificio M/360/EdifM_SALIDA.jpg",
    ],
    "Nodo": [
        "buildings/Edificio N/360/Nodo_ARRIBA.jpg",
        "buildings/Edificio N/360/Nodo_ENTRADA_ATRAS.jpg",
        "buildings/Edificio N/360/Nodo_ENTRADA_FRENTE.jpg",
    ],
    "Q": [
        "buildings/Edificio Q/360/EdifQ_PASILLO.jpg",
    ],
    "U": [
        "buildings/Edificio U/360/EdifU_ABAJO_DER.jpg",
        "buildings/Edificio U/360/EdifU_ABAJO_IZQ.jpg",
        "buildings/Edificio U/360/EdifU_ARRIBA.jpg",
        "buildings/Edificio U/360/EdifU_ARRIBA_DER.jpg",
        "buildings/Edificio U/360/EdifU_ARRIBA_IZQ.jpg",
        "buildings/Edificio U/360/EdifU_ENTRADA_ATRAS.jpg",
        "buildings/Edificio U/360/EdifU_ENTRADA_FRENTE.jpg",
        "buildings/Edificio U/360/EdifU_TRAILAS1.jpg",
        "buildings/Edificio U/360/EdifU_TRAILAS2.jpg",
    ],
    "V": [
        "buildings/Edificio V/360/EdifV_PASILLO.jpg",
        "buildings/Edificio V/360/EdifV_PUERTA.jpg",
    ],
    "X": [
        "buildings/Edificio X/360/EdifX_PASILLO.jpg",
        "buildings/Edificio X/360/EdifX_PUERTA.jpg",
    ],
    "Cafeteria": [
        "buildings/Cafeteria/360/Cafetería_ENTRADA.jpg",
        "buildings/Cafeteria/360/Cafetería_PASILLO.jpg",
    ],
}

# POI names must match the `name` column in `point_of_interest`.
# "Cancha Fútbol" and "Estacionamiento" are inserted in this migration.
POI_360: dict[str, list[str]] = {
    "Cancha Basketball": [
        "buildings/Puntos de interes/360/BASKETG.jpg",
    ],
    "Cancha Fútbol": [
        "buildings/Puntos de interes/360/FUTBOLG.jpg",
    ],
    "Estacionamiento": [
        "buildings/Puntos de interes/360/PARKINGL.jpg",
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
