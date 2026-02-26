"""
Syllabus Formatter - Convert between structured JSON and readable text formats.

This module provides utilities to convert syllabus data between the structured
JSON schema (matching the Syllabus Tool format) and human-readable text.
"""

from typing import Dict, Any, Optional
import json
import logging

logger = logging.getLogger(__name__)


def syllabus_json_to_text(syllabus: Dict[str, Any], language: str = "en") -> str:
    """
    Convert structured syllabus JSON to readable text format.

    Args:
        syllabus: Dictionary containing syllabus data matching SyllabusSchema
        language: Output language ('en' for English, 'es' for Spanish)

    Returns:
        Formatted text string suitable for display in UI
    """
    sections = []

    # Labels based on language
    labels = {
        "en": {
            "code": "Course Code",
            "semester": "Semester",
            "instructor": "Instructor",
            "description": "Description",
            "prerequisites": "Prerequisites",
            "learning_goals": "Learning Goals",
            "learning_resources": "Learning Resources",
            "schedule": "Course Schedule",
            "policies": "Course Policies",
            "grading": "Grading",
            "attendance": "Attendance",
            "academic_integrity": "Academic Integrity",
            "accessibility": "Accessibility",
            "office_hours": "Office Hours",
            "week": "Week",
        },
        "es": {
            "code": "Código del Curso",
            "semester": "Semestre",
            "instructor": "Instructor",
            "description": "Descripción",
            "prerequisites": "Prerrequisitos",
            "learning_goals": "Objetivos de Aprendizaje",
            "learning_resources": "Recursos de Aprendizaje",
            "schedule": "Calendario del Curso",
            "policies": "Políticas del Curso",
            "grading": "Calificación",
            "attendance": "Asistencia",
            "academic_integrity": "Integridad Académica",
            "accessibility": "Accesibilidad",
            "office_hours": "Horas de Oficina",
            "week": "Semana",
        }
    }
    l = labels.get(language, labels["en"])

    # Course Info Section
    info = syllabus.get("course_info", {})
    title = info.get("title", "Course Title")
    sections.append(f"# {title}")

    if info.get("code"):
        sections.append(f"**{l['code']}:** {info['code']}")
    if info.get("semester"):
        sections.append(f"**{l['semester']}:** {info['semester']}")
    if info.get("instructor"):
        sections.append(f"**{l['instructor']}:** {info['instructor']}")

    if info.get("description"):
        sections.append(f"\n## {l['description']}\n{info['description']}")

    if info.get("prerequisites"):
        sections.append(f"\n**{l['prerequisites']}:** {info['prerequisites']}")

    # Learning Goals Section
    goals = syllabus.get("learning_goals", [])
    if goals:
        sections.append(f"\n## {l['learning_goals']}")
        for i, goal in enumerate(goals, 1):
            sections.append(f"{i}. {goal}")

    # Learning Resources Section
    resources = syllabus.get("learning_resources", [])
    if resources:
        sections.append(f"\n## {l['learning_resources']}")
        for resource in resources:
            sections.append(f"- {resource}")

    # Course Schedule Section
    schedule = syllabus.get("schedule", [])
    if schedule:
        sections.append(f"\n## {l['schedule']}")
        for item in schedule:
            week = item.get("week", "?")
            module = item.get("module", "")
            topic = item.get("topic", "")
            sections.append(f"**{l['week']} {week}:** {module} - {topic}")

    # Policies Section
    policies = syllabus.get("policies", {})
    if policies:
        sections.append(f"\n## {l['policies']}")
        if policies.get("grading"):
            sections.append(f"**{l['grading']}:** {policies['grading']}")
        if policies.get("attendance"):
            sections.append(f"**{l['attendance']}:** {policies['attendance']}")
        if policies.get("academic_integrity"):
            sections.append(f"**{l['academic_integrity']}:** {policies['academic_integrity']}")
        if policies.get("accessibility"):
            sections.append(f"**{l['accessibility']}:** {policies['accessibility']}")
        if policies.get("office_hours"):
            sections.append(f"**{l['office_hours']}:** {policies['office_hours']}")

    return "\n".join(sections)


def text_to_syllabus_json(text: str) -> Optional[Dict[str, Any]]:
    """
    Attempt to parse syllabus text back into structured JSON.

    This is a best-effort parser for syllabi that may have been manually edited.
    For reliable structured data, use AI-generated JSON output.

    Args:
        text: Syllabus text (potentially in markdown format)

    Returns:
        Dictionary matching SyllabusSchema, or None if parsing fails
    """
    # This is a simple implementation - in practice, you'd use LLM to parse
    logger.warning("text_to_syllabus_json is a basic parser - consider using LLM for better results")

    try:
        # If the text is already JSON, parse it directly
        if text.strip().startswith("{"):
            return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Return None for manual text - would need LLM parsing
    return None


def validate_syllabus_json(syllabus: Dict[str, Any]) -> tuple[bool, Optional[str]]:
    """
    Validate syllabus JSON against the expected schema.

    Args:
        syllabus: Dictionary to validate

    Returns:
        Tuple of (is_valid, error_message)
    """
    from api.schemas.syllabus import SyllabusSchema
    from pydantic import ValidationError

    try:
        SyllabusSchema(**syllabus)
        return True, None
    except ValidationError as e:
        return False, str(e)


def extract_learning_goals_from_syllabus(syllabus: Dict[str, Any]) -> list[str]:
    """
    Extract learning goals/objectives from a structured syllabus.

    Args:
        syllabus: Syllabus dictionary

    Returns:
        List of learning goal strings
    """
    return syllabus.get("learning_goals", [])
