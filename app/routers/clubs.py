from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.club.club import Club
from app.models.club.club_category import ClubCategory
from app.models.club.club_member import ClubMember
from app.models.club.event import ClubEvent
from app.schemas.auth.auth import CurrentUser
from app.schemas.club.club import (
    ClubCreate,
    ClubDetailResponse,
    ClubResponse,
    ClubUpdate,
)
from app.schemas.club.event import EventCreate, EventResponse, EventUpdate

router = APIRouter(prefix="/clubs", tags=["clubs"])


# --- Helper de validación de membresía para eventos ---
def _verify_membership(
    club: Club, user_id: int, db: Session, require_leader: bool = False
):
    if require_leader:
        if club.id_leader != user_id:
            raise HTTPException(403, "Solo el líder puede realizar esta acción")
        return

    # Si es el líder, automáticamente tiene acceso como miembro
    if club.id_leader == user_id:
        return

    is_member = (
        db.query(ClubMember)
        .filter(ClubMember.id_club == club.id, ClubMember.id_user == user_id)
        .first()
    )

    if not is_member:
        raise HTTPException(403, "El usuario no es miembro del club")


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
        raise HTTPException(404, "Club no encontrado")

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
        raise HTTPException(400, "Nombre de club ya existe")

    category = (
        db.query(ClubCategory).filter(ClubCategory.id == payload.id_category).first()
    )
    if not category:
        raise HTTPException(400, "Categoría inválida")

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
        raise HTTPException(404, "Club no encontrado")

    if club.id_leader != current_user.id:
        raise HTTPException(403, "Solo el líder puede editar")

    if "name" in payload.model_fields_set and payload.name is not None:
        existing = db.query(Club).filter(Club.name == payload.name).first()
        if existing and existing.id != club.id:
            raise HTTPException(400, "Nombre de club ya existe")
        club.name = payload.name

    if "description" in payload.model_fields_set and payload.description is not None:
        club.description = payload.description

    if "image" in payload.model_fields_set:
        club.image = payload.image

    if "id_category" in payload.model_fields_set and payload.id_category is not None:
        category = (
            db.query(ClubCategory)
            .filter(ClubCategory.id == payload.id_category)
            .first()
        )
        if not category:
            raise HTTPException(400, "Categoría inválida")
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
        raise HTTPException(404, "Club no encontrado")

    if club.id_leader != current_user.id:
        raise HTTPException(403, "Solo el líder puede eliminar")

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
        raise HTTPException(404, "Club no encontrado")

    exists = (
        db.query(ClubMember)
        .filter(ClubMember.id_club == club_id, ClubMember.id_user == current_user.id)
        .first()
    )

    if exists:
        raise HTTPException(400, "Ya eres miembro")

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
        raise HTTPException(404, "Club no encontrado")

    if club.id_leader == current_user.id:
        raise HTTPException(400, "El líder no puede salirse")

    member = (
        db.query(ClubMember)
        .filter(ClubMember.id_club == club_id, ClubMember.id_user == current_user.id)
        .first()
    )

    if not member:
        raise HTTPException(404, "No eres miembro")

    db.delete(member)
    db.commit()

    return {"message": "Saliste del club"}


# ==========================================
# NUEVOS ENDPOINTS: EVENTOS DEL CLUB
# ==========================================


@router.get("/{club_id}/events", response_model=list[EventResponse])
def list_club_events(
    club_id: int,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    club = db.query(Club).filter(Club.id == club_id).first()
    if not club:
        raise HTTPException(404, "Club no encontrado")

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
        raise HTTPException(404, "Club no encontrado")

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
        raise HTTPException(404, "Club no encontrado")

    _verify_membership(club, current_user.id, db, require_leader=True)

    event = (
        db.query(ClubEvent)
        .filter(ClubEvent.id == event_id, ClubEvent.id_club == club_id)
        .first()
    )

    if not event:
        raise HTTPException(404, "Evento no encontrado")

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
        raise HTTPException(404, "Club no encontrado")

    _verify_membership(club, current_user.id, db, require_leader=True)

    event = (
        db.query(ClubEvent)
        .filter(ClubEvent.id == event_id, ClubEvent.id_club == club_id)
        .first()
    )

    if not event:
        raise HTTPException(404, "Evento no encontrado")

    db.delete(event)
    db.commit()
    return None
