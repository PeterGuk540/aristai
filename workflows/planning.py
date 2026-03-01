"""
Planning Workflow: Syllabus -> Session Plans

This workflow generates structured session plans from a course syllabus.
Uses LangGraph for orchestration with the following pipeline:
    ParseSyllabus -> PlanPerSession -> DesignFlow -> ConsistencyCheck

Supports both OpenAI and Anthropic LLMs.
Includes observability tracking (Milestone 6).
"""
import json
import logging
import os
import time
from datetime import datetime
from typing import Any, Dict, List, TypedDict, Optional

import httpx
from langgraph.graph import StateGraph, END
from sqlalchemy.orm import Session

from api.core.config import get_settings
from api.core.database import SessionLocal
from api.models.course import Course
from api.models.session import Session as SessionModel
from workflows.llm_utils import (
    get_llm_with_tracking,
    invoke_llm_with_metrics,
    parse_json_response,
    LLMMetrics,
    aggregate_metrics,
)
from workflows.prompts.planning_prompts import (
    PARSE_SYLLABUS_PROMPT,
    PLAN_SESSION_PROMPT,
    DESIGN_FLOW_PROMPT,
    CONSISTENCY_CHECK_PROMPT,
)

logger = logging.getLogger(__name__)

SYLLABUS_TOOL_URL = os.getenv("SYLLABUS_TOOL_URL", "http://syllabus-tool:8002")


def generate_syllabus_via_tool(
    course_title: str,
    target_audience: str = "University students",
    duration: str = "16 weeks",
) -> Dict[str, Any] | None:
    """Delegate syllabus generation to the syllabus-tool service.

    Returns the structured syllabus data (course_info, learning_goals,
    schedule, policies) or None if the call fails.
    """
    payload = {
        "course_title": course_title,
        "target_audience": target_audience,
        "duration": duration,
    }
    try:
        resp = httpx.post(
            f"{SYLLABUS_TOOL_URL}/api/v1/generate/draft",
            json=payload,
            timeout=120,
        )
        resp.raise_for_status()
        return resp.json()
    except Exception as exc:
        logger.warning("Syllabus-tool call failed: %s", exc)
        return None


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

    # Observability (Milestone 6)
    llm_metrics: List[LLMMetrics]
    start_time: float
    used_fallback: bool


# ============ Workflow Nodes ============

def parse_syllabus(state: PlanningState) -> PlanningState:
    """Node 1: Parse syllabus and extract structure."""
    logger.info(f"ParseSyllabus: Processing course {state['course_id']}")

    # Check if total_sessions was pre-set (e.g., from imported sessions)
    preset_sessions = state.get("total_sessions", 0)
    if preset_sessions > 0:
        logger.info(f"ParseSyllabus: Using pre-set session count of {preset_sessions} (from imported sessions)")

    llm, model_name = get_llm_with_tracking()
    if not llm:
        state["errors"].append("No LLM API key configured")
        state["used_fallback"] = True
        # Fallback to reasonable defaults
        fallback_sessions = preset_sessions if preset_sessions > 0 else 8
        state["parsed_syllabus"] = {
            "course_summary": f"Course: {state['course_title']}",
            "total_sessions": fallback_sessions,
            "main_topics": state["objectives"][:5] if state["objectives"] else ["Introduction"],
            "key_concepts": [],
            "objectives_breakdown": [{"objective": obj, "related_topics": []} for obj in state["objectives"]],
        }
        state["total_sessions"] = fallback_sessions
        state["model_name"] = "fallback"
        return state

    state["model_name"] = model_name

    prompt = PARSE_SYLLABUS_PROMPT.format(
        course_title=state["course_title"],
        syllabus_text=state["syllabus_text"] or "No syllabus provided.",
        objectives="\n".join(f"- {obj}" for obj in state["objectives"]) or "No objectives provided.",
    )

    response = invoke_llm_with_metrics(llm, prompt, model_name)
    state["llm_metrics"].append(response.metrics)

    if response.success:
        parsed = parse_json_response(response.content)
        if parsed:
            state["parsed_syllabus"] = parsed
            # If we have pre-set sessions (from imports), use that count; otherwise use LLM suggestion
            if preset_sessions > 0:
                state["total_sessions"] = preset_sessions
                logger.info(f"ParseSyllabus: Using {preset_sessions} sessions (from imported sessions)")
            else:
                # Guard against zero/None: ensure at least 1 session
                state["total_sessions"] = max(parsed.get("total_sessions", 8) or 1, 1)
                logger.info(f"ParseSyllabus: Determined {state['total_sessions']} sessions from LLM")
            return state

    # Fallback if LLM failed
    state["errors"].append("Failed to parse syllabus response")
    fallback_sessions = preset_sessions if preset_sessions > 0 else 8
    state["parsed_syllabus"] = {
        "course_summary": state["course_title"],
        "total_sessions": fallback_sessions,
        "main_topics": state["objectives"][:5] if state["objectives"] else [],
        "key_concepts": [],
        "objectives_breakdown": [],
    }
    state["total_sessions"] = fallback_sessions

    logger.info(f"ParseSyllabus: Determined {state['total_sessions']} sessions")
    return state


def plan_per_session(state: PlanningState) -> PlanningState:
    """Node 2: Generate plan for each session."""
    logger.info(f"PlanPerSession: Generating {state['total_sessions']} session plans")

    llm, model_name = get_llm_with_tracking()
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

            response = invoke_llm_with_metrics(llm, prompt, model_name)
            state["llm_metrics"].append(response.metrics)

            if response.success:
                plan = parse_json_response(response.content)
                if plan:
                    plan["session_number"] = session_num  # Ensure correct number
                    session_plans.append(plan)
                    continue

        # Fallback plan if LLM fails or not available
        state["used_fallback"] = True
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

    llm, model_name = get_llm_with_tracking()
    sessions_with_flow = []

    for plan in state["session_plans"]:
        if llm:
            prompt = DESIGN_FLOW_PROMPT.format(
                session_plan=json.dumps(plan, indent=2)
            )

            response = invoke_llm_with_metrics(llm, prompt, model_name)
            state["llm_metrics"].append(response.metrics)

            if response.success:
                flow_data = parse_json_response(response.content)
                if flow_data:
                    plan["flow"] = flow_data.get("flow", [])
                    plan["checkpoints"] = flow_data.get("checkpoints", [])
                    plan["total_duration_minutes"] = flow_data.get("total_duration_minutes", 55)
                    sessions_with_flow.append(plan)
                    continue

        # Fallback flow
        state["used_fallback"] = True
        topics = plan.get('topics', [])
        first_topic = topics[0] if topics else plan.get('title', 'the topic')
        plan["flow"] = [
            {"phase": "intro", "duration_minutes": 5, "activity": "Welcome and overview"},
            {"phase": "theory", "duration_minutes": 15, "activity": f"Present: {first_topic}"},
            {"phase": "case", "duration_minutes": 10, "activity": "Case study introduction"},
            {"phase": "discussion", "duration_minutes": 20, "activity": "Facilitated discussion"},
            {"phase": "wrap-up", "duration_minutes": 5, "activity": "Summary and next steps"},
        ]
        plan["checkpoints"] = [
            {
                "type": "poll",
                "timing": "after_theory",
                "question": f"How confident are you with {first_topic}?",
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

    llm, model_name = get_llm_with_tracking()

    if llm:
        prompt = CONSISTENCY_CHECK_PROMPT.format(
            course_title=state["course_title"],
            objectives="\n".join(f"- {obj}" for obj in state["objectives"]) or "No objectives provided.",
            session_plans=json.dumps(state["sessions_with_flow"], indent=2),
        )

        response = invoke_llm_with_metrics(llm, prompt, model_name)
        state["llm_metrics"].append(response.metrics)

        if response.success:
            report = parse_json_response(response.content)
            if report:
                state["consistency_report"] = report
                logger.info(f"ConsistencyCheck: Quality score {report.get('overall_quality_score', 'N/A')}/10")
                return state

    # Fallback report
    state["used_fallback"] = True
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

    If sessions already exist (e.g., imported from UPP), the workflow will UPDATE
    those sessions with generated plan content rather than creating new ones.

    Args:
        course_id: ID of the course to generate plans for

    Returns:
        Dict with generated plans, consistency report, metadata, and observability
    """
    db: Session = SessionLocal()
    start_time = time.time()

    try:
        # Load course
        course = db.query(Course).filter(Course.id == course_id).first()
        if not course:
            return {"error": "Course not found", "course_id": course_id}

        logger.info(f"Starting planning workflow for course {course_id}: {course.title}")

        # Check for existing sessions (e.g., imported from UPP/Canvas)
        existing_sessions = db.query(SessionModel).filter(
            SessionModel.course_id == course_id
        ).order_by(SessionModel.id).all()

        # Separate imported sessions (no plan_json or no model_name) from auto-generated ones
        imported_sessions = [s for s in existing_sessions if s.model_name is None]
        auto_generated_sessions = [s for s in existing_sessions if s.model_name is not None]

        # Delete only previously auto-generated sessions (keeps imported sessions)
        if auto_generated_sessions:
            for session in auto_generated_sessions:
                db.delete(session)
            logger.info(f"Deleted {len(auto_generated_sessions)} existing auto-generated sessions")
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
            # Observability (Milestone 6)
            "llm_metrics": [],
            "start_time": start_time,
            "used_fallback": False,
        }

        # If we have imported sessions, use their count as the target
        if imported_sessions:
            logger.info(f"Found {len(imported_sessions)} imported sessions - will update them with plans")
            # Override total_sessions in parsed_syllabus to match imported count
            initial_state["total_sessions"] = len(imported_sessions)

        # Run LangGraph workflow
        graph = build_planning_graph()
        final_state = graph.invoke(initial_state)

        # Calculate aggregated observability metrics
        execution_time = round(time.time() - start_time, 3)
        aggregated = aggregate_metrics(final_state["llm_metrics"])

        # Persist session plans to database with observability fields
        version = f"v_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"

        sessions_updated = 0
        sessions_created = 0

        for plan in final_state["sessions_with_flow"]:
            session_num = plan.get("session_number", 0)

            # Try to find a matching imported session to update
            matching_session = None
            if imported_sessions and session_num > 0 and session_num <= len(imported_sessions):
                matching_session = imported_sessions[session_num - 1]

            if matching_session:
                # UPDATE existing imported session with the generated plan
                matching_session.plan_json = plan
                matching_session.plan_version = version
                matching_session.model_name = final_state["model_name"]
                matching_session.prompt_version = final_state["prompt_version"]
                matching_session.planning_execution_time_seconds = execution_time
                matching_session.planning_total_tokens = aggregated.total_tokens if aggregated.total_tokens > 0 else None
                matching_session.planning_estimated_cost_usd = aggregated.estimated_cost_usd if aggregated.estimated_cost_usd > 0 else None
                matching_session.planning_used_fallback = 1 if final_state["used_fallback"] else 0
                # Optionally update title if it's generic (like "Semana 1")
                if matching_session.title and matching_session.title.lower().startswith("semana"):
                    # Keep original title but could enhance it
                    pass
                sessions_updated += 1
                logger.info(f"Updated existing session {matching_session.id} ({matching_session.title}) with plan")
            else:
                # CREATE new session (no matching imported session)
                db_session = SessionModel(
                    course_id=course_id,
                    title=plan.get("title", f"Session {plan.get('session_number', '?')}"),
                    plan_json=plan,
                    plan_version=version,
                    model_name=final_state["model_name"],
                    prompt_version=final_state["prompt_version"],
                    # Observability fields (Milestone 6)
                    planning_execution_time_seconds=execution_time,
                    planning_total_tokens=aggregated.total_tokens if aggregated.total_tokens > 0 else None,
                    planning_estimated_cost_usd=aggregated.estimated_cost_usd if aggregated.estimated_cost_usd > 0 else None,
                    planning_used_fallback=1 if final_state["used_fallback"] else 0,
                )
                db.add(db_session)
                sessions_created += 1

        db.commit()

        logger.info(
            f"Planning workflow complete: {sessions_updated} updated, {sessions_created} created, "
            f"tokens={aggregated.total_tokens}, cost=${aggregated.estimated_cost_usd:.4f}"
        )

        # Return results with observability
        return {
            "course_id": course_id,
            "course_title": course.title,
            "sessions_generated": len(final_state["sessions_with_flow"]),
            "sessions_updated": sessions_updated,
            "sessions_created": sessions_created,
            "sessions": final_state["sessions_with_flow"],
            "consistency_report": final_state["consistency_report"],
            "model_name": final_state["model_name"],
            "prompt_version": final_state["prompt_version"],
            "version": version,
            "errors": final_state["errors"] if final_state["errors"] else None,
            # Observability (Milestone 6)
            "observability": {
                "execution_time_seconds": execution_time,
                "total_tokens": aggregated.total_tokens,
                "prompt_tokens": aggregated.prompt_tokens,
                "completion_tokens": aggregated.completion_tokens,
                "estimated_cost_usd": aggregated.estimated_cost_usd,
                "used_fallback": final_state["used_fallback"],
            },
        }

    except Exception as e:
        db.rollback()
        logger.exception(f"Planning workflow failed for course {course_id}")
        return {"error": str(e), "course_id": course_id}

    finally:
        db.close()
