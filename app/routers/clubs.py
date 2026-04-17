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
from app.schemas.auth.auth import CurrentUser
from app.schemas.club.club import (
    ClubCategoryResponse,
    ClubDetailResponse,
    ClubResponse,
)
from app.services.storage_service import storage_service

router = APIRouter(prefix="/clubs", tags=["clubs"])


def _build_image_url(image_key: str | None) -> str | None:
    if not image_key:
        return None
    return f"{settings.R2_PUBLIC_URL}/{image_key}"


def _to_club_response(club: Club) -> ClubResponse:
    return ClubResponse.model_validate(
        {
            **club.__dict__,
            "image": _build_image_url(club.image),
        }
    )


def _to_club_detail_response(club: Club, members_count: int) -> ClubDetailResponse:
    return ClubDetailResponse.model_validate(
        {
            **club.__dict__,
            "image": _build_image_url(club.image),
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


def _clean_optional_text(
    value: str | None,
    field_name: str,
    max_length: int,
) -> str | None:
    if value is None:
        return None

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
        raise HTTPException(404, "Club no encontrado")

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
    image: Annotated[UploadFile | None, File()] = None,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    clean_name = _clean_required_text(name, "name", 255)
    clean_description = _clean_required_text(description, "description", 250)

    existing = db.query(Club).filter(Club.name == clean_name).first()
    if existing:
        raise HTTPException(400, "Nombre de club ya existe")

    category = db.query(ClubCategory).filter(ClubCategory.id == id_category).first()
    if not category:
        raise HTTPException(400, "Categoría inválida")

    club = Club(
        name=clean_name,
        description=clean_description,
        image=None,
        id_category=id_category,
        id_leader=current_user.id,
    )

    try:
        db.add(club)
        db.flush()

        if image is not None and image.filename:
            club.image = await storage_service.upload_file(
                file=image,
                bucket_name=settings.R2_BUCKET_PUBLIC,
                prefix=f"clubs/{club.id}/images",
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
    image: Annotated[UploadFile | None, File()] = None,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    club = db.query(Club).filter(Club.id == club_id).first()

    if not club:
        raise HTTPException(404, "Club no encontrado")

    if club.id_leader != current_user.id:
        raise HTTPException(403, "Solo el líder puede editar")

    if name is not None:
        clean_name = _clean_optional_text(name, "name", 255)
        existing = db.query(Club).filter(Club.name == clean_name).first()
        if existing and existing.id != club.id:
            raise HTTPException(400, "Nombre de club ya existe")
        club.name = clean_name

    if description is not None:
        clean_description = _clean_optional_text(description, "description", 250)
        club.description = clean_description

    if id_category is not None:
        category = db.query(ClubCategory).filter(ClubCategory.id == id_category).first()
        if not category:
            raise HTTPException(400, "Categoría inválida")
        club.id_category = id_category

    if image is not None and image.filename:
        if club.image is not None:
            await storage_service.delete_file(
                bucket_name=settings.R2_BUCKET_PUBLIC,
                object_key=club.image,
            )

        club.image = await storage_service.upload_file(
            file=image,
            bucket_name=settings.R2_BUCKET_PUBLIC,
            prefix=f"clubs/{club.id}/images",
        )

    db.commit()
    db.refresh(club)

    return _to_club_response(club)


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


@router.patch("/{club_id}/members/{user_id}/leader")
def transfer_leadership(
    club_id: int,
    user_id: int,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    club = db.query(Club).filter(Club.id == club_id).first()

    if not club:
        raise HTTPException(404, "Club no encontrado")

    if club.id_leader != current_user.id:
        raise HTTPException(403, "Solo el líder actual puede transferir")

    if user_id == club.id_leader:
        raise HTTPException(409, "El usuario ya es el líder actual")

    member = (
        db.query(ClubMember)
        .filter(
            ClubMember.id_club == club_id,
            ClubMember.id_user == user_id,
        )
        .first()
    )

    if not member:
        raise HTTPException(400, "El usuario destino debe ser miembro del club")

    club.id_leader = user_id
    db.commit()
    db.refresh(club)

    return {"message": "Liderazgo transferido"}
