"""
Report Workflow: Post-Discussion Feedback Generation

This workflow generates structured feedback reports after a session ends.
Uses LangGraph for orchestration with the following pipeline:
    Cluster → AlignToObjectives → Misconceptions → BestPracticeAnswer → StudentSummary → ScoreAnswers

Includes:
- Poll results as classroom state evidence (Milestone 5)
- Token tracking and cost metrics (Milestone 6)
- Rolling summary for token control (Milestone 6)
- Participation tracking with enrollment data
- Answer scoring comparing student posts to best practice

All claims about student contributions include post_id citations.
Hallucination guardrails: "insufficient evidence" when claims aren't supported.
"""
import json
import logging
import time
from datetime import datetime
from typing import Any, Dict, List, TypedDict, Optional

from langgraph.graph import StateGraph, END
from sqlalchemy.orm import Session
from sqlalchemy import func

from api.core.database import SessionLocal
from api.models.session import Session as SessionModel
from api.models.course import Course, CourseResource
from api.models.post import Post
from api.models.user import User, UserRole
from api.models.poll import Poll, PollVote
from api.models.report import Report
from api.models.enrollment import Enrollment
from workflows.llm_utils import (
    get_llm_with_tracking,
    invoke_llm_with_metrics,
    parse_json_response,
    format_posts_for_prompt,
    create_rolling_summary_with_metadata,
    LLMMetrics,
    RollingSummaryResult,
    aggregate_metrics,
)
from workflows.prompts.report_prompts import (
    CLUSTER_POSTS_PROMPT,
    ALIGN_OBJECTIVES_PROMPT,
    MISCONCEPTIONS_PROMPT,
    BEST_PRACTICE_PROMPT,
    STUDENT_SUMMARY_PROMPT,
    SCORE_ANSWERS_PROMPT,
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
    posts: List[Dict[str, Any]]  # {post_id, author_role, content, timestamp, pinned, labels, user_id, user_name}
    older_posts_summary: Optional[str]  # Summary of older posts for token control

    # Rolling summary metadata (Milestone 6)
    rolling_summary_metadata: Optional[Dict[str, Any]]

    # Poll data (Milestone 5)
    poll_results: List[Dict[str, Any]]

    # Participation data
    participation_metrics: Optional[Dict[str, Any]]

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

    # After ScoreAnswers
    answer_scores: Optional[Dict[str, Any]]

    # Final outputs
    report_json: Optional[Dict[str, Any]]
    report_md: Optional[str]

    # Metadata
    model_name: str
    prompt_version: str
    errors: List[str]

    # Observability (Milestone 6)
    llm_metrics: List[LLMMetrics]
    start_time: float


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

    llm, model_name = get_llm_with_tracking()
    state["model_name"] = model_name or "fallback"

    session_topics = []
    if state["session_plan"]:
        session_topics = state["session_plan"].get("topics", [])

    # Include older posts summary if available
    posts_text = format_posts_for_prompt(state["posts"])
    if state.get("older_posts_summary"):
        posts_text = state["older_posts_summary"] + "\n\n" + posts_text

    if llm:
        prompt = CLUSTER_POSTS_PROMPT.format(
            session_title=state["session_title"],
            session_topics=", ".join(session_topics) if session_topics else "General discussion",
            posts_formatted=posts_text,
        )

        response = invoke_llm_with_metrics(llm, prompt, model_name)
        state["llm_metrics"].append(response.metrics)

        if response.success:
            clusters = parse_json_response(response.content)
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

    llm, model_name = get_llm_with_tracking()

    if llm and state["objectives"]:
        prompt = ALIGN_OBJECTIVES_PROMPT.format(
            objectives="\n".join(f"- {obj}" for obj in state["objectives"]),
            clusters_json=json.dumps(state["clusters"], indent=2),
            posts_formatted=format_posts_for_prompt(state["posts"]),
        )

        response = invoke_llm_with_metrics(llm, prompt, model_name)
        state["llm_metrics"].append(response.metrics)

        if response.success:
            alignment = parse_json_response(response.content)
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

    llm, model_name = get_llm_with_tracking()

    session_topics = state["session_plan"].get("topics", []) if state["session_plan"] else []

    if llm:
        prompt = MISCONCEPTIONS_PROMPT.format(
            session_topics=", ".join(session_topics) if session_topics else "General topics",
            syllabus_text=state["syllabus_text"] or "No syllabus provided.",
            resources_text=state["resources_text"] or "No additional resources.",
            posts_formatted=format_posts_for_prompt(state["posts"]),
        )

        response = invoke_llm_with_metrics(llm, prompt, model_name)
        state["llm_metrics"].append(response.metrics)

        if response.success:
            misconceptions = parse_json_response(response.content)
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

    llm, model_name = get_llm_with_tracking()

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

        response = invoke_llm_with_metrics(llm, prompt, model_name)
        state["llm_metrics"].append(response.metrics)

        if response.success:
            best_practice = parse_json_response(response.content)
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

    llm, model_name = get_llm_with_tracking()

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

        response = invoke_llm_with_metrics(llm, prompt, model_name)
        state["llm_metrics"].append(response.metrics)

        if response.success:
            summary = parse_json_response(response.content)
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


def score_student_answers(state: ReportState) -> ReportState:
    """Node 6: Score student answers against the best practice answer."""
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
            f"[Post #{p['post_id']} by User {p.get('user_id', 'Unknown')} ({p.get('user_name', 'Unknown')})]\n{p['content']}"
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
        content_len = len(p.get("content", ""))
        if content_len > 200:
            score += 15  # Longer responses get bonus
        if content_len > 500:
            score += 10  # Even longer get more
        if "high-quality" in (p.get("labels") or []):
            score += 25  # Instructor marked as high quality
        if "needs-clarification" in (p.get("labels") or []):
            score -= 20  # Needs work

        score = max(0, min(100, score))  # Clamp to 0-100

        fallback_scores.append({
            "user_id": p.get("user_id"),
            "user_name": p.get("user_name"),
            "post_id": p["post_id"],
            "score": score,
            "key_points_covered": [],
            "missing_points": [],
            "feedback": "Automated scoring based on instructor labels and post length"
        })

    if fallback_scores:
        scores_only = [s["score"] for s in fallback_scores]
        avg_score = sum(scores_only) / len(scores_only)
        highest = max(fallback_scores, key=lambda x: x["score"])
        lowest = min(fallback_scores, key=lambda x: x["score"])

        state["answer_scores"] = {
            "student_scores": fallback_scores,
            "class_statistics": {
                "average_score": round(avg_score, 1),
                "highest_score": highest["score"],
                "lowest_score": lowest["score"],
                "score_distribution": {
                    "excellent": sum(1 for s in scores_only if s >= 90),
                    "good": sum(1 for s in scores_only if 75 <= s < 90),
                    "satisfactory": sum(1 for s in scores_only if 60 <= s < 75),
                    "needs_improvement": sum(1 for s in scores_only if 40 <= s < 60),
                    "insufficient": sum(1 for s in scores_only if s < 40),
                }
            },
            "closest_to_correct": {
                "user_id": highest.get("user_id"),
                "user_name": highest.get("user_name"),
                "post_id": highest.get("post_id"),
                "score": highest.get("score")
            },
            "furthest_from_correct": {
                "user_id": lowest.get("user_id"),
                "user_name": lowest.get("user_name"),
                "post_id": lowest.get("post_id"),
                "score": lowest.get("score")
            },
            "note": "Fallback scoring used - LLM unavailable"
        }
    else:
        state["answer_scores"] = {
            "student_scores": [],
            "class_statistics": None,
            "note": "No scores generated"
        }

    return state


# ============ Report Generation ============

def compile_report(state: ReportState) -> Dict[str, Any]:
    """Compile all workflow outputs into final report_json, including poll results."""
    clusters = state["clusters"] or {}
    alignment = state["objectives_alignment"] or {}
    misconceptions = state["misconceptions"] or {}
    best_practice = state["best_practice"] or {}
    student_summary = state["student_summary"] or {}
    rolling_meta = state.get("rolling_summary_metadata") or {}

    # Aggregate LLM metrics
    aggregated_metrics = aggregate_metrics(state["llm_metrics"])

    return {
        "session_id": state["session_id"],
        "session_title": state["session_title"],
        "generated_at": datetime.utcnow().isoformat(),
        "model_name": state["model_name"],

        "summary": {
            "total_posts": rolling_meta.get("total_posts", len(state["posts"])),
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

        # Poll results as classroom evidence (Milestone 5)
        "poll_results": state.get("poll_results", []),

        # Participation metrics
        "participation": state.get("participation_metrics", {}),

        # Answer scoring
        "answer_scores": state.get("answer_scores", {}),

        # Rolling summary metadata for explainability (Milestone 6)
        "rolling_summary": {
            "summarization_applied": rolling_meta.get("summarization_applied", False),
            "total_posts": rolling_meta.get("total_posts", len(state["posts"])),
            "posts_summarized": rolling_meta.get("posts_summarized", 0),
            "recent_posts_analyzed": rolling_meta.get("recent_posts_analyzed", len(state["posts"])),
            "older_posts_summary": rolling_meta.get("older_posts_summary"),
        },

        # Observability metadata (Milestone 6)
        "observability": {
            "total_tokens": aggregated_metrics.total_tokens,
            "prompt_tokens": aggregated_metrics.prompt_tokens,
            "completion_tokens": aggregated_metrics.completion_tokens,
            "estimated_cost_usd": aggregated_metrics.estimated_cost_usd,
            "execution_time_seconds": round(time.time() - state["start_time"], 2),
            "llm_calls": len(state["llm_metrics"]),
            "used_fallback": aggregated_metrics.used_fallback,
            "retry_count": aggregated_metrics.retry_count,
        },

        "errors": state["errors"] if state["errors"] else None,
    }


def generate_markdown_report(report_json: Dict[str, Any]) -> str:
    """Generate markdown version of the report, including poll results."""
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

    # Poll Results as Classroom Evidence (Milestone 5)
    poll_results = report_json.get("poll_results", [])
    if poll_results:
        lines.append("## Classroom Evidence (Poll Results)")
        lines.append("")
        lines.append("The following polls were conducted during this session to gauge understanding:")
        lines.append("")
        for poll in poll_results:
            lines.append(f"### Poll: {poll.get('question', 'Unknown')}")
            lines.append(f"*Total votes: {poll.get('total_votes', 0)}*")
            lines.append("")
            options = poll.get("options", [])
            counts = poll.get("vote_counts", [])
            total = poll.get("total_votes", 1) or 1
            for opt, count in zip(options, counts):
                pct = (count / total * 100)
                bar = "█" * int(pct / 5) + "░" * (20 - int(pct / 5))
                lines.append(f"- {opt}: **{count}** ({pct:.1f}%) {bar}")
            lines.append("")
            if poll.get("interpretation"):
                lines.append(f"*Interpretation: {poll['interpretation']}*")
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

    # Participation Metrics
    participation = report_json.get("participation", {})
    if participation and participation.get("total_enrolled_students", 0) > 0:
        lines.append("---")
        lines.append("")
        lines.append("# Participation Summary")
        lines.append("")
        lines.append(f"- **Enrolled students**: {participation.get('total_enrolled_students', 'N/A')}")
        lines.append(f"- **Students who participated**: {participation.get('participation_count', 0)}")
        lines.append(f"- **Participation rate**: {participation.get('participation_rate', 0)}%")
        lines.append("")

        non_participants = participation.get("students_who_did_not_participate", [])
        if non_participants:
            lines.append("### Students Who Did Not Participate")
            for s in non_participants:
                lines.append(f"- {s.get('name', 'Unknown')} (ID: {s.get('user_id')})")
            lines.append("")

    # Answer Scoring
    scores = report_json.get("answer_scores", {})
    if scores and scores.get("student_scores"):
        lines.append("---")
        lines.append("")
        lines.append("# Answer Scoring")
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
            name = closest.get('user_name') or f"User {closest.get('user_id')}"
            lines.append(f"🏆 **Closest to Correct:** {name} (Post #{closest.get('post_id')}) - Score: {closest.get('score')}")
        if furthest:
            name = furthest.get('user_name') or f"User {furthest.get('user_id')}"
            lines.append(f"📚 **Needs Most Improvement:** {name} (Post #{furthest.get('post_id')}) - Score: {furthest.get('score')}")
        lines.append("")

        # Individual scores table
        lines.append("### Individual Scores")
        lines.append("")
        lines.append("| Student | Post | Score | Feedback |")
        lines.append("|---------|------|-------|----------|")

        for s in sorted(scores["student_scores"], key=lambda x: x.get("score", 0), reverse=True):
            name = s.get("user_name") or f"User {s.get('user_id')}"
            feedback = s.get("feedback", "")[:50] + "..." if len(s.get("feedback", "")) > 50 else s.get("feedback", "")
            lines.append(f"| {name} | #{s.get('post_id')} | {s.get('score')}/100 | {feedback} |")

        lines.append("")

    # Observability footer
    obs = report_json.get("observability", {})
    if obs:
        lines.append("---")
        lines.append("")
        lines.append("*Report Metadata:*")
        lines.append(f"- Model: {report_json.get('model_name', 'N/A')}")
        lines.append(f"- Tokens: {obs.get('total_tokens', 'N/A')} (prompt: {obs.get('prompt_tokens', 'N/A')}, completion: {obs.get('completion_tokens', 'N/A')})")
        lines.append(f"- Estimated cost: ${obs.get('estimated_cost_usd', 0):.4f}")
        lines.append(f"- Execution time: {obs.get('execution_time_seconds', 'N/A')}s")
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
    workflow.add_node("score_student_answers", score_student_answers)

    # Define edges (linear flow)
    workflow.set_entry_point("cluster_posts")
    workflow.add_edge("cluster_posts", "align_to_objectives")
    workflow.add_edge("align_to_objectives", "identify_misconceptions")
    workflow.add_edge("identify_misconceptions", "generate_best_practice")
    workflow.add_edge("generate_best_practice", "generate_student_summary")
    workflow.add_edge("generate_student_summary", "score_student_answers")
    workflow.add_edge("score_student_answers", END)

    return workflow.compile()


# ============ Poll Results Fetching (Milestone 5) ============

def fetch_poll_results(db: Session, session_id: int) -> List[Dict[str, Any]]:
    """
    Fetch all poll results for a session.

    Returns list of poll results with vote counts and percentages.
    """
    polls = db.query(Poll).filter(Poll.session_id == session_id).all()

    poll_results = []
    for poll in polls:
        votes = db.query(PollVote).filter(PollVote.poll_id == poll.id).all()
        options = poll.options_json or []

        # Count votes per option
        vote_counts = [0] * len(options)
        for v in votes:
            if 0 <= v.option_index < len(options):
                vote_counts[v.option_index] += 1

        total_votes = len(votes)

        # Generate interpretation based on results
        interpretation = None
        if total_votes > 0:
            max_votes = max(vote_counts)
            max_idx = vote_counts.index(max_votes)
            max_pct = (max_votes / total_votes * 100)

            if max_pct >= 70:
                interpretation = f"Strong consensus ({max_pct:.0f}%) around: {options[max_idx]}"
            elif max_pct >= 50:
                interpretation = f"Majority ({max_pct:.0f}%) chose: {options[max_idx]}"
            else:
                interpretation = "Mixed responses indicate diverse perspectives or potential confusion."

        poll_results.append({
            "poll_id": poll.id,
            "question": poll.question,
            "options": options,
            "vote_counts": vote_counts,
            "total_votes": total_votes,
            "percentages": [
                round((c / total_votes * 100), 1) if total_votes > 0 else 0
                for c in vote_counts
            ],
            "interpretation": interpretation,
            "created_at": poll.created_at.isoformat() if poll.created_at else None,
        })

    return poll_results


# ============ Participation Metrics ============

def calculate_participation_metrics(
    db: Session,
    session_id: int,
    course_id: int
) -> Dict[str, Any]:
    """
    Calculate participation metrics for a session based on enrolled students.

    Returns:
        Dict with participation rate, participants, and non-participants
    """
    # Get enrolled students for the course
    enrolled_students = (
        db.query(User)
        .join(Enrollment, User.id == Enrollment.user_id)
        .filter(
            Enrollment.course_id == course_id,
            User.role == UserRole.student
        )
        .all()
    )

    enrolled_ids = {s.id for s in enrolled_students}
    enrolled_count = len(enrolled_ids)

    if enrolled_count == 0:
        return {
            "total_enrolled_students": 0,
            "students_who_participated": [],
            "participation_count": 0,
            "students_who_did_not_participate": [],
            "non_participation_count": 0,
            "participation_rate": 0.0,
            "note": "No students enrolled in course"
        }

    # Get students who posted in this session
    posts_by_student = (
        db.query(
            Post.user_id,
            User.name,
            func.count(Post.id).label('post_count')
        )
        .join(User, Post.user_id == User.id)
        .filter(
            Post.session_id == session_id,
            User.role == UserRole.student
        )
        .group_by(Post.user_id, User.name)
        .all()
    )

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


# ============ Main Entry Point ============

def run_report_workflow(session_id: int) -> Dict[str, Any]:
    """
    Generate post-discussion feedback report using LangGraph pipeline.

    Pipeline: Cluster → AlignToObjectives → Misconceptions → BestPracticeAnswer → StudentSummary

    Includes:
    - Poll results as classroom evidence (Milestone 5)
    - Token tracking and observability (Milestone 6)
    - Rolling summary for token control (Milestone 6)

    Args:
        session_id: ID of the session to generate report for

    Returns:
        Dict with generated report and metadata
    """
    db: Session = SessionLocal()
    start_time = time.time()
    error_message = None

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
                "user_id": user.id,
                "user_name": user.name,
                "author_role": user.role.value if user.role else "student",
                "content": post.content,
                "timestamp": post.created_at.isoformat() if post.created_at else "",
                "pinned": post.pinned,
                "labels": post.labels_json or [],
            }
            for post, user in posts_with_users
        ]

        # Calculate participation metrics
        participation_metrics = calculate_participation_metrics(db, session_id, course.id)
        logger.info(f"Participation rate: {participation_metrics.get('participation_rate', 0)}%")

        # Apply rolling summary for token control (Milestone 6)
        rolling_result = create_rolling_summary_with_metadata(posts_data, max_posts=30)
        recent_posts = rolling_result.recent_posts
        older_summary = rolling_result.older_summary_text

        # Build rolling summary metadata for explainability
        rolling_summary_metadata = {
            "summarization_applied": rolling_result.summarization_applied,
            "total_posts": rolling_result.total_posts,
            "posts_summarized": rolling_result.posts_summarized,
            "recent_posts_analyzed": rolling_result.recent_posts_count,
            "older_posts_summary": rolling_result.older_summary_text,
        }

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

        # Fetch poll results (Milestone 5)
        poll_results = fetch_poll_results(db, session_id)
        logger.info(f"Found {len(poll_results)} polls for session {session_id}")

        # Prepare initial state
        initial_state: ReportState = {
            "session_id": session_id,
            "session_title": session.title,
            "session_plan": session.plan_json,
            "case_prompt": case_prompt,
            "syllabus_text": course.syllabus_text or "",
            "objectives": objectives,
            "resources_text": resources_text,
            "posts": recent_posts,
            "older_posts_summary": older_summary,
            "rolling_summary_metadata": rolling_summary_metadata,
            "poll_results": poll_results,
            "participation_metrics": participation_metrics,
            "clusters": None,
            "objectives_alignment": None,
            "misconceptions": None,
            "best_practice": None,
            "student_summary": None,
            "answer_scores": None,
            "report_json": None,
            "report_md": None,
            "model_name": "",
            "prompt_version": "v1.0",
            "errors": [],
            "llm_metrics": [],
            "start_time": start_time,
        }

        # Run LangGraph workflow
        graph = build_report_graph()
        final_state = graph.invoke(initial_state)

        # Compile final report
        report_json = compile_report(final_state)
        report_md = generate_markdown_report(report_json)

        # Aggregate metrics for database storage
        aggregated_metrics = aggregate_metrics(final_state["llm_metrics"])
        execution_time = round(time.time() - start_time, 2)
        used_fallback = 1 if aggregated_metrics.used_fallback or final_state["model_name"] == "fallback" else 0

        # Save to database
        version = f"v_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"

        db_report = Report(
            session_id=session_id,
            version=version,
            report_md=report_md,
            report_json=report_json,
            model_name=final_state["model_name"],
            prompt_version=final_state["prompt_version"],
            # Observability fields (Milestone 6)
            execution_time_seconds=execution_time,
            total_tokens=aggregated_metrics.total_tokens,
            prompt_tokens=aggregated_metrics.prompt_tokens,
            completion_tokens=aggregated_metrics.completion_tokens,
            estimated_cost_usd=aggregated_metrics.estimated_cost_usd,
            used_fallback=used_fallback,
            error_message=aggregated_metrics.error_message,
            retry_count=aggregated_metrics.retry_count,  # Track LLM retries
        )
        db.add(db_report)
        db.commit()

        logger.info(f"Report workflow complete for session {session_id}, version {version}")

        return {
            "session_id": session_id,
            "version": version,
            "report_json": report_json,
            "report_md": report_md,
            "observability": {
                "execution_time_seconds": execution_time,
                "total_tokens": aggregated_metrics.total_tokens,
                "estimated_cost_usd": aggregated_metrics.estimated_cost_usd,
                "used_fallback": used_fallback == 1,
            },
        }

    except Exception as e:
        db.rollback()
        error_message = str(e)
        logger.exception(f"Report workflow failed for session {session_id}")

        # Try to save error report
        try:
            execution_time = round(time.time() - start_time, 2)
            version = f"error_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"
            db_report = Report(
                session_id=session_id,
                version=version,
                report_md=None,
                report_json={"error": error_message},
                model_name="error",
                prompt_version="v1.0",
                execution_time_seconds=execution_time,
                error_message=error_message,
            )
            db.add(db_report)
            db.commit()
        except Exception:
            pass

        return {"error": error_message, "session_id": session_id}

    finally:
        db.close()
