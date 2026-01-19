# AristAI Enhancement Implementation Plan

This document outlines the implementation plan for addressing the identified issues and adding new features to AristAI.

---

## Overview of Changes

| # | Feature | Priority | Files Affected |
|---|---------|----------|----------------|
| 1 | Session listing by course | High | `api/routes/courses.py`, `ui_streamlit/app.py` |
| 2 | Role-based UI | High | `ui_streamlit/app.py` |
| 3 | Display Cases in Discussion | Critical | `ui_streamlit/app.py`, `api/routes/sessions.py` |
| 4 | Enrollment model + Participation tracking | Medium | New model, `workflows/report.py`, migration |
| 5 | Answer scoring in reports | Medium | `workflows/report.py`, `workflows/prompts/report_prompts.py` |

---

## 1. Session Listing by Course

### 1.1 Backend: Add API Endpoint

**File:** `api/api/routes/courses.py`

Add new endpoint after line 44:

```python
from api.models.session import Session as SessionModel
from api.schemas.session import SessionResponse

@router.get("/{course_id}/sessions", response_model=List[SessionResponse])
def list_course_sessions(
    course_id: int,
    status: str = None,  # Optional filter by status
    db: Session = Depends(get_db)
):
    """List all sessions for a course."""
    course = db.query(Course).filter(Course.id == course_id).first()
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")

    query = db.query(SessionModel).filter(SessionModel.course_id == course_id)

    if status:
        query = query.filter(SessionModel.status == status)

    sessions = query.order_by(SessionModel.created_at.desc()).all()
    return sessions
```

### 1.2 Frontend: Replace Manual ID Input with Dropdown

**File:** `ui_streamlit/app.py`

Replace the "View Sessions" tab (lines 194-272) with:

```python
with tab1:
    st.subheader("Course Sessions")
    st.markdown("_Sessions are generated from the course syllabus or created manually._")

    # Fetch sessions for this course
    sessions = api_get(f"/courses/{course_id}/sessions")

    if sessions:
        # Create dropdown options
        session_options = {
            f"{s['title']} (ID: {s['id']}) - {s['status'].upper()}": s['id']
            for s in sessions
        }

        selected_session = st.selectbox(
            "Select Session to View",
            list(session_options.keys()),
            key="view_session_select"
        )

        if selected_session:
            session_id = session_options[selected_session]
            session = api_get(f"/sessions/{session_id}")

            if session:
                # ... existing session display code (lines 209-272)
    else:
        st.info("No sessions found for this course. Create one in the 'Create Session' tab or generate plans from the Courses page.")
```

---

## 2. Role-Based UI

### 2.1 Add User Selection to Sidebar

**File:** `ui_streamlit/app.py`

Add after line 25 (after navigation radio):

```python
st.sidebar.markdown("---")
st.sidebar.markdown("**User Context**")

# Fetch users for selection
users = api_get("/users/")
if users:
    user_options = {f"{u['name']} ({u['role']})": u for u in users}
    selected_user_label = st.sidebar.selectbox(
        "Acting as:",
        list(user_options.keys()),
        key="current_user"
    )
    current_user = user_options[selected_user_label]
    st.session_state["current_user"] = current_user
    st.session_state["is_instructor"] = current_user["role"] == "instructor"
else:
    st.session_state["current_user"] = None
    st.session_state["is_instructor"] = False
```

### 2.2 Conditionally Render Forum Page

**File:** `ui_streamlit/app.py`

Modify the Forum page (lines 347-475):

```python
elif page == "Forum":
    st.title("Discussion Forum")

    is_instructor = st.session_state.get("is_instructor", False)
    current_user = st.session_state.get("current_user")

    session_id = st.number_input("Session ID", min_value=1, step=1, key="forum_session_id")

    if session_id:
        session = api_get(f"/sessions/{session_id}")
        if session:
            status = session['status']
            st.markdown(f"**{session['title']}** - :{get_status_color(status)}[{status.upper()}]")

        # Different tabs based on role
        if is_instructor:
            tab1, tab2, tab3 = st.tabs(["Discussion", "Post Case", "Post Reply"])
        else:
            tab1, tab2 = st.tabs(["Discussion", "Post Reply"])
            tab3 = None  # Students don't see Post Case

        with tab1:
            # ... existing Discussion tab code

            # Moderation controls only for instructors
            if is_instructor:
                with st.expander("Moderate", expanded=False):
                    # ... existing moderation code
            # Students just see posts without moderation options

        if is_instructor and tab2:
            with tab2:
                # Post Case tab (instructor only)
                st.subheader("Post Case (Instructor)")
                # ... existing Post Case code

        # Post Reply tab (for both, but use correct tab reference)
        reply_tab = tab3 if is_instructor else tab2
        with reply_tab:
            st.subheader("Post Reply")
            # Auto-fill user_id from current user
            if current_user:
                st.info(f"Posting as: {current_user['name']}")
                user_id = current_user['id']
            else:
                user_id = st.number_input("Your User ID", min_value=1, step=1, value=1)
            # ... rest of Post Reply code
```

### 2.3 Hide Instructor Console from Students

**File:** `ui_streamlit/app.py`

Modify navigation (lines 22-25):

```python
# Determine available pages based on role
is_instructor = st.session_state.get("is_instructor", True)  # Default True for first load

if is_instructor:
    available_pages = ["Courses", "Sessions", "Forum", "Instructor Console", "Reports"]
else:
    available_pages = ["Courses", "Sessions", "Forum", "Reports"]

page = st.sidebar.radio("Navigation", available_pages)
```

---

## 3. Display Cases in Discussion Tab

### 3.1 Add API Endpoint to Get Session Cases

**File:** `api/api/routes/sessions.py`

Add new endpoint:

```python
from typing import List
from api.schemas.session import CaseResponse

@router.get("/{session_id}/cases", response_model=List[CaseResponse])
def get_session_cases(session_id: int, db: Session = Depends(get_db)):
    """Get all cases for a session."""
    session = db.query(SessionModel).filter(SessionModel.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    return session.cases
```

### 3.2 Display Cases at Top of Discussion Tab

**File:** `ui_streamlit/app.py`

In the Discussion tab (tab1), add before showing posts:

```python
with tab1:
    st.subheader("Discussion Thread")

    col1, col2 = st.columns([1, 4])
    with col1:
        if st.button("Refresh"):
            st.rerun()

    # === NEW: Display Cases First ===
    cases = api_get(f"/sessions/{session_id}/cases")
    if cases:
        st.markdown("### 📋 Case Study / Discussion Prompt")
        for case in cases:
            with st.container():
                st.markdown(f"**Posted:** {format_timestamp(case.get('created_at'))}")
                st.info(case['prompt'])
                if case.get('attachments'):
                    st.caption(f"Attachments: {len(case['attachments'])} file(s)")
        st.markdown("---")
        st.markdown("### 💬 Student Responses")
    # === END NEW ===

    posts = api_get(f"/posts/session/{session_id}")
    # ... rest of existing posts display code
```

---

## 4. Enrollment Model & Participation Tracking

### 4.1 Create Enrollment Model

**New File:** `api/models/enrollment.py`

```python
from sqlalchemy import Column, Integer, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from api.core.database import Base


class Enrollment(Base):
    __tablename__ = "enrollments"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    course_id = Column(Integer, ForeignKey("courses.id", ondelete="CASCADE"), nullable=False, index=True)
    enrolled_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    user = relationship("User", back_populates="enrollments")
    course = relationship("Course", back_populates="enrollments")

    __table_args__ = (
        UniqueConstraint('user_id', 'course_id', name='unique_enrollment'),
    )
```

### 4.2 Update User and Course Models

**File:** `api/models/user.py` - Add relationship:

```python
enrollments = relationship("Enrollment", back_populates="user", cascade="all, delete-orphan")
```

**File:** `api/models/course.py` - Add relationship:

```python
enrollments = relationship("Enrollment", back_populates="course", cascade="all, delete-orphan")
```

### 4.3 Create Database Migration

**New File:** `alembic/versions/XXX_add_enrollments.py`

```python
"""Add enrollments table

Revision ID: XXX
"""
from alembic import op
import sqlalchemy as sa

def upgrade():
    op.create_table(
        'enrollments',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('course_id', sa.Integer(), nullable=False),
        sa.Column('enrolled_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['course_id'], ['courses.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'course_id', name='unique_enrollment')
    )
    op.create_index('ix_enrollments_user_id', 'enrollments', ['user_id'])
    op.create_index('ix_enrollments_course_id', 'enrollments', ['course_id'])

def downgrade():
    op.drop_table('enrollments')
```

### 4.4 Add Enrollment API Endpoints

**New File:** `api/api/routes/enrollments.py`

```python
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from api.core.database import get_db
from api.models.enrollment import Enrollment
from api.models.user import User
from api.models.course import Course
from pydantic import BaseModel

router = APIRouter()

class EnrollmentCreate(BaseModel):
    user_id: int
    course_id: int

class EnrollmentResponse(BaseModel):
    id: int
    user_id: int
    course_id: int
    enrolled_at: str

    class Config:
        from_attributes = True

@router.post("/", response_model=EnrollmentResponse, status_code=status.HTTP_201_CREATED)
def enroll_user(enrollment: EnrollmentCreate, db: Session = Depends(get_db)):
    """Enroll a user in a course."""
    # Validate user and course exist
    user = db.query(User).filter(User.id == enrollment.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    course = db.query(Course).filter(Course.id == enrollment.course_id).first()
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")

    # Check if already enrolled
    existing = db.query(Enrollment).filter(
        Enrollment.user_id == enrollment.user_id,
        Enrollment.course_id == enrollment.course_id
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="User already enrolled")

    db_enrollment = Enrollment(**enrollment.model_dump())
    db.add(db_enrollment)
    db.commit()
    db.refresh(db_enrollment)
    return db_enrollment

@router.get("/course/{course_id}/students", response_model=List[dict])
def get_enrolled_students(course_id: int, db: Session = Depends(get_db)):
    """Get all students enrolled in a course."""
    enrollments = db.query(Enrollment, User).join(User).filter(
        Enrollment.course_id == course_id,
        User.role == "student"
    ).all()

    return [
        {"user_id": u.id, "name": u.name, "email": u.email, "enrolled_at": e.enrolled_at.isoformat()}
        for e, u in enrollments
    ]
```

### 4.5 Add Participation Tracking to Report Workflow

**File:** `workflows/report.py`

Add new function after `fetch_poll_results`:

```python
def calculate_participation_metrics(
    db: Session,
    session_id: int,
    course_id: int
) -> Dict[str, Any]:
    """
    Calculate participation metrics for a session.

    Returns:
        Dict with participation rate, participants, and non-participants
    """
    from api.models.enrollment import Enrollment

    # Get enrolled students for the course
    enrolled_students = db.query(User).join(Enrollment).filter(
        Enrollment.course_id == course_id,
        User.role == "student"
    ).all()

    enrolled_ids = {s.id for s in enrolled_students}
    enrolled_count = len(enrolled_ids)

    if enrolled_count == 0:
        return {
            "total_enrolled_students": 0,
            "students_who_participated": [],
            "students_who_did_not_participate": [],
            "participation_rate": 0.0,
            "note": "No students enrolled in course"
        }

    # Get students who posted in this session
    posts_by_student = db.query(
        Post.user_id,
        User.name,
        func.count(Post.id).label('post_count')
    ).join(User).filter(
        Post.session_id == session_id,
        User.role == "student"
    ).group_by(Post.user_id, User.name).all()

    participated_ids = {p.user_id for p in posts_by_student}

    students_who_participated = [
        {"user_id": p.user_id, "name": p.name, "post_count": p.post_count}
        for p in posts_by_student
    ]

    students_who_did_not_participate = [
        {"user_id": s.id, "name": s.name}
        for s in enrolled_students if s.id not in participated_ids
    ]

    participation_rate = (len(participated_ids) / enrolled_count * 100) if enrolled_count > 0 else 0.0

    return {
        "total_enrolled_students": enrolled_count,
        "students_who_participated": students_who_participated,
        "participation_count": len(participated_ids),
        "students_who_did_not_participate": students_who_did_not_participate,
        "non_participation_count": len(students_who_did_not_participate),
        "participation_rate": round(participation_rate, 1)
    }
```

In `run_report_workflow`, add after fetching poll_results:

```python
# Fetch participation metrics
participation_metrics = calculate_participation_metrics(db, session_id, course.id)
logger.info(f"Participation rate: {participation_metrics['participation_rate']}%")
```

Add to `initial_state`:

```python
"participation_metrics": participation_metrics,
```

Update `compile_report` to include:

```python
"participation": state.get("participation_metrics", {}),
```

Update `generate_markdown_report` to include participation section:

```python
# Participation Metrics
participation = report_json.get("participation", {})
if participation:
    lines.append("## Participation Summary")
    lines.append(f"- **Enrolled students**: {participation.get('total_enrolled_students', 'N/A')}")
    lines.append(f"- **Students who participated**: {participation.get('participation_count', 0)}")
    lines.append(f"- **Participation rate**: {participation.get('participation_rate', 0)}%")
    lines.append("")

    non_participants = participation.get("students_who_did_not_participate", [])
    if non_participants:
        lines.append("### Students Who Did Not Participate")
        for s in non_participants:
            lines.append(f"- {s['name']} (ID: {s['user_id']})")
        lines.append("")
```

---

## 5. Answer Scoring in Reports

### 5.1 Add Scoring Prompt

**File:** `workflows/prompts/report_prompts.py`

Add new prompt:

```python
SCORE_ANSWERS_PROMPT = """You are an educational assessment expert. Compare each student's response to the best-practice answer and assign a score.

## Best Practice Answer
{best_practice_answer}

## Key Concepts That Should Be Addressed
{key_concepts}

## Student Posts to Evaluate
{student_posts}

## Scoring Rubric
- 90-100: Excellent - Covers all key concepts with deep understanding
- 75-89: Good - Covers most key concepts with solid understanding
- 60-74: Satisfactory - Covers some key concepts, room for improvement
- 40-59: Needs Improvement - Missing key concepts, shows partial understanding
- 0-39: Insufficient - Does not demonstrate understanding of the topic

## Instructions
For each student post:
1. Identify which key concepts they addressed
2. Evaluate the accuracy and depth of their explanation
3. Assign a score based on the rubric
4. Provide brief feedback

Return JSON in this exact format:
{{
    "student_scores": [
        {{
            "user_id": <int>,
            "user_name": "<string>",
            "post_id": <int>,
            "score": <int 0-100>,
            "key_points_covered": ["<concept1>", "<concept2>"],
            "missing_points": ["<concept3>"],
            "feedback": "<brief constructive feedback>"
        }}
    ],
    "class_statistics": {{
        "average_score": <float>,
        "highest_score": <int>,
        "lowest_score": <int>,
        "score_distribution": {{
            "excellent": <count>,
            "good": <count>,
            "satisfactory": <count>,
            "needs_improvement": <count>,
            "insufficient": <count>
        }}
    }},
    "closest_to_correct": {{
        "user_id": <int>,
        "user_name": "<string>",
        "post_id": <int>,
        "score": <int>
    }},
    "furthest_from_correct": {{
        "user_id": <int>,
        "user_name": "<string>",
        "post_id": <int>,
        "score": <int>
    }}
}}
"""
```

### 5.2 Add Scoring Node to Workflow

**File:** `workflows/report.py`

Add new node after `generate_student_summary`:

```python
def score_student_answers(state: ReportState) -> ReportState:
    """Node 6: Score student answers against best practice."""
    logger.info("ScoreAnswers: Evaluating student responses")

    # Only score student posts
    student_posts = [p for p in state["posts"] if p["author_role"] == "student"]

    if not student_posts:
        state["answer_scores"] = {
            "student_scores": [],
            "class_statistics": None,
            "note": "No student posts to score"
        }
        return state

    best_practice = state.get("best_practice", {}).get("best_practice_answer", {})
    if not best_practice:
        state["answer_scores"] = {
            "student_scores": [],
            "class_statistics": None,
            "note": "No best practice answer available for comparison"
        }
        return state

    llm, model_name = get_llm_with_tracking()

    if llm:
        # Format student posts with user info
        posts_formatted = "\n\n".join(
            f"[Post #{p['post_id']} by User {p.get('user_id', 'Unknown')}]\n{p['content']}"
            for p in student_posts
        )

        key_concepts = best_practice.get("key_concepts", [])

        prompt = SCORE_ANSWERS_PROMPT.format(
            best_practice_answer=best_practice.get("detailed_explanation", best_practice.get("summary", "")),
            key_concepts="\n".join(f"- {c}" for c in key_concepts) if key_concepts else "See best practice answer",
            student_posts=posts_formatted
        )

        response = invoke_llm_with_metrics(llm, prompt, model_name)
        state["llm_metrics"].append(response.metrics)

        if response.success:
            scores = parse_json_response(response.content)
            if scores:
                state["answer_scores"] = scores
                logger.info(f"ScoreAnswers: Scored {len(scores.get('student_scores', []))} posts")
                return state

    # Fallback - basic scoring based on post length and labels
    fallback_scores = []
    for p in student_posts:
        # Simple heuristic scoring
        score = 50  # Base score
        if len(p["content"]) > 200:
            score += 15  # Longer responses get bonus
        if "high-quality" in (p.get("labels") or []):
            score += 25  # Instructor marked as high quality
        if "needs-clarification" in (p.get("labels") or []):
            score -= 20  # Needs work

        score = max(0, min(100, score))  # Clamp to 0-100

        fallback_scores.append({
            "user_id": p.get("user_id"),
            "post_id": p["post_id"],
            "score": score,
            "feedback": "Automated scoring based on instructor labels"
        })

    avg_score = sum(s["score"] for s in fallback_scores) / len(fallback_scores) if fallback_scores else 0

    state["answer_scores"] = {
        "student_scores": fallback_scores,
        "class_statistics": {
            "average_score": round(avg_score, 1),
            "highest_score": max(s["score"] for s in fallback_scores) if fallback_scores else 0,
            "lowest_score": min(s["score"] for s in fallback_scores) if fallback_scores else 0,
        },
        "note": "Fallback scoring used - LLM unavailable"
    }

    return state
```

### 5.3 Update Workflow Graph

**File:** `workflows/report.py`

Update `build_report_graph`:

```python
def build_report_graph() -> StateGraph:
    """Build the LangGraph workflow for report generation."""
    workflow = StateGraph(ReportState)

    # Add nodes
    workflow.add_node("cluster_posts", cluster_posts)
    workflow.add_node("align_to_objectives", align_to_objectives)
    workflow.add_node("identify_misconceptions", identify_misconceptions)
    workflow.add_node("generate_best_practice", generate_best_practice)
    workflow.add_node("generate_student_summary", generate_student_summary)
    workflow.add_node("score_student_answers", score_student_answers)  # NEW

    # Define edges (linear flow)
    workflow.set_entry_point("cluster_posts")
    workflow.add_edge("cluster_posts", "align_to_objectives")
    workflow.add_edge("align_to_objectives", "identify_misconceptions")
    workflow.add_edge("identify_misconceptions", "generate_best_practice")
    workflow.add_edge("generate_best_practice", "generate_student_summary")
    workflow.add_edge("generate_student_summary", "score_student_answers")  # NEW
    workflow.add_edge("score_student_answers", END)  # UPDATED

    return workflow.compile()
```

### 5.4 Update State Definition

Add to `ReportState`:

```python
# After StudentSummary
answer_scores: Optional[Dict[str, Any]]
```

### 5.5 Update Report Compilation

In `compile_report`, add:

```python
# Answer Scoring
"answer_scores": state.get("answer_scores", {}),
```

In `generate_markdown_report`, add:

```python
# Answer Scoring Section
scores = report_json.get("answer_scores", {})
if scores and scores.get("student_scores"):
    lines.append("## Answer Scoring")
    lines.append("")

    stats = scores.get("class_statistics", {})
    if stats:
        lines.append(f"**Class Average:** {stats.get('average_score', 'N/A')}/100")
        lines.append(f"**Highest Score:** {stats.get('highest_score', 'N/A')}")
        lines.append(f"**Lowest Score:** {stats.get('lowest_score', 'N/A')}")
        lines.append("")

    # Show closest and furthest
    closest = scores.get("closest_to_correct")
    furthest = scores.get("furthest_from_correct")

    if closest:
        lines.append(f"🏆 **Closest to Correct:** {closest.get('user_name', f'User {closest.get(\"user_id\")}')} "
                     f"(Post #{closest.get('post_id')}) - Score: {closest.get('score')}")
    if furthest:
        lines.append(f"📚 **Needs Most Improvement:** {furthest.get('user_name', f'User {furthest.get(\"user_id\")}')} "
                     f"(Post #{furthest.get('post_id')}) - Score: {furthest.get('score')}")
    lines.append("")

    # Individual scores table
    lines.append("### Individual Scores")
    lines.append("")
    lines.append("| Student | Post | Score | Feedback |")
    lines.append("|---------|------|-------|----------|")

    for s in sorted(scores["student_scores"], key=lambda x: x.get("score", 0), reverse=True):
        name = s.get("user_name", f"User {s.get('user_id')}")
        feedback = s.get("feedback", "")[:50] + "..." if len(s.get("feedback", "")) > 50 else s.get("feedback", "")
        lines.append(f"| {name} | #{s.get('post_id')} | {s.get('score')}/100 | {feedback} |")

    lines.append("")
```

---

## Implementation Order

### Phase 1: Critical Bug Fixes (Do First)
1. ✅ Display Cases in Discussion tab (Section 3)

### Phase 2: Core UX Improvements
2. Add Session listing by course API + UI (Section 1)
3. Add Role-based UI (Section 2)

### Phase 3: New Features
4. Add Enrollment model + Participation tracking (Section 4)
5. Add Answer scoring (Section 5)

---

## Database Migration Commands

After implementing the enrollment model:

```bash
# Generate migration
docker compose exec api alembic revision --autogenerate -m "Add enrollments table"

# Apply migration
docker compose exec api alembic upgrade head
```

---

## Testing Checklist

### Section 1: Session Listing
- [ ] `/api/courses/{id}/sessions` returns correct sessions
- [ ] UI dropdown shows sessions for selected course
- [ ] Sessions display correct status badges

### Section 2: Role-Based UI
- [ ] User selector appears in sidebar
- [ ] Instructor sees all tabs (Discussion, Post Case, Post Reply)
- [ ] Student sees only Discussion and Post Reply
- [ ] Student cannot see moderation controls
- [ ] Instructor Console hidden from students

### Section 3: Case Display
- [ ] Cases appear at top of Discussion tab
- [ ] Cases are visually distinct from student posts
- [ ] Multiple cases display correctly
- [ ] Case timestamp displays correctly

### Section 4: Participation Tracking
- [ ] Enrollment CRUD works correctly
- [ ] Report shows participation rate
- [ ] Report lists non-participants
- [ ] Works correctly when no students enrolled

### Section 5: Answer Scoring
- [ ] Scores generated for student posts
- [ ] Class statistics calculated correctly
- [ ] Closest/furthest identified
- [ ] Fallback works when LLM unavailable
- [ ] Scores appear in report markdown and JSON

---

## Notes

- All changes maintain backward compatibility
- Fallback behaviors exist for LLM-dependent features
- UI changes are additive, not destructive
- Database migrations are reversible
