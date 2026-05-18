from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.config import settings
from pathlib import PurePosixPath
from app.core.database import get_db
from app.core.security import get_current_user
from app.models.campus import Building, PointOfInterest
from app.schemas.auth.auth import CurrentUser
from app.schemas.map import (
    BuildingDetailResponse,
    BuildingMediaResponse,
    PointMediaResponse,
    PointOfInterestDetailResponse,
)

router = APIRouter(prefix="/map", tags=["map"])


def _public_url(bucket_name: str, object_key: str) -> str:
    if settings.R2_PUBLIC_URL:
        return f"{settings.R2_PUBLIC_URL.rstrip('/')}/{object_key.lstrip('/')}"

    return f"{settings.R2_ENDPOINT.rstrip('/')}/{bucket_name}/{object_key.lstrip('/')}"


def _build_building_response(building: Building) -> BuildingDetailResponse:
    images = [
        BuildingMediaResponse(
            id=image.id,
            url=PurePosixPath(image.url).name,
            floor=image.floor,
        )
        for image in sorted(building.images, key=lambda image: image.floor)
    ]

    views_360 = [
        BuildingMediaResponse(
            id=view.id,
            url=PurePosixPath(view.url).name,
            floor=view.floor,
        )
        for view in sorted(building.images_360, key=lambda view: view.floor)
    ]

    return BuildingDetailResponse(
        id=building.id,
        name=building.name,
        description=building.description,
        images=images,
        views_360=views_360,
        created_at=building.created_at,
    )


@router.get("/buildings", response_model=list[BuildingDetailResponse])
async def get_buildings(
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _ = current_user

    buildings = db.execute(
        select(Building)
        .options(selectinload(Building.images), selectinload(Building.images_360))
        .order_by(Building.id)
    ).scalars().all()

    return [_build_building_response(building) for building in buildings]


@router.get("/buildings/{building_id}", response_model=BuildingDetailResponse)
async def get_building_detail(
    building_id: int,
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _ = current_user

    building = db.execute(
        select(Building)
        .options(selectinload(Building.images), selectinload(Building.images_360))
        .where(Building.id == building_id)
    ).scalar_one_or_none()

    if building is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Edificio no encontrado",
        )

    return _build_building_response(building)


@router.get("/points/{point_id}", response_model=PointOfInterestDetailResponse)
async def get_point_of_interest_detail(
    point_id: int,
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _ = current_user

    point = db.execute(
        select(PointOfInterest)
        .options(
            selectinload(PointOfInterest.images),
            selectinload(PointOfInterest.images_360),
        )
        .where(PointOfInterest.id == point_id)
    ).scalar_one_or_none()

    if point is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Punto de interés no encontrado",
        )

    images: list[PointMediaResponse] = [
        PointMediaResponse(
            id=image.id,
            url=PurePosixPath(image.url).name,
        )
        for image in point.images
    ]

    views_360: list[PointMediaResponse] = [
        PointMediaResponse(
            id=view.id,
            url=PurePosixPath(view.url).name,
        )
        for view in point.images_360
    ]

    return PointOfInterestDetailResponse(
        id=point.id,
        name=point.name,
        description=point.description,
        latitude=point.latitude,
        longitude=point.longitude,
        images=images,
        views_360=views_360,
        created_at=point.created_at,
    )
