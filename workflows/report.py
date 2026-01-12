"""
Report Workflow: Post-Discussion Feedback Generation

This workflow generates structured feedback reports after a session ends.
Uses LangGraph for orchestration with the following pipeline:
    Cluster → AlignToObjectives → Misconceptions → BestPracticeAnswer → StudentSummary

All claims about student contributions include post_id citations.
Hallucination guardrails: "insufficient evidence" when claims aren't supported.
"""
import json
import logging
from datetime import datetime
from typing import Any, Dict, List, TypedDict, Optional

from langgraph.graph import StateGraph, END
from sqlalchemy.orm import Session

from api.core.config import get_settings
from api.core.database import SessionLocal
from api.models.session import Session as SessionModel
from api.models.course import Course, CourseResource
from api.models.post import Post
from api.models.user import User
from api.models.poll import Poll, PollVote
from api.models.report import Report
from workflows.prompts.report_prompts import (
    CLUSTER_POSTS_PROMPT,
    ALIGN_OBJECTIVES_PROMPT,
    MISCONCEPTIONS_PROMPT,
    BEST_PRACTICE_PROMPT,
    STUDENT_SUMMARY_PROMPT,
)

logger = logging.getLogger(__name__)


# ============ State Definition ============

class ReportState(TypedDict):
    """State passed through the report workflow."""
    # Input data
    session_id: int
    session_title: str
    session_plan: Optional[Dict[str, Any]]
    case_prompt: str
    syllabus_text: str
    objectives: List[str]
    resources_text: str
    posts: List[Dict[str, Any]]  # {post_id, author_role, content, timestamp, pinned, labels}

    # After Cluster
    clusters: Optional[Dict[str, Any]]

    # After AlignToObjectives
    objectives_alignment: Optional[Dict[str, Any]]

    # After Misconceptions
    misconceptions: Optional[Dict[str, Any]]

    # After BestPracticeAnswer
    best_practice: Optional[Dict[str, Any]]

    # After StudentSummary
    student_summary: Optional[Dict[str, Any]]

    # Final outputs
    report_json: Optional[Dict[str, Any]]
    report_md: Optional[str]

    # Metadata
    model_name: str
    prompt_version: str
    errors: List[str]


# ============ LLM Helpers ============

def get_llm():
    """Get the appropriate LLM based on available API keys."""
    settings = get_settings()

    if settings.openai_api_key:
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(
            model="gpt-4o-mini",
            api_key=settings.openai_api_key,
            temperature=0.7,
        ), "gpt-4o-mini"
    elif settings.anthropic_api_key:
        from langchain_anthropic import ChatAnthropic
        return ChatAnthropic(
            model="claude-3-haiku-20240307",
            api_key=settings.anthropic_api_key,
            temperature=0.7,
        ), "claude-3-haiku"
    else:
        return None, None


def invoke_llm(llm, prompt: str) -> Optional[str]:
    """Invoke LLM and return text response."""
    try:
        response = llm.invoke(prompt)
        return response.content
    except Exception as e:
        logger.exception(f"LLM invocation failed: {e}")
        return None


def parse_json_response(response: str) -> Optional[Dict[str, Any]]:
    """Parse JSON from LLM response, handling markdown code blocks."""
    if not response:
        return None

    text = response.strip()
    if text.startswith("```json"):
        text = text[7:]
    elif text.startswith("```"):
        text = text[3:]
    if text.endswith("```"):
        text = text[:-3]
    text = text.strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse JSON: {e}\nResponse: {text[:500]}")
        return None


def format_posts_for_prompt(posts: List[Dict[str, Any]]) -> str:
    """Format posts for inclusion in prompts."""
    lines = []
    for p in posts:
        role_label = "INSTRUCTOR" if p["author_role"] == "instructor" else "STUDENT"
        pinned = " [PINNED]" if p.get("pinned") else ""
        labels = f" [{', '.join(p.get('labels', []))}]" if p.get("labels") else ""
        lines.append(f"[Post #{p['post_id']}] ({role_label}{pinned}{labels}) {p['timestamp']}")
        lines.append(f"  {p['content']}")
        lines.append("")
    return "\n".join(lines) if lines else "No posts in this discussion."


# ============ Workflow Nodes ============

def cluster_posts(state: ReportState) -> ReportState:
    """Node 1: Cluster posts into themes."""
    logger.info(f"Cluster: Analyzing {len(state['posts'])} posts")

    if not state["posts"]:
        state["clusters"] = {
            "clusters": [],
            "unclustered_posts": [],
            "discussion_quality": "insufficient_data",
            "participation_summary": {"total_posts": 0, "student_posts": 0, "instructor_posts": 0}
        }
        state["errors"].append("No posts to analyze")
        return state

    llm, model_name = get_llm()
    state["model_name"] = model_name or "fallback"

    session_topics = []
    if state["session_plan"]:
        session_topics = state["session_plan"].get("topics", [])

    if llm:
        prompt = CLUSTER_POSTS_PROMPT.format(
            session_title=state["session_title"],
            session_topics=", ".join(session_topics) if session_topics else "General discussion",
            posts_formatted=format_posts_for_prompt(state["posts"]),
        )

        response = invoke_llm(llm, prompt)
        clusters = parse_json_response(response)

        if clusters:
            state["clusters"] = clusters
            logger.info(f"Cluster: Found {len(clusters.get('clusters', []))} themes")
            return state

    # Fallback clustering
    student_posts = [p for p in state["posts"] if p["author_role"] == "student"]
    instructor_posts = [p for p in state["posts"] if p["author_role"] == "instructor"]

    state["clusters"] = {
        "clusters": [
            {
                "theme": "General Discussion",
                "description": "All discussion posts",
                "post_ids": [p["post_id"] for p in state["posts"]],
                "key_points": ["Discussion occurred but clustering requires LLM"]
            }
        ],
        "unclustered_posts": [],
        "discussion_quality": "unknown",
        "participation_summary": {
            "total_posts": len(state["posts"]),
            "student_posts": len(student_posts),
            "instructor_posts": len(instructor_posts),
        }
    }
    state["errors"].append("Used fallback clustering (no LLM available)")
    return state


def align_to_objectives(state: ReportState) -> ReportState:
    """Node 2: Align discussion to learning objectives."""
    logger.info("AlignToObjectives: Mapping clusters to objectives")

    llm, _ = get_llm()

    if llm and state["objectives"]:
        prompt = ALIGN_OBJECTIVES_PROMPT.format(
            objectives="\n".join(f"- {obj}" for obj in state["objectives"]),
            clusters_json=json.dumps(state["clusters"], indent=2),
            posts_formatted=format_posts_for_prompt(state["posts"]),
        )

        response = invoke_llm(llm, prompt)
        alignment = parse_json_response(response)

        if alignment:
            state["objectives_alignment"] = alignment
            logger.info(f"AlignToObjectives: Found {len(alignment.get('strong_contributions', []))} strong contributions")
            return state

    # Fallback alignment
    pinned_posts = [p for p in state["posts"] if p.get("pinned")]
    high_quality = [p for p in state["posts"] if "high-quality" in (p.get("labels") or [])]

    state["objectives_alignment"] = {
        "objective_alignment": [
            {
                "objective": obj,
                "coverage": "insufficient_evidence",
                "evidence_post_ids": [],
                "explanation": "Automated alignment requires LLM analysis"
            }
            for obj in state["objectives"]
        ],
        "strong_contributions": [
            {"post_id": p["post_id"], "reason": "Marked as high quality by instructor", "related_objectives": []}
            for p in high_quality
        ] + [
            {"post_id": p["post_id"], "reason": "Pinned by instructor", "related_objectives": []}
            for p in pinned_posts if p not in high_quality
        ],
        "gaps": ["Detailed gap analysis requires LLM"]
    }
    return state


def identify_misconceptions(state: ReportState) -> ReportState:
    """Node 3: Identify misconceptions with corrections."""
    logger.info("Misconceptions: Analyzing for incorrect understanding")

    llm, _ = get_llm()

    session_topics = state["session_plan"].get("topics", []) if state["session_plan"] else []

    if llm:
        prompt = MISCONCEPTIONS_PROMPT.format(
            session_topics=", ".join(session_topics) if session_topics else "General topics",
            syllabus_text=state["syllabus_text"] or "No syllabus provided.",
            resources_text=state["resources_text"] or "No additional resources.",
            posts_formatted=format_posts_for_prompt(state["posts"]),
        )

        response = invoke_llm(llm, prompt)
        misconceptions = parse_json_response(response)

        if misconceptions:
            state["misconceptions"] = misconceptions
            logger.info(f"Misconceptions: Found {len(misconceptions.get('misconceptions', []))} issues")
            return state

    # Fallback - check for posts marked as needing clarification
    needs_clarification = [p for p in state["posts"] if "needs-clarification" in (p.get("labels") or [])]

    state["misconceptions"] = {
        "misconceptions": [
            {
                "post_id": p["post_id"],
                "misconception": "Flagged by instructor as needing clarification",
                "quote": p["content"][:100] + "..." if len(p["content"]) > 100 else p["content"],
                "correction": "Please review this post for accuracy",
                "source": "Instructor flag"
            }
            for p in needs_clarification
        ],
        "common_confusion_points": [],
        "overall_understanding": "unknown",
        "evidence_note": "Detailed misconception analysis requires LLM" if not needs_clarification else None
    }
    return state


def generate_best_practice(state: ReportState) -> ReportState:
    """Node 4: Generate best-practice answer grounded in materials."""
    logger.info("BestPracticeAnswer: Generating ideal answer")

    llm, _ = get_llm()

    case_prompt = state["case_prompt"] or "No specific case provided"
    if state["session_plan"] and state["session_plan"].get("case_prompt"):
        case_prompt = state["session_plan"]["case_prompt"]

    if llm:
        prompt = BEST_PRACTICE_PROMPT.format(
            session_plan=json.dumps(state["session_plan"], indent=2) if state["session_plan"] else "No session plan available",
            case_prompt=case_prompt,
            syllabus_text=state["syllabus_text"] or "No syllabus provided.",
            resources_text=state["resources_text"] or "No additional resources.",
            objectives="\n".join(f"- {obj}" for obj in state["objectives"]) if state["objectives"] else "No objectives specified.",
        )

        response = invoke_llm(llm, prompt)
        best_practice = parse_json_response(response)

        if best_practice:
            state["best_practice"] = best_practice
            logger.info("BestPracticeAnswer: Generated successfully")
            return state

    # Fallback
    key_concepts = []
    if state["session_plan"]:
        key_concepts = state["session_plan"].get("key_takeaways", []) or state["session_plan"].get("topics", [])

    state["best_practice"] = {
        "best_practice_answer": {
            "summary": f"This session covered: {state['session_title']}",
            "detailed_explanation": "Detailed best-practice answer requires LLM analysis of course materials.",
            "key_concepts": key_concepts[:5] if key_concepts else ["Review session materials"],
            "connection_to_objectives": [
                {"objective": obj, "how_addressed": "See course materials"}
                for obj in state["objectives"][:3]
            ],
            "sources_used": ["Syllabus", "Session plan"]
        },
        "suggested_next_steps": ["Review the session materials", "Complete any assigned readings"],
        "additional_resources": []
    }
    return state


def generate_student_summary(state: ReportState) -> ReportState:
    """Node 5: Generate student-facing summary."""
    logger.info("StudentSummary: Creating student feedback")

    llm, _ = get_llm()

    strong_contributions = state["objectives_alignment"].get("strong_contributions", []) if state["objectives_alignment"] else []
    misconceptions = state["misconceptions"].get("misconceptions", []) if state["misconceptions"] else []
    gaps = state["objectives_alignment"].get("gaps", []) if state["objectives_alignment"] else []
    objectives_coverage = state["objectives_alignment"].get("objective_alignment", []) if state["objectives_alignment"] else []

    if llm:
        prompt = STUDENT_SUMMARY_PROMPT.format(
            session_title=state["session_title"],
            strong_contributions=json.dumps(strong_contributions, indent=2) if strong_contributions else "No specific contributions highlighted",
            misconceptions=json.dumps(misconceptions, indent=2) if misconceptions else "No misconceptions identified",
            gaps=json.dumps(gaps, indent=2) if gaps else "No gaps identified",
            objectives_coverage=json.dumps(objectives_coverage, indent=2) if objectives_coverage else "Objectives not analyzed",
        )

        response = invoke_llm(llm, prompt)
        summary = parse_json_response(response)

        if summary:
            state["student_summary"] = summary
            logger.info("StudentSummary: Generated successfully")
            return state

    # Fallback summary
    state["student_summary"] = {
        "student_summary": {
            "what_you_did_well": [
                "Participated in the discussion",
                "Engaged with the case study" if state["case_prompt"] else "Explored the session topics"
            ],
            "what_to_improve": [
                "Continue to connect ideas to course objectives",
                "Review any concepts that were unclear"
            ],
            "key_takeaways": [
                f"Key topic: {state['session_title']}"
            ]
        },
        "practice_questions": [
            {
                "question": f"What are the main concepts from {state['session_title']}?",
                "hint": "Review the session materials",
                "related_objective": state["objectives"][0] if state["objectives"] else "General understanding"
            },
            {
                "question": "How would you apply what you learned to a real-world scenario?",
                "hint": "Think about practical applications",
                "related_objective": state["objectives"][1] if len(state["objectives"]) > 1 else "Application"
            },
            {
                "question": "What questions do you still have about this topic?",
                "hint": "Identify areas for further study",
                "related_objective": "Self-reflection"
            }
        ],
        "encouragement": "Keep up the good work! Every discussion helps deepen your understanding."
    }
    return state


# ============ Report Generation ============

def compile_report(state: ReportState) -> Dict[str, Any]:
    """Compile all workflow outputs into final report_json."""
    clusters = state["clusters"] or {}
    alignment = state["objectives_alignment"] or {}
    misconceptions = state["misconceptions"] or {}
    best_practice = state["best_practice"] or {}
    student_summary = state["student_summary"] or {}

    return {
        "session_id": state["session_id"],
        "session_title": state["session_title"],
        "generated_at": datetime.utcnow().isoformat(),
        "model_name": state["model_name"],

        "summary": {
            "total_posts": clusters.get("participation_summary", {}).get("total_posts", len(state["posts"])),
            "student_posts": clusters.get("participation_summary", {}).get("student_posts", 0),
            "instructor_posts": clusters.get("participation_summary", {}).get("instructor_posts", 0),
            "discussion_quality": clusters.get("discussion_quality", "unknown"),
        },

        "theme_clusters": clusters.get("clusters", []),

        "learning_objectives_alignment": alignment.get("objective_alignment", []),

        "strong_contributions": alignment.get("strong_contributions", []),

        "misconceptions": misconceptions.get("misconceptions", []),
        "common_confusion_points": misconceptions.get("common_confusion_points", []),
        "overall_understanding": misconceptions.get("overall_understanding", "unknown"),

        "best_practice_answer": best_practice.get("best_practice_answer", {}),
        "suggested_next_steps": best_practice.get("suggested_next_steps", []),

        "student_summary": student_summary.get("student_summary", {}),
        "practice_questions": student_summary.get("practice_questions", []),

        "gaps": alignment.get("gaps", []),
        "errors": state["errors"] if state["errors"] else None,
    }


def generate_markdown_report(report_json: Dict[str, Any]) -> str:
    """Generate markdown version of the report."""
    lines = [
        f"# Session Report: {report_json['session_title']}",
        f"*Generated: {report_json['generated_at'][:19].replace('T', ' ')} UTC*",
        "",
        "---",
        "",
        "## Summary",
        f"- **Total posts**: {report_json['summary']['total_posts']}",
        f"- **Student posts**: {report_json['summary']['student_posts']}",
        f"- **Instructor posts**: {report_json['summary']['instructor_posts']}",
        f"- **Discussion quality**: {report_json['summary']['discussion_quality']}",
        "",
    ]

    # Key Concepts
    best_practice = report_json.get("best_practice_answer", {})
    if best_practice.get("key_concepts"):
        lines.append("## Key Concepts")
        for concept in best_practice["key_concepts"]:
            lines.append(f"- {concept}")
        lines.append("")

    # Learning Objectives Alignment
    if report_json.get("learning_objectives_alignment"):
        lines.append("## Learning Objectives Alignment")
        for obj in report_json["learning_objectives_alignment"]:
            coverage_emoji = {"fully": "✅", "partially": "🔶", "not_covered": "❌", "insufficient_evidence": "❓"}.get(obj.get("coverage"), "❓")
            lines.append(f"- {coverage_emoji} **{obj.get('objective', 'Unknown')}**: {obj.get('coverage', 'unknown')}")
            if obj.get("evidence_post_ids"):
                lines.append(f"  - Evidence: Posts #{', #'.join(str(p) for p in obj['evidence_post_ids'])}")
            if obj.get("explanation"):
                lines.append(f"  - {obj['explanation']}")
        lines.append("")

    # Theme Clusters
    if report_json.get("theme_clusters"):
        lines.append("## Discussion Themes")
        for i, cluster in enumerate(report_json["theme_clusters"], 1):
            lines.append(f"### Theme {i}: {cluster.get('theme', 'Unknown')}")
            lines.append(f"{cluster.get('description', '')}")
            if cluster.get("post_ids"):
                lines.append(f"- **Posts**: #{', #'.join(str(p) for p in cluster['post_ids'])}")
            if cluster.get("key_points"):
                for point in cluster["key_points"]:
                    lines.append(f"- {point}")
            lines.append("")

    # Strong Contributions
    if report_json.get("strong_contributions"):
        lines.append("## Strong Contributions")
        for contrib in report_json["strong_contributions"]:
            lines.append(f"- **Post #{contrib.get('post_id', '?')}**: {contrib.get('reason', 'Good contribution')}")
        lines.append("")

    # Misconceptions
    if report_json.get("misconceptions"):
        lines.append("## Misconceptions Identified")
        for misc in report_json["misconceptions"]:
            lines.append(f"### Post #{misc.get('post_id', '?')}")
            lines.append(f"**Issue**: {misc.get('misconception', 'Unknown')}")
            if misc.get("quote"):
                lines.append(f"> \"{misc['quote']}\"")
            lines.append(f"**Correction**: {misc.get('correction', 'Review needed')}")
            if misc.get("source"):
                lines.append(f"*Source: {misc['source']}*")
            lines.append("")
    elif report_json.get("overall_understanding"):
        lines.append("## Misconceptions")
        lines.append(f"No significant misconceptions identified. Overall understanding: {report_json['overall_understanding']}")
        lines.append("")

    # Best Practice Answer
    if best_practice:
        lines.append("## Best Practice Answer")
        if best_practice.get("summary"):
            lines.append(f"**Summary**: {best_practice['summary']}")
            lines.append("")
        if best_practice.get("detailed_explanation"):
            lines.append(best_practice["detailed_explanation"])
            lines.append("")
        if best_practice.get("sources_used"):
            lines.append(f"*Sources: {', '.join(best_practice['sources_used'])}*")
            lines.append("")

    # Suggested Next Steps
    if report_json.get("suggested_next_steps"):
        lines.append("## Suggested Next Steps")
        for step in report_json["suggested_next_steps"]:
            lines.append(f"- {step}")
        lines.append("")

    # Gaps
    if report_json.get("gaps"):
        lines.append("## Coverage Gaps")
        for gap in report_json["gaps"]:
            lines.append(f"- {gap}")
        lines.append("")

    lines.append("---")
    lines.append("")

    # Student Summary Section
    lines.append("# Student Summary")
    lines.append("")

    student_summary = report_json.get("student_summary", {})
    if student_summary.get("what_you_did_well"):
        lines.append("## What You Did Well")
        for item in student_summary["what_you_did_well"]:
            lines.append(f"- {item}")
        lines.append("")

    if student_summary.get("what_to_improve"):
        lines.append("## What to Improve")
        for item in student_summary["what_to_improve"]:
            lines.append(f"- {item}")
        lines.append("")

    if student_summary.get("key_takeaways"):
        lines.append("## Key Takeaways")
        for item in student_summary["key_takeaways"]:
            lines.append(f"- {item}")
        lines.append("")

    # Practice Questions
    if report_json.get("practice_questions"):
        lines.append("## Practice Questions")
        for i, q in enumerate(report_json["practice_questions"], 1):
            lines.append(f"**{i}. {q.get('question', 'Question')}**")
            if q.get("hint"):
                lines.append(f"   *Hint: {q['hint']}*")
            if q.get("related_objective"):
                lines.append(f"   *Tests: {q['related_objective']}*")
            lines.append("")

    return "\n".join(lines)


# ============ Build Graph ============

def build_report_graph() -> StateGraph:
    """Build the LangGraph workflow for report generation."""
    workflow = StateGraph(ReportState)

    # Add nodes
    workflow.add_node("cluster_posts", cluster_posts)
    workflow.add_node("align_to_objectives", align_to_objectives)
    workflow.add_node("identify_misconceptions", identify_misconceptions)
    workflow.add_node("generate_best_practice", generate_best_practice)
    workflow.add_node("generate_student_summary", generate_student_summary)

    # Define edges (linear flow)
    workflow.set_entry_point("cluster_posts")
    workflow.add_edge("cluster_posts", "align_to_objectives")
    workflow.add_edge("align_to_objectives", "identify_misconceptions")
    workflow.add_edge("identify_misconceptions", "generate_best_practice")
    workflow.add_edge("generate_best_practice", "generate_student_summary")
    workflow.add_edge("generate_student_summary", END)

    return workflow.compile()


# ============ Main Entry Point ============

def run_report_workflow(session_id: int) -> Dict[str, Any]:
    """
    Generate post-discussion feedback report using LangGraph pipeline.

    Pipeline: Cluster → AlignToObjectives → Misconceptions → BestPracticeAnswer → StudentSummary

    Args:
        session_id: ID of the session to generate report for

    Returns:
        Dict with generated report and metadata
    """
    db: Session = SessionLocal()
    try:
        # Load session with course
        session = db.query(SessionModel).filter(SessionModel.id == session_id).first()
        if not session:
            return {"error": "Session not found", "session_id": session_id}

        course = db.query(Course).filter(Course.id == session.course_id).first()
        if not course:
            return {"error": "Course not found", "session_id": session_id}

        logger.info(f"Starting report workflow for session {session_id}: {session.title}")

        # Load posts with user roles (join posts → users)
        posts_with_users = (
            db.query(Post, User)
            .join(User, Post.user_id == User.id)
            .filter(Post.session_id == session_id)
            .order_by(Post.created_at.asc())
            .all()
        )

        posts_data = [
            {
                "post_id": post.id,
                "author_role": user.role.value if user.role else "student",
                "content": post.content,
                "timestamp": post.created_at.isoformat() if post.created_at else "",
                "pinned": post.pinned,
                "labels": post.labels_json or [],
            }
            for post, user in posts_with_users
        ]

        # Load course resources
        resources = db.query(CourseResource).filter(CourseResource.course_id == course.id).all()
        resources_text = "\n\n".join(
            f"[{r.resource_type}] {r.title}: {r.content or r.link or 'No content'}"
            for r in resources
        ) if resources else ""

        # Get case prompt from session's cases
        case_prompt = ""
        if session.cases:
            case_prompt = session.cases[0].prompt

        # Prepare objectives
        objectives = course.objectives_json if isinstance(course.objectives_json, list) else []

        # Prepare initial state
        initial_state: ReportState = {
            "session_id": session_id,
            "session_title": session.title,
            "session_plan": session.plan_json,
            "case_prompt": case_prompt,
            "syllabus_text": course.syllabus_text or "",
            "objectives": objectives,
            "resources_text": resources_text,
            "posts": posts_data,
            "clusters": None,
            "objectives_alignment": None,
            "misconceptions": None,
            "best_practice": None,
            "student_summary": None,
            "report_json": None,
            "report_md": None,
            "model_name": "",
            "prompt_version": "v1.0",
            "errors": [],
        }

        # Run LangGraph workflow
        graph = build_report_graph()
        final_state = graph.invoke(initial_state)

        # Compile final report
        report_json = compile_report(final_state)
        report_md = generate_markdown_report(report_json)

        # Save to database
        version = f"v_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"

        db_report = Report(
            session_id=session_id,
            version=version,
            report_md=report_md,
            report_json=report_json,
            model_name=final_state["model_name"],
            prompt_version=final_state["prompt_version"],
        )
        db.add(db_report)
        db.commit()

        logger.info(f"Report workflow complete for session {session_id}, version {version}")

        return {
            "session_id": session_id,
            "version": version,
            "report_json": report_json,
            "report_md": report_md,
        }

    except Exception as e:
        db.rollback()
        logger.exception(f"Report workflow failed for session {session_id}")
        return {"error": str(e), "session_id": session_id}

    finally:
        db.close()
