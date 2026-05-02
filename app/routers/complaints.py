from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    UploadFile,
    status,
)
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.core.config import settings
from app.core.database import get_db
from app.core.roles import RoleName
from app.core.security import get_current_user
from app.models.complaint.complaint import (
    Complaint,
    ComplaintCategory,
    ComplaintStatus,
    ComplaintType,
)
from app.models.complaint.complaint_evidence import ComplaintEvidence
from app.models.complaint.complaint_image import ComplaintImage
from app.models.complaint.complaint_status_history import ComplaintStatusHistory
from app.models.notification.notification import (
    NotificationCategory,
    NotificationEventType,
)
from app.schemas.auth.auth import CurrentUser
from app.schemas.complaint import (
    ComplaintListItemResponse,
    ComplaintListResponse,
    ComplaintOut,
    ComplaintResponse,
    ComplaintStats,
    ComplaintStatusUpdate,
    ComplaintUpdate,
)
from app.services.storage_service import storage_service

router = APIRouter(prefix="/complaints", tags=["complaints"])


def _notify_complaint_submitted(
    user_id: int, complaint_id: int, complaint_title: str
) -> None:
    from app.core.database import SessionLocal
    from app.services.notification_service import create_notification

    db = SessionLocal()
    try:
        create_notification(
            db,
            id_user=user_id,
            category=NotificationCategory.REPORTS,
            event_type=NotificationEventType.COMPLAINT_SUBMITTED,
            title="Queja enviada",
            body=f'Tu queja "{complaint_title}" fue recibida y está siendo revisada.',
            reference_id=complaint_id,
        )
    finally:
        db.close()


def _notify_complaint_status_changed(
    user_id: int,
    complaint_id: int,
    complaint_title: str,
    new_status: ComplaintStatus,
) -> None:
    from app.core.database import SessionLocal
    from app.services.notification_service import create_notification

    _event_map = {
        ComplaintStatus.IN_PROGRESS: (
            NotificationEventType.COMPLAINT_IN_PROGRESS,
            "Queja en progreso",
            f'Tu queja "{complaint_title}" está siendo atendida.',
        ),
        ComplaintStatus.RESOLVED: (
            NotificationEventType.COMPLAINT_RESOLVED,
            "Queja resuelta",
            f'Tu queja "{complaint_title}" ha sido resuelta.',
        ),
        ComplaintStatus.REJECTED: (
            NotificationEventType.COMPLAINT_REJECTED,
            "Queja rechazada",
            f'Tu queja "{complaint_title}" fue rechazada.',
        ),
    }

    if new_status not in _event_map:
        return

    event_type, title, body = _event_map[new_status]

    db = SessionLocal()
    try:
        create_notification(
            db,
            id_user=user_id,
            category=NotificationCategory.REPORTS,
            event_type=event_type,
            title=title,
            body=body,
            reference_id=complaint_id,
        )
    finally:
        db.close()


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
        type=complaint.type,
        title=complaint.title,
        description=complaint.description,
        category=complaint.category,
        id_building=complaint.id_building,
        classroom=complaint.classroom,
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
    background_tasks: BackgroundTasks,
    title: str = Form(...),
    description: str = Form(...),
    category: ComplaintCategory = Form(...),
    type: ComplaintType = Form(default=ComplaintType.REPORT),
    id_building: int | None = Form(default=None),
    classroom: str | None = Form(default=None),
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
        type=type,
        title=title_clean,
        description=description_clean,
        category=category,
        id_building=id_building,
        classroom=classroom,
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

    background_tasks.add_task(
        _notify_complaint_submitted,
        user_id=current_user.id,
        complaint_id=complaint.id,
        complaint_title=complaint.title,
    )

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
            type=complaint.type,
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


async def require_staff_role(
    current_user: CurrentUser = Depends(get_current_user),
) -> CurrentUser:
    if current_user.role not in {RoleName.STAFF, RoleName.ADMIN}:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acceso denegado. Se requieren permisos de Staff o Administrador.",
        )
    return current_user


@router.get("", response_model=ComplaintListResponse)
async def get_all_complaints(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_staff_role),
):
    stats_rows = db.execute(
        select(Complaint.status, func.count().label("cnt")).group_by(Complaint.status)
    ).all()

    stats_map: dict[str, int] = {row.status.value: row.cnt for row in stats_rows}
    total = sum(stats_map.values())

    rows = (
        db.execute(
            select(Complaint)
            .options(selectinload(Complaint.images), selectinload(Complaint.evidences))
            .order_by(Complaint.created_at.desc(), Complaint.id.desc())
            .limit(limit)
            .offset(offset)
        )
        .scalars()
        .all()
    )

    complaint_items = [ComplaintOut.model_validate(row) for row in rows]

    return ComplaintListResponse(
        items=complaint_items,
        total=total,
        limit=limit,
        offset=offset,
        stats=ComplaintStats(
            total=total,
            pending=stats_map.get(ComplaintStatus.PENDING.value, 0),
            in_progress=stats_map.get(ComplaintStatus.IN_PROGRESS.value, 0),
            resolved=stats_map.get(ComplaintStatus.RESOLVED.value, 0),
        ),
    )


@router.post("/{complaint_id}/evidence")
async def upload_complaint_evidence(
    complaint_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_staff_role),
):
    complaint = db.execute(
        select(Complaint).where(Complaint.id == complaint_id)
    ).scalar_one_or_none()
    if not complaint:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Queja no encontrada",
        )

    bucket_name = settings.R2_BUCKET_PRIVATE
    prefix = f"complaints/{complaint_id}/evidence"

    object_key = await storage_service.upload_file(
        file=file, bucket_name=bucket_name, prefix=prefix
    )

    new_evidence = ComplaintEvidence(
        id_complaint=complaint_id,
        id_user=current_user.id,
        url=object_key,
    )
    db.add(new_evidence)
    db.commit()

    return {
        "message": "Evidencia subida y guardada exitosamente",
        "object_key": object_key,
    }


@router.patch("/{complaint_id}/status")
async def update_complaint_status(
    complaint_id: int,
    status_update: ComplaintStatusUpdate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_staff_role),
):
    complaint = db.execute(
        select(Complaint)
        .options(selectinload(Complaint.evidences))
        .where(Complaint.id == complaint_id)
    ).scalar_one_or_none()
    if not complaint:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Queja no encontrada",
        )

    if status_update.status == ComplaintStatus.RESOLVED:
        if not complaint.evidences:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No se puede resolver una queja sin antes subir una evidencia.",
            )

    old_status = complaint.status
    complaint.status = status_update.status

    db.add(
        ComplaintStatusHistory(
            id_complaint=complaint.id,
            old_status=old_status,
            new_status=status_update.status,
            id_user=current_user.id,
        )
    )
    db.commit()

    background_tasks.add_task(
        _notify_complaint_status_changed,
        user_id=complaint.id_user,
        complaint_id=complaint.id,
        complaint_title=complaint.title,
        new_status=status_update.status,
    )

    return {
        "message": "Estado actualizado exitosamente",
        "new_status": complaint.status,
    }


@router.delete("/{complaint_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_complaint(
    complaint_id: int,
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    complaint = db.execute(
        select(Complaint).where(Complaint.id == complaint_id)
    ).scalar_one_or_none()

    if complaint is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Queja no encontrada",
        )

    is_owner = complaint.id_user == current_user.id
    is_staff_or_admin = current_user.role in {RoleName.STAFF, RoleName.ADMIN}

    if not is_owner and not is_staff_or_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tienes permiso para eliminar esta queja",
        )

    db.delete(complaint)
    db.commit()


@router.patch("/{complaint_id}", response_model=ComplaintResponse)
async def update_complaint(
    complaint_id: int,
    body: ComplaintUpdate,
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

    if complaint.status != ComplaintStatus.PENDING:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Solo se pueden editar quejas en estado PENDING",
        )

    if body.title is not None:
        title_clean = body.title.strip()
        if not title_clean:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="El título no puede estar vacío",
            )
        complaint.title = title_clean
    if body.description is not None:
        description_clean = body.description.strip()
        if not description_clean:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="La descripción no puede estar vacía",
            )
        complaint.description = description_clean

    db.commit()
    db.refresh(complaint)

    return await _serialize_complaint(complaint)
