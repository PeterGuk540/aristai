"""
Enhanced AI Features Workflows

This module implements the 10 enhanced AI features for the discussion platform:
1. Smart Discussion Summarization (Real-time)
2. AI-Powered Student Grouping
3. Personalized Follow-up Generator
4. Question Bank Builder
5. Attendance & Participation Insights
6. AI Teaching Assistant Mode
7. Session Recording & Transcript Analysis
8. Learning Objective Alignment Dashboard
9. Peer Review Workflow
10. Multi-Language Support
"""
import json
import logging
import random
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from api.core.database import SessionLocal
from api.models.session import Session as SessionModel, Case
from api.models.course import Course
from api.models.course_material import CourseMaterial
from api.models.post import Post
from api.models.user import User
from api.models.enrollment import Enrollment
from api.models.enhanced_features import (
    LiveSummary,
    StudentGroup, StudentGroupMember,
    PersonalizedFollowup,
    QuestionBankItem,
    ParticipationSnapshot, ParticipationAlert,
    AIAssistantMessage,
    SessionRecording, TranscriptPostLink,
    ObjectiveCoverage,
    PeerReviewAssignment, PeerReviewFeedback,
    PostTranslation,
)
from workflows.llm_utils import (
    get_llm_with_tracking,
    invoke_llm_with_metrics,
    format_posts_for_prompt,
    parse_json_response,
    LLMMetrics,
)

logger = logging.getLogger(__name__)


# ============ Prompts ============

LIVE_SUMMARY_PROMPT = """You are an educational AI assistant. Analyze this live discussion and provide a real-time summary.

Session: {session_title}
Topic: {topics}

Discussion Posts:
{posts_formatted}

Provide a JSON response with:
{{
    "summary_text": "A 2-3 paragraph summary of the key discussion points",
    "key_themes": ["theme1", "theme2", "theme3"],
    "unanswered_questions": ["question1", "question2"],
    "misconceptions": [
        {{"concept": "...", "misconception": "...", "correction": "..."}}
    ],
    "engagement_pulse": "high" | "medium" | "low"
}}
"""

STUDENT_GROUPING_PROMPT = """You are an educational AI assistant. Create optimal student groups based on their discussion participation.

Session: {session_title}
Group Type: {group_type}
Number of Groups: {num_groups}
Topics for Assignment: {topics}

Student Participation Data:
{participation_data}

Create groups that {grouping_criteria}.

Provide a JSON response:
{{
    "groups": [
        {{
            "name": "Group 1",
            "topic": "Topic if jigsaw mode",
            "members": [
                {{"user_id": 1, "role": "facilitator"}}
            ],
            "rationale": "Why these students were grouped together"
        }}
    ]
}}
"""

FOLLOWUP_PROMPT = """You are an educational AI assistant. Generate personalized follow-up feedback for this student based on their discussion participation.

Session: {session_title}
Student: {student_name}

Student's Posts:
{student_posts}

Session Context:
{session_summary}

Generate personalized feedback with:
{{
    "strengths": ["What they did well"],
    "improvements": ["Areas to improve"],
    "key_takeaways": ["Personalized takeaways for this student"],
    "suggested_resources": [
        {{"title": "Resource name", "type": "article|video|book", "url": "optional"}}
    ],
    "custom_message": "A personalized 2-3 paragraph message to the student"
}}
"""

QUESTION_GENERATION_PROMPT = """You are an educational AI assistant. Generate quiz questions based on the session content.

Session: {session_title}
Topics: {topics}

=== DISCUSSION POSTS ===
{posts_formatted}

=== CASE STUDIES ===
{cases_formatted}

=== COURSE MATERIALS ===
{materials_formatted}

=== SESSION TRANSCRIPTS ===
{transcripts_formatted}

Generate {num_questions} questions of types: {question_types}
Difficulty level: {difficulty}

Use ALL available content sources above to create comprehensive, relevant questions.
Prioritize content that students have engaged with (discussion posts, cases).

Provide a JSON response:
{{
    "questions": [
        {{
            "question_type": "mcq" | "short_answer" | "essay" | "true_false",
            "question_text": "The question",
            "options": ["A", "B", "C", "D"],  // for MCQ only
            "correct_answer": "The correct answer",
            "explanation": "Why this is correct",
            "difficulty": "easy" | "medium" | "hard",
            "learning_objective": "What learning objective this tests",
            "tags": ["topic1", "topic2"]
        }}
    ]
}}
"""

PARTICIPATION_ANALYSIS_PROMPT = """You are an educational AI assistant. Analyze student participation quality for this discussion.

Student: {student_name}
Posts Count: {post_count}
Reply Count: {reply_count}

Student's Posts:
{student_posts}

Analyze and provide:
{{
    "quality_score": 0.0-1.0,
    "engagement_level": "highly_active" | "active" | "idle" | "disengaged",
    "at_risk": true | false,
    "risk_factors": ["factor1", "factor2"] if at_risk
}}
"""

AI_ASSISTANT_PROMPT = """You are an AI Teaching Assistant for this course. Answer the student's question based on the course materials and discussion context.

Course: {course_name}
Session: {session_title}
Course Materials Summary: {materials_context}
Discussion Context: {discussion_context}

Student Question: {question}

Guidelines:
- Be helpful and encouraging
- Use the Socratic method when appropriate
- Reference specific course materials when possible
- Don't give direct answers to homework/quiz questions
- Encourage further exploration

Provide a response that helps the student understand the concept better.
"""

OBJECTIVE_COVERAGE_PROMPT = """You are an educational AI assistant. Analyze how well this discussion session covered the course learning objectives.

Course Learning Objectives:
{objectives}

Session Topic: {session_title}

Discussion Posts:
{posts_formatted}

For each objective, analyze:
{{
    "objectives": [
        {{
            "objective_text": "The objective",
            "coverage_level": "fully" | "partially" | "not_covered",
            "coverage_score": 0.0-1.0,
            "coverage_summary": "How this objective was addressed",
            "gaps_identified": ["What aspects weren't covered"]
        }}
    ],
    "recommended_topics": ["Topics to cover in future sessions"]
}}
"""

PEER_REVIEW_MATCHING_PROMPT = """You are an educational AI assistant. Create optimal peer review assignments that promote learning.

Session: {session_title}

Submissions to Review:
{submissions}

Available Reviewers:
{reviewers}

Create assignments that:
- Avoid self-review
- Mix different perspectives
- Pair students who can learn from each other

Provide a JSON response:
{{
    "assignments": [
        {{
            "submission_author_id": 1,
            "reviewer_id": 2,
            "match_rationale": "Why this pairing is beneficial"
        }}
    ]
}}
"""

TRANSLATION_PROMPT = """Translate the following text from {source_language} to {target_language}. Maintain the original meaning, tone, and educational context.

Text to translate:
{text}

Provide a JSON response:
{{
    "translated_text": "The translation",
    "confidence_score": 0.0-1.0,
    "source_language_detected": "language code"
}}
"""


# ============ Feature 1: Smart Discussion Summarization ============

def generate_live_summary(session_id: int) -> Dict[str, Any]:
    """Generate a real-time discussion summary."""
    db = SessionLocal()
    try:
        session = db.query(SessionModel).filter(SessionModel.id == session_id).first()
        if not session:
            return {"error": "Session not found"}

        # Get posts
        posts = db.query(Post).filter(Post.session_id == session_id).order_by(Post.created_at.asc()).all()
        posts_data = [
            {
                "post_id": p.id,
                "author_role": "instructor" if p.user.role.value == "instructor" else "student",
                "content": p.content,
                "timestamp": p.created_at.isoformat() if p.created_at else "",
                "pinned": p.pinned,
                "labels": p.labels_json or [],
            }
            for p in posts
        ]

        posts_formatted = format_posts_for_prompt(posts_data[:50])
        topics = session.plan_json.get("topics", []) if session.plan_json else []

        # Get LLM
        llm, model_name = get_llm_with_tracking()
        if not llm:
            return {"error": "No LLM configured"}

        prompt = LIVE_SUMMARY_PROMPT.format(
            session_title=session.title,
            topics=", ".join(topics) if topics else "General discussion",
            posts_formatted=posts_formatted,
        )

        response = invoke_llm_with_metrics(llm, prompt, model_name)
        if not response.success:
            return {"error": response.metrics.error_message}

        result = parse_json_response(response.content)
        if not result:
            return {"error": "Failed to parse LLM response"}

        # Save summary
        summary = LiveSummary(
            session_id=session_id,
            summary_text=result.get("summary_text", ""),
            key_themes=result.get("key_themes", []),
            unanswered_questions=result.get("unanswered_questions", []),
            misconceptions=result.get("misconceptions", []),
            engagement_pulse=result.get("engagement_pulse", "medium"),
            posts_analyzed=len(posts_data),
            last_post_id=posts[-1].id if posts else None,
            model_name=model_name,
            total_tokens=response.metrics.total_tokens,
            estimated_cost_usd=response.metrics.estimated_cost_usd,
        )
        db.add(summary)
        db.commit()

        return {"summary_id": summary.id, "summary": result}

    finally:
        db.close()


# ============ Feature 2: AI-Powered Student Grouping ============

def generate_student_groups(
    session_id: int,
    group_type: str = "mixed_participation",
    num_groups: int = 4,
    topics: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Generate AI-powered student groups."""
    db = SessionLocal()
    try:
        session = db.query(SessionModel).filter(SessionModel.id == session_id).first()
        if not session:
            return {"error": "Session not found"}

        # Get enrolled students with their participation
        enrollments = db.query(Enrollment).filter(
            Enrollment.course_id == session.course_id
        ).all()

        participation_data = []
        for enrollment in enrollments:
            user = db.query(User).filter(User.id == enrollment.user_id).first()
            if not user or user.role.value == "instructor":
                continue

            posts = db.query(Post).filter(
                Post.session_id == session_id,
                Post.user_id == user.id
            ).all()

            participation_data.append({
                "user_id": user.id,
                "name": user.name,
                "post_count": len(posts),
                "posts_preview": [p.content[:100] for p in posts[:3]],
            })

        if len(participation_data) < num_groups:
            return {"error": f"Not enough students ({len(participation_data)}) for {num_groups} groups"}

        # Grouping criteria based on type
        criteria_map = {
            "debate": "create opposing viewpoint pairs for debate",
            "mixed_participation": "mix high and low participation students evenly",
            "learning_gap": "group students with similar learning gaps together",
            "jigsaw": "assign each group a different topic to become experts on",
        }
        grouping_criteria = criteria_map.get(group_type, criteria_map["mixed_participation"])

        # Get LLM
        llm, model_name = get_llm_with_tracking()
        if not llm:
            # Fallback: random grouping
            random.shuffle(participation_data)
            groups_result = []
            per_group = len(participation_data) // num_groups
            for i in range(num_groups):
                start = i * per_group
                end = start + per_group if i < num_groups - 1 else len(participation_data)
                group_members = participation_data[start:end]
                groups_result.append({
                    "name": f"Group {i+1}",
                    "topic": topics[i] if topics and i < len(topics) else None,
                    "members": [{"user_id": m["user_id"], "role": "member"} for m in group_members],
                    "rationale": "Randomly assigned (LLM unavailable)",
                })
        else:
            prompt = STUDENT_GROUPING_PROMPT.format(
                session_title=session.title,
                group_type=group_type,
                num_groups=num_groups,
                topics=json.dumps(topics) if topics else "N/A",
                participation_data=json.dumps(participation_data, indent=2),
                grouping_criteria=grouping_criteria,
            )

            response = invoke_llm_with_metrics(llm, prompt, model_name)
            if not response.success:
                return {"error": response.metrics.error_message}

            result = parse_json_response(response.content)
            if not result or "groups" not in result:
                return {"error": "Failed to parse LLM response"}

            groups_result = result["groups"]

        # Deactivate existing groups
        db.query(StudentGroup).filter(
            StudentGroup.session_id == session_id,
            StudentGroup.is_active == True
        ).update({"is_active": False})

        # Save new groups
        created_groups = []
        for g in groups_result:
            group = StudentGroup(
                session_id=session_id,
                name=g["name"],
                group_type=group_type,
                topic=g.get("topic"),
                rationale=g.get("rationale"),
                is_active=True,
            )
            db.add(group)
            db.flush()

            for m in g.get("members", []):
                member = StudentGroupMember(
                    group_id=group.id,
                    user_id=m["user_id"],
                    role=m.get("role"),
                )
                db.add(member)

            created_groups.append(group.id)

        db.commit()

        return {"group_ids": created_groups, "groups_count": len(created_groups)}

    finally:
        db.close()


# ============ Feature 3: Personalized Follow-up Generator ============

def generate_followups(
    session_id: int,
    student_ids: Optional[List[int]] = None,
) -> Dict[str, Any]:
    """Generate personalized follow-up messages for students."""
    db = SessionLocal()
    try:
        session = db.query(SessionModel).filter(SessionModel.id == session_id).first()
        if not session:
            return {"error": "Session not found"}

        # Get session summary for context
        summary = db.query(LiveSummary).filter(
            LiveSummary.session_id == session_id
        ).order_by(LiveSummary.created_at.desc()).first()

        session_summary = summary.summary_text if summary else "No summary available"

        # Get students to generate followups for
        if student_ids:
            students = db.query(User).filter(User.id.in_(student_ids)).all()
        else:
            # Get all students who participated
            post_user_ids = db.query(Post.user_id).filter(
                Post.session_id == session_id
            ).distinct().all()
            post_user_ids = [uid[0] for uid in post_user_ids]
            students = db.query(User).filter(
                User.id.in_(post_user_ids),
                User.role != "instructor"
            ).all()

        llm, model_name = get_llm_with_tracking()
        created_followups = []

        for student in students:
            # Get student's posts
            posts = db.query(Post).filter(
                Post.session_id == session_id,
                Post.user_id == student.id
            ).order_by(Post.created_at.asc()).all()

            if not posts:
                continue

            student_posts = "\n".join([f"- {p.content}" for p in posts])

            if llm:
                prompt = FOLLOWUP_PROMPT.format(
                    session_title=session.title,
                    student_name=student.name,
                    student_posts=student_posts,
                    session_summary=session_summary,
                )

                response = invoke_llm_with_metrics(llm, prompt, model_name)
                if response.success:
                    result = parse_json_response(response.content)
                    if result:
                        followup = PersonalizedFollowup(
                            session_id=session_id,
                            user_id=student.id,
                            strengths=result.get("strengths", []),
                            improvements=result.get("improvements", []),
                            key_takeaways=result.get("key_takeaways", []),
                            suggested_resources=result.get("suggested_resources", []),
                            custom_message=result.get("custom_message", ""),
                            status="draft",
                            model_name=model_name,
                            total_tokens=response.metrics.total_tokens,
                        )
                        db.add(followup)
                        created_followups.append(student.id)
            else:
                # Basic followup without AI
                followup = PersonalizedFollowup(
                    session_id=session_id,
                    user_id=student.id,
                    strengths=[f"Contributed {len(posts)} posts to the discussion"],
                    improvements=["Continue engaging with peers' ideas"],
                    key_takeaways=["Review the session summary for key concepts"],
                    custom_message=f"Thank you for participating in {session.title}!",
                    status="draft",
                )
                db.add(followup)
                created_followups.append(student.id)

        db.commit()

        return {"followups_created": len(created_followups), "student_ids": created_followups}

    finally:
        db.close()


# ============ Feature 4: Question Bank Builder ============

def generate_questions(
    session_id: int,
    question_types: List[str],
    num_questions: int = 5,
    difficulty: Optional[str] = None,
) -> Dict[str, Any]:
    """Generate quiz questions from session content (posts, cases, materials, transcripts)."""
    db = SessionLocal()
    try:
        session = db.query(SessionModel).filter(SessionModel.id == session_id).first()
        if not session:
            return {"error": "Session not found"}

        # 1. Fetch discussion posts
        posts = db.query(Post).filter(Post.session_id == session_id).order_by(Post.created_at.asc()).all()
        posts_data = [
            {
                "post_id": p.id,
                "author_role": "instructor" if p.user.role.value == "instructor" else "student",
                "content": p.content,
                "pinned": p.pinned,
                "labels": p.labels_json or [],
            }
            for p in posts
        ]
        posts_formatted = format_posts_for_prompt(posts_data[:30])

        # 2. Fetch case studies
        cases = db.query(Case).filter(Case.session_id == session_id).all()
        if cases:
            cases_formatted = "\n".join([
                f"Case {i+1}: {c.prompt[:500]}{'...' if len(c.prompt) > 500 else ''}"
                for i, c in enumerate(cases)
            ])
        else:
            cases_formatted = "No case studies for this session."

        # 3. Fetch course materials (metadata only)
        materials = db.query(CourseMaterial).filter(
            CourseMaterial.course_id == session.course_id
        ).all()
        if materials:
            materials_formatted = "\n".join([
                f"- {m.filename} ({m.content_type}): {m.description or 'No description'}"
                for m in materials[:10]
            ])
        else:
            materials_formatted = "No course materials uploaded."

        # 4. Fetch session transcripts (if available)
        recordings = db.query(SessionRecording).filter(
            SessionRecording.session_id == session_id
        ).all()
        if recordings:
            transcripts_formatted = "\n".join([
                f"Recording: {r.transcript_text[:1000]}{'...' if r.transcript_text and len(r.transcript_text) > 1000 else ''}"
                for r in recordings if r.transcript_text
            ])
            if not transcripts_formatted:
                transcripts_formatted = "No transcripts available."
        else:
            transcripts_formatted = "No session recordings."

        topics = session.plan_json.get("topics", []) if session.plan_json else []

        llm, model_name = get_llm_with_tracking()
        if not llm:
            return {"error": "No LLM configured"}

        prompt = QUESTION_GENERATION_PROMPT.format(
            session_title=session.title,
            topics=", ".join(topics) if topics else "General discussion",
            posts_formatted=posts_formatted,
            cases_formatted=cases_formatted,
            materials_formatted=materials_formatted,
            transcripts_formatted=transcripts_formatted,
            num_questions=num_questions,
            question_types=", ".join(question_types),
            difficulty=difficulty or "mixed",
        )

        response = invoke_llm_with_metrics(llm, prompt, model_name)
        if not response.success:
            return {"error": response.metrics.error_message}

        result = parse_json_response(response.content)
        if not result or "questions" not in result:
            return {"error": "Failed to parse LLM response"}

        created_questions = []
        for q in result["questions"]:
            question = QuestionBankItem(
                course_id=session.course_id,
                session_id=session_id,
                question_type=q.get("question_type", "mcq"),
                question_text=q.get("question_text", ""),
                options=q.get("options"),
                correct_answer=q.get("correct_answer"),
                explanation=q.get("explanation"),
                difficulty=q.get("difficulty", "medium"),
                learning_objective=q.get("learning_objective"),
                tags=q.get("tags", []),
                status="approved",  # Auto-approve generated questions
            )
            db.add(question)
            db.flush()
            created_questions.append(question.id)

        db.commit()

        return {"questions_created": len(created_questions), "question_ids": created_questions}

    finally:
        db.close()


# ============ Feature 5: Attendance & Participation Insights ============

def analyze_participation(course_id: int) -> Dict[str, Any]:
    """Analyze participation metrics for a course."""
    db = SessionLocal()
    try:
        course = db.query(Course).filter(Course.id == course_id).first()
        if not course:
            return {"error": "Course not found"}

        # Get all sessions for this course
        sessions = db.query(SessionModel).filter(SessionModel.course_id == course_id).all()
        session_ids = [s.id for s in sessions]

        # Get all enrollments
        enrollments = db.query(Enrollment).filter(Enrollment.course_id == course_id).all()

        llm, model_name = get_llm_with_tracking()
        snapshots_created = 0
        alerts_created = 0

        for enrollment in enrollments:
            user = db.query(User).filter(User.id == enrollment.user_id).first()
            if not user or user.role.value == "instructor":
                continue

            # Get participation metrics
            posts = db.query(Post).filter(
                Post.session_id.in_(session_ids),
                Post.user_id == user.id
            ).all()

            replies = [p for p in posts if p.parent_id is not None]

            # Calculate quality score using LLM if available
            quality_score = 0.5
            engagement_level = "active"
            at_risk = False
            risk_factors = []

            if llm and posts:
                student_posts = "\n".join([f"- {p.content}" for p in posts[:10]])
                prompt = PARTICIPATION_ANALYSIS_PROMPT.format(
                    student_name=user.name,
                    post_count=len(posts),
                    reply_count=len(replies),
                    student_posts=student_posts,
                )
                response = invoke_llm_with_metrics(llm, prompt, model_name)
                if response.success:
                    result = parse_json_response(response.content)
                    if result:
                        quality_score = result.get("quality_score", 0.5)
                        engagement_level = result.get("engagement_level", "active")
                        at_risk = result.get("at_risk", False)
                        risk_factors = result.get("risk_factors", [])
            else:
                # Basic heuristics
                if len(posts) == 0:
                    engagement_level = "disengaged"
                    at_risk = True
                    risk_factors = ["No posts in course"]
                elif len(posts) < 3:
                    engagement_level = "idle"
                    at_risk = True
                    risk_factors = ["Low participation"]

            # Create snapshot
            snapshot = ParticipationSnapshot(
                course_id=course_id,
                user_id=user.id,
                post_count=len(posts),
                reply_count=len(replies),
                quality_score=quality_score,
                engagement_level=engagement_level,
                at_risk=at_risk,
                risk_factors=risk_factors if risk_factors else None,
            )
            db.add(snapshot)
            snapshots_created += 1

            # Create alert if at-risk
            if at_risk:
                alert = ParticipationAlert(
                    course_id=course_id,
                    user_id=user.id,
                    alert_type="low_participation",
                    severity="warning" if engagement_level == "idle" else "critical",
                    message=f"{user.name} has low participation: {', '.join(risk_factors)}",
                )
                db.add(alert)
                alerts_created += 1

        db.commit()

        return {
            "snapshots_created": snapshots_created,
            "alerts_created": alerts_created,
        }

    finally:
        db.close()


# ============ Feature 6: AI Teaching Assistant Mode ============

def generate_ai_assistant_response(
    session_id: int,
    student_id: int,
    question: str,
    post_id: Optional[int] = None,
) -> Dict[str, Any]:
    """Generate AI teaching assistant response to a student question."""
    db = SessionLocal()
    try:
        session = db.query(SessionModel).filter(SessionModel.id == session_id).first()
        if not session:
            return {"error": "Session not found"}

        course = db.query(Course).filter(Course.id == session.course_id).first()

        # Get discussion context
        recent_posts = db.query(Post).filter(
            Post.session_id == session_id
        ).order_by(Post.created_at.desc()).limit(10).all()

        discussion_context = "\n".join([f"- {p.content[:200]}" for p in recent_posts])

        # Get course materials context (from syllabus/plan)
        materials_context = course.syllabus_text[:500] if course and course.syllabus_text else "N/A"

        llm, model_name = get_llm_with_tracking()
        if not llm:
            return {"error": "No LLM configured"}

        prompt = AI_ASSISTANT_PROMPT.format(
            course_name=course.name if course else "Unknown",
            session_title=session.title,
            materials_context=materials_context,
            discussion_context=discussion_context,
            question=question,
        )

        response = invoke_llm_with_metrics(llm, prompt, model_name)
        if not response.success:
            return {"error": response.metrics.error_message}

        # Save the AI response
        message = AIAssistantMessage(
            session_id=session_id,
            student_id=student_id,
            student_question=question,
            student_post_id=post_id,
            ai_response=response.content,
            confidence_score=0.8,  # Could be enhanced with actual confidence scoring
            status="pending",
            model_name=model_name,
            total_tokens=response.metrics.total_tokens,
        )
        db.add(message)
        db.commit()

        return {"message_id": message.id, "response": response.content}

    finally:
        db.close()


# ============ Feature 7: Session Recording & Transcript Analysis ============

def transcribe_recording(recording_id: int) -> Dict[str, Any]:
    """Transcribe and analyze a session recording."""
    db = SessionLocal()
    try:
        recording = db.query(SessionRecording).filter(SessionRecording.id == recording_id).first()
        if not recording:
            return {"error": "Recording not found"}

        recording.status = "transcribing"
        db.commit()

        # TODO: Integrate with actual transcription service (e.g., Whisper API)
        # For now, simulate transcription
        recording.transcript_text = "Transcription service not yet integrated. This is a placeholder."
        recording.transcript_segments = []
        recording.key_moments = []
        recording.topics_discussed = []
        recording.status = "completed"
        recording.processed_at = datetime.now(timezone.utc)

        db.commit()

        return {
            "recording_id": recording_id,
            "status": "completed",
            "message": "Transcription service integration pending",
        }

    except Exception as e:
        recording.status = "failed"
        recording.error_message = str(e)
        db.commit()
        return {"error": str(e)}

    finally:
        db.close()


# ============ Feature 8: Learning Objective Alignment Dashboard ============

def analyze_objective_coverage(course_id: int) -> Dict[str, Any]:
    """Analyze learning objective coverage for a course."""
    db = SessionLocal()
    try:
        course = db.query(Course).filter(Course.id == course_id).first()
        if not course:
            return {"error": "Course not found"}

        # Get learning objectives from course
        objectives = course.learning_objectives or []
        if not objectives:
            return {"error": "No learning objectives defined for course"}

        # Get all sessions with posts
        sessions = db.query(SessionModel).filter(SessionModel.course_id == course_id).all()

        llm, model_name = get_llm_with_tracking()
        if not llm:
            return {"error": "No LLM configured"}

        coverage_created = 0

        for session in sessions:
            posts = db.query(Post).filter(Post.session_id == session.id).all()
            if not posts:
                continue

            posts_data = [
                {
                    "post_id": p.id,
                    "author_role": "instructor" if p.user.role.value == "instructor" else "student",
                    "content": p.content,
                    "pinned": p.pinned,
                }
                for p in posts
            ]
            posts_formatted = format_posts_for_prompt(posts_data[:30])

            prompt = OBJECTIVE_COVERAGE_PROMPT.format(
                objectives=json.dumps(objectives, indent=2),
                session_title=session.title,
                posts_formatted=posts_formatted,
            )

            response = invoke_llm_with_metrics(llm, prompt, model_name)
            if response.success:
                result = parse_json_response(response.content)
                if result and "objectives" in result:
                    for i, obj in enumerate(result["objectives"]):
                        coverage = ObjectiveCoverage(
                            course_id=course_id,
                            session_id=session.id,
                            objective_text=obj.get("objective_text", objectives[i] if i < len(objectives) else ""),
                            objective_index=i,
                            coverage_level=obj.get("coverage_level", "not_covered"),
                            coverage_score=obj.get("coverage_score", 0.0),
                            coverage_summary=obj.get("coverage_summary"),
                            gaps_identified=obj.get("gaps_identified"),
                        )
                        db.add(coverage)
                        coverage_created += 1

        db.commit()

        return {"coverage_records_created": coverage_created}

    finally:
        db.close()


# ============ Feature 9: Peer Review Workflow ============

def create_peer_review_assignments(
    session_id: int,
    submission_post_ids: Optional[List[int]] = None,
    reviews_per_submission: int = 2,
) -> Dict[str, Any]:
    """Create AI-matched peer review assignments."""
    db = SessionLocal()
    try:
        session = db.query(SessionModel).filter(SessionModel.id == session_id).first()
        if not session:
            return {"error": "Session not found"}

        # Get submissions (top-level posts)
        if submission_post_ids:
            submissions = db.query(Post).filter(Post.id.in_(submission_post_ids)).all()
        else:
            submissions = db.query(Post).filter(
                Post.session_id == session_id,
                Post.parent_id == None
            ).all()

        if not submissions:
            return {"error": "No submissions found"}

        # Get potential reviewers (students who posted)
        reviewer_ids = set()
        for sub in submissions:
            reviewer_ids.add(sub.user_id)

        reviewers = db.query(User).filter(
            User.id.in_(reviewer_ids),
            User.role != "instructor"
        ).all()

        llm, model_name = get_llm_with_tracking()

        assignments_created = 0

        if llm and len(submissions) > 2:
            # Use AI for matching
            submissions_data = [
                {"post_id": s.id, "author_id": s.user_id, "content_preview": s.content[:200]}
                for s in submissions
            ]
            reviewers_data = [
                {"user_id": r.id, "name": r.name}
                for r in reviewers
            ]

            prompt = PEER_REVIEW_MATCHING_PROMPT.format(
                session_title=session.title,
                submissions=json.dumps(submissions_data, indent=2),
                reviewers=json.dumps(reviewers_data, indent=2),
            )

            response = invoke_llm_with_metrics(llm, prompt, model_name)
            if response.success:
                result = parse_json_response(response.content)
                if result and "assignments" in result:
                    for a in result["assignments"]:
                        submission = next((s for s in submissions if s.user_id == a["submission_author_id"]), None)
                        if submission and a["reviewer_id"] != a["submission_author_id"]:
                            assignment = PeerReviewAssignment(
                                session_id=session_id,
                                submission_post_id=submission.id,
                                author_id=a["submission_author_id"],
                                reviewer_id=a["reviewer_id"],
                                status="assigned",
                                match_rationale=a.get("match_rationale"),
                            )
                            db.add(assignment)
                            assignments_created += 1
        else:
            # Simple round-robin assignment
            reviewer_list = list(reviewers)
            for submission in submissions:
                assigned = 0
                for reviewer in reviewer_list:
                    if reviewer.id != submission.user_id and assigned < reviews_per_submission:
                        assignment = PeerReviewAssignment(
                            session_id=session_id,
                            submission_post_id=submission.id,
                            author_id=submission.user_id,
                            reviewer_id=reviewer.id,
                            status="assigned",
                            match_rationale="Assigned via round-robin",
                        )
                        db.add(assignment)
                        assignments_created += 1
                        assigned += 1

        db.commit()

        return {"assignments_created": assignments_created}

    finally:
        db.close()


# ============ Feature 10: Multi-Language Support ============

def translate_post(post_id: int, target_language: str) -> Dict[str, Any]:
    """Translate a single post to a target language."""
    db = SessionLocal()
    try:
        post = db.query(Post).filter(Post.id == post_id).first()
        if not post:
            return {"error": "Post not found"}

        llm, model_name = get_llm_with_tracking()
        if not llm:
            return {"error": "No LLM configured"}

        prompt = TRANSLATION_PROMPT.format(
            source_language="auto-detect",
            target_language=target_language,
            text=post.content,
        )

        response = invoke_llm_with_metrics(llm, prompt, model_name)
        if not response.success:
            return {"error": response.metrics.error_message}

        result = parse_json_response(response.content)
        if not result:
            return {"error": "Failed to parse translation response"}

        translation = PostTranslation(
            post_id=post_id,
            source_language=result.get("source_language_detected", "unknown"),
            target_language=target_language,
            translated_content=result.get("translated_text", ""),
            confidence_score=result.get("confidence_score", 0.8),
            model_name=model_name,
            total_tokens=response.metrics.total_tokens,
        )
        db.add(translation)
        db.commit()

        return {
            "translation_id": translation.id,
            "translated_content": translation.translated_content,
        }

    finally:
        db.close()


def translate_session_posts(session_id: int, target_language: str) -> Dict[str, Any]:
    """Translate all posts in a session to a target language."""
    db = SessionLocal()
    try:
        posts = db.query(Post).filter(Post.session_id == session_id).all()
        if not posts:
            return {"error": "No posts found"}

        translated_count = 0
        for post in posts:
            # Check if already translated
            existing = db.query(PostTranslation).filter(
                PostTranslation.post_id == post.id,
                PostTranslation.target_language == target_language
            ).first()

            if not existing:
                result = translate_post(post.id, target_language)
                if "translation_id" in result:
                    translated_count += 1

        return {
            "posts_translated": translated_count,
            "total_posts": len(posts),
        }

    finally:
        db.close()
