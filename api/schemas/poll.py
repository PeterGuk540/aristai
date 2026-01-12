from pydantic import BaseModel
from typing import List
from datetime import datetime
from api.schemas.base import BaseSchema


# Request schemas
class PollCreate(BaseModel):
    question: str
    options_json: List[str]


class PollVoteCreate(BaseModel):
    user_id: int
    option_index: int


# Response schemas
class PollResponse(BaseSchema):
    id: int
    session_id: int
    question: str
    options_json: List[str]
    created_at: datetime


class PollResultsResponse(BaseModel):
    """Computed response for poll results (not directly from ORM)."""
    poll_id: int
    question: str
    options: List[str]  # Mapped from options_json in route
    vote_counts: List[int]
    total_votes: int
