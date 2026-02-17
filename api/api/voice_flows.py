"""Voice Conversation Flow Definitions.

This module provides declarative flow definitions for voice-driven workflows.
Each flow defines:
1. Required fields to collect
2. Field prompts and validation
3. State transitions
4. AI generation options
5. Final action to execute

This replaces scattered if-else logic with clean, declarative configurations.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Union


class FieldType(str, Enum):
    """Types of form fields that can be collected via voice."""
    TEXT = "text"  # Simple text input
    TEXTAREA = "textarea"  # Multi-line text (syllabus, description)
    SELECT = "select"  # Dropdown selection
    BOOLEAN = "boolean"  # Yes/no confirmation
    NUMBER = "number"  # Numeric value


class AIGenerationOption(str, Enum):
    """AI content generation options for a field."""
    NONE = "none"  # No AI generation
    OPTIONAL = "optional"  # User can choose to generate
    REQUIRED = "required"  # Always generate with AI


@dataclass
class FlowField:
    """Definition of a field to collect in a conversation flow."""
    name: str  # Field identifier (e.g., "title", "syllabus")
    voice_id: str  # DOM element data-voice-id
    field_type: FieldType = FieldType.TEXT
    required: bool = True

    # Prompts - dict with 'en' and 'es' keys
    prompt: Dict[str, str] = field(default_factory=dict)
    skip_prompt: Optional[Dict[str, str]] = None  # Prompt shown after skip

    # AI generation
    ai_generation: AIGenerationOption = AIGenerationOption.NONE
    ai_prompt_template: Optional[str] = None  # Template for AI generation

    # Validation
    min_length: int = 1
    max_length: int = 5000
    validation_hint: Optional[Dict[str, str]] = None


@dataclass
class ConversationFlow:
    """Definition of a complete conversation flow."""
    name: str  # Flow identifier (e.g., "create_course", "create_poll")
    description: str  # Human-readable description

    # Fields to collect (in order)
    fields: List[FlowField] = field(default_factory=list)

    # Page requirements
    required_page: Optional[str] = None  # Page must match this pattern
    target_page: Optional[str] = None  # Navigate here before starting

    # Actions
    submit_button_voice_id: Optional[str] = None  # Button to click after form completion
    final_action: Optional[str] = None  # MCP tool to call

    # Confirmation
    requires_confirmation: bool = True
    confirmation_prompt: Dict[str, str] = field(default_factory=dict)

    # Post-completion
    success_message: Dict[str, str] = field(default_factory=dict)
    next_suggestions: List[str] = field(default_factory=list)


# =============================================================================
# FLOW DEFINITIONS
# =============================================================================

CREATE_COURSE_FLOW = ConversationFlow(
    name="create_course",
    description="Guide user through creating a new course",
    required_page="/courses",
    fields=[
        FlowField(
            name="title",
            voice_id="input-course-title",
            field_type=FieldType.TEXT,
            required=True,
            prompt={
                "en": "What would you like to name your course?",
                "es": "Como te gustaria llamar tu curso?",
            },
            min_length=3,
            max_length=200,
        ),
        FlowField(
            name="syllabus",
            voice_id="textarea-syllabus",
            field_type=FieldType.TEXTAREA,
            required=False,
            prompt={
                "en": "Now for the syllabus. Would you like me to generate one, or would you prefer to dictate it? You can also say 'skip'.",
                "es": "Ahora el programa de estudios. Te gustaria que genere uno, o prefieres dictarlo? Tambien puedes decir 'saltar'.",
            },
            skip_prompt={
                "en": "Skipped. Moving to learning objectives.",
                "es": "Saltado. Pasando a los objetivos de aprendizaje.",
            },
            ai_generation=AIGenerationOption.OPTIONAL,
            ai_prompt_template="Generate a comprehensive syllabus for a course titled '{title}'.",
        ),
        FlowField(
            name="learning_objectives",
            voice_id="textarea-learning-objectives",
            field_type=FieldType.TEXTAREA,
            required=False,
            prompt={
                "en": "Now for learning objectives. Would you like me to generate them, or would you prefer to dictate? You can also say 'skip'.",
                "es": "Ahora los objetivos de aprendizaje. Te gustaria que los genere, o prefieres dictarlos? Tambien puedes decir 'saltar'.",
            },
            skip_prompt={
                "en": "Skipped. The course is ready to create.",
                "es": "Saltado. El curso esta listo para crear.",
            },
            ai_generation=AIGenerationOption.OPTIONAL,
            ai_prompt_template="Generate 5-7 learning objectives for a course titled '{title}' with syllabus: {syllabus}",
        ),
    ],
    submit_button_voice_id="create-course-with-plans",
    requires_confirmation=True,
    confirmation_prompt={
        "en": "I have all the details. Would you like me to create the course now?",
        "es": "Tengo todos los detalles. Te gustaria que cree el curso ahora?",
    },
    success_message={
        "en": "Course created successfully! Would you like to add sessions?",
        "es": "Curso creado exitosamente! Te gustaria agregar sesiones?",
    },
    next_suggestions=["Create session", "View sessions", "Add students"],
)


CREATE_SESSION_FLOW = ConversationFlow(
    name="create_session",
    description="Guide user through creating a new session",
    required_page="/courses/",  # Must be on a course page
    fields=[
        FlowField(
            name="title",
            voice_id="input-session-title",
            field_type=FieldType.TEXT,
            required=True,
            prompt={
                "en": "What topic will this session cover?",
                "es": "Que tema cubrira esta sesion?",
            },
            min_length=3,
            max_length=200,
        ),
        FlowField(
            name="description",
            voice_id="textarea-session-description",
            field_type=FieldType.TEXTAREA,
            required=False,
            prompt={
                "en": "Would you like to add a description? You can dictate it, say 'generate' for AI, or 'skip' to continue.",
                "es": "Te gustaria agregar una descripcion? Puedes dictarla, decir 'generar' para IA, o 'saltar' para continuar.",
            },
            ai_generation=AIGenerationOption.OPTIONAL,
            ai_prompt_template="Generate a brief session description for a session titled '{title}'.",
        ),
    ],
    submit_button_voice_id="create-session",
    requires_confirmation=True,
    confirmation_prompt={
        "en": "Ready to create the session. Shall I proceed?",
        "es": "Listo para crear la sesion. Procedo?",
    },
    success_message={
        "en": "Session created! Would you like to go live now?",
        "es": "Sesion creada! Te gustaria ponerla en vivo ahora?",
    },
    next_suggestions=["Go live", "Edit session", "Create another session"],
)


CREATE_POLL_FLOW = ConversationFlow(
    name="create_poll",
    description="Guide user through creating a poll",
    required_page="/sessions/",  # Must be on a session page
    fields=[
        FlowField(
            name="question",
            voice_id="input-poll-question",
            field_type=FieldType.TEXT,
            required=True,
            prompt={
                "en": "What question would you like to ask in the poll?",
                "es": "Que pregunta te gustaria hacer en la encuesta?",
            },
            min_length=5,
            max_length=500,
        ),
        FlowField(
            name="option_1",
            voice_id="input-poll-option-1",
            field_type=FieldType.TEXT,
            required=True,
            prompt={
                "en": "What's the first option?",
                "es": "Cual es la primera opcion?",
            },
        ),
        FlowField(
            name="option_2",
            voice_id="input-poll-option-2",
            field_type=FieldType.TEXT,
            required=True,
            prompt={
                "en": "What's the second option?",
                "es": "Cual es la segunda opcion?",
            },
        ),
        FlowField(
            name="option_3",
            voice_id="input-poll-option-3",
            field_type=FieldType.TEXT,
            required=False,
            prompt={
                "en": "Would you like to add a third option? Say 'skip' if not.",
                "es": "Te gustaria agregar una tercera opcion? Di 'saltar' si no.",
            },
        ),
        FlowField(
            name="option_4",
            voice_id="input-poll-option-4",
            field_type=FieldType.TEXT,
            required=False,
            prompt={
                "en": "Would you like to add a fourth option? Say 'skip' if not.",
                "es": "Te gustaria agregar una cuarta opcion? Di 'saltar' si no.",
            },
        ),
    ],
    submit_button_voice_id="create-poll",
    requires_confirmation=True,
    confirmation_prompt={
        "en": "Ready to create the poll. Shall I launch it now?",
        "es": "Listo para crear la encuesta. La lanzo ahora?",
    },
    success_message={
        "en": "Poll launched! Students can now respond.",
        "es": "Encuesta lanzada! Los estudiantes ya pueden responder.",
    },
    next_suggestions=["View responses", "Create another poll", "Post case"],
)


POST_CASE_FLOW = ConversationFlow(
    name="post_case",
    description="Guide user through posting a case study",
    required_page="/sessions/",
    fields=[
        FlowField(
            name="prompt",
            voice_id="textarea-case-prompt",
            field_type=FieldType.TEXTAREA,
            required=True,
            prompt={
                "en": "What case scenario would you like to post? You can dictate the prompt.",
                "es": "Que escenario de caso te gustaria publicar? Puedes dictar el prompt.",
            },
            min_length=10,
            max_length=5000,
        ),
    ],
    submit_button_voice_id="post-case",
    requires_confirmation=True,
    confirmation_prompt={
        "en": "Ready to post the case. Shall I publish it?",
        "es": "Listo para publicar el caso. Lo publico?",
    },
    success_message={
        "en": "Case posted! Students can now respond.",
        "es": "Caso publicado! Los estudiantes ya pueden responder.",
    },
    next_suggestions=["View responses", "Create poll", "View forum"],
)


# =============================================================================
# FLOW REGISTRY
# =============================================================================

FLOW_REGISTRY: Dict[str, ConversationFlow] = {
    "create_course": CREATE_COURSE_FLOW,
    "create_course_flow": CREATE_COURSE_FLOW,
    "create_session": CREATE_SESSION_FLOW,
    "create_poll": CREATE_POLL_FLOW,
    "post_case": POST_CASE_FLOW,
}


def get_flow(action: str) -> Optional[ConversationFlow]:
    """Get the conversation flow for an action."""
    return FLOW_REGISTRY.get(action)


def get_flow_prompt(flow: ConversationFlow, field_index: int, language: str = 'en') -> str:
    """Get the prompt for a specific field in a flow."""
    if field_index >= len(flow.fields):
        return flow.confirmation_prompt.get(language, flow.confirmation_prompt.get('en', ''))

    field = flow.fields[field_index]
    return field.prompt.get(language, field.prompt.get('en', f"Please provide {field.name}"))


def get_field_by_name(flow: ConversationFlow, field_name: str) -> Optional[FlowField]:
    """Get a field definition by name."""
    for f in flow.fields:
        if f.name == field_name:
            return f
    return None


def is_page_valid_for_flow(flow: ConversationFlow, current_page: Optional[str]) -> bool:
    """Check if the current page is valid for starting this flow."""
    if not flow.required_page:
        return True
    if not current_page:
        return False

    # Support both exact match and prefix match (for required_page ending with /)
    if flow.required_page.endswith('/'):
        return current_page.startswith(flow.required_page) or current_page == flow.required_page.rstrip('/')
    return current_page == flow.required_page or current_page.startswith(flow.required_page + '/')
