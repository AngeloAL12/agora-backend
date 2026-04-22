from typing import Annotated

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
from pydantic import ValidationError
from sqlalchemy import select
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
from app.schemas.auth.auth import CurrentUser
from app.schemas.club.club import (
    ClubCategoryResponse,
    ClubDetailResponse,
    ClubResponse,
)
from app.schemas.club.event import EventCreate, EventResponse, EventUpdate
from app.schemas.club.message import ClubMessageInput, ClubMessageResponse
from app.services.push_service import send_push_notification
from app.services.storage_service import storage_service

router = APIRouter(prefix="/clubs", tags=["clubs"])


class ClubChatConnectionManager:
    def __init__(self):
        self._connections: dict[int, dict[int, set[WebSocket]]] = {}

    def connect(self, club_id: int, user_id: int, websocket: WebSocket) -> None:
        if club_id not in self._connections:
            self._connections[club_id] = {}
        if user_id not in self._connections[club_id]:
            self._connections[club_id][user_id] = set()
        self._connections[club_id][user_id].add(websocket)

    def disconnect(self, club_id: int, user_id: int, websocket: WebSocket) -> None:
        club_connections = self._connections.get(club_id)
        if not club_connections:
            return

        user_connections = club_connections.get(user_id)
        if not user_connections:
            return

        user_connections.discard(websocket)
        if not user_connections:
            del club_connections[user_id]
        if not club_connections:
            del self._connections[club_id]

    def connected_user_ids(self, club_id: int) -> set[int]:
        return set(self._connections.get(club_id, {}).keys())

    async def broadcast(self, club_id: int, payload: dict) -> None:
        club_connections = self._connections.get(club_id, {})
        stale_sockets: list[tuple[int, WebSocket]] = []

        for user_id, sockets in club_connections.items():
            for socket in sockets:
                try:
                    await socket.send_json(payload)
                except RuntimeError:
                    stale_sockets.append((user_id, socket))

        for user_id, socket in stale_sockets:
            self.disconnect(club_id, user_id, socket)


chat_manager = ClubChatConnectionManager()


# --- Helper de validación de membresía para eventos ---
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

    membership = (
        db.query(ClubMember)
        .filter(ClubMember.id_club == club.id, ClubMember.id_user == user_id)
        .first()
    )
    return membership is not None


def _authenticate_ws_user(token: str, db: Session) -> User | None:
    try:
        payload = decode_access_token(token)
    except TokenDecodeError:
        return None

    user_id = payload.get("sub")
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
        user={
            "id": message.user.id,
            "name": message.user.name,
            "photo": message.user.photo,
        },
    ).model_dump(mode="json")


def _notify_offline_members(
    db: Session,
    *,
    club: Club,
    sender: User,
    content: str,
    connected_user_ids: set[int],
) -> None:
    member_ids = {
        member_id
        for member_id in db.execute(
            select(ClubMember.id_user).where(ClubMember.id_club == club.id)
        )
        .scalars()
        .all()
        if member_id != sender.id
    }

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
        if not push_token:
            continue

        send_push_notification(
            token=push_token,
            title=f"Nuevo mensaje en {club.name}",
            body=f"{sender.name}: {preview}",
            data={
                "category": "CLUB_CHAT",
                "id_club": club.id,
                "id_user": id_user,
            },
        )


@router.get("", response_model=list[ClubResponse])
def get_clubs(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    clubs = db.query(Club).offset(skip).limit(limit).all()
    return [_to_club_response(club) for club in clubs]


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

    offset = (page - 1) * limit
    messages = (
        db.execute(
            select(ClubMessage)
            .options(joinedload(ClubMessage.user))
            .where(ClubMessage.id_club == club_id)
            .order_by(ClubMessage.created_at.desc(), ClubMessage.id.desc())
            .offset(offset)
            .limit(limit)
        )
        .scalars()
        .all()
    )

    # Se devuelve cronológico para que el cliente renderice de arriba a abajo.
    return [ClubMessageResponse.model_validate(item) for item in reversed(messages)]


@router.websocket("/{club_id}/chat")
async def club_chat(
    websocket: WebSocket,
    club_id: int,
    token: str,
    db: Session = Depends(get_db),
):
    await websocket.accept()
    user: User | None = None
    content_error = "content debe ser requerido y tener entre 1 y 1000 caracteres"

    try:
        user = _authenticate_ws_user(token, db)
        if user is None:
            await websocket.close(code=4001)
            return

        club = db.query(Club).filter(Club.id == club_id).first()
        if not club or not _is_club_member(club, user.id, db):
            await websocket.close(code=4003)
            return

        chat_manager.connect(club_id, user.id, websocket)

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

            message = ClubMessage(id_club=club.id, id_user=user.id, content=content)
            db.add(message)
            db.commit()
            db.refresh(message)
            db.refresh(user)

            db_message = db.execute(
                select(ClubMessage)
                .options(joinedload(ClubMessage.user))
                .where(ClubMessage.id == message.id)
            ).scalar_one()

            response_payload = _build_message_payload(db_message)
            await chat_manager.broadcast(club_id, response_payload)

            _notify_offline_members(
                db,
                club=club,
                sender=user,
                content=content,
                connected_user_ids=chat_manager.connected_user_ids(club_id),
            )

    except WebSocketDisconnect:
        pass
    finally:
        if user is not None:
            chat_manager.disconnect(club_id, user.id, websocket)


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

    db.query(ClubMember).filter(ClubMember.id_club == club_id).delete()
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
