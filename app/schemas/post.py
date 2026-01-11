from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
from app.schemas.base import BaseSchema


# Request schemas
class PostCreate(BaseModel):
    user_id: int
    content: str
    parent_post_id: Optional[int] = None


class PostLabelUpdate(BaseModel):
    labels: List[str]


class PostPinUpdate(BaseModel):
    pinned: bool


class PostModerationUpdate(BaseModel):
    """Combined moderation update for labels and/or pinned status."""
    labels: Optional[List[str]] = None
    pinned: Optional[bool] = None


# Response schemas
class PostResponse(BaseSchema):
    id: int
    session_id: int
    user_id: int
    content: str
    parent_post_id: Optional[int] = None
    labels_json: Optional[List[str]] = None
    pinned: bool = False
    created_at: datetime
