from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models.moderation.content_report import ContentReport, ContentTargetType
from app.models.moderation.user_block import UserBlock


def get_blocked_user_ids(db: Session, viewer_id: int) -> set[int]:
    return set(
        db.execute(
            select(UserBlock.blocked_id).where(UserBlock.blocker_id == viewer_id)
        )
        .scalars()
        .all()
    )


def get_reported_target_ids(
    db: Session, viewer_id: int, target_type: ContentTargetType
) -> set[int]:
    return set(
        db.execute(
            select(ContentReport.target_id).where(
                ContentReport.reporter_id == viewer_id,
                ContentReport.target_type == target_type,
            )
        )
        .scalars()
        .all()
    )


def users_are_disconnected(
    db: Session, first_user_id: int, second_user_id: int
) -> bool:
    if first_user_id == second_user_id:
        return False
    return (
        db.execute(
            select(UserBlock.id).where(
                or_(
                    (
                        (UserBlock.blocker_id == first_user_id)
                        & (UserBlock.blocked_id == second_user_id)
                    ),
                    (
                        (UserBlock.blocker_id == second_user_id)
                        & (UserBlock.blocked_id == first_user_id)
                    ),
                )
            )
        ).scalar_one_or_none()
        is not None
    )
