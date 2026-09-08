from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.club.user import UserOut


class PostImageOut(BaseModel):
    id: int
    url: str

    model_config = ConfigDict(from_attributes=True)


class CommentPreviewOut(BaseModel):
    id: int
    content: str
    created_at: datetime
    user: UserOut

    model_config = ConfigDict(from_attributes=True)


class PostResponse(BaseModel):
    id: int
    id_club: int
    content: str
    like_count: int
    user_has_liked: bool
    comment_count: int
    comments_preview: list[CommentPreviewOut]
    images: list[PostImageOut]
    author: UserOut
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PostCreate(BaseModel):
    content: str = Field(..., min_length=1, max_length=1000)


class CommentResponse(BaseModel):
    id: int
    id_post: int
    content: str
    created_at: datetime
    user: UserOut

    model_config = ConfigDict(from_attributes=True)


class CommentCreate(BaseModel):
    content: str = Field(..., min_length=1, max_length=500)


class LikeResponse(BaseModel):
    id_post: int
    id_user: int
    like_count: int
