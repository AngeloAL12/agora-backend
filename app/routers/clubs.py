import logging
from typing import Annotated, Any

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    UploadFile,
    WebSocket,
    WebSocketDisconnect,
    status,
)
from fastapi.concurrency import run_in_threadpool
from pydantic import ValidationError
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from app.core.config import settings
from app.core.database import get_db
from app.core.security import (
    TokenDecodeError,
    decode_access_token,
    get_current_user,
)
from app.models.auth.user import User
from app.models.auth.user_session import UserSession
from app.models.club.club import Club
from app.models.club.club_category import ClubCategory
from app.models.club.club_member import ClubMember
from app.models.club.event import ClubEvent
from app.models.club.message import ClubMessage
from app.models.club.post import ClubPost
from app.models.club.post_comment import ClubPostComment
from app.models.club.post_like import ClubPostLike
from app.schemas.auth.auth import CurrentUser
from app.schemas.club.club import (
    ClubCategoryResponse,
    ClubDetailResponse,
    ClubMemberResponse,
    ClubResponse,
)
from app.schemas.club.event import EventCreate, EventResponse, EventUpdate
from app.schemas.club.message import (
    ClubMessageInput,
    ClubMessageResponse,
    ClubMessageUserResponse,
)
from app.schemas.club.post import (
    CommentCreate,
    CommentResponse,
    LikeResponse,
    PostResponse,
)
from app.services.club.club_service import (
    create_club_post_service,
    get_club_posts_service,
)
from app.services.push_service import send_push_notification
from app.services.redis_service import redis_chat_manager
from app.services.storage_service import storage_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/clubs", tags=["clubs"])


def _verify_membership(
    club: Club, user_id: int, db: Session, require_leader: bool = False
):
    if require_leader:
        if club.id_leader != user_id:
            raise HTTPException(
                status_code=403, detail="Solo el líder puede realizar esta acción"
            )
        return

    if club.id_leader == user_id:
        return

    is_member = (
        db.query(ClubMember)
        .filter(ClubMember.id_club == club.id, ClubMember.id_user == user_id)
        .first()
    )

    if not is_member:
        raise HTTPException(status_code=403, detail="El usuario no es miembro del club")


# --- Endpoints de Clubes ---


def _build_image_url(image_key: str | None) -> str | None:
    if not image_key:
        return None
    return f"{settings.R2_PUBLIC_URL}/{image_key}"


def _to_club_response(club: Club) -> ClubResponse:
    return ClubResponse.model_validate(
        {
            **club.__dict__,
            "profile_image": _build_image_url(club.profile_image),
            "cover_image": _build_image_url(club.cover_image),
        }
    )


def _to_club_detail_response(club: Club, members_count: int) -> ClubDetailResponse:
    return ClubDetailResponse.model_validate(
        {
            **club.__dict__,
            "profile_image": _build_image_url(club.profile_image),
            "cover_image": _build_image_url(club.cover_image),
            "members_count": members_count,
        }
    )


def _clean_required_text(value: str, field_name: str, max_length: int) -> str:
    cleaned = value.strip()
    if not cleaned:
        raise HTTPException(
            status_code=400,
            detail=f"El campo {field_name} no puede contener solo espacios en blanco",
        )
    if len(cleaned) > max_length:
        raise HTTPException(
            status_code=400,
            detail=f"El campo {field_name} no puede exceder {max_length} caracteres",
        )
    return cleaned


def _is_club_member(club: Club, user_id: int, db: Session) -> bool:
    if club.id_leader == user_id:
        return True

    membership = db.execute(
        select(ClubMember).where(
            ClubMember.id_club == club.id, ClubMember.id_user == user_id
        )
    ).scalar_one_or_none()
    return membership is not None


def _authenticate_ws_user(
    headers: dict[str, str], db: Session, token: str | None = None
) -> User | None:
    """Autentica usuario para WebSocket desde header o query token.

    Valida que:
    - Exista Authorization header con formato 'Bearer <token>' o token por query
    - El token sea válido
    - El claim type sea estrictamente 'access'
    - El usuario exista y esté activo
    """
    if token is None:
        auth_header = headers.get("authorization", "")
        if not auth_header.startswith("Bearer "):
            return None
        token = auth_header[7:]  # Remover "Bearer "

    try:
        payload = decode_access_token(token)
    except TokenDecodeError:
        return None

    # Validar que el claim type sea estrictamente "access"
    if payload.get("type") != "access":
        return None

    user_id = payload.get("sub")
    if user_id is None:
        return None
    try:
        user_id_int = int(user_id)
    except (TypeError, ValueError):
        return None

    user = db.execute(select(User).where(User.id == user_id_int)).scalar_one_or_none()
    if not user or not user.is_active:
        return None

    return user


def _build_message_payload(message: ClubMessage) -> dict:
    return ClubMessageResponse(
        id=message.id,
        id_club=message.id_club,
        content=message.content,
        created_at=message.created_at,
        user=ClubMessageUserResponse(
            id=message.user.id,
            name=message.user.name,
            photo=message.user.photo,
        ),
    ).model_dump(mode="json")


def _authenticate_ws_user_for_club(
    headers: dict[str, str], club_id: int, db: Session
) -> tuple[User, Club] | None:
    """Autenticates WS user from Authorization header and validates club membership.

    Returns (user, club) if auth + membership pass, None otherwise.
    """
    auth_header = headers.get("authorization", "")
    if not auth_header.startswith("Bearer "):
        return None
    token = auth_header[7:]

    user = _authenticate_ws_user(headers, db, token=token)
    if user is None:
        return None

    club = db.query(Club).filter(Club.id == club_id).first()
    if not club:
        return None

    if not _is_club_member(club, user.id, db):
        return None

    return user, club


def _create_message_and_notify_offline(
    db: Session,
    *,
    club: Club,
    sender: User,
    content: str,
    connected_user_ids: set[int],
) -> dict:
    """Persiste mensaje y notifica miembros offline en una operación síncrona."""
    if not club or not sender:
        raise ValueError("Club o usuario no encontrado")

    try:
        message = ClubMessage(id_club=club.id, id_user=sender.id, content=content)
        db.add(message)
        db.commit()
        db.refresh(message)
    except Exception:
        db.rollback()
        raise

    db_message = db.execute(
        select(ClubMessage)
        .options(joinedload(ClubMessage.user))
        .where(ClubMessage.id == message.id)
    ).scalar_one()

    response_payload = _build_message_payload(db_message)

    try:
        _notify_offline_members(
            db,
            club=club,
            sender=sender,
            content=content,
            connected_user_ids=connected_user_ids,
        )
    except Exception:
        logger.error("Push notification failed, continuing", exc_info=True)

    return response_payload


def _notify_offline_members(
    db: Session,
    *,
    club: Club,
    sender: User,
    content: str,
    connected_user_ids: set[int],
) -> None:
    """Envía notificaciones push a miembros offline del club.

    Args:
        db: Sesión de BD
        club: Club en el que se envió el mensaje
        sender: Usuario que envió el mensaje
        content: Contenido del mensaje
        connected_user_ids: IDs de usuarios conectados (para excluir)
    """
    # Incluir al líder en la lista de miembros
    member_ids = {club.id_leader}

    # Agregar todos los miembros
    member_ids.update(
        db.execute(select(ClubMember.id_user).where(ClubMember.id_club == club.id))
        .scalars()
        .all()
    )

    # Excluir al remitente
    member_ids.discard(sender.id)

    # Calcular quiénes están offline
    offline_ids = member_ids - connected_user_ids
    if not offline_ids:
        return

    sessions = db.execute(
        select(UserSession.id_user, UserSession.push_token).where(
            UserSession.id_user.in_(offline_ids),
            UserSession.push_token.is_not(None),
        )
    ).all()

    preview = content if len(content) <= 120 else f"{content[:117]}..."

    for id_user, push_token in sessions:
        send_push_notification(
            token=push_token,
            title=f"Nuevo mensaje en {club.name}",
            body=f"{sender.name}: {preview}",
            data={
                "category": "CLUB_CHAT",
                "id_club": club.id,
                "id_leader": club.id_leader,
                "id_user": id_user,
            },
        )


@router.get("", response_model=list[ClubDetailResponse])
def get_clubs(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    rows = (
        db.query(Club, func.count(ClubMember.id).label("members_count"))
        .outerjoin(ClubMember, Club.id == ClubMember.id_club)
        .group_by(Club.id)
        .order_by(Club.id)
        .offset(skip)
        .limit(limit)
        .all()
    )
    return [_to_club_detail_response(club, count) for club, count in rows]


@router.get("/me", response_model=list[ClubDetailResponse])
def get_my_clubs(
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Returns clubs where the authenticated user is leader or member."""
    membership_subq = (
        db.query(ClubMember.id_club)
        .filter(ClubMember.id_user == current_user.id)
        .subquery()
    )
    rows = (
        db.query(Club, func.count(ClubMember.id).label("members_count"))
        .outerjoin(ClubMember, Club.id == ClubMember.id_club)
        .filter((Club.id_leader == current_user.id) | Club.id.in_(membership_subq))
        .group_by(Club.id)
        .order_by(Club.id)
        .all()
    )
    return [_to_club_detail_response(club, count) for club, count in rows]


@router.get("/categories", response_model=list[ClubCategoryResponse])
def get_club_categories(db: Session = Depends(get_db)):
    return db.query(ClubCategory).order_by(ClubCategory.name.asc()).all()


@router.get("/{club_id}", response_model=ClubDetailResponse)
def get_club(club_id: int, db: Session = Depends(get_db)):
    club = db.query(Club).filter(Club.id == club_id).first()

    if not club:
        raise HTTPException(status_code=404, detail="Club no encontrado")

    members_count = db.query(ClubMember).filter(ClubMember.id_club == club_id).count()

    return _to_club_detail_response(club, members_count)


@router.get("/{club_id}/messages", response_model=list[ClubMessageResponse])
def get_club_messages(
    club_id: int,
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    club = db.query(Club).filter(Club.id == club_id).first()
    if not club:
        raise HTTPException(status_code=404, detail="Club no encontrado")

    _verify_membership(club, current_user.id, db, require_leader=False)

    messages = (
        db.execute(
            select(ClubMessage)
            .options(joinedload(ClubMessage.user))
            .where(ClubMessage.id_club == club_id)
            .order_by(ClubMessage.created_at.asc(), ClubMessage.id.asc())
            .offset((page - 1) * limit)
            .limit(limit)
        )
        .scalars()
        .all()
    )

    return [ClubMessageResponse.model_validate(item) for item in messages]


@router.websocket("/{club_id}/chat")
async def club_chat(
    websocket: WebSocket,
    club_id: int,
    db: Session = Depends(get_db),
):
    """WebSocket endpoint para chat en club.

    Autenticación: Bearer token en header Authorization.
    Requiere token con claim type 'access'.
    """
    user_id: int | None = None
    ws_callback: Any = None
    content_error = "content debe ser requerido y tener entre 1 y 1000 caracteres"

    await websocket.accept()

    result = await run_in_threadpool(
        _authenticate_ws_user_for_club,
        dict(websocket.headers),
        club_id,
        db,
    )

    if result is None:
        auth_header = dict(websocket.headers).get("authorization", "")
        if not auth_header.startswith("Bearer "):
            await websocket.close(code=4001, reason="Invalid authentication")
        else:
            user_check = await run_in_threadpool(
                _authenticate_ws_user, dict(websocket.headers), db
            )
            if user_check is None:
                await websocket.close(code=4001, reason="Invalid authentication")
            else:
                await websocket.close(code=4003, reason="Not a club member")
        return

    user, club = result
    user_id = user.id

    try:
        # Crear callback para recibir mensajes del Redis
        async def on_message_from_redis(message: dict) -> None:
            try:
                await websocket.send_json(message)
            except RuntimeError as exc:
                if "WebSocket is not connected" in str(exc):
                    logger.debug(f"WebSocket cerrado para usuario {user_id}")
                else:
                    raise

        ws_callback = on_message_from_redis

        # Suscribirse a mensajes del club
        await redis_chat_manager.subscribe(club_id, user_id, ws_callback)

        while True:
            payload = await websocket.receive_json()

            try:
                incoming = ClubMessageInput.model_validate(payload)
            except ValidationError:
                await websocket.send_json({"detail": content_error})
                continue

            content = incoming.content.strip()
            if not content:
                await websocket.send_json({"detail": content_error})
                continue

            try:
                connected_ids = await redis_chat_manager.get_connected_user_ids(club_id)
                response_payload = await run_in_threadpool(
                    _create_message_and_notify_offline,
                    db,
                    club=club,
                    sender=user,
                    content=content,
                    connected_user_ids=connected_ids,
                )

                await redis_chat_manager.publish_message(club_id, response_payload)
            except Exception as e:
                logger.error(f"Error al procesar mensaje: {e}")
                await websocket.send_json({"detail": "Error procesando mensaje"})

    except WebSocketDisconnect:
        logger.info(f"Usuario {user_id} desconectado del club {club_id}")
    except Exception as e:
        logger.error(f"Error en WebSocket: {e}")
    finally:
        if user_id is not None and ws_callback is not None:
            await redis_chat_manager.unsubscribe(club_id, user_id, ws_callback)


@router.post(
    "",
    response_model=ClubResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_club(
    name: Annotated[str, Form(...)],
    description: Annotated[str, Form(...)],
    id_category: Annotated[int, Form(...)],
    profile_image: Annotated[UploadFile | None, File()] = None,
    cover_image: Annotated[UploadFile | None, File()] = None,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    clean_name = _clean_required_text(name, "name", 255)
    clean_description = _clean_required_text(description, "description", 250)

    existing = db.query(Club).filter(Club.name == clean_name).first()
    if existing:
        raise HTTPException(status_code=400, detail="Nombre de club ya existe")

    category = db.query(ClubCategory).filter(ClubCategory.id == id_category).first()
    if not category:
        raise HTTPException(status_code=400, detail="Categoría inválida")

    club = Club(
        name=clean_name,
        description=clean_description,
        profile_image=None,
        cover_image=None,
        id_category=id_category,
        id_leader=current_user.id,
    )

    try:
        db.add(club)
        db.flush()

        if profile_image is not None and profile_image.filename:
            club.profile_image = await storage_service.upload_file(
                file=profile_image,
                bucket_name=settings.R2_BUCKET_PUBLIC,
                prefix=f"clubs/{club.id}/profile",
            )

        if cover_image is not None and cover_image.filename:
            club.cover_image = await storage_service.upload_file(
                file=cover_image,
                bucket_name=settings.R2_BUCKET_PUBLIC,
                prefix=f"clubs/{club.id}/cover",
            )

        db.add(
            ClubMember(
                id_club=club.id,
                id_user=current_user.id,
            )
        )

        db.commit()
        db.refresh(club)
        return _to_club_response(club)

    except IntegrityError as err:
        db.rollback()
        raise HTTPException(status_code=400, detail="Error al crear el club") from err


@router.patch("/{club_id}", response_model=ClubResponse)
async def update_club(
    club_id: int,
    name: Annotated[str | None, Form()] = None,
    description: Annotated[str | None, Form()] = None,
    id_category: Annotated[int | None, Form()] = None,
    profile_image: Annotated[UploadFile | None, File()] = None,
    cover_image: Annotated[UploadFile | None, File()] = None,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    club = db.query(Club).filter(Club.id == club_id).first()

    if not club:
        raise HTTPException(status_code=404, detail="Club no encontrado")

    if club.id_leader != current_user.id:
        raise HTTPException(status_code=403, detail="Solo el líder puede editar")

    if name is not None:
        clean_name = _clean_required_text(name, "name", 255)
        existing = db.query(Club).filter(Club.name == clean_name).first()
        if existing and existing.id != club.id:
            raise HTTPException(400, "Nombre de club ya existe")
        club.name = clean_name

    if description is not None:
        club.description = _clean_required_text(description, "description", 250)

    if id_category is not None:
        category = db.query(ClubCategory).filter(ClubCategory.id == id_category).first()
        if not category:
            raise HTTPException(400, "Categoría inválida")
        club.id_category = id_category

    if profile_image is not None and profile_image.filename:
        if club.profile_image is not None:
            await storage_service.delete_file(
                bucket_name=settings.R2_BUCKET_PUBLIC,
                object_key=club.profile_image,
            )

        club.profile_image = await storage_service.upload_file(
            file=profile_image,
            bucket_name=settings.R2_BUCKET_PUBLIC,
            prefix=f"clubs/{club.id}/profile",
        )

    if cover_image is not None and cover_image.filename:
        if club.cover_image is not None:
            await storage_service.delete_file(
                bucket_name=settings.R2_BUCKET_PUBLIC,
                object_key=club.cover_image,
            )

        club.cover_image = await storage_service.upload_file(
            file=cover_image,
            bucket_name=settings.R2_BUCKET_PUBLIC,
            prefix=f"clubs/{club.id}/cover",
        )

    db.commit()
    db.refresh(club)

    return _to_club_response(club)


@router.delete("/{club_id}")
async def delete_club(
    club_id: int,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    club = db.query(Club).filter(Club.id == club_id).first()
    if not club:
        raise HTTPException(status_code=404, detail="Club no encontrado")

    if club.id_leader != current_user.id:
        raise HTTPException(status_code=403, detail="Solo el líder puede eliminar")

    if club.profile_image:
        await storage_service.delete_file(
            bucket_name=settings.R2_BUCKET_PUBLIC,
            object_key=club.profile_image,
        )

    if club.cover_image:
        await storage_service.delete_file(
            bucket_name=settings.R2_BUCKET_PUBLIC,
            object_key=club.cover_image,
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


@router.get("/{club_id}/members", response_model=list[ClubMemberResponse])
def get_club_members(
    club_id: int,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    club = db.query(Club).filter(Club.id == club_id).first()
    if not club:
        raise HTTPException(status_code=404, detail="Club no encontrado")

    _verify_membership(club, current_user.id, db, require_leader=False)

    regular_members = (
        db.query(User)
        .join(ClubMember, ClubMember.id_user == User.id)
        .filter(ClubMember.id_club == club_id)
        .all()
    )

    leader = db.query(User).filter(User.id == club.id_leader).first()

    result: list[ClubMemberResponse] = []
    if leader:
        result.append(
            ClubMemberResponse(
                id=leader.id,
                name=leader.name,
                photo=_build_image_url(leader.photo),
                is_leader=True,
            )
        )
    for user in regular_members:
        if user.id != club.id_leader:
            result.append(
                ClubMemberResponse(
                    id=user.id,
                    name=user.name,
                    photo=_build_image_url(user.photo),
                    is_leader=False,
                )
            )
    return result


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

    _verify_membership(club, current_user.id, db, require_leader=False)

    post = (
        db.query(ClubPost)
        .filter(ClubPost.id == post_id, ClubPost.id_club == club_id)
        .first()
    )
    if not post:
        raise HTTPException(status_code=404, detail="Publicación no encontrada")

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

    _verify_membership(club, current_user.id, db, require_leader=False)

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

    _verify_membership(club, current_user.id, db, require_leader=False)

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

    _verify_membership(club, current_user.id, db, require_leader=False)
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

    _verify_membership(club, current_user.id, db, require_leader=False)
    post = (
        db.query(ClubPost)
        .filter(ClubPost.id == post_id, ClubPost.id_club == club_id)
        .first()
    )
    if not post:
        raise HTTPException(status_code=404, detail="Publicación no encontrada")

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

    _verify_membership(club, current_user.id, db, require_leader=False)

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

    _verify_membership(club, current_user.id, db, require_leader=False)

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

    _verify_membership(club, current_user.id, db, require_leader=True)

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

    _verify_membership(club, current_user.id, db, require_leader=True)

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

    _verify_membership(club, current_user.id, db, require_leader=True)

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
