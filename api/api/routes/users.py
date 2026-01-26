from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from typing import List, Optional
from datetime import datetime
from api.core.database import get_db
from api.models.user import User, InstructorRequestStatus, UserRole
from api.schemas.user import UserCreate, UserUpdate, UserResponse, UserRegisterOrGet

router = APIRouter()


@router.post("/", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def create_user(user: UserCreate, db: Session = Depends(get_db)):
    """Create a new user."""
    try:
        db_user = User(**user.model_dump())
        db.add(db_user)
        db.commit()
        db.refresh(db_user)
        return db_user
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User with this email already exists"
        )
    except SQLAlchemyError as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


@router.post("/register-or-get", response_model=UserResponse)
def register_or_get_user(user_data: UserRegisterOrGet, db: Session = Depends(get_db)):
    """
    Register a new user or get existing user on login.
    Used by OAuth flows (Google, Cognito) to ensure user exists in database.

    Users are uniquely identified by email + auth_provider combination.
    This allows the same email to have separate accounts for different auth methods
    (e.g., email/password vs Google login).
    """
    try:
        # Check if user already exists by email AND auth_provider
        existing_user = db.query(User).filter(
            User.email == user_data.email,
            User.auth_provider == user_data.auth_provider
        ).first()

        if existing_user:
            # Update cognito_sub if it was provided and not set
            if user_data.cognito_sub and not existing_user.cognito_sub:
                existing_user.cognito_sub = user_data.cognito_sub
                db.commit()
                db.refresh(existing_user)
            return existing_user

        # Create new user
        db_user = User(
            name=user_data.name,
            email=user_data.email,
            auth_provider=user_data.auth_provider,
            cognito_sub=user_data.cognito_sub,
            role="student"  # Default role for new users
        )
        db.add(db_user)
        db.commit()
        db.refresh(db_user)
        return db_user
    except SQLAlchemyError as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


@router.get("/by-email/{email}", response_model=UserResponse)
def get_user_by_email(email: str, auth_provider: Optional[str] = None, db: Session = Depends(get_db)):
    """Get a user by email address, optionally filtered by auth_provider."""
    query = db.query(User).filter(User.email == email)
    if auth_provider:
        query = query.filter(User.auth_provider == auth_provider)
    user = query.first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


# IMPORTANT: This route must be before /{user_id} to avoid path conflicts
@router.get("/instructor-requests", response_model=List[UserResponse])
def list_instructor_requests(admin_user_id: int, db: Session = Depends(get_db)):
    """List all pending instructor requests. (Admin only)"""
    # Verify admin
    admin = db.query(User).filter(User.id == admin_user_id).first()
    if not admin or not admin.is_admin:
        raise HTTPException(status_code=403, detail="Admin access required")

    requests = db.query(User).filter(
        User.instructor_request_status == InstructorRequestStatus.pending
    ).order_by(User.instructor_request_date.desc()).all()
    return requests


@router.get("/{user_id}", response_model=UserResponse)
def get_user(user_id: int, db: Session = Depends(get_db)):
    """Get a user by ID."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


@router.get("/", response_model=List[UserResponse])
def list_users(
    skip: int = 0,
    limit: int = 100,
    role: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """List all users with optional role filter."""
    query = db.query(User)
    if role:
        query = query.filter(User.role == role)
    users = query.offset(skip).limit(limit).all()
    return users


@router.patch("/{user_id}", response_model=UserResponse)
def update_user(user_id: int, user_update: UserUpdate, db: Session = Depends(get_db)):
    """Update a user's name or role."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    try:
        update_data = user_update.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(user, field, value)
        db.commit()
        db.refresh(user)
        return user
    except SQLAlchemyError as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user(user_id: int, db: Session = Depends(get_db)):
    """Delete a user."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    try:
        db.delete(user)
        db.commit()
    except SQLAlchemyError as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


# Instructor Request Workflow Endpoints

@router.post("/{user_id}/request-instructor", response_model=UserResponse)
def request_instructor_status(user_id: int, db: Session = Depends(get_db)):
    """Request instructor status for a student account."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if user.role == UserRole.instructor:
        raise HTTPException(status_code=400, detail="User is already an instructor")

    if user.instructor_request_status == InstructorRequestStatus.pending:
        raise HTTPException(status_code=400, detail="Request already pending")

    try:
        user.instructor_request_status = InstructorRequestStatus.pending
        user.instructor_request_date = datetime.utcnow()
        db.commit()
        db.refresh(user)
        return user
    except SQLAlchemyError as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


@router.post("/{user_id}/approve-instructor", response_model=UserResponse)
def approve_instructor_request(user_id: int, admin_user_id: int, db: Session = Depends(get_db)):
    """Approve an instructor request and promote user to instructor role. (Admin only)"""
    # Verify admin
    admin = db.query(User).filter(User.id == admin_user_id).first()
    if not admin or not admin.is_admin:
        raise HTTPException(status_code=403, detail="Admin access required")

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if user.instructor_request_status != InstructorRequestStatus.pending:
        raise HTTPException(status_code=400, detail="No pending request for this user")

    try:
        user.role = UserRole.instructor
        user.instructor_request_status = InstructorRequestStatus.approved
        db.commit()
        db.refresh(user)
        return user
    except SQLAlchemyError as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


@router.post("/{user_id}/reject-instructor", response_model=UserResponse)
def reject_instructor_request(user_id: int, admin_user_id: int, db: Session = Depends(get_db)):
    """Reject an instructor request. (Admin only)"""
    # Verify admin
    admin = db.query(User).filter(User.id == admin_user_id).first()
    if not admin or not admin.is_admin:
        raise HTTPException(status_code=403, detail="Admin access required")

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if user.instructor_request_status != InstructorRequestStatus.pending:
        raise HTTPException(status_code=400, detail="No pending request for this user")

    try:
        user.instructor_request_status = InstructorRequestStatus.rejected
        db.commit()
        db.refresh(user)
        return user
    except SQLAlchemyError as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
