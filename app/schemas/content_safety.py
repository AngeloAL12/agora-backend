from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.moderation.content_report import (
    ContentReportReason,
    ContentReportStatus,
    ContentTargetType,
    ModerationAction,
)


class ContentReportCreate(BaseModel):
    target_type: ContentTargetType
    target_id: int = Field(..., gt=0)
    reason: ContentReportReason
    details: str | None = Field(default=None, max_length=1000)


class ContentReportResponse(BaseModel):
    id: int
    target_type: ContentTargetType
    target_id: int
    reported_user_id: int
    club_id: int
    reason: ContentReportReason
    details: str | None
    status: ContentReportStatus
    action_taken: ModerationAction
    created_at: datetime
    reviewed_at: datetime | None

    model_config = ConfigDict(from_attributes=True)


class AdminContentReportResponse(ContentReportResponse):
    reporter_id: int
    reporter_name: str
    reported_user_name: str
    content_snapshot: str
    content_image_urls: list[str] = Field(default_factory=list)
    moderator_id: int | None
    moderator_comment: str | None


class AdminModerationUpdate(BaseModel):
    status: ContentReportStatus
    action: ModerationAction = ModerationAction.NONE
    moderator_comment: str | None = Field(default=None, max_length=1000)

    @model_validator(mode="after")
    def validate_resolution(self) -> "AdminModerationUpdate":
        if self.status == ContentReportStatus.PENDING:
            raise ValueError("Un administrador no puede regresar un reporte a PENDING")
        if (
            self.status == ContentReportStatus.DISMISSED
            and self.action != ModerationAction.NONE
        ):
            raise ValueError("Un reporte descartado no puede aplicar acciones")
        if (
            self.action != ModerationAction.NONE
            and self.status != ContentReportStatus.RESOLVED
        ):
            raise ValueError("Las acciones requieren resolver el reporte")
        return self


class BlockedUserResponse(BaseModel):
    id: int
    name: str
    photo: str | None
    blocked_at: datetime
