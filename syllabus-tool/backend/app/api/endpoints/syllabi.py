from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime

from app.db.session import get_db
from app.models.syllabus import Syllabus

router = APIRouter()


# --- Pydantic schemas ---

class SyllabusCreate(BaseModel):
    title: str
    content: dict
    template_id: str = "BGSU_Standard"
    instructor_id: Optional[int] = None
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
    source: str
    forum_course_title: Optional[str]
    created_at: Optional[datetime]
    updated_at: Optional[datetime]

    class Config:
        from_attributes = True


# --- Endpoints ---

@router.post("/", response_model=SyllabusResponse)
def create_syllabus(data: SyllabusCreate, db: Session = Depends(get_db)):
    db_syllabus = Syllabus(
        title=data.title,
        content=data.content,
        template_id=data.template_id,
        instructor_id=data.instructor_id,
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
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
):
    query = db.query(Syllabus)
    if instructor_id is not None:
        query = query.filter(Syllabus.instructor_id == instructor_id)
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
