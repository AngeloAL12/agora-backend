from fastapi import HTTPException, UploadFile
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from app.core.config import settings
from app.models.auth.user import User
from app.models.club.club import Club
from app.models.club.club_join_request import ClubJoinRequest, JoinRequestStatus
from app.models.club.club_member import ClubMember
from app.models.club.post import ClubPost
from app.models.club.post_comment import ClubPostComment
from app.models.club.post_image import ClubPostImage
from app.models.club.post_like import ClubPostLike
from app.models.notification.notification import (
    NotificationCategory,
    NotificationEventType,
)
from app.schemas.club.join_request import JoinRequestAction
from app.services.notification_service import create_notification
from app.services.storage_service import storage_service


def request_join_club(db: Session, club: Club, user_id: int) -> ClubJoinRequest:
    if not club.is_private:
        raise HTTPException(
            status_code=400, detail="El club es público, únete directamente"
        )

    is_member = club.id_leader == user_id or (
        db.query(ClubMember)
        .filter(ClubMember.id_club == club.id, ClubMember.id_user == user_id)
        .first()
        is not None
    )
    if is_member:
        raise HTTPException(status_code=400, detail="Ya eres miembro del club")

    existing = (
        db.query(ClubJoinRequest)
        .filter(
            ClubJoinRequest.id_club == club.id,
            ClubJoinRequest.id_user == user_id,
            ClubJoinRequest.status == JoinRequestStatus.PENDING,
        )
        .first()
    )
    if existing:
        raise HTTPException(status_code=409, detail="Ya tienes una solicitud pendiente")

    join_request = ClubJoinRequest(
        id_club=club.id,
        id_user=user_id,
        status=JoinRequestStatus.PENDING,
    )
    db.add(join_request)
    db.flush()

    user = db.query(User).filter(User.id == user_id).first()
    create_notification(
        db,
        id_user=club.id_leader,
        category=NotificationCategory.CLUBS,
        event_type=NotificationEventType.CLUB_JOIN_REQUEST,
        title=f"{user.name} quiere unirse a {club.name}",
        body="Acepta o rechaza la solicitud desde notificaciones",
        reference_id=club.id,
        extra_id=join_request.id,
    )

    db.commit()
    db.refresh(join_request)
    return join_request


def resolve_join_request(
    db: Session,
    club: Club,
    request_id: int,
    action: str,
    current_user_id: int,
) -> ClubJoinRequest:
    if club.id_leader != current_user_id:
        raise HTTPException(
            status_code=403, detail="Solo el líder puede resolver solicitudes"
        )

    join_request = (
        db.query(ClubJoinRequest)
        .filter(ClubJoinRequest.id == request_id, ClubJoinRequest.id_club == club.id)
        .first()
    )
    if not join_request:
        raise HTTPException(status_code=404, detail="Solicitud no encontrada")

    if join_request.status != JoinRequestStatus.PENDING:
        raise HTTPException(status_code=409, detail="La solicitud ya fue resuelta")

    if action == JoinRequestAction.ACCEPT:
        join_request.status = JoinRequestStatus.ACCEPTED
        try:
            db.add(ClubMember(id_club=club.id, id_user=join_request.id_user))
            db.flush()
        except IntegrityError as exc:
            db.rollback()
            raise HTTPException(
                status_code=409, detail="El usuario ya es miembro del club"
            ) from exc
        create_notification(
            db,
            id_user=join_request.id_user,
            category=NotificationCategory.CLUBS,
            event_type=NotificationEventType.CLUB_JOIN_ACCEPTED,
            title=f"Tu solicitud a {club.name} fue aceptada",
            body="Ya eres miembro del club",
            reference_id=club.id,
        )
    elif action == JoinRequestAction.REJECT:
        join_request.status = JoinRequestStatus.REJECTED
        create_notification(
            db,
            id_user=join_request.id_user,
            category=NotificationCategory.CLUBS,
            event_type=NotificationEventType.CLUB_JOIN_REJECTED,
            title=f"Tu solicitud a {club.name} fue rechazada",
            body="El líder no aceptó tu solicitud",
            reference_id=club.id,
        )
    else:
        raise HTTPException(status_code=400, detail="Acción inválida")

    db.commit()
    db.refresh(join_request)
    return join_request


def list_pending_requests(
    db: Session, club: Club, current_user_id: int
) -> list[ClubJoinRequest]:
    if club.id_leader != current_user_id:
        raise HTTPException(
            status_code=403, detail="Solo el líder puede ver las solicitudes"
        )

    return (
        db.query(ClubJoinRequest)
        .options(joinedload(ClubJoinRequest.user))
        .filter(
            ClubJoinRequest.id_club == club.id,
            ClubJoinRequest.status == JoinRequestStatus.PENDING,
        )
        .order_by(ClubJoinRequest.created_at.asc())
        .all()
    )


def _public_url(object_key: str) -> str:
    if not settings.R2_PUBLIC_URL:
        return object_key

    base = settings.R2_PUBLIC_URL.rstrip("/")
    return f"{base}/{object_key}"


def verify_membership(
    db: Session,
    club: Club,
    user_id: int,
    require_leader: bool = False,
):
    if require_leader:
        if club.id_leader != user_id:
            raise HTTPException(
                status_code=403,
                detail="Solo el líder puede realizar esta acción",
            )
        return

    if club.id_leader == user_id:
        return

    member = (
        db.query(ClubMember)
        .filter(
            ClubMember.id_club == club.id,
            ClubMember.id_user == user_id,
        )
        .first()
    )

    if not member:
        raise HTTPException(
            status_code=403,
            detail="El usuario no es miembro del club",
        )


def get_club_posts_service(
    db: Session,
    club: Club,
    user_id: int,
    page: int,
    limit: int,
):
    verify_membership(db, club, user_id, require_leader=False)

    offset = (page - 1) * limit

    posts = (
        db.query(ClubPost)
        .filter(ClubPost.id_club == club.id)
        .order_by(ClubPost.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )

    if not posts:
        return []

    post_ids = [p.id for p in posts]

    like_counts = dict(
        db.query(ClubPostLike.id_post, func.count(ClubPostLike.id_user))
        .filter(ClubPostLike.id_post.in_(post_ids))
        .group_by(ClubPostLike.id_post)
        .all()
    )

    liked_set = {
        row[0]
        for row in db.query(ClubPostLike.id_post)
        .filter(ClubPostLike.id_post.in_(post_ids), ClubPostLike.id_user == user_id)
        .all()
    }

    comment_counts = dict(
        db.query(ClubPostComment.id_post, func.count(ClubPostComment.id))
        .filter(ClubPostComment.id_post.in_(post_ids))
        .group_by(ClubPostComment.id_post)
        .all()
    )

    result = []

    for post in posts:
        image_urls = [
            {"id": img.id, "url": _public_url(img.url)} for img in post.images
        ]

        result.append(
            {
                "id": post.id,
                "id_club": post.id_club,
                "content": post.content,
                "like_count": like_counts.get(post.id, 0),
                "user_has_liked": post.id in liked_set,
                "comment_count": comment_counts.get(post.id, 0),
                "comments_preview": [
                    {
                        "id": comment.id,
                        "content": comment.content,
                        "created_at": comment.created_at,
                        "user": {
                            "id": comment.user.id,
                            "name": comment.user.name,
                            "photo": _public_url(comment.user.photo)
                            if comment.user.photo
                            else None,
                        },
                    }
                    for comment in post.comments[:3]
                ],
                "images": image_urls,
                "author": {
                    "id": post.author.id,
                    "name": post.author.name,
                    "photo": _public_url(post.author.photo)
                    if post.author.photo
                    else None,
                },
                "created_at": post.created_at,
            }
        )

    return result


async def create_club_post_service(
    db: Session,
    club: Club,
    user_id: int,
    content: str,
    images: list[UploadFile],
):
    verify_membership(db, club, user_id, require_leader=False)

    post = ClubPost(
        content=content,
        id_club=club.id,
        id_author=user_id,
    )

    try:
        db.add(post)
        db.flush()

        for file in images:
            object_key = await storage_service.upload_file(
                file, settings.R2_BUCKET_PUBLIC, f"clubs/{club.id}/posts"
            )
            db.add(ClubPostImage(url=object_key, id_post=post.id))

        db.commit()
        db.refresh(post)
    except IntegrityError as err:
        db.rollback()
        raise HTTPException(
            status_code=400,
            detail="Error al crear la publicación",
        ) from err

    image_urls = [{"id": img.id, "url": _public_url(img.url)} for img in post.images]

    return {
        "id": post.id,
        "id_club": post.id_club,
        "content": post.content,
        "like_count": 0,
        "user_has_liked": False,
        "comment_count": 0,
        "comments_preview": [],
        "images": image_urls,
        "author": {
            "id": post.author.id,
            "name": post.author.name,
            "photo": post.author.photo,
        },
        "created_at": post.created_at,
    }
