from pydantic import BaseModel, EmailStr
from typing import Optional
from datetime import datetime
from enum import Enum
from api.schemas.base import BaseSchema


class UserRole(str, Enum):
    instructor = "instructor"
    student = "student"


class AuthProvider(str, Enum):
    cognito = "cognito"
    google = "google"
    microsoft = "microsoft"


class InstructorRequestStatus(str, Enum):
    none = "none"
    pending = "pending"
    approved = "approved"
    rejected = "rejected"


# Request schemas
class UserCreate(BaseModel):
    name: str
    email: EmailStr
    role: UserRole = UserRole.student
    auth_provider: AuthProvider = AuthProvider.cognito
    cognito_sub: Optional[str] = None


class UserRegisterOrGet(BaseModel):
    """Schema for registering a new user or getting existing one on login"""
    name: str
    email: EmailStr
    auth_provider: AuthProvider
    cognito_sub: Optional[str] = None


class UserUpdate(BaseModel):
    name: Optional[str] = None
    role: Optional[UserRole] = None


# Response schemas
class UserResponse(BaseSchema):
    id: int
    name: str
    email: str
    role: UserRole
    auth_provider: AuthProvider
    cognito_sub: Optional[str] = None
    instructor_request_status: InstructorRequestStatus = InstructorRequestStatus.none
    instructor_request_date: Optional[datetime] = None
    is_admin: bool = False
    created_at: datetime
