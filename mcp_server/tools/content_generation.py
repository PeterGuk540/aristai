"""
Content Generation MCP tools.

AI-powered tools for generating course content:
- Syllabus generation from course name
- Learning objectives generation
- Session plan generation (discussion prompts, case studies)

Uses the same LLM infrastructure as copilot.
"""

import logging
from typing import Any, Dict, List, Optional

from workflows.llm_utils import (
    get_llm_with_tracking,
    invoke_llm_with_metrics,
    parse_json_response,
)

logger = logging.getLogger(__name__)


# ============ Prompts ============

SYLLABUS_GENERATION_PROMPT = """You are an expert curriculum designer. Generate a comprehensive syllabus for the following course.

Course Name: {course_name}
{description_section}

Create a well-structured syllabus that includes:
1. Course Overview (2-3 sentences)
2. Weekly Topics (8-12 weeks, with brief descriptions)
3. Key Concepts covered
4. Assessment methods (exams, projects, participation)

Format the syllabus in a clear, readable format with proper headings and bullet points.
Keep it professional and suitable for a university or professional training course.

Output ONLY the syllabus text, no additional commentary."""

OBJECTIVES_GENERATION_PROMPT = """You are an expert instructional designer. Generate learning objectives for the following course.

Course Name: {course_name}
{syllabus_section}

Create 5-7 specific, measurable learning objectives following Bloom's taxonomy.
Each objective should:
- Start with an action verb (e.g., Analyze, Apply, Evaluate, Create)
- Be specific and measurable
- Align with the course content

Return a JSON array of objectives:
{{"objectives": ["objective 1", "objective 2", ...]}}

Output ONLY valid JSON, no additional text."""

SESSION_PLAN_GENERATION_PROMPT = """You are an expert instructional designer. Generate a session plan for the following class session.

Course Name: {course_name}
Session Topic: {session_topic}
{context_section}

Create a comprehensive session plan that includes:

1. Session Title: A clear, descriptive title
2. Learning Goals: 2-3 specific goals for this session
3. Key Concepts: Main concepts to cover
4. Discussion Prompts: 2-3 thought-provoking questions to spark discussion
5. Case Study: A relevant, engaging scenario for students to analyze

Return a JSON object with this structure:
{{
    "title": "Session Title",
    "goals": ["goal 1", "goal 2"],
    "key_concepts": ["concept 1", "concept 2", "concept 3"],
    "discussion_prompts": ["prompt 1", "prompt 2"],
    "case_prompt": "A detailed case study scenario (2-3 paragraphs) that students can discuss and analyze..."
}}

Make the case study realistic, relevant, and thought-provoking.
Output ONLY valid JSON, no additional text."""


# ============ Generation Functions ============

def generate_syllabus(
    course_name: str,
    description: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Generate a syllabus for a course using AI.

    Args:
        course_name: The name of the course
        description: Optional additional description or context

    Returns:
        Dict with generated syllabus and metadata
    """
    if not course_name or not course_name.strip():
        return {"error": "Course name is required"}

    llm, model_name = get_llm_with_tracking()
    if llm is None:
        return {
            "error": "No LLM API key configured. Please add an OpenAI or Anthropic API key.",
            "fallback": True,
        }

    # Build prompt
    description_section = f"Description: {description}" if description else ""
    prompt = SYLLABUS_GENERATION_PROMPT.format(
        course_name=course_name,
        description_section=description_section,
    )

    # Invoke LLM
    logger.info(f"Generating syllabus for course: {course_name}")
    response = invoke_llm_with_metrics(llm, prompt, model_name)

    if not response.success or not response.content:
        logger.error(f"Syllabus generation failed: {response.metrics.error_message}")
        return {
            "error": "Failed to generate syllabus. Please try again.",
            "details": response.metrics.error_message,
        }

    syllabus = response.content.strip()

    # Extract key info for voice summary
    lines = syllabus.split('\n')
    week_count = sum(1 for line in lines if 'week' in line.lower() and any(c.isdigit() for c in line))

    message = f"Generated a syllabus for '{course_name}' "
    if week_count > 0:
        message += f"covering {week_count} weeks. "
    message += "Review and edit as needed."

    return {
        "message": message,
        "syllabus": syllabus,
        "course_name": course_name,
        "model_name": model_name,
        "tokens_used": response.metrics.total_tokens,
        "success": True,
    }


def generate_objectives(
    course_name: str,
    syllabus: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Generate learning objectives for a course using AI.

    Args:
        course_name: The name of the course
        syllabus: Optional syllabus text for context

    Returns:
        Dict with generated objectives and metadata
    """
    if not course_name or not course_name.strip():
        return {"error": "Course name is required"}

    llm, model_name = get_llm_with_tracking()
    if llm is None:
        return {
            "error": "No LLM API key configured. Please add an OpenAI or Anthropic API key.",
            "fallback": True,
        }

    # Build prompt
    syllabus_section = ""
    if syllabus:
        # Truncate syllabus if too long
        syllabus_preview = syllabus[:2000] + "..." if len(syllabus) > 2000 else syllabus
        syllabus_section = f"Syllabus:\n{syllabus_preview}"

    prompt = OBJECTIVES_GENERATION_PROMPT.format(
        course_name=course_name,
        syllabus_section=syllabus_section,
    )

    # Invoke LLM
    logger.info(f"Generating objectives for course: {course_name}")
    response = invoke_llm_with_metrics(llm, prompt, model_name)

    if not response.success or not response.content:
        logger.error(f"Objectives generation failed: {response.metrics.error_message}")
        return {
            "error": "Failed to generate objectives. Please try again.",
            "details": response.metrics.error_message,
        }

    # Parse JSON response
    parsed = parse_json_response(response.content)
    if not parsed or 'objectives' not in parsed:
        # Try to extract objectives from plain text
        lines = response.content.strip().split('\n')
        objectives = [
            line.strip().lstrip('0123456789.-) ').strip()
            for line in lines
            if line.strip() and len(line.strip()) > 10
        ][:7]  # Limit to 7 objectives
        if not objectives:
            return {
                "error": "Failed to parse generated objectives.",
                "raw_content": response.content,
            }
    else:
        objectives = parsed['objectives']

    message = f"Generated {len(objectives)} learning objectives for '{course_name}'. "
    if objectives:
        message += f"First objective: {objectives[0][:50]}..."

    return {
        "message": message,
        "objectives": objectives,
        "course_name": course_name,
        "count": len(objectives),
        "model_name": model_name,
        "tokens_used": response.metrics.total_tokens,
        "success": True,
    }


def generate_session_plan(
    course_name: str,
    session_topic: str,
    syllabus: Optional[str] = None,
    objectives: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    Generate a session plan with discussion prompts and case study.

    Args:
        course_name: The name of the course
        session_topic: The topic for this session
        syllabus: Optional syllabus for context
        objectives: Optional learning objectives for alignment

    Returns:
        Dict with generated session plan and metadata
    """
    if not course_name or not course_name.strip():
        return {"error": "Course name is required"}
    if not session_topic or not session_topic.strip():
        return {"error": "Session topic is required"}

    llm, model_name = get_llm_with_tracking()
    if llm is None:
        return {
            "error": "No LLM API key configured. Please add an OpenAI or Anthropic API key.",
            "fallback": True,
        }

    # Build context section
    context_parts = []
    if syllabus:
        syllabus_preview = syllabus[:1000] + "..." if len(syllabus) > 1000 else syllabus
        context_parts.append(f"Course Syllabus (excerpt):\n{syllabus_preview}")
    if objectives:
        context_parts.append(f"Learning Objectives:\n" + "\n".join(f"- {obj}" for obj in objectives[:5]))

    context_section = "\n\n".join(context_parts) if context_parts else "No additional context provided."

    prompt = SESSION_PLAN_GENERATION_PROMPT.format(
        course_name=course_name,
        session_topic=session_topic,
        context_section=context_section,
    )

    # Invoke LLM
    logger.info(f"Generating session plan for: {session_topic}")
    response = invoke_llm_with_metrics(llm, prompt, model_name)

    if not response.success or not response.content:
        logger.error(f"Session plan generation failed: {response.metrics.error_message}")
        return {
            "error": "Failed to generate session plan. Please try again.",
            "details": response.metrics.error_message,
        }

    # Parse JSON response
    parsed = parse_json_response(response.content)
    if not parsed:
        return {
            "error": "Failed to parse generated session plan.",
            "raw_content": response.content,
        }

    # Ensure all expected fields exist
    plan = {
        "title": parsed.get("title", session_topic),
        "goals": parsed.get("goals", []),
        "key_concepts": parsed.get("key_concepts", []),
        "discussion_prompts": parsed.get("discussion_prompts", []),
        "case_prompt": parsed.get("case_prompt", ""),
    }

    message = f"Generated session plan for '{plan['title']}'. "
    if plan["discussion_prompts"]:
        message += f"Includes {len(plan['discussion_prompts'])} discussion prompts. "
    if plan["case_prompt"]:
        message += "Includes a case study for discussion."

    return {
        "message": message,
        "plan": plan,
        "session_topic": session_topic,
        "course_name": course_name,
        "model_name": model_name,
        "tokens_used": response.metrics.total_tokens,
        "success": True,
    }


def generate_case_study(
    course_name: str,
    session_topic: str,
    context: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Generate just a case study for a session.

    Args:
        course_name: The name of the course
        session_topic: The topic for the case study
        context: Optional additional context

    Returns:
        Dict with generated case study
    """
    # Use session plan generation and extract just the case
    result = generate_session_plan(course_name, session_topic, context)
    if result.get("error"):
        return result

    plan = result.get("plan", {})
    case_prompt = plan.get("case_prompt", "")

    if not case_prompt:
        return {"error": "Failed to generate case study."}

    return {
        "message": f"Generated case study for '{session_topic}'.",
        "case_prompt": case_prompt,
        "session_topic": session_topic,
        "success": True,
    }


def generate_discussion_prompts(
    course_name: str,
    session_topic: str,
    count: int = 3,
) -> Dict[str, Any]:
    """
    Generate discussion prompts for a session.

    Args:
        course_name: The name of the course
        session_topic: The topic for discussion
        count: Number of prompts to generate (default: 3)

    Returns:
        Dict with generated discussion prompts
    """
    # Use session plan generation and extract prompts
    result = generate_session_plan(course_name, session_topic)
    if result.get("error"):
        return result

    plan = result.get("plan", {})
    prompts = plan.get("discussion_prompts", [])

    if not prompts:
        return {"error": "Failed to generate discussion prompts."}

    return {
        "message": f"Generated {len(prompts)} discussion prompts for '{session_topic}'.",
        "prompts": prompts[:count],
        "session_topic": session_topic,
        "success": True,
    }
