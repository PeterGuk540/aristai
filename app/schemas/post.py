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


# Response schemas
class PostResponse(BaseSchema):
    id: int
    session_id: int
    user_id: int
    content: str
    parent_post_id: Optional[int] = None
    labels_json: Optional[List[str]] = None
    created_at: datetime
