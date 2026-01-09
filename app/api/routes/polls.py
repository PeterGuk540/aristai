from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from app.core.database import get_db
from app.models.poll import Poll, PollVote
from app.models.session import Session as SessionModel
from app.schemas.poll import PollCreate, PollResponse, PollVoteCreate, PollResultsResponse

router = APIRouter()


@router.post(
    "/session/{session_id}",
    response_model=PollResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_poll(session_id: int, poll: PollCreate, db: Session = Depends(get_db)):
    """Create a new poll in a session."""
    session = db.query(SessionModel).filter(SessionModel.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    try:
        db_poll = Poll(session_id=session_id, **poll.model_dump())
        db.add(db_poll)
        db.commit()
        db.refresh(db_poll)
        return db_poll
    except SQLAlchemyError as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


@router.post("/{poll_id}/vote", status_code=status.HTTP_201_CREATED)
def vote_on_poll(poll_id: int, vote: PollVoteCreate, db: Session = Depends(get_db)):
    """Cast a vote on a poll."""
    poll = db.query(Poll).filter(Poll.id == poll_id).first()
    if not poll:
        raise HTTPException(status_code=404, detail="Poll not found")

    # Validate option_index is within range
    options = poll.options_json or []
    if vote.option_index < 0 or vote.option_index >= len(options):
        raise HTTPException(
            status_code=400,
            detail=f"option_index must be between 0 and {len(options) - 1}",
        )

    try:
        db_vote = PollVote(poll_id=poll_id, **vote.model_dump())
        db.add(db_vote)
        db.commit()
        return {"status": "vote_recorded"}
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail="User has already voted on this poll")
    except SQLAlchemyError as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


@router.get("/{poll_id}/results", response_model=PollResultsResponse)
def get_poll_results(poll_id: int, db: Session = Depends(get_db)):
    """Get poll results with vote counts."""
    poll = db.query(Poll).filter(Poll.id == poll_id).first()
    if not poll:
        raise HTTPException(status_code=404, detail="Poll not found")

    votes = db.query(PollVote).filter(PollVote.poll_id == poll_id).all()
    options = poll.options_json or []

    # Count votes per option
    vote_counts = [0] * len(options)
    for v in votes:
        if 0 <= v.option_index < len(options):
            vote_counts[v.option_index] += 1

    return PollResultsResponse(
        poll_id=poll.id,
        question=poll.question,
        options=options,  # Map options_json to options
        vote_counts=vote_counts,
        total_votes=len(votes),
    )
