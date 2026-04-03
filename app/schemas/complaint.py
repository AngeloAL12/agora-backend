from datetime import datetime

from pydantic import BaseModel

from app.models.complaint import ComplaintStatus


class ComplaintOut(BaseModel):
    id: int
    id_user: int
    title: str
    description: str
    status: ComplaintStatus
    has_appealed: bool
    created_at: datetime

    class Config:
        from_attributes = True


class ComplaintStatusUpdate(BaseModel):
    status: ComplaintStatus
