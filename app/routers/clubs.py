from typing import Annotated

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
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.core.security import get_current_user
from app.models.club.club import Club
from app.models.club.club_category import ClubCategory
from app.models.club.club_member import ClubMember
from app.models.club.event import ClubEvent
from app.schemas.auth.auth import CurrentUser
from app.schemas.club.club import (
    ClubCategoryResponse,
    ClubDetailResponse,
    ClubResponse,
)
from app.schemas.club.event import EventCreate, EventResponse, EventUpdate
from app.services.storage_service import storage_service

router = APIRouter(prefix="/clubs", tags=["clubs"])


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
