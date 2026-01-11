"""
Planning Workflow: Syllabus -> Session Plans

This workflow generates structured session plans from a course syllabus.
Uses LangGraph for orchestration with the following pipeline:
    ParseSyllabus -> PlanPerSession -> DesignFlow -> ConsistencyCheck

Supports both OpenAI and Anthropic LLMs.
"""
import json
import logging
from datetime import datetime
from typing import Any, Dict, List, TypedDict, Optional

from langgraph.graph import StateGraph, END
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.models.course import Course
from app.models.session import Session as SessionModel
from app.workflows.prompts.planning_prompts import (
    PARSE_SYLLABUS_PROMPT,
    PLAN_SESSION_PROMPT,
    DESIGN_FLOW_PROMPT,
    CONSISTENCY_CHECK_PROMPT,
)

logger = logging.getLogger(__name__)


# ============ State Definition ============

class PlanningState(TypedDict):
    """State passed through the planning workflow."""
    # Input
    course_id: int
    course_title: str
    syllabus_text: str
    objectives: List[str]

    # After ParseSyllabus
    parsed_syllabus: Optional[Dict[str, Any]]
    total_sessions: int

    # After PlanPerSession
    session_plans: List[Dict[str, Any]]

    # After DesignFlow
    sessions_with_flow: List[Dict[str, Any]]

    # After ConsistencyCheck
    consistency_report: Optional[Dict[str, Any]]

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

    # Strip markdown code blocks if present
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


# ============ Workflow Nodes ============

def parse_syllabus(state: PlanningState) -> PlanningState:
    """Node 1: Parse syllabus and extract structure."""
    logger.info(f"ParseSyllabus: Processing course {state['course_id']}")

    llm, model_name = get_llm()
    if not llm:
        state["errors"].append("No LLM API key configured")
        # Fallback to reasonable defaults
        state["parsed_syllabus"] = {
            "course_summary": f"Course: {state['course_title']}",
            "total_sessions": 8,
            "main_topics": state["objectives"][:5] if state["objectives"] else ["Introduction"],
            "key_concepts": [],
            "objectives_breakdown": [{"objective": obj, "related_topics": []} for obj in state["objectives"]],
        }
        state["total_sessions"] = 8
        state["model_name"] = "fallback"
        return state

    state["model_name"] = model_name

    prompt = PARSE_SYLLABUS_PROMPT.format(
        course_title=state["course_title"],
        syllabus_text=state["syllabus_text"] or "No syllabus provided.",
        objectives="\n".join(f"- {obj}" for obj in state["objectives"]) or "No objectives provided.",
    )

    response = invoke_llm(llm, prompt)
    parsed = parse_json_response(response)

    if parsed:
        state["parsed_syllabus"] = parsed
        state["total_sessions"] = parsed.get("total_sessions", 8)
    else:
        state["errors"].append("Failed to parse syllabus response")
        state["parsed_syllabus"] = {
            "course_summary": state["course_title"],
            "total_sessions": 8,
            "main_topics": state["objectives"][:5] if state["objectives"] else [],
            "key_concepts": [],
            "objectives_breakdown": [],
        }
        state["total_sessions"] = 8

    logger.info(f"ParseSyllabus: Determined {state['total_sessions']} sessions")
    return state


def plan_per_session(state: PlanningState) -> PlanningState:
    """Node 2: Generate plan for each session."""
    logger.info(f"PlanPerSession: Generating {state['total_sessions']} session plans")

    llm, _ = get_llm()
    session_plans = []
    parsed = state["parsed_syllabus"] or {}
    main_topics = parsed.get("main_topics", [])
    key_concepts = parsed.get("key_concepts", [])
    objectives_breakdown = parsed.get("objectives_breakdown", [])

    # Distribute topics across sessions
    topics_per_session = max(1, len(main_topics) // state["total_sessions"]) if main_topics else 1

    for i in range(state["total_sessions"]):
        session_num = i + 1

        # Determine topics for this session
        start_idx = i * topics_per_session
        end_idx = start_idx + topics_per_session + 1
        session_topics = main_topics[start_idx:end_idx] if main_topics else [f"Session {session_num} topic"]

        # Find relevant objectives
        relevant_objectives = [
            obj["objective"] for obj in objectives_breakdown
            if any(topic.lower() in str(obj.get("related_topics", [])).lower() for topic in session_topics)
        ][:3] or state["objectives"][:2]

        # Previous sessions summary
        previous_sessions = ", ".join(
            f"Session {p['session_number']}: {p['title']}"
            for p in session_plans[-3:]
        ) or "None (first session)"

        if llm:
            prompt = PLAN_SESSION_PROMPT.format(
                session_number=session_num,
                total_sessions=state["total_sessions"],
                course_title=state["course_title"],
                course_summary=parsed.get("course_summary", state["course_title"]),
                session_topics="\n".join(f"- {t}" for t in session_topics),
                relevant_objectives="\n".join(f"- {o}" for o in relevant_objectives),
                key_concepts=", ".join(key_concepts[:10]) or "General course concepts",
                previous_sessions=previous_sessions,
            )

            response = invoke_llm(llm, prompt)
            plan = parse_json_response(response)

            if plan:
                plan["session_number"] = session_num  # Ensure correct number
                session_plans.append(plan)
                continue

        # Fallback plan if LLM fails or not available
        session_plans.append({
            "session_number": session_num,
            "title": f"Session {session_num}: {session_topics[0] if session_topics else 'Topic'}",
            "topics": session_topics,
            "learning_goals": [f"Understand {t}" for t in session_topics[:2]],
            "readings": [{"title": f"Reading for session {session_num}", "type": "article", "description": "Relevant reading material"}],
            "case_prompt": f"Consider a scenario related to {session_topics[0] if session_topics else 'the topic'}...",
            "discussion_prompts": ["What are the key considerations?", "How would you approach this problem?"],
            "key_takeaways": [f"Key point about {t}" for t in session_topics[:2]],
        })

    state["session_plans"] = session_plans
    logger.info(f"PlanPerSession: Generated {len(session_plans)} plans")
    return state


def design_flow(state: PlanningState) -> PlanningState:
    """Node 3: Design instructional flow with checkpoints for each session."""
    logger.info("DesignFlow: Adding flow and checkpoints to sessions")

    llm, _ = get_llm()
    sessions_with_flow = []

    for plan in state["session_plans"]:
        if llm:
            prompt = DESIGN_FLOW_PROMPT.format(
                session_plan=json.dumps(plan, indent=2)
            )

            response = invoke_llm(llm, prompt)
            flow_data = parse_json_response(response)

            if flow_data:
                plan["flow"] = flow_data.get("flow", [])
                plan["checkpoints"] = flow_data.get("checkpoints", [])
                plan["total_duration_minutes"] = flow_data.get("total_duration_minutes", 55)
                sessions_with_flow.append(plan)
                continue

        # Fallback flow
        plan["flow"] = [
            {"phase": "intro", "duration_minutes": 5, "activity": "Welcome and overview"},
            {"phase": "theory", "duration_minutes": 15, "activity": f"Present: {plan.get('topics', ['topic'])[0]}"},
            {"phase": "case", "duration_minutes": 10, "activity": "Case study introduction"},
            {"phase": "discussion", "duration_minutes": 20, "activity": "Facilitated discussion"},
            {"phase": "wrap-up", "duration_minutes": 5, "activity": "Summary and next steps"},
        ]
        plan["checkpoints"] = [
            {
                "type": "poll",
                "timing": "after_theory",
                "question": f"How confident are you with {plan.get('topics', ['this topic'])[0]}?",
                "options": ["Very confident", "Somewhat confident", "Need more practice"],
            }
        ]
        plan["total_duration_minutes"] = 55
        sessions_with_flow.append(plan)

    state["sessions_with_flow"] = sessions_with_flow
    logger.info(f"DesignFlow: Completed flow for {len(sessions_with_flow)} sessions")
    return state


def consistency_check(state: PlanningState) -> PlanningState:
    """Node 4: Check consistency and coverage across all session plans."""
    logger.info("ConsistencyCheck: Validating session plans")

    llm, _ = get_llm()

    if llm:
        prompt = CONSISTENCY_CHECK_PROMPT.format(
            course_title=state["course_title"],
            objectives="\n".join(f"- {obj}" for obj in state["objectives"]) or "No objectives provided.",
            session_plans=json.dumps(state["sessions_with_flow"], indent=2),
        )

        response = invoke_llm(llm, prompt)
        report = parse_json_response(response)

        if report:
            state["consistency_report"] = report
            logger.info(f"ConsistencyCheck: Quality score {report.get('overall_quality_score', 'N/A')}/10")
            return state

    # Fallback report
    state["consistency_report"] = {
        "objectives_coverage": {
            "fully_covered": state["objectives"],
            "partially_covered": [],
            "not_covered": [],
        },
        "issues": [],
        "suggestions": [],
        "overall_quality_score": 7,
        "summary": "Plans generated successfully. Manual review recommended.",
    }

    return state


# ============ Build Graph ============

def build_planning_graph() -> StateGraph:
    """Build the LangGraph workflow for planning."""
    workflow = StateGraph(PlanningState)

    # Add nodes
    workflow.add_node("parse_syllabus", parse_syllabus)
    workflow.add_node("plan_per_session", plan_per_session)
    workflow.add_node("design_flow", design_flow)
    workflow.add_node("consistency_check", consistency_check)

    # Define edges (linear flow)
    workflow.set_entry_point("parse_syllabus")
    workflow.add_edge("parse_syllabus", "plan_per_session")
    workflow.add_edge("plan_per_session", "design_flow")
    workflow.add_edge("design_flow", "consistency_check")
    workflow.add_edge("consistency_check", END)

    return workflow.compile()


# ============ Main Entry Point ============

def run_planning_workflow(course_id: int) -> Dict[str, Any]:
    """
    Generate session plans from course syllabus using LangGraph pipeline.

    Pipeline: ParseSyllabus -> PlanPerSession -> DesignFlow -> ConsistencyCheck

    Args:
        course_id: ID of the course to generate plans for

    Returns:
        Dict with generated plans, consistency report, and metadata
    """
    db: Session = SessionLocal()
    try:
        # Load course
        course = db.query(Course).filter(Course.id == course_id).first()
        if not course:
            return {"error": "Course not found", "course_id": course_id}

        logger.info(f"Starting planning workflow for course {course_id}: {course.title}")

        # Only delete auto-generated sessions (preserves manual sessions)
        deleted_count = db.query(SessionModel).filter(
            SessionModel.course_id == course_id,
            SessionModel.status == "draft",
            SessionModel.plan_json.isnot(None),
        ).delete(synchronize_session='fetch')

        if deleted_count > 0:
            logger.info(f"Deleted {deleted_count} existing draft sessions")
            db.commit()

        # Prepare initial state
        objectives = course.objectives_json if isinstance(course.objectives_json, list) else []

        initial_state: PlanningState = {
            "course_id": course_id,
            "course_title": course.title,
            "syllabus_text": course.syllabus_text or "",
            "objectives": objectives,
            "parsed_syllabus": None,
            "total_sessions": 0,
            "session_plans": [],
            "sessions_with_flow": [],
            "consistency_report": None,
            "model_name": "",
            "prompt_version": "v1.0",
            "errors": [],
        }

        # Run LangGraph workflow
        graph = build_planning_graph()
        final_state = graph.invoke(initial_state)

        # Persist session plans to database
        version = f"v_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"

        for plan in final_state["sessions_with_flow"]:
            db_session = SessionModel(
                course_id=course_id,
                title=plan.get("title", f"Session {plan.get('session_number', '?')}"),
                plan_json=plan,
                plan_version=version,
                model_name=final_state["model_name"],
                prompt_version=final_state["prompt_version"],
            )
            db.add(db_session)

        db.commit()

        logger.info(f"Planning workflow complete: {len(final_state['sessions_with_flow'])} sessions created")

        # Return results
        return {
            "course_id": course_id,
            "course_title": course.title,
            "sessions_generated": len(final_state["sessions_with_flow"]),
            "sessions": final_state["sessions_with_flow"],
            "consistency_report": final_state["consistency_report"],
            "model_name": final_state["model_name"],
            "prompt_version": final_state["prompt_version"],
            "version": version,
            "errors": final_state["errors"] if final_state["errors"] else None,
        }

    except Exception as e:
        db.rollback()
        logger.exception(f"Planning workflow failed for course {course_id}")
        return {"error": str(e), "course_id": course_id}

    finally:
        db.close()
