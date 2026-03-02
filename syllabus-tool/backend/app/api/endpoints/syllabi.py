import logging
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import or_
from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime

from app.db.session import get_db
from app.models.syllabus import Syllabus
from app.services import forum_client, schema_mapper

logger = logging.getLogger(__name__)
router = APIRouter()


# --- Pydantic schemas ---

class SyllabusCreate(BaseModel):
    title: str
    content: dict
    template_id: str = "BGSU_Standard"
    instructor_id: Optional[int] = None
    cognito_sub: Optional[str] = None
    source: str = "standalone"
    forum_course_title: Optional[str] = None


class SyllabusUpdate(BaseModel):
    title: Optional[str] = None
    content: Optional[dict] = None


class SyllabusResponse(BaseModel):
    id: int
    title: str
    content: dict
    template_id: str
    instructor_id: Optional[int]
    cognito_sub: Optional[str]
    source: str
    forum_course_title: Optional[str]
    created_at: Optional[datetime]
    updated_at: Optional[datetime]

    class Config:
        from_attributes = True


class PushToForumResponse(BaseModel):
    forum_course_id: int
    forum_course_title: str
    join_code: Optional[str] = None


# --- Endpoints ---

@router.post("/", response_model=SyllabusResponse)
async def create_syllabus(data: SyllabusCreate, db: Session = Depends(get_db)):
    instructor_id = data.instructor_id

    # If cognito_sub provided but no instructor_id, try to resolve via forum
    if data.cognito_sub and not instructor_id:
        try:
            forum_user = await forum_client.resolve_cognito_sub(data.cognito_sub)
            if forum_user:
                instructor_id = forum_user["id"]
        except Exception as exc:
            logger.warning(f"Best-effort cognito_sub resolution failed: {exc}")

    db_syllabus = Syllabus(
        title=data.title,
        content=data.content,
        template_id=data.template_id,
        instructor_id=instructor_id,
        cognito_sub=data.cognito_sub,
        source=data.source,
        forum_course_title=data.forum_course_title,
    )
    db.add(db_syllabus)
    db.commit()
    db.refresh(db_syllabus)
    return db_syllabus


@router.get("/", response_model=List[SyllabusResponse])
def list_syllabi(
    instructor_id: Optional[int] = Query(None),
    cognito_sub: Optional[str] = Query(None),
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
):
    query = db.query(Syllabus)

    # Filter by instructor_id OR cognito_sub (either identifies the user)
    if instructor_id is not None and cognito_sub:
        query = query.filter(
            or_(Syllabus.instructor_id == instructor_id, Syllabus.cognito_sub == cognito_sub)
        )
    elif instructor_id is not None:
        query = query.filter(Syllabus.instructor_id == instructor_id)
    elif cognito_sub:
        query = query.filter(Syllabus.cognito_sub == cognito_sub)

    syllabi = query.order_by(Syllabus.created_at.desc()).offset(skip).limit(limit).all()
    return syllabi


@router.get("/{syllabus_id}", response_model=SyllabusResponse)
def get_syllabus(syllabus_id: int, db: Session = Depends(get_db)):
    syllabus = db.query(Syllabus).filter(Syllabus.id == syllabus_id).first()
    if syllabus is None:
        raise HTTPException(status_code=404, detail="Syllabus not found")
    return syllabus


@router.put("/{syllabus_id}", response_model=SyllabusResponse)
def update_syllabus(syllabus_id: int, data: SyllabusUpdate, db: Session = Depends(get_db)):
    db_syllabus = db.query(Syllabus).filter(Syllabus.id == syllabus_id).first()
    if db_syllabus is None:
        raise HTTPException(status_code=404, detail="Syllabus not found")

    update_data = data.dict(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_syllabus, key, value)

    db.commit()
    db.refresh(db_syllabus)
    return db_syllabus


@router.delete("/{syllabus_id}")
def delete_syllabus(syllabus_id: int, db: Session = Depends(get_db)):
    db_syllabus = db.query(Syllabus).filter(Syllabus.id == syllabus_id).first()
    if db_syllabus is None:
        raise HTTPException(status_code=404, detail="Syllabus not found")

    db.delete(db_syllabus)
    db.commit()
    return {"message": "Syllabus deleted successfully"}


@router.post("/{syllabus_id}/push-to-forum", response_model=PushToForumResponse)
async def push_to_forum(
    syllabus_id: int,
    instructor_id: Optional[int] = Query(None),
    cognito_sub: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    """Push a saved syllabus to the forum as a new course."""
    db_syllabus = db.query(Syllabus).filter(Syllabus.id == syllabus_id).first()
    if db_syllabus is None:
        raise HTTPException(status_code=404, detail="Syllabus not found")

    # Resolve the forum user ID
    forum_user_id = instructor_id or db_syllabus.instructor_id
    if not forum_user_id:
        # Try resolving from cognito_sub
        sub = cognito_sub or db_syllabus.cognito_sub
        if sub:
            forum_user = await forum_client.resolve_cognito_sub(sub)
            if forum_user:
                forum_user_id = forum_user["id"]

    if not forum_user_id:
        raise HTTPException(
            status_code=400,
            detail="Cannot determine forum user. Provide instructor_id or cognito_sub.",
        )

    # Map syllabus content to forum course schema
    title = db_syllabus.title or "Untitled Course"
    mapped = schema_mapper.syllabus_to_forum_course(db_syllabus.content or {}, title)
    mapped["created_by"] = forum_user_id

    # Create the course in the forum
    try:
        course = await forum_client.create_course(mapped)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except Exception as exc:
        logger.error(f"push-to-forum failed: {exc}")
        raise HTTPException(status_code=502, detail=f"Failed to create forum course: {exc}")

    return PushToForumResponse(
        forum_course_id=course["id"],
        forum_course_title=course.get("title", title),
        join_code=course.get("join_code"),
    )
