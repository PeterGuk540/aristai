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
    created_at: datetime
