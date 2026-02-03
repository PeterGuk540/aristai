"""
Forum-related MCP tools.

Tools for managing posts, cases, and moderation in discussions.
"""

import logging
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from api.models.session import Session as SessionModel, Case
from api.models.post import Post
from api.models.user import User

logger = logging.getLogger(__name__)


def get_session_cases(db: Session, session_id: int) -> Dict[str, Any]:
    """
    Get case studies/discussion prompts for a session.
    """
    session = db.query(SessionModel).filter(SessionModel.id == session_id).first()
    if not session:
        return {"error": f"Session {session_id} not found"}
    
    cases = db.query(Case).filter(Case.session_id == session_id).order_by(Case.created_at.asc()).all()
    
    if not cases:
        # Check if there's a case in the session plan
        plan_case = None
        if session.plan_json:
            plan_case = session.plan_json.get("case_prompt", session.plan_json.get("case"))
        
        if plan_case:
            return {
                "message": f"No posted cases yet, but the session plan has a case study.",
                "cases": [],
                "plan_case": plan_case if isinstance(plan_case, str) else str(plan_case),
                "count": 0,
            }
        
        return {
            "message": f"No case studies have been posted for this session yet.",
            "cases": [],
            "count": 0,
        }
    
    case_list = []
    for c in cases:
        case_list.append({
            "id": c.id,
            "prompt": c.prompt,
            "has_attachments": bool(c.attachments),
            "created_at": c.created_at.isoformat() if c.created_at else None,
        })
    
    # Voice-friendly: read the first case
    first_case = cases[0].prompt
    preview = first_case[:300] + "..." if len(first_case) > 300 else first_case
    message = f"There {'is' if len(cases) == 1 else 'are'} {len(cases)} case{'s' if len(cases) != 1 else ''} posted. "
    message += f"The case is: {preview}"
    
    return {
        "message": message,
        "cases": case_list,
        "count": len(cases),
    }


def post_case(db: Session, session_id: int, prompt: str) -> Dict[str, Any]:
    """
    Post a new case study for students to discuss.
    """
    session = db.query(SessionModel).filter(SessionModel.id == session_id).first()
    if not session:
        return {"error": f"Session {session_id} not found"}
    
    try:
        case = Case(session_id=session_id, prompt=prompt)
        db.add(case)
        db.commit()
        db.refresh(case)
        
        preview = prompt[:100] + "..." if len(prompt) > 100 else prompt
        message = f"Posted case study to session '{session.title}': {preview}"
        
        return {
            "message": message,
            "id": case.id,
            "session_id": session_id,
            "prompt_preview": preview,
            "success": True,
        }
        
    except Exception as e:
        db.rollback()
        logger.exception(f"Failed to post case: {e}")
        return {"error": f"Failed to post case: {str(e)}"}


def get_session_posts(
    db: Session,
    session_id: int,
    include_content: bool = True,
) -> Dict[str, Any]:
    """
    Get all posts in a session's discussion.
    """
    session = db.query(SessionModel).filter(SessionModel.id == session_id).first()
    if not session:
        return {"error": f"Session {session_id} not found"}
    
    posts = (
        db.query(Post, User)
        .join(User, Post.user_id == User.id)
        .filter(Post.session_id == session_id)
        .order_by(Post.created_at.asc())
        .all()
    )
    
    if not posts:
        return {
            "message": "No posts in this discussion yet.",
            "posts": [],
            "count": 0,
            "pinned_count": 0,
        }
    
    post_list = []
    pinned_count = 0
    student_count = 0
    instructor_count = 0
    
    for post, user in posts:
        role = user.role.value if hasattr(user.role, 'value') else str(user.role)
        
        post_data = {
            "id": post.id,
            "user_id": user.id,
            "user_name": user.name,
            "role": role,
            "pinned": post.pinned,
            "labels": post.labels_json or [],
            "parent_post_id": post.parent_post_id,
            "created_at": post.created_at.isoformat() if post.created_at else None,
        }
        
        if include_content:
            post_data["content"] = post.content
        else:
            post_data["content_preview"] = post.content[:100] + "..." if len(post.content) > 100 else post.content
        
        post_list.append(post_data)
        
        if post.pinned:
            pinned_count += 1
        if role == "student":
            student_count += 1
        else:
            instructor_count += 1
    
    message = f"There are {len(posts)} posts: {student_count} from students, {instructor_count} from instructors. "
    if pinned_count > 0:
        message += f"{pinned_count} {'is' if pinned_count == 1 else 'are'} pinned."
    
    return {
        "message": message,
        "posts": post_list,
        "count": len(posts),
        "student_posts": student_count,
        "instructor_posts": instructor_count,
        "pinned_count": pinned_count,
    }


def get_latest_posts(
    db: Session,
    session_id: int,
    count: int = 5,
) -> Dict[str, Any]:
    """
    Get the most recent posts in a session.
    """
    session = db.query(SessionModel).filter(SessionModel.id == session_id).first()
    if not session:
        return {"error": f"Session {session_id} not found"}
    
    posts = (
        db.query(Post, User)
        .join(User, Post.user_id == User.id)
        .filter(Post.session_id == session_id)
        .order_by(Post.created_at.desc())
        .limit(count)
        .all()
    )
    
    if not posts:
        return {
            "message": "No posts yet in this discussion.",
            "posts": [],
            "count": 0,
        }
    
    post_list = []
    for post, user in posts:
        role = user.role.value if hasattr(user.role, 'value') else str(user.role)
        post_list.append({
            "id": post.id,
            "user_name": user.name,
            "role": role,
            "content": post.content,
            "pinned": post.pinned,
            "labels": post.labels_json or [],
            "created_at": post.created_at.isoformat() if post.created_at else None,
        })
    
    # Reverse to show chronological order
    post_list.reverse()
    
    # Voice-friendly summary of latest post
    latest = posts[0]
    latest_post, latest_user = latest
    preview = latest_post.content[:150] + "..." if len(latest_post.content) > 150 else latest_post.content
    message = f"Latest post from {latest_user.name}: {preview}"
    
    return {
        "message": message,
        "posts": post_list,
        "count": len(posts),
    }


def get_pinned_posts(db: Session, session_id: int) -> Dict[str, Any]:
    """
    Get all pinned posts in a session.
    """
    session = db.query(SessionModel).filter(SessionModel.id == session_id).first()
    if not session:
        return {"error": f"Session {session_id} not found"}
    
    posts = (
        db.query(Post, User)
        .join(User, Post.user_id == User.id)
        .filter(Post.session_id == session_id, Post.pinned == True)
        .order_by(Post.created_at.asc())
        .all()
    )
    
    if not posts:
        return {
            "message": "No posts have been pinned yet.",
            "posts": [],
            "count": 0,
        }
    
    post_list = []
    for post, user in posts:
        post_list.append({
            "id": post.id,
            "user_name": user.name,
            "content": post.content,
            "labels": post.labels_json or [],
            "created_at": post.created_at.isoformat() if post.created_at else None,
        })
    
    message = f"There {'is' if len(posts) == 1 else 'are'} {len(posts)} pinned post{'s' if len(posts) != 1 else ''}."
    
    return {
        "message": message,
        "posts": post_list,
        "count": len(posts),
    }


def get_post(db: Session, post_id: int) -> Dict[str, Any]:
    """
    Get details of a specific post.
    """
    result = (
        db.query(Post, User)
        .join(User, Post.user_id == User.id)
        .filter(Post.id == post_id)
        .first()
    )
    
    if not result:
        return {"error": f"Post {post_id} not found"}
    
    post, user = result
    role = user.role.value if hasattr(user.role, 'value') else str(user.role)
    
    # Get replies
    replies = (
        db.query(Post, User)
        .join(User, Post.user_id == User.id)
        .filter(Post.parent_post_id == post_id)
        .order_by(Post.created_at.asc())
        .all()
    )
    
    reply_list = []
    for reply, reply_user in replies:
        reply_list.append({
            "id": reply.id,
            "user_name": reply_user.name,
            "content": reply.content,
            "created_at": reply.created_at.isoformat() if reply.created_at else None,
        })
    
    message = f"Post {post_id} by {user.name} ({role}): {post.content[:200]}"
    if len(post.content) > 200:
        message += "..."
    if replies:
        message += f" It has {len(replies)} {'reply' if len(replies) == 1 else 'replies'}."
    
    return {
        "message": message,
        "id": post.id,
        "user_id": user.id,
        "user_name": user.name,
        "role": role,
        "content": post.content,
        "pinned": post.pinned,
        "labels": post.labels_json or [],
        "parent_post_id": post.parent_post_id,
        "replies": reply_list,
        "reply_count": len(replies),
        "created_at": post.created_at.isoformat() if post.created_at else None,
    }


def search_posts(db: Session, session_id: int, query: str) -> Dict[str, Any]:
    """
    Search for posts containing specific keywords.
    """
    session = db.query(SessionModel).filter(SessionModel.id == session_id).first()
    if not session:
        return {"error": f"Session {session_id} not found"}
    
    # Simple case-insensitive search
    posts = (
        db.query(Post, User)
        .join(User, Post.user_id == User.id)
        .filter(
            Post.session_id == session_id,
            Post.content.ilike(f"%{query}%")
        )
        .order_by(Post.created_at.asc())
        .all()
    )
    
    if not posts:
        return {
            "message": f"No posts found containing '{query}'.",
            "posts": [],
            "count": 0,
            "query": query,
        }
    
    post_list = []
    for post, user in posts:
        post_list.append({
            "id": post.id,
            "user_name": user.name,
            "content": post.content,
            "pinned": post.pinned,
            "created_at": post.created_at.isoformat() if post.created_at else None,
        })
    
    message = f"Found {len(posts)} post{'s' if len(posts) != 1 else ''} containing '{query}'."
    
    return {
        "message": message,
        "posts": post_list,
        "count": len(posts),
        "query": query,
    }


def create_post(
    db: Session,
    session_id: int,
    user_id: int,
    content: str,
) -> Dict[str, Any]:
    """
    Create a new post in a discussion.
    """
    session = db.query(SessionModel).filter(SessionModel.id == session_id).first()
    if not session:
        return {"error": f"Session {session_id} not found"}
    
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        return {"error": f"User {user_id} not found"}
    
    try:
        post = Post(
            session_id=session_id,
            user_id=user_id,
            content=content,
        )
        db.add(post)
        db.commit()
        db.refresh(post)
        
        preview = content[:100] + "..." if len(content) > 100 else content
        message = f"Posted by {user.name}: {preview}"
        
        return {
            "message": message,
            "id": post.id,
            "user_name": user.name,
            "content_preview": preview,
            "success": True,
        }
        
    except Exception as e:
        db.rollback()
        logger.exception(f"Failed to create post: {e}")
        return {"error": f"Failed to create post: {str(e)}"}


def reply_to_post(
    db: Session,
    session_id: int,
    parent_post_id: int,
    user_id: int,
    content: str,
) -> Dict[str, Any]:
    """
    Reply to an existing post.
    """
    session = db.query(SessionModel).filter(SessionModel.id == session_id).first()
    if not session:
        return {"error": f"Session {session_id} not found"}
    
    parent = db.query(Post).filter(Post.id == parent_post_id).first()
    if not parent:
        return {"error": f"Parent post {parent_post_id} not found"}
    
    if parent.session_id != session_id:
        return {"error": "Parent post belongs to a different session"}
    
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        return {"error": f"User {user_id} not found"}
    
    try:
        post = Post(
            session_id=session_id,
            user_id=user_id,
            content=content,
            parent_post_id=parent_post_id,
        )
        db.add(post)
        db.commit()
        db.refresh(post)
        
        preview = content[:100] + "..." if len(content) > 100 else content
        message = f"Reply by {user.name} to post {parent_post_id}: {preview}"
        
        return {
            "message": message,
            "id": post.id,
            "parent_post_id": parent_post_id,
            "user_name": user.name,
            "content_preview": preview,
            "success": True,
        }
        
    except Exception as e:
        db.rollback()
        logger.exception(f"Failed to create reply: {e}")
        return {"error": f"Failed to create reply: {str(e)}"}


def pin_post(db: Session, post_id: int, pinned: bool) -> Dict[str, Any]:
    """
    Pin or unpin a post.
    """
    post = db.query(Post).filter(Post.id == post_id).first()
    if not post:
        return {"error": f"Post {post_id} not found"}
    
    try:
        post.pinned = pinned
        db.commit()
        
        action = "pinned" if pinned else "unpinned"
        message = f"Post {post_id} has been {action}."
        
        return {
            "message": message,
            "id": post_id,
            "pinned": pinned,
            "success": True,
        }
        
    except Exception as e:
        db.rollback()
        logger.exception(f"Failed to pin post: {e}")
        return {"error": f"Failed to pin post: {str(e)}"}


def label_post(db: Session, post_id: int, labels: List[str]) -> Dict[str, Any]:
    """
    Set labels on a post.
    """
    post = db.query(Post).filter(Post.id == post_id).first()
    if not post:
        return {"error": f"Post {post_id} not found"}
    
    valid_labels = {"high-quality", "needs-clarification", "insightful", "misconception", "question"}
    invalid = [l for l in labels if l not in valid_labels]
    if invalid:
        return {
            "error": f"Invalid labels: {', '.join(invalid)}. Valid labels are: {', '.join(valid_labels)}"
        }
    
    try:
        post.labels_json = labels
        db.commit()
        
        if labels:
            message = f"Post {post_id} labeled as: {', '.join(labels)}."
        else:
            message = f"Labels cleared from post {post_id}."
        
        return {
            "message": message,
            "id": post_id,
            "labels": labels,
            "success": True,
        }
        
    except Exception as e:
        db.rollback()
        logger.exception(f"Failed to label post: {e}")
        return {"error": f"Failed to label post: {str(e)}"}


def mark_high_quality(db: Session, post_id: int) -> Dict[str, Any]:
    """
    Shortcut to mark a post as high-quality.
    """
    post = db.query(Post).filter(Post.id == post_id).first()
    if not post:
        return {"error": f"Post {post_id} not found"}
    
    current_labels = post.labels_json or []
    if "high-quality" not in current_labels:
        current_labels.append("high-quality")
    
    # Remove conflicting label
    if "needs-clarification" in current_labels:
        current_labels.remove("needs-clarification")
    
    return label_post(db, post_id, current_labels)


def mark_needs_clarification(db: Session, post_id: int) -> Dict[str, Any]:
    """
    Shortcut to mark a post as needing clarification.
    """
    post = db.query(Post).filter(Post.id == post_id).first()
    if not post:
        return {"error": f"Post {post_id} not found"}
    
    current_labels = post.labels_json or []
    if "needs-clarification" not in current_labels:
        current_labels.append("needs-clarification")
    
    # Remove conflicting label
    if "high-quality" in current_labels:
        current_labels.remove("high-quality")
    
    return label_post(db, post_id, current_labels)
