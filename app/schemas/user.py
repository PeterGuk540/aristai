from pydantic import BaseModel, EmailStr
from typing import Optional
from datetime import datetime
from enum import Enum
from app.schemas.base import BaseSchema


class UserRole(str, Enum):
    instructor = "instructor"
    student = "student"


# Request schemas
class UserCreate(BaseModel):
    name: str
    email: EmailStr
    role: UserRole = UserRole.student


class UserUpdate(BaseModel):
    name: Optional[str] = None
    role: Optional[UserRole] = None


# Response schemas
class UserResponse(BaseSchema):
    id: int
    name: str
    email: str
    role: UserRole
    created_at: datetime
