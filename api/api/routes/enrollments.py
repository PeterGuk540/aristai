from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError, IntegrityError
from typing import List
from pydantic import BaseModel
from datetime import datetime
import csv
import io
from api.core.database import get_db
from api.models.enrollment import Enrollment
from api.models.user import User, UserRole
from api.models.course import Course

router = APIRouter()


# Request/Response schemas
class EnrollmentCreate(BaseModel):
    user_id: int
    course_id: int


class EnrollmentResponse(BaseModel):
    id: int
    user_id: int
    course_id: int
    enrolled_at: datetime

    class Config:
        from_attributes = True


class EnrolledStudentResponse(BaseModel):
    user_id: int
    name: str
    email: str
    enrolled_at: datetime


@router.post("/", response_model=EnrollmentResponse, status_code=status.HTTP_201_CREATED)
def enroll_user(enrollment: EnrollmentCreate, db: Session = Depends(get_db)):
    """Enroll a user in a course."""
    # Validate user exists
    user = db.query(User).filter(User.id == enrollment.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Validate course exists
    course = db.query(Course).filter(Course.id == enrollment.course_id).first()
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")

    try:
        db_enrollment = Enrollment(**enrollment.model_dump())
        db.add(db_enrollment)
        db.commit()
        db.refresh(db_enrollment)
        return db_enrollment
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail="User already enrolled in this course")
    except SQLAlchemyError as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


@router.delete("/{enrollment_id}", status_code=status.HTTP_204_NO_CONTENT)
def unenroll_user(enrollment_id: int, db: Session = Depends(get_db)):
    """Remove a user from a course."""
    enrollment = db.query(Enrollment).filter(Enrollment.id == enrollment_id).first()
    if not enrollment:
        raise HTTPException(status_code=404, detail="Enrollment not found")

    try:
        db.delete(enrollment)
        db.commit()
    except SQLAlchemyError as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


@router.get("/course/{course_id}/students", response_model=List[EnrolledStudentResponse])
def get_enrolled_students(course_id: int, db: Session = Depends(get_db)):
    """Get all students enrolled in a course."""
    course = db.query(Course).filter(Course.id == course_id).first()
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")

    enrollments = (
        db.query(Enrollment, User)
        .join(User, Enrollment.user_id == User.id)
        .filter(
            Enrollment.course_id == course_id,
            User.role == UserRole.student
        )
        .all()
    )

    return [
        EnrolledStudentResponse(
            user_id=user.id,
            name=user.name,
            email=user.email,
            enrolled_at=enrollment.enrolled_at
        )
        for enrollment, user in enrollments
    ]


@router.get("/user/{user_id}/courses", response_model=List[dict])
def get_user_enrollments(user_id: int, db: Session = Depends(get_db)):
    """Get all courses a user is enrolled in."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    enrollments = (
        db.query(Enrollment, Course)
        .join(Course, Enrollment.course_id == Course.id)
        .filter(Enrollment.user_id == user_id)
        .all()
    )

    return [
        {
            "enrollment_id": enrollment.id,
            "course_id": course.id,
            "course_title": course.title,
            "enrolled_at": enrollment.enrolled_at.isoformat()
        }
        for enrollment, course in enrollments
    ]


@router.post("/course/{course_id}/enroll-all-students", status_code=status.HTTP_201_CREATED)
def enroll_all_students(course_id: int, db: Session = Depends(get_db)):
    """Enroll all students (users with role='student') in a course. Useful for setup."""
    course = db.query(Course).filter(Course.id == course_id).first()
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")

    # Get all students
    students = db.query(User).filter(User.role == UserRole.student).all()

    # Get already enrolled user IDs
    existing_enrollments = db.query(Enrollment.user_id).filter(
        Enrollment.course_id == course_id
    ).all()
    enrolled_ids = {e.user_id for e in existing_enrollments}

    # Enroll students not yet enrolled
    new_enrollments = []
    for student in students:
        if student.id not in enrolled_ids:
            enrollment = Enrollment(user_id=student.id, course_id=course_id)
            db.add(enrollment)
            new_enrollments.append(student.id)

    try:
        db.commit()
        return {
            "message": f"Enrolled {len(new_enrollments)} students",
            "newly_enrolled_user_ids": new_enrollments,
            "already_enrolled_count": len(enrolled_ids)
        }
    except SQLAlchemyError as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


class BulkEnrollRequest(BaseModel):
    user_ids: List[int]
    course_id: int


@router.post("/bulk", status_code=status.HTTP_201_CREATED)
def bulk_enroll_students(request: BulkEnrollRequest, db: Session = Depends(get_db)):
    """Bulk enroll selected students in a course."""
    course = db.query(Course).filter(Course.id == request.course_id).first()
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")

    # Get already enrolled user IDs for this course
    existing_enrollments = db.query(Enrollment.user_id).filter(
        Enrollment.course_id == request.course_id
    ).all()
    enrolled_ids = {e.user_id for e in existing_enrollments}

    # Validate all user_ids exist
    valid_users = db.query(User).filter(User.id.in_(request.user_ids)).all()
    valid_user_ids = {u.id for u in valid_users}

    invalid_ids = set(request.user_ids) - valid_user_ids
    if invalid_ids:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid user IDs: {list(invalid_ids)}"
        )

    # Enroll students not yet enrolled
    new_enrollments = []
    already_enrolled = []
    for user_id in request.user_ids:
        if user_id in enrolled_ids:
            already_enrolled.append(user_id)
        else:
            enrollment = Enrollment(user_id=user_id, course_id=request.course_id)
            db.add(enrollment)
            new_enrollments.append(user_id)

    try:
        db.commit()
        return {
            "message": f"Enrolled {len(new_enrollments)} students",
            "newly_enrolled_user_ids": new_enrollments,
            "already_enrolled_user_ids": already_enrolled
        }
    except SQLAlchemyError as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


@router.post("/course/{course_id}/upload-roster", status_code=status.HTTP_201_CREATED)
async def upload_roster_csv(course_id: int, file: UploadFile = File(...), db: Session = Depends(get_db)):
    """
    Upload a CSV roster file to create/find users and enroll them in a course.

    CSV format: email,name (header row required)
    - If user exists by email, they are enrolled
    - If user doesn't exist, a new student account is created and enrolled
    """
    course = db.query(Course).filter(Course.id == course_id).first()
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")

    # Validate file type
    if not file.filename.endswith('.csv'):
        raise HTTPException(status_code=400, detail="File must be a CSV")

    try:
        # Read file content
        content = await file.read()
        decoded = content.decode('utf-8')
        reader = csv.DictReader(io.StringIO(decoded))

        # Validate headers
        if not reader.fieldnames or 'email' not in [f.lower() for f in reader.fieldnames]:
            raise HTTPException(
                status_code=400,
                detail="CSV must have 'email' column. Optional: 'name' column"
            )

        # Normalize fieldnames for case-insensitive access
        fieldnames = {f.lower(): f for f in reader.fieldnames}

        # Get already enrolled user IDs
        existing_enrollments = db.query(Enrollment.user_id).filter(
            Enrollment.course_id == course_id
        ).all()
        enrolled_ids = {e.user_id for e in existing_enrollments}

        results = {
            "created_and_enrolled": [],
            "existing_enrolled": [],
            "already_enrolled": [],
            "errors": []
        }

        for row_num, row in enumerate(reader, start=2):  # Start at 2 (1 is header)
            try:
                # Get values with case-insensitive keys
                email = row.get(fieldnames.get('email', 'email'), '').strip().lower()
                name = row.get(fieldnames.get('name', 'name'), '').strip() if 'name' in fieldnames else ''

                if not email:
                    results["errors"].append(f"Row {row_num}: Missing email")
                    continue

                # Check if user exists
                user = db.query(User).filter(User.email == email).first()

                if user:
                    # User exists - check if already enrolled
                    if user.id in enrolled_ids:
                        results["already_enrolled"].append(email)
                    else:
                        # Enroll existing user
                        enrollment = Enrollment(user_id=user.id, course_id=course_id)
                        db.add(enrollment)
                        enrolled_ids.add(user.id)
                        results["existing_enrolled"].append(email)
                else:
                    # Create new user as student
                    if not name:
                        name = email.split('@')[0]  # Use email prefix as name if not provided

                    new_user = User(
                        name=name,
                        email=email,
                        role=UserRole.student
                    )
                    db.add(new_user)
                    db.flush()  # Get the user ID

                    # Enroll new user
                    enrollment = Enrollment(user_id=new_user.id, course_id=course_id)
                    db.add(enrollment)
                    enrolled_ids.add(new_user.id)
                    results["created_and_enrolled"].append(email)

            except Exception as e:
                results["errors"].append(f"Row {row_num}: {str(e)}")

        db.commit()

        return {
            "message": f"Processed roster for course {course_id}",
            "created_and_enrolled_count": len(results["created_and_enrolled"]),
            "existing_enrolled_count": len(results["existing_enrolled"]),
            "already_enrolled_count": len(results["already_enrolled"]),
            "error_count": len(results["errors"]),
            "details": results
        }

    except csv.Error as e:
        raise HTTPException(status_code=400, detail=f"Invalid CSV format: {str(e)}")
    except UnicodeDecodeError:
        raise HTTPException(status_code=400, detail="File must be UTF-8 encoded")
    except SQLAlchemyError as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
