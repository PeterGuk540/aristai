"""
Poll-related MCP tools.

Tools for creating polls and viewing results.
"""

import logging
from typing import Any, Dict, List

from sqlalchemy.orm import Session

from api.models.session import Session as SessionModel
from api.models.poll import Poll, PollVote
from api.models.user import User

logger = logging.getLogger(__name__)


def get_session_polls(db: Session, session_id: int) -> Dict[str, Any]:
    """
    Get all polls for a session.
    """
    session = db.query(SessionModel).filter(SessionModel.id == session_id).first()
    if not session:
        return {"error": f"Session {session_id} not found"}
    
    polls = db.query(Poll).filter(Poll.session_id == session_id).order_by(Poll.created_at.desc()).all()
    
    if not polls:
        return {
            "message": "No polls have been created for this session yet.",
            "polls": [],
            "count": 0,
        }
    
    poll_list = []
    for p in polls:
        vote_count = db.query(PollVote).filter(PollVote.poll_id == p.id).count()
        poll_list.append({
            "id": p.id,
            "question": p.question,
            "options": p.options_json,
            "vote_count": vote_count,
            "created_at": p.created_at.isoformat() if p.created_at else None,
        })
    
    # Voice-friendly: describe the most recent poll
    latest = polls[0]
    latest_votes = db.query(PollVote).filter(PollVote.poll_id == latest.id).count()
    message = f"There {'is' if len(polls) == 1 else 'are'} {len(polls)} poll{'s' if len(polls) != 1 else ''}. "
    message += f"Latest poll: '{latest.question}' with {latest_votes} votes."
    
    return {
        "message": message,
        "polls": poll_list,
        "count": len(polls),
    }


def get_poll_results(db: Session, poll_id: int) -> Dict[str, Any]:
    """
    Get detailed results of a specific poll.
    """
    poll = db.query(Poll).filter(Poll.id == poll_id).first()
    if not poll:
        return {"error": f"Poll {poll_id} not found"}
    
    votes = db.query(PollVote).filter(PollVote.poll_id == poll_id).all()
    options = poll.options_json or []
    
    # Count votes per option
    vote_counts = [0] * len(options)
    for v in votes:
        if 0 <= v.option_index < len(options):
            vote_counts[v.option_index] += 1
    
    total_votes = len(votes)
    
    # Calculate percentages
    percentages = []
    for count in vote_counts:
        pct = (count / total_votes * 100) if total_votes > 0 else 0
        percentages.append(round(pct, 1))
    
    # Build results list
    results = []
    for i, opt in enumerate(options):
        results.append({
            "option_index": i,
            "option_text": opt,
            "votes": vote_counts[i],
            "percentage": percentages[i],
        })
    
    # Sort by votes descending for easy reading
    results_sorted = sorted(results, key=lambda x: x["votes"], reverse=True)
    
    # Voice-friendly summary
    message = f"Poll: '{poll.question}'. Total votes: {total_votes}. "
    if total_votes > 0:
        winner = results_sorted[0]
        message += f"Leading option: '{winner['option_text']}' with {winner['percentage']}%."
    else:
        message += "No votes yet."
    
    return {
        "message": message,
        "poll_id": poll_id,
        "question": poll.question,
        "options": options,
        "total_votes": total_votes,
        "results": results_sorted,
        "vote_counts": vote_counts,
        "percentages": percentages,
    }


def create_poll(
    db: Session,
    session_id: int,
    question: str,
    options: List[str],
) -> Dict[str, Any]:
    """
    Create a new poll in a session.
    """
    session = db.query(SessionModel).filter(SessionModel.id == session_id).first()
    if not session:
        return {"error": f"Session {session_id} not found"}
    
    if len(options) < 2:
        return {"error": "Poll needs at least 2 options"}
    
    if len(options) > 10:
        return {"error": "Poll can have at most 10 options"}
    
    try:
        poll = Poll(
            session_id=session_id,
            question=question,
            options_json=options,
        )
        db.add(poll)
        db.commit()
        db.refresh(poll)
        
        options_str = ", ".join(f"'{o}'" for o in options[:3])
        if len(options) > 3:
            options_str += f", and {len(options) - 3} more"
        
        message = f"Created poll: '{question}'. Options: {options_str}."
        
        return {
            "message": message,
            "id": poll.id,
            "question": question,
            "options": options,
            "success": True,
        }
        
    except Exception as e:
        db.rollback()
        logger.exception(f"Failed to create poll: {e}")
        return {"error": f"Failed to create poll: {str(e)}"}


def vote_on_poll(
    db: Session,
    poll_id: int,
    user_id: int,
    option_index: int,
) -> Dict[str, Any]:
    """
    Cast a vote on a poll.
    """
    poll = db.query(Poll).filter(Poll.id == poll_id).first()
    if not poll:
        return {"error": f"Poll {poll_id} not found"}
    
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        return {"error": f"User {user_id} not found"}
    
    options = poll.options_json or []
    if option_index < 0 or option_index >= len(options):
        return {"error": f"Invalid option index. Must be between 0 and {len(options) - 1}"}
    
    # Check if user already voted
    existing = db.query(PollVote).filter(
        PollVote.poll_id == poll_id,
        PollVote.user_id == user_id,
    ).first()
    
    if existing:
        return {
            "error": f"User {user.name} has already voted on this poll",
            "existing_vote": options[existing.option_index],
        }
    
    try:
        vote = PollVote(
            poll_id=poll_id,
            user_id=user_id,
            option_index=option_index,
        )
        db.add(vote)
        db.commit()
        
        selected_option = options[option_index]
        message = f"{user.name} voted for '{selected_option}'."
        
        return {
            "message": message,
            "poll_id": poll_id,
            "user_name": user.name,
            "selected_option": selected_option,
            "option_index": option_index,
            "success": True,
        }
        
    except Exception as e:
        db.rollback()
        logger.exception(f"Failed to vote: {e}")
        return {"error": f"Failed to cast vote: {str(e)}"}
