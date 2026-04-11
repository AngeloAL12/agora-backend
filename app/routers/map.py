from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.config import settings
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
from app.services.storage_service import storage_service

router = APIRouter(prefix="/map", tags=["map"])


@router.get("/buildings/{id}", response_model=BuildingDetailResponse)
async def get_building_detail(
    id: int,
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _ = current_user

    building = db.execute(
        select(Building)
        .options(selectinload(Building.images), selectinload(Building.images_360))
        .where(Building.id == id)
    ).scalar_one_or_none()

    if building is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Edificio no encontrado",
        )

    images: list[BuildingMediaResponse] = []
    for image in building.images:
        images.append(
            BuildingMediaResponse(
                id=image.id,
                url=await storage_service.get_presigned_url(
                    settings.R2_BUCKET_PUBLIC,
                    image.url,
                ),
                floor=image.floor,
            )
        )

    views_360: list[BuildingMediaResponse] = []
    for view in building.images_360:
        views_360.append(
            BuildingMediaResponse(
                id=view.id,
                url=await storage_service.get_presigned_url(
                    settings.R2_BUCKET_PUBLIC,
                    view.url,
                ),
                floor=view.floor,
            )
        )

    return BuildingDetailResponse(
        id=building.id,
        name=building.name,
        description=building.description,
        images=images,
        views_360=views_360,
        created_at=building.created_at,
    )


@router.get("/points/{id}", response_model=PointOfInterestDetailResponse)
async def get_point_of_interest_detail(
    id: int,
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
        .where(PointOfInterest.id == id)
    ).scalar_one_or_none()

    if point is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Punto de interés no encontrado",
        )

    images: list[PointMediaResponse] = []
    for image in point.images:
        images.append(
            PointMediaResponse(
                id=image.id,
                url=await storage_service.get_presigned_url(
                    settings.R2_BUCKET_PUBLIC,
                    image.url,
                ),
            )
        )

    views_360: list[PointMediaResponse] = []
    for view in point.images_360:
        views_360.append(
            PointMediaResponse(
                id=view.id,
                url=await storage_service.get_presigned_url(
                    settings.R2_BUCKET_PUBLIC,
                    view.url,
                ),
            )
        )

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
