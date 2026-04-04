from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.config import settings
from app.core.database import get_db
from app.core.security import get_current_user
from app.models.complaint.complaint import Complaint, ComplaintCategory, ComplaintStatus
from app.models.complaint.complaint_image import ComplaintImage
from app.models.complaint.complaint_status_history import ComplaintStatusHistory
from app.schemas.auth.auth import CurrentUser
from app.schemas.complaint import (
    ComplaintListItemResponse,
    ComplaintResponse,
)
from app.services.storage_service import storage_service

router = APIRouter(prefix="/complaints", tags=["complaints"])


async def _serialize_complaint(complaint: Complaint) -> ComplaintResponse:
    image_responses = []
    for image in complaint.images:
        image_responses.append(
            {
                "id": image.id,
                "url": await storage_service.get_presigned_url(
                    settings.R2_BUCKET_PRIVATE,
                    image.url,
                ),
                "created_at": image.created_at,
            }
        )

    return ComplaintResponse(
        id=complaint.id,
        title=complaint.title,
        description=complaint.description,
        category=complaint.category,
        status=complaint.status,
        has_appealed=complaint.has_appealed,
        created_at=complaint.created_at,
        images=image_responses,
    )


@router.post(
    "",
    response_model=ComplaintResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_complaint(
    title: str = Form(...),
    description: str = Form(...),
    category: ComplaintCategory = Form(...),
    images: list[UploadFile] | None = File(default=None),
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Crea una nueva queja con datos multipart/form-data.
    El campo images es opcional (0..3 archivos).
    """
    if images and len(images) > 3:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Máximo 3 imágenes permitidas",
        )

    title_clean = title.strip()
    description_clean = description.strip()

    if not title_clean:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El título no puede estar vacío",
        )
    if not description_clean:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="La descripción no puede estar vacía",
        )

    complaint = Complaint(
        id_user=current_user.id,
        title=title_clean,
        description=description_clean,
        category=category,
        status=ComplaintStatus.PENDING,
    )
    db.add(complaint)
    db.flush()

    if images:
        for image in images:
            object_key = await storage_service.upload_file(
                image,
                settings.R2_BUCKET_PRIVATE,
                f"complaints/{complaint.id}/images",
            )
            db.add(ComplaintImage(id_complaint=complaint.id, url=object_key))

    db.add(
        ComplaintStatusHistory(
            id_complaint=complaint.id,
            id_user=current_user.id,
            old_status=None,
            new_status=ComplaintStatus.PENDING,
        )
    )
    db.commit()

    complaint = db.execute(
        select(Complaint)
        .options(selectinload(Complaint.images))
        .where(Complaint.id == complaint.id)
    ).scalar_one()

    return await _serialize_complaint(complaint)


@router.get("/me", response_model=list[ComplaintListItemResponse])
async def get_my_complaints(
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    complaints = (
        db.execute(
            select(Complaint)
            .where(Complaint.id_user == current_user.id)
            .order_by(Complaint.created_at.desc(), Complaint.id.desc())
        )
        .scalars()
        .all()
    )

    return [
        ComplaintListItemResponse(
            id=complaint.id,
            title=complaint.title,
            status=complaint.status,
            created_at=complaint.created_at,
        )
        for complaint in complaints
    ]


@router.get("/{complaint_id}", response_model=ComplaintResponse)
async def get_my_complaint_detail(
    complaint_id: int,
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    complaint = db.execute(
        select(Complaint)
        .options(selectinload(Complaint.images))
        .where(Complaint.id == complaint_id)
    ).scalar_one_or_none()

    if complaint is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Queja no encontrada",
        )

    if complaint.id_user != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tienes acceso a esta queja",
        )

    return await _serialize_complaint(complaint)
