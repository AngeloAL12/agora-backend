from fastapi import APIRouter, Depends, HTTPException
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
    ClubMembershipRequest,
    ClubResponse,
    ClubUpdate,
    RemoveMemberRequest,
    TransferLeadershipRequest,
)

router = APIRouter(prefix="", tags=["clubs"])


@router.get("/clubs", response_model=list[ClubResponse])
def get_clubs(db: Session = Depends(get_db)):
    return db.query(Club).all()


@router.get("/clubs/{club_id}", response_model=ClubDetailResponse)
def get_club(club_id: int, db: Session = Depends(get_db)):
    club = db.query(Club).filter(Club.id == club_id).first()

    if not club:
        raise HTTPException(404, "Club no encontrado")

    members_count = db.query(ClubMember).filter(ClubMember.id_club == club_id).count()

    return ClubDetailResponse(
        **club.__dict__,
        members_count=members_count,
    )


@router.post("/clubs", response_model=ClubResponse)
def create_club(
    payload: ClubCreate,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    # ✅ validar nombre único
    existing = db.query(Club).filter(Club.name == payload.name).first()
    if existing:
        raise HTTPException(400, "Nombre de club ya existe")

    # ✅ validar categoría existente
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
        raise HTTPException(
            status_code=400, detail=f"Error de integridad: {err.orig}"
        ) from err


@router.patch("/clubs/{club_id}", response_model=ClubResponse)
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

    # ✅ validar nombre único si se cambia
    if payload.name:
        existing = db.query(Club).filter(Club.name == payload.name).first()
        if existing and existing.id != club.id:
            raise HTTPException(400, "Nombre de club ya existe")
        club.name = payload.name

    if payload.description:
        club.description = payload.description

    if payload.image is not None:
        club.image = payload.image

    if payload.id_category:
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


@router.delete("/clubs/{club_id}")
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


@router.post("/join")
def join_club(
    payload: ClubMembershipRequest,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    club = db.query(Club).filter(Club.id == payload.club_id).first()

    if not club:
        raise HTTPException(404, "Club no encontrado")

    exists = (
        db.query(ClubMember)
        .filter(
            ClubMember.id_club == payload.club_id,
            ClubMember.id_user == current_user.id,
        )
        .first()
    )

    if exists:
        raise HTTPException(400, "Ya eres miembro")

    db.add(
        ClubMember(
            id_club=payload.club_id,
            id_user=current_user.id,
        )
    )
    db.commit()

    return {"message": "Te uniste al club"}


@router.delete("/members/me")
def leave_club(
    payload: ClubMembershipRequest,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    club = db.query(Club).filter(Club.id == payload.club_id).first()

    if not club:
        raise HTTPException(404, "Club no encontrado")

    if club.id_leader == current_user.id:
        raise HTTPException(400, "El líder no puede salirse")

    member = (
        db.query(ClubMember)
        .filter(
            ClubMember.id_club == payload.club_id,
            ClubMember.id_user == current_user.id,
        )
        .first()
    )

    if not member:
        raise HTTPException(404, "No eres miembro")

    db.delete(member)
    db.commit()

    return {"message": "Saliste del club"}


@router.delete("/members/{user_id}")
def remove_member(
    user_id: int,
    payload: RemoveMemberRequest,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    club = db.query(Club).filter(Club.id == payload.club_id).first()

    if not club:
        raise HTTPException(404, "Club no encontrado")

    if club.id_leader != current_user.id:
        raise HTTPException(403, "Solo el líder puede expulsar")

    member = (
        db.query(ClubMember)
        .filter(
            ClubMember.id_club == payload.club_id,
            ClubMember.id_user == user_id,
        )
        .first()
    )

    if not member:
        raise HTTPException(404, "No es miembro")

    db.delete(member)
    db.commit()

    return {"message": "Miembro expulsado"}


@router.post("/clubs/{club_id}/transfer-leadership")
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
