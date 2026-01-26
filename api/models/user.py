from sqlalchemy import Column, Integer, String, DateTime, UniqueConstraint, Boolean
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import enum
from api.core.database import Base


class UserRole(str, enum.Enum):
    instructor = "instructor"
    student = "student"


class AuthProvider(str, enum.Enum):
    cognito = "cognito"
    google = "google"
    microsoft = "microsoft"


class InstructorRequestStatus(str, enum.Enum):
    none = "none"
    pending = "pending"
    approved = "approved"
    rejected = "rejected"


class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        # Unique constraint on (email, auth_provider) allows same email with different auth methods
        UniqueConstraint('email', 'auth_provider', name='ix_users_email_auth_provider'),
    )

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    email = Column(String(255), nullable=False, index=True)  # Not unique alone, unique with auth_provider
    role = Column(SAEnum(UserRole, name="user_role"), nullable=False, default=UserRole.student)
    auth_provider = Column(SAEnum(AuthProvider, name="auth_provider"), nullable=False, default=AuthProvider.cognito)
    cognito_sub = Column(String(255), nullable=True, index=True)  # Cognito user sub ID
    instructor_request_status = Column(
        SAEnum(InstructorRequestStatus, name="instructor_request_status"),
        nullable=False,
        default=InstructorRequestStatus.none
    )
    instructor_request_date = Column(DateTime(timezone=True), nullable=True)
    is_admin = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    posts = relationship("Post", back_populates="user")
    poll_votes = relationship("PollVote", back_populates="user")
    enrollments = relationship("Enrollment", back_populates="user", cascade="all, delete-orphan")
