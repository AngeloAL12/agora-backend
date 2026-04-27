from fastapi import HTTPException
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.club.club import Club
from app.models.club.club_member import ClubMember
from app.models.club.post import ClubPost
from app.models.club.post_comment import ClubPostComment
from app.models.club.post_image import ClubPostImage
from app.models.club.post_like import ClubPostLike


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

    result = []

    for post in posts:
        like_count = (
            db.query(func.count(ClubPostLike.id_user))
            .filter(ClubPostLike.id_post == post.id)
            .scalar()
        ) or 0

        user_has_liked = (
            db.query(ClubPostLike)
            .filter(
                ClubPostLike.id_post == post.id,
                ClubPostLike.id_user == user_id,
            )
            .first()
        ) is not None

        comment_count = (
            db.query(func.count(ClubPostComment.id))
            .filter(ClubPostComment.id_post == post.id)
            .scalar()
        ) or 0

        result.append(
            {
                "id": post.id,
                "id_club": post.id_club,
                "content": post.content,
                "like_count": like_count,
                "user_has_liked": user_has_liked,
                "comment_count": comment_count,
                "comments_preview": [
                    {
                        "id": comment.id,
                        "content": comment.content,
                        "created_at": comment.created_at,
                        "user": {
                            "id": comment.user.id,
                            "name": comment.user.name,
                            "photo": comment.user.photo,
                        },
                    }
                    for comment in post.comments[:3]
                ],
                "images": [{"id": img.id, "url": img.url} for img in post.images],
                "author": {
                    "id": post.author.id,
                    "name": post.author.name,
                    "photo": post.author.photo,
                },
                "created_at": post.created_at,
            }
        )

    return result


def create_club_post_service(
    db: Session,
    club: Club,
    user_id: int,
    content: str,
    images: list,
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

        for url in images:
            db.add(ClubPostImage(url=str(url), id_post=post.id))

        db.commit()
        db.refresh(post)
    except IntegrityError as err:
        db.rollback()
        raise HTTPException(
            status_code=400,
            detail="Error al crear la publicación",
        ) from err

    return {
        "id": post.id,
        "id_club": post.id_club,
        "content": post.content,
        "like_count": 0,
        "user_has_liked": False,
        "comment_count": 0,
        "comments_preview": [],
        "images": [{"id": img.id, "url": img.url} for img in post.images],
        "author": {
            "id": post.author.id,
            "name": post.author.name,
            "photo": post.author.photo,
        },
        "created_at": post.created_at,
    }
