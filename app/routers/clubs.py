from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    UploadFile,
    status,
)
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.club.club import Club
from app.models.club.club_category import ClubCategory
from app.models.club.club_member import ClubMember
from app.models.club.event import ClubEvent
from app.models.club.post import ClubPost
from app.models.club.post_comment import ClubPostComment
from app.models.club.post_image import ClubPostImage
from app.models.club.post_like import ClubPostLike
from app.schemas.auth.auth import CurrentUser
from app.schemas.club.club import (
    ClubCreate,
    ClubDetailResponse,
    ClubResponse,
    ClubUpdate,
)
from app.schemas.club.event import EventCreate, EventResponse, EventUpdate
from app.schemas.club.post import (
    CommentCreate,
    CommentResponse,
    LikeResponse,
    PostResponse,
)
from app.services.club.club_service import (
    create_club_post_service,
    get_club_posts_service,
    verify_membership,
)

router = APIRouter(prefix="/clubs", tags=["clubs"])


# --- Endpoints de Clubes ---


@router.get("", response_model=list[ClubResponse])
def get_clubs(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    return db.query(Club).offset(skip).limit(limit).all()


@router.get("/{club_id}", response_model=ClubDetailResponse)
def get_club(club_id: int, db: Session = Depends(get_db)):
    club = db.query(Club).filter(Club.id == club_id).first()

    if not club:
        raise HTTPException(status_code=404, detail="Club no encontrado")

    members_count = db.query(ClubMember).filter(ClubMember.id_club == club_id).count()

    return ClubDetailResponse.model_validate(
        {**club.__dict__, "members_count": members_count}
    )


@router.post("", response_model=ClubResponse)
def create_club(
    payload: ClubCreate,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    existing = db.query(Club).filter(Club.name == payload.name).first()
    if existing:
        raise HTTPException(status_code=400, detail="Nombre de club ya existe")

    category = (
        db.query(ClubCategory).filter(ClubCategory.id == payload.id_category).first()
    )
    if not category:
        raise HTTPException(status_code=400, detail="Categoría inválida")

    club = Club(
        name=payload.name,
        description=payload.description,
        image=payload.image,
        id_category=payload.id_category,
        id_leader=current_user.id,
    )

    try:
        db.add(club)
        db.flush()
        db.add(ClubMember(id_club=club.id, id_user=current_user.id))
        db.commit()
        db.refresh(club)
        return club
    except IntegrityError as err:
        db.rollback()
        raise HTTPException(status_code=400, detail="Error al crear el club") from err


@router.patch("/{club_id}", response_model=ClubResponse)
def update_club(
    club_id: int,
    payload: ClubUpdate,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    club = db.query(Club).filter(Club.id == club_id).first()

    if not club:
        raise HTTPException(status_code=404, detail="Club no encontrado")

    if club.id_leader != current_user.id:
        raise HTTPException(status_code=403, detail="Solo el líder puede editar")

    # Los tests esperan explícitamente 400 si se envía null en campos obligatorios
    if "name" in payload.model_fields_set:
        if payload.name is None:
            raise HTTPException(status_code=400, detail="El nombre no puede ser null")
        existing = db.query(Club).filter(Club.name == payload.name).first()
        if existing and existing.id != club.id:
            raise HTTPException(status_code=400, detail="Nombre de club ya existe")
        club.name = payload.name

    if "description" in payload.model_fields_set:
        if payload.description is None:
            raise HTTPException(
                status_code=400, detail="La descripción no puede ser null"
            )
        club.description = payload.description

    if "image" in payload.model_fields_set:
        club.image = payload.image

    if "id_category" in payload.model_fields_set:
        if payload.id_category is None:
            raise HTTPException(status_code=400, detail="Categoría inválida")
        category = (
            db.query(ClubCategory)
            .filter(ClubCategory.id == payload.id_category)
            .first()
        )
        if not category:
            raise HTTPException(status_code=400, detail="Categoría inválida")
        club.id_category = payload.id_category

    db.commit()
    db.refresh(club)
    return club


@router.delete("/{club_id}")
def delete_club(
    club_id: int,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    club = db.query(Club).filter(Club.id == club_id).first()
    if not club:
        raise HTTPException(status_code=404, detail="Club no encontrado")

    if club.id_leader != current_user.id:
        raise HTTPException(status_code=403, detail="Solo el líder puede eliminar")

    # Fallback para SQLite en tests — PostgreSQL usa ON DELETE CASCADE en FK.
    if db.bind and db.bind.dialect.name == "sqlite":
        post_ids = [
            r[0]
            for r in db.query(ClubPost.id).filter(ClubPost.id_club == club_id).all()
        ]
        if post_ids:
            db.query(ClubPostLike).filter(ClubPostLike.id_post.in_(post_ids)).delete(
                synchronize_session=False
            )
            db.query(ClubPostComment).filter(
                ClubPostComment.id_post.in_(post_ids)
            ).delete(synchronize_session=False)
            db.query(ClubPostImage).filter(ClubPostImage.id_post.in_(post_ids)).delete(
                synchronize_session=False
            )
        db.query(ClubPost).filter(ClubPost.id_club == club_id).delete(
            synchronize_session=False
        )
        db.query(ClubEvent).filter(ClubEvent.id_club == club_id).delete(
            synchronize_session=False
        )
        db.query(ClubMember).filter(ClubMember.id_club == club_id).delete(
            synchronize_session=False
        )

    db.delete(club)
    db.commit()

    return {"message": "Club eliminado"}


@router.post("/{club_id}/members")
def join_club(
    club_id: int,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    club = db.query(Club).filter(Club.id == club_id).first()
    if not club:
        raise HTTPException(status_code=404, detail="Club no encontrado")

    exists = (
        db.query(ClubMember)
        .filter(ClubMember.id_club == club_id, ClubMember.id_user == current_user.id)
        .first()
    )
    if exists:
        raise HTTPException(status_code=400, detail="Ya eres miembro")

    db.add(ClubMember(id_club=club_id, id_user=current_user.id))
    db.commit()
    return {"message": "Te uniste al club"}


@router.delete("/{club_id}/members/me")
def leave_club(
    club_id: int,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    club = db.query(Club).filter(Club.id == club_id).first()
    if not club:
        raise HTTPException(status_code=404, detail="Club no encontrado")

    if club.id_leader == current_user.id:
        raise HTTPException(status_code=400, detail="El líder no puede salirse")

    member = (
        db.query(ClubMember)
        .filter(ClubMember.id_club == club_id, ClubMember.id_user == current_user.id)
        .first()
    )
    if not member:
        raise HTTPException(status_code=404, detail="No eres miembro")

    db.delete(member)
    db.commit()
    return {"message": "Saliste del club"}


@router.delete("/{club_id}/members/{user_id}")
def remove_member(
    club_id: int,
    user_id: int,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    club = db.query(Club).filter(Club.id == club_id).first()
    if not club:
        raise HTTPException(status_code=404, detail="Club no encontrado")

    if club.id_leader != current_user.id:
        raise HTTPException(status_code=403, detail="Solo el líder puede expulsar")

    if user_id == club.id_leader:
        raise HTTPException(status_code=400, detail="No puedes expulsar al líder")

    member = (
        db.query(ClubMember)
        .filter(ClubMember.id_club == club_id, ClubMember.id_user == user_id)
        .first()
    )
    if not member:
        raise HTTPException(status_code=404, detail="No es miembro")

    db.delete(member)
    db.commit()
    return {"message": "Miembro expulsado"}


@router.patch("/{club_id}/members/{user_id}/leader")
def transfer_leadership(
    club_id: int,
    user_id: int,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    club = db.query(Club).filter(Club.id == club_id).first()
    if not club:
        raise HTTPException(status_code=404, detail="Club no encontrado")

    if club.id_leader != current_user.id:
        raise HTTPException(
            status_code=403, detail="Solo el líder actual puede transferir"
        )

    if user_id == club.id_leader:
        raise HTTPException(status_code=409, detail="El usuario ya es el líder actual")

    member = (
        db.query(ClubMember)
        .filter(ClubMember.id_club == club_id, ClubMember.id_user == user_id)
        .first()
    )
    if not member:
        raise HTTPException(
            status_code=400, detail="El usuario destino debe ser miembro del club"
        )

    club.id_leader = user_id
    db.commit()
    db.refresh(club)
    return {"message": "Liderazgo transferido"}


# --- Endpoints de Publicaciones ---


@router.get("/{club_id}/posts", response_model=list[PostResponse])
def get_club_posts(
    club_id: int,
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    club = db.query(Club).filter(Club.id == club_id).first()
    if not club:
        raise HTTPException(status_code=404, detail="Club no encontrado")

    return get_club_posts_service(
        db=db,
        club=club,
        user_id=current_user.id,
        page=page,
        limit=limit,
    )


@router.post(
    "/{club_id}/posts",
    response_model=PostResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_club_post(
    club_id: int,
    content: str = Form(..., min_length=1, max_length=1000),
    images: list[UploadFile] = File(default=[]),
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    if len(images) > 5:
        raise HTTPException(status_code=400, detail="Máximo 5 imágenes por publicación")

    club = db.query(Club).filter(Club.id == club_id).first()
    if not club:
        raise HTTPException(status_code=404, detail="Club no encontrado")

    return await create_club_post_service(
        db=db,
        club=club,
        user_id=current_user.id,
        content=content,
        images=images,
    )


@router.delete("/{club_id}/posts/{post_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_club_post(
    club_id: int,
    post_id: int,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    club = db.query(Club).filter(Club.id == club_id).first()
    if not club:
        raise HTTPException(status_code=404, detail="Club no encontrado")

    verify_membership(db, club, current_user.id, require_leader=False)

    post = (
        db.query(ClubPost)
        .filter(ClubPost.id == post_id, ClubPost.id_club == club_id)
        .first()
    )
    if not post:
        raise HTTPException(status_code=404, detail="Publicación no encontrada")

    # Only author or leader can delete
    if post.id_author != current_user.id and club.id_leader != current_user.id:
        raise HTTPException(
            status_code=403,
            detail="Solo el autor o el líder pueden eliminar esta publicación",
        )

    db.delete(post)
    db.commit()
    return None


@router.get("/{club_id}/posts/{post_id}/comments", response_model=list[CommentResponse])
def get_post_comments(
    club_id: int,
    post_id: int,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    club = db.query(Club).filter(Club.id == club_id).first()
    if not club:
        raise HTTPException(status_code=404, detail="Club no encontrado")

    verify_membership(db, club, current_user.id, require_leader=False)

    post = (
        db.query(ClubPost)
        .filter(ClubPost.id == post_id, ClubPost.id_club == club_id)
        .first()
    )
    if not post:
        raise HTTPException(status_code=404, detail="Publicación no encontrada")

    comments = (
        db.query(ClubPostComment)
        .filter(ClubPostComment.id_post == post_id)
        .order_by(ClubPostComment.created_at.asc())
        .all()
    )

    return [
        {
            "id": comment.id,
            "id_post": comment.id_post,
            "content": comment.content,
            "created_at": comment.created_at,
            "user": {
                "id": comment.user.id,
                "name": comment.user.name,
                "photo": comment.user.photo,
            },
        }
        for comment in comments
    ]


@router.post(
    "/{club_id}/posts/{post_id}/comments",
    response_model=CommentResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_post_comment(
    club_id: int,
    post_id: int,
    payload: CommentCreate,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    club = db.query(Club).filter(Club.id == club_id).first()
    if not club:
        raise HTTPException(status_code=404, detail="Club no encontrado")

    verify_membership(db, club, current_user.id, require_leader=False)

    post = (
        db.query(ClubPost)
        .filter(ClubPost.id == post_id, ClubPost.id_club == club_id)
        .first()
    )
    if not post:
        raise HTTPException(status_code=404, detail="Publicación no encontrada")

    comment = ClubPostComment(
        content=payload.content,
        id_post=post_id,
        id_user=current_user.id,
    )

    try:
        db.add(comment)
        db.commit()
        db.refresh(comment)
    except IntegrityError as err:
        db.rollback()
        raise HTTPException(
            status_code=400, detail="Error al crear el comentario"
        ) from err

    return {
        "id": comment.id,
        "id_post": comment.id_post,
        "content": comment.content,
        "created_at": comment.created_at,
        "user": {
            "id": comment.user.id,
            "name": comment.user.name,
            "photo": comment.user.photo,
        },
    }


@router.delete(
    "/{club_id}/posts/{post_id}/comments/{comment_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_post_comment(
    club_id: int,
    post_id: int,
    comment_id: int,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    club = db.query(Club).filter(Club.id == club_id).first()
    if not club:
        raise HTTPException(status_code=404, detail="Club no encontrado")

    verify_membership(db, club, current_user.id, require_leader=False)
    comment = (
        db.query(ClubPostComment)
        .filter(
            ClubPostComment.id == comment_id,
            ClubPostComment.id_post == post_id,
        )
        .first()
    )
    if not comment:
        raise HTTPException(status_code=404, detail="Comentario no encontrado")

    # Only author or leader can delete
    if comment.id_user != current_user.id and club.id_leader != current_user.id:
        raise HTTPException(
            status_code=403,
            detail="Solo el autor del comentario o el líder pueden eliminarlo",
        )

    db.delete(comment)
    db.commit()
    return None


@router.post(
    "/{club_id}/posts/{post_id}/like",
    response_model=LikeResponse,
    status_code=status.HTTP_201_CREATED,
)
def like_post(
    club_id: int,
    post_id: int,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    club = db.query(Club).filter(Club.id == club_id).first()
    if not club:
        raise HTTPException(status_code=404, detail="Club no encontrado")

    verify_membership(db, club, current_user.id, require_leader=False)
    post = (
        db.query(ClubPost)
        .filter(ClubPost.id == post_id, ClubPost.id_club == club_id)
        .first()
    )
    if not post:
        raise HTTPException(status_code=404, detail="Publicación no encontrada")

    # Check if already liked
    existing_like = (
        db.query(ClubPostLike)
        .filter(
            ClubPostLike.id_post == post_id, ClubPostLike.id_user == current_user.id
        )
        .first()
    )
    if existing_like:
        raise HTTPException(
            status_code=400, detail="El usuario ya dio like a esta publicación"
        )

    like = ClubPostLike(id_post=post_id, id_user=current_user.id)

    try:
        db.add(like)
        db.commit()
    except IntegrityError as err:
        db.rollback()
        raise HTTPException(status_code=400, detail="Error al dar like") from err

    like_count = (
        db.query(func.count(ClubPostLike.id_user))
        .filter(ClubPostLike.id_post == post_id)
        .scalar()
    )
    return {
        "id_post": post_id,
        "id_user": current_user.id,
        "like_count": like_count,
    }


@router.delete("/{club_id}/posts/{post_id}/like", response_model=LikeResponse)
def unlike_post(
    club_id: int,
    post_id: int,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    club = db.query(Club).filter(Club.id == club_id).first()
    if not club:
        raise HTTPException(status_code=404, detail="Club no encontrado")

    verify_membership(db, club, current_user.id, require_leader=False)

    post = (
        db.query(ClubPost)
        .filter(ClubPost.id == post_id, ClubPost.id_club == club_id)
        .first()
    )
    if not post:
        raise HTTPException(status_code=404, detail="Publicación no encontrada")

    like = (
        db.query(ClubPostLike)
        .filter(
            ClubPostLike.id_post == post_id,
            ClubPostLike.id_user == current_user.id,
        )
        .first()
    )
    if not like:
        raise HTTPException(
            status_code=400,
            detail="El usuario no había dado like a esta publicación",
        )

    db.delete(like)
    db.commit()

    like_count = (
        db.query(func.count(ClubPostLike.id_user))
        .filter(ClubPostLike.id_post == post_id)
        .scalar()
    ) or 0

    return {
        "id_post": post_id,
        "id_user": current_user.id,
        "like_count": like_count,
    }


# --- Endpoints de Eventos ---


@router.get("/{club_id}/events", response_model=list[EventResponse])
def list_club_events(
    club_id: int,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    club = db.query(Club).filter(Club.id == club_id).first()
    if not club:
        raise HTTPException(status_code=404, detail="Club no encontrado")

    verify_membership(db, club, current_user.id, require_leader=False)
    return (
        db.query(ClubEvent)
        .filter(ClubEvent.id_club == club_id)
        .order_by(ClubEvent.date.asc())
        .all()
    )


@router.post(
    "/{club_id}/events",
    response_model=EventResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_club_event(
    club_id: int,
    payload: EventCreate,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    club = db.query(Club).filter(Club.id == club_id).first()
    if not club:
        raise HTTPException(status_code=404, detail="Club no encontrado")

    verify_membership(db, club, current_user.id, require_leader=True)

    event = ClubEvent(
        id_club=club_id,
        id_author=current_user.id,
        title=payload.title,
        description=payload.description,
        date=payload.date,
        latitude=payload.latitude,
        longitude=payload.longitude,
    )
    db.add(event)
    db.commit()
    db.refresh(event)
    return event


@router.patch("/{club_id}/events/{event_id}", response_model=EventResponse)
def update_club_event(
    club_id: int,
    event_id: int,
    payload: EventUpdate,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    club = db.query(Club).filter(Club.id == club_id).first()
    if not club:
        raise HTTPException(status_code=404, detail="Club no encontrado")

    verify_membership(db, club, current_user.id, require_leader=True)
    event = (
        db.query(ClubEvent)
        .filter(ClubEvent.id == event_id, ClubEvent.id_club == club_id)
        .first()
    )
    if not event:
        raise HTTPException(status_code=404, detail="Evento no encontrado")

    if "title" in payload.model_fields_set and payload.title is not None:
        event.title = payload.title
    if "description" in payload.model_fields_set:
        event.description = payload.description
    if "date" in payload.model_fields_set and payload.date is not None:
        event.date = payload.date
    if "latitude" in payload.model_fields_set:
        event.latitude = payload.latitude
    if "longitude" in payload.model_fields_set:
        event.longitude = payload.longitude

    db.commit()
    db.refresh(event)
    return event


@router.delete("/{club_id}/events/{event_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_club_event(
    club_id: int,
    event_id: int,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    club = db.query(Club).filter(Club.id == club_id).first()
    if not club:
        raise HTTPException(status_code=404, detail="Club no encontrado")

    verify_membership(db, club, current_user.id, require_leader=True)

    event = (
        db.query(ClubEvent)
        .filter(ClubEvent.id == event_id, ClubEvent.id_club == club_id)
        .first()
    )
    if not event:
        raise HTTPException(status_code=404, detail="Evento no encontrado")

    db.delete(event)
    db.commit()
    return None
