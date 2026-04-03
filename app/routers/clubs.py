from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.club.club import Club
from app.models.club.club_category import ClubCategory
from app.models.club.club_member import ClubMember
from app.schemas.auth.auth import CurrentUser
from app.schemas.club.club import (
    ClubCreate,
    ClubDetailResponse,
    ClubResponse,
    ClubUpdate,
    TransferLeadershipRequest,
)

router = APIRouter(prefix="/clubs", tags=["clubs"])


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

        db.add(
            ClubMember(
                id_club=club.id,
                id_user=current_user.id,
            )
        )

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

    if payload.name:
        existing = db.query(Club).filter(Club.name == payload.name).first()
        if existing and existing.id != club.id:
            raise HTTPException(400, "Nombre de club ya existe")
        club.name = payload.name

    if payload.description:
        club.description = payload.description

    if payload.image is not None:
        club.image = payload.image

    if payload.id_category is not None:
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
        .filter(
            ClubMember.id_club == club_id,
            ClubMember.id_user == current_user.id,
        )
        .first()
    )

    if exists:
        raise HTTPException(400, "Ya eres miembro")

    db.add(
        ClubMember(
            id_club=club_id,
            id_user=current_user.id,
        )
    )
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
        .filter(
            ClubMember.id_club == club_id,
            ClubMember.id_user == current_user.id,
        )
        .first()
    )

    if not member:
        raise HTTPException(404, "No eres miembro")

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
        raise HTTPException(404, "Club no encontrado")

    if club.id_leader != current_user.id:
        raise HTTPException(403, "Solo el líder puede expulsar")

    if user_id == club.id_leader:
        raise HTTPException(400, "No puedes expulsar al líder")

    member = (
        db.query(ClubMember)
        .filter(
            ClubMember.id_club == club_id,
            ClubMember.id_user == user_id,
        )
        .first()
    )

    if not member:
        raise HTTPException(404, "No es miembro")

    db.delete(member)
    db.commit()

    return {"message": "Miembro expulsado"}


@router.post("/{club_id}/transfer-leadership")
def transfer_leadership(
    club_id: int,
    payload: TransferLeadershipRequest,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    club = db.query(Club).filter(Club.id == club_id).first()

    if not club:
        raise HTTPException(404, "Club no encontrado")

    if club.id_leader != current_user.id:
        raise HTTPException(403, "Solo el líder puede transferir")

    member = (
        db.query(ClubMember)
        .filter(
            ClubMember.id_club == club_id,
            ClubMember.id_user == payload.new_leader_id,
        )
        .first()
    )

    if not member:
        raise HTTPException(400, "Debe ser miembro")

    club.id_leader = payload.new_leader_id
    db.commit()

    return {"message": "Liderazgo transferido"}
