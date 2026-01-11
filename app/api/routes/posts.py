from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from typing import List
from app.core.database import get_db
from app.models.post import Post
from app.models.session import Session as SessionModel
from app.models.user import User
from app.schemas.post import PostCreate, PostResponse, PostLabelUpdate, PostPinUpdate, PostModerationUpdate

router = APIRouter()


@router.get("/session/{session_id}", response_model=List[PostResponse])
def get_session_posts(session_id: int, db: Session = Depends(get_db)):
    """Get all posts for a session."""
    # Check session exists for consistency with create_post
    session = db.query(SessionModel).filter(SessionModel.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    posts = (
        db.query(Post)
        .filter(Post.session_id == session_id)
        .order_by(Post.created_at.asc())
        .all()
    )
    return posts


@router.post(
    "/session/{session_id}",
    response_model=PostResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_post(session_id: int, post: PostCreate, db: Session = Depends(get_db)):
    """Create a new post in a session."""
    session = db.query(SessionModel).filter(SessionModel.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    # Validate user_id exists
    user = db.query(User).filter(User.id == post.user_id).first()
    if not user:
        raise HTTPException(status_code=400, detail="User not found")

    # Validate parent_post_id if provided
    if post.parent_post_id is not None:
        parent = db.query(Post).filter(Post.id == post.parent_post_id).first()
        if not parent:
            raise HTTPException(status_code=400, detail="Parent post not found")
        if parent.session_id != session_id:
            raise HTTPException(status_code=400, detail="Parent post belongs to different session")

    try:
        db_post = Post(session_id=session_id, **post.model_dump())
        db.add(db_post)
        db.commit()
        db.refresh(db_post)
        return db_post
    except SQLAlchemyError as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


@router.post("/{post_id}/label", response_model=PostResponse)
def label_post(post_id: int, label_update: PostLabelUpdate, db: Session = Depends(get_db)):
    """Add or update labels on a post (instructor action)."""
    post = db.query(Post).filter(Post.id == post_id).first()
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")

    try:
        post.labels_json = label_update.labels
        db.commit()
        db.refresh(post)
        return post
    except SQLAlchemyError as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


@router.post("/{post_id}/pin", response_model=PostResponse)
def pin_post(post_id: int, pin_update: PostPinUpdate, db: Session = Depends(get_db)):
    """Pin or unpin a post (instructor action)."""
    post = db.query(Post).filter(Post.id == post_id).first()
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")

    try:
        post.pinned = pin_update.pinned
        db.commit()
        db.refresh(post)
        return post
    except SQLAlchemyError as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


@router.patch("/{post_id}/moderate", response_model=PostResponse)
def moderate_post(post_id: int, moderation: PostModerationUpdate, db: Session = Depends(get_db)):
    """
    Update moderation fields on a post (instructor action).

    Allows updating labels and/or pinned status in a single request.
    Only provided fields are updated.
    """
    post = db.query(Post).filter(Post.id == post_id).first()
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")

    try:
        if moderation.labels is not None:
            post.labels_json = moderation.labels
        if moderation.pinned is not None:
            post.pinned = moderation.pinned
        db.commit()
        db.refresh(post)
        return post
    except SQLAlchemyError as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
