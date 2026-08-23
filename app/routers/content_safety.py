from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from app.core.config import settings
from app.core.database import get_db
from app.core.roles import RoleName
from app.core.security import _auth_user_cache_key, get_current_user, require_admin
from app.models.auth.user import User
from app.models.club.club import Club
from app.models.club.club_member import ClubMember
from app.models.club.message import ClubMessage
from app.models.club.post import ClubPost
from app.models.club.post_comment import ClubPostComment
from app.models.moderation.content_report import (
    ContentReport,
    ContentReportStatus,
    ContentTargetType,
    ModerationAction,
)
from app.models.moderation.user_block import UserBlock
from app.schemas.auth.auth import CurrentUser
from app.schemas.content_safety import (
    AdminContentReportResponse,
    AdminModerationUpdate,
    BlockedUserResponse,
    ContentReportCreate,
    ContentReportResponse,
)
from app.services.cache_service import cache_service

router = APIRouter(prefix="/content-safety", tags=["content-safety"])


def _photo_url(object_key: str | None) -> str | None:
    if not object_key:
        return None
    if object_key.startswith(("http://", "https://")):
        return object_key
    base = (
        settings.R2_PUBLIC_URL or f"{settings.R2_ENDPOINT}/{settings.R2_BUCKET_PUBLIC}"
    ).rstrip("/")
    return f"{base}/{object_key}"


def _ensure_membership(db: Session, club_id: int, user_id: int) -> None:
    club = db.get(Club, club_id)
    if not club:
        raise HTTPException(status_code=404, detail="Club no encontrado")
    if club.id_leader == user_id:
        return
    membership = db.execute(
        select(ClubMember).where(
            ClubMember.id_club == club_id,
            ClubMember.id_user == user_id,
        )
    ).scalar_one_or_none()
    if not membership:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Debes pertenecer al club para denunciar este contenido",
        )


def _resolve_target(
    db: Session, target_type: ContentTargetType, target_id: int
) -> tuple[ClubPost | ClubPostComment | ClubMessage, int, int, str]:
    if target_type == ContentTargetType.POST:
        target = db.get(ClubPost, target_id)
        if not target:
            raise HTTPException(status_code=404, detail="Publicación no encontrada")
        return target, target.id_author, target.id_club, target.content

    if target_type == ContentTargetType.COMMENT:
        target = db.execute(
            select(ClubPostComment)
            .options(joinedload(ClubPostComment.post))
            .where(ClubPostComment.id == target_id)
        ).scalar_one_or_none()
        if not target:
            raise HTTPException(status_code=404, detail="Comentario no encontrado")
        return target, target.id_user, target.post.id_club, target.content

    target = db.get(ClubMessage, target_id)
    if not target:
        raise HTTPException(status_code=404, detail="Mensaje no encontrado")
    return target, target.id_user, target.id_club, target.content


def _serialize_admin_report(
    db: Session, report: ContentReport
) -> AdminContentReportResponse:
    image_urls: list[str] = []
    if report.target_type == ContentTargetType.POST:
        post = db.get(ClubPost, report.target_id)
        if post:
            image_urls = [
                url
                for image in post.images
                if (url := _photo_url(image.url)) is not None
            ]
    return AdminContentReportResponse(
        id=report.id,
        reporter_id=report.reporter_id,
        reporter_name=report.reporter.name,
        reported_user_id=report.reported_user_id,
        reported_user_name=report.reported_user.name,
        moderator_id=report.moderator_id,
        target_type=report.target_type,
        target_id=report.target_id,
        club_id=report.club_id,
        reason=report.reason,
        details=report.details,
        content_snapshot=report.content_snapshot,
        content_image_urls=image_urls,
        status=report.status,
        action_taken=report.action_taken,
        moderator_comment=report.moderator_comment,
        created_at=report.created_at,
        reviewed_at=report.reviewed_at,
    )


@router.post(
    "/reports",
    response_model=ContentReportResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_content_report(
    payload: ContentReportCreate,
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    target, author_id, club_id, snapshot = _resolve_target(
        db, payload.target_type, payload.target_id
    )
    if target.is_removed:
        raise HTTPException(status_code=410, detail="El contenido ya fue retirado")
    _ensure_membership(db, club_id, current_user.id)
    if author_id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No puedes denunciar tu propio contenido",
        )

    details = payload.details.strip() if payload.details else None
    report = ContentReport(
        reporter_id=current_user.id,
        reported_user_id=author_id,
        target_type=payload.target_type,
        target_id=payload.target_id,
        club_id=club_id,
        reason=payload.reason,
        details=details or None,
        content_snapshot=snapshot,
    )
    try:
        db.add(report)
        db.commit()
        db.refresh(report)
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Ya denunciaste este contenido",
        ) from exc
    return report


@router.get("/reports/me", response_model=list[ContentReportResponse])
def get_my_content_reports(
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return (
        db.execute(
            select(ContentReport)
            .where(ContentReport.reporter_id == current_user.id)
            .order_by(ContentReport.created_at.desc())
        )
        .scalars()
        .all()
    )


@router.post(
    "/blocks/{user_id}",
    response_model=BlockedUserResponse,
    status_code=status.HTTP_201_CREATED,
)
def block_user(
    user_id: int,
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if user_id == current_user.id:
        raise HTTPException(status_code=400, detail="No puedes bloquearte a ti mismo")
    blocked_user = db.get(User, user_id)
    if not blocked_user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")

    block = UserBlock(blocker_id=current_user.id, blocked_id=user_id)
    try:
        db.add(block)
        db.commit()
        db.refresh(block)
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=409, detail="Este usuario ya está bloqueado"
        ) from exc

    return BlockedUserResponse(
        id=blocked_user.id,
        name=blocked_user.name,
        photo=_photo_url(blocked_user.photo),
        blocked_at=block.created_at,
    )


@router.delete("/blocks/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def unblock_user(
    user_id: int,
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    block = db.execute(
        select(UserBlock).where(
            UserBlock.blocker_id == current_user.id,
            UserBlock.blocked_id == user_id,
        )
    ).scalar_one_or_none()
    if not block:
        raise HTTPException(status_code=404, detail="El usuario no está bloqueado")
    db.delete(block)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/blocks/me", response_model=list[BlockedUserResponse])
def get_blocked_users(
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    blocks = (
        db.execute(
            select(UserBlock)
            .options(joinedload(UserBlock.blocked))
            .where(UserBlock.blocker_id == current_user.id)
            .order_by(UserBlock.created_at.desc())
        )
        .scalars()
        .all()
    )
    return [
        BlockedUserResponse(
            id=block.blocked.id,
            name=block.blocked.name,
            photo=_photo_url(block.blocked.photo),
            blocked_at=block.created_at,
        )
        for block in blocks
    ]


@router.get("/admin/reports", response_model=list[AdminContentReportResponse])
def get_admin_content_reports(
    report_status: ContentReportStatus | None = Query(default=None, alias="status"),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
    _: CurrentUser = Depends(require_admin),
    db: Session = Depends(get_db),
):
    query = select(ContentReport).options(
        joinedload(ContentReport.reporter),
        joinedload(ContentReport.reported_user),
        joinedload(ContentReport.moderator),
    )
    if report_status is not None:
        query = query.where(ContentReport.status == report_status)
    reports = (
        db.execute(
            query.order_by(ContentReport.created_at.asc()).offset(skip).limit(limit)
        )
        .scalars()
        .all()
    )
    return [_serialize_admin_report(db, report) for report in reports]


@router.get("/admin/reports/{report_id}", response_model=AdminContentReportResponse)
def get_admin_content_report(
    report_id: int,
    _: CurrentUser = Depends(require_admin),
    db: Session = Depends(get_db),
):
    report = db.execute(
        select(ContentReport)
        .options(
            joinedload(ContentReport.reporter),
            joinedload(ContentReport.reported_user),
            joinedload(ContentReport.moderator),
        )
        .where(ContentReport.id == report_id)
    ).scalar_one_or_none()
    if not report:
        raise HTTPException(status_code=404, detail="Denuncia no encontrada")
    return _serialize_admin_report(db, report)


@router.patch("/admin/reports/{report_id}", response_model=AdminContentReportResponse)
def moderate_content_report(
    report_id: int,
    payload: AdminModerationUpdate,
    current_admin: CurrentUser = Depends(require_admin),
    db: Session = Depends(get_db),
):
    report = db.execute(
        select(ContentReport)
        .options(
            joinedload(ContentReport.reporter),
            joinedload(ContentReport.reported_user).joinedload(User.role),
            joinedload(ContentReport.moderator),
        )
        .where(ContentReport.id == report_id)
    ).scalar_one_or_none()
    if not report:
        raise HTTPException(status_code=404, detail="Denuncia no encontrada")
    if report.status in {ContentReportStatus.RESOLVED, ContentReportStatus.DISMISSED}:
        raise HTTPException(status_code=409, detail="La denuncia ya fue finalizada")

    now = datetime.now(UTC)
    if payload.action in {
        ModerationAction.REMOVE_CONTENT,
        ModerationAction.REMOVE_AND_SUSPEND,
    }:
        target, _, _, _ = _resolve_target(db, report.target_type, report.target_id)
        target.is_removed = True
        target.removed_at = now
        target.removed_by_admin_id = current_admin.id
        target.removed_reason = payload.moderator_comment or report.reason.value

    if payload.action in {
        ModerationAction.SUSPEND_USER,
        ModerationAction.REMOVE_AND_SUSPEND,
    }:
        if report.reported_user.role.name == RoleName.ADMIN.value:
            raise HTTPException(
                status_code=403,
                detail="No se puede suspender a otro administrador desde moderación",
            )
        report.reported_user.is_active = False
        cache_service.delete(_auth_user_cache_key(report.reported_user_id))
        cache_service.delete(f"users:me:v1:{report.reported_user_id}")

    report.status = payload.status
    report.action_taken = payload.action
    report.moderator_comment = (
        payload.moderator_comment.strip() if payload.moderator_comment else None
    )
    report.moderator_id = current_admin.id
    report.reviewed_at = now
    db.commit()

    return get_admin_content_report(report.id, current_admin, db)
