"""
Conversational Voice Endpoint for AristAI

This module provides a conversational AI interface that:
1. Understands natural language queries
2. Determines intent (navigate, execute action, provide info)
3. Returns conversational responses with context
4. Executes MCP tools when appropriate

Add this router to your main API router.
"""

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from typing import Optional, List, Any, Dict, Tuple
import re

from sqlalchemy.orm import Session

from api.core.database import get_db

# Phase 3: Import from modular components
from api.api.voice_responses import (
    RESPONSE_TEMPLATES,
    PAGE_NAMES,
    STATUS_NAMES,
    get_response,
    get_page_name,
    get_status_name,
    # LLM-based response generation
    generate_voice_response,
    build_navigation_situation,
    build_tab_switch_situation,
    build_confirmation_request_situation,
    build_form_cancelled_situation,
    build_error_situation,
    build_hesitation_situation,
    build_skipped_field_situation,
    build_generate_offer_situation,
    build_content_saved_situation,
    build_poll_situation,
)
from api.api.voice_extraction import (
    normalize_spanish_text,
    extract_dictated_content as _extract_dictated_content,
    extract_universal_dictation as _extract_universal_dictation,
    extract_dropdown_hint as _extract_dropdown_hint,
    extract_button_info as _extract_button_info,
    extract_search_query as _extract_search_query,
    extract_student_name as _extract_student_name,
    extract_tab_info as _extract_tab_info,
    extract_dropdown_selection as _extract_dropdown_selection,
    is_confirmation,
    get_confirmation_type,
    extract_full_context,
)
from api.api.voice_helpers import (
    get_page_suggestions,
    get_action_suggestions,
    generate_fallback_response,
)
from api.models.course import Course
from api.models.user import User
from api.models.integration import IntegrationProviderConnection, IntegrationCourseMapping
from api.models.session import Session as SessionModel, SessionStatus
from api.api.mcp_executor import invoke_tool_handler
from api.services.integrations.registry import list_supported_providers
from api.services.speech_filter import sanitize_speech
from api.services.tool_response import normalize_tool_result
from api.services.context_store import ContextStore
from api.services.voice_conversation_state import (
    VoiceConversationManager,
    ConversationState,
    DropdownOption,
)
from mcp_server.server import TOOL_REGISTRY
from workflows.voice_orchestrator import run_voice_orchestrator, generate_summary
from workflows.llm_utils import get_llm_with_tracking, invoke_llm_with_metrics, parse_json_response

# LLM-based intent classification (natural language understanding)
from api.api.voice_intent_classifier import (
    classify_intent,
    intent_to_legacy_format,
    build_page_context,
    IntentCategory,
    PageContext,
    # Form input classification for distinguishing content vs meta-conversation
    classify_form_input,
    InputType,
    InputTypeResult,
    # Phase 6: LLM-based UI element identification
    classify_tab_switch,
    classify_button_click,
    classify_dropdown_selection,
    UIElementType,
    UIElementResult,
    # Phase 6: LLM-based response generation
    generate_llm_response,
)

# Instructor enhancement features voice handlers
from api.api.voice_instructor_handlers import handle_instructor_feature

# Initialize context store for voice memory
context_store = ContextStore()

# Initialize conversation state manager for conversational flows
conversation_manager = VoiceConversationManager()

# ============================================================================
# CONFIGURATION: LLM-based Intent Detection
# ============================================================================
# LLM-first intent detection is now the ONLY mode (Phase 1 refactor)
# Regex patterns are deprecated and kept only for reference
USE_LLM_INTENT_DETECTION = True  # Always True - regex fallback removed

# Confidence threshold for LLM intent detection
# If confidence is below this, ask for clarification (no regex fallback)
LLM_INTENT_CONFIDENCE_THRESHOLD = 0.5  # Lowered from 0.6 - trust LLM more

# ============================================================================
# Phase 2.5: AUTO-NAVIGATION FOR CROSS-PAGE COMMANDS
# ============================================================================
# Maps actions to the page(s) they can be executed from.
# If user issues a command from a different page, navigate first then execute.

ACTION_REQUIRED_PAGES: Dict[str, List[str]] = {
    # Course actions - require /courses or /courses/* pages
    "create_course": ["/courses"],
    "create_course_flow": ["/courses"],

    # Enrollment actions - REQUIRE /courses page with advanced tab
    "manage_enrollments": ["/courses"],
    "enroll_students": ["/courses"],
    "list_enrollments": ["/courses"],

    # Session actions - require session or course context
    "create_session": ["/courses/", "/sessions"],
    "start_session": ["/sessions/"],
    "end_session": ["/sessions/"],
    "go_live": ["/sessions/"],

    # Forum actions - require /forum page
    "create_forum_post": ["/forum", "/courses/"],
    "post_to_forum": ["/forum", "/courses/"],

    # Poll/Quiz actions - require session context
    "create_poll": ["/sessions/"],
    "launch_poll": ["/sessions/"],
    "create_quiz": ["/sessions/", "/courses/"],

    # AI features - typically require session context
    "generate_summary": ["/sessions/"],
    "start_copilot": ["/sessions/"],
    "stop_copilot": ["/sessions/"],

    # Assignment actions - require course context
    "create_assignment": ["/courses/"],
    "grade_submissions": ["/courses/", "/assignments/"],
}

# Maps actions to their target navigation page when auto-navigation is needed
ACTION_TARGET_PAGES: Dict[str, str] = {
    "create_course": "/courses",
    "create_course_flow": "/courses",
    "create_forum_post": "/forum",
    "post_to_forum": "/forum",
    # Session actions require course context first
    "create_session": "/courses",
    # Other actions that need specific pages
    "create_assignment": "/courses",
    "manage_enrollments": "/courses",
}

# Maps actions to the tab they should switch to after navigation
ACTION_TARGET_TABS: Dict[str, str] = {
    "create_course": "create",
    "create_course_flow": "create",
    "create_session": "create",
    "manage_enrollments": "advanced",
    "list_enrollments": "advanced",
    "enroll_students": "advanced",
    "post_to_forum": "discussion",
    "create_forum_post": "cases",
}


def get_auto_navigation(action: str, current_page: Optional[str]) -> Optional[str]:
    """
    Check if the current action requires navigation to a different page.

    Returns:
        Target path to navigate to, or None if no navigation needed.
    """
    if not action or not current_page:
        return None

    required_pages = ACTION_REQUIRED_PAGES.get(action)
    if not required_pages:
        # Action doesn't have page requirements - can execute anywhere
        return None

    # Check if current page matches any required page pattern
    for required in required_pages:
        if required.endswith("/"):
            # Prefix match (e.g., "/courses/" matches "/courses/123")
            if current_page.startswith(required) or current_page == required.rstrip("/"):
                return None
        else:
            # Exact or prefix match
            if current_page == required or current_page.startswith(required + "/"):
                return None

    # Need to navigate - get target page
    target = ACTION_TARGET_PAGES.get(action)
    if not target:
        # Use first required page as fallback
        target = required_pages[0].rstrip("/")

    return target


# Import your existing dependencies
# from .auth import get_current_user
# from .database import get_db
# from ..mcp_server.server import mcp_server

router = APIRouter(prefix="/voice", tags=["voice"])


class LogoutRequest(BaseModel):
    user_id: Optional[int] = None


@router.post("/logout")
async def voice_logout(request: LogoutRequest):
    """Clear voice context on user logout."""
    if request.user_id:
        conversation_manager.clear_context(request.user_id)
        context_store.clear_context(request.user_id)
    return {"message": "Voice context cleared"}


class PendingActionRequest(BaseModel):
    user_id: Optional[int] = None
    current_page: Optional[str] = None
    language: Optional[str] = "en"


class PendingActionResponse(BaseModel):
    has_pending: bool
    action: Optional[str] = None
    parameters: Optional[Dict[str, Any]] = None
    transcript: Optional[str] = None
    message: Optional[str] = None


@router.post("/pending-action")
async def check_pending_action(request: PendingActionRequest, db: Session = Depends(get_db)):
    """
    Check for and execute any pending action after navigation.

    Phase 2.5: When a user issues a command from a wrong page, we navigate first
    and store the action. After navigation completes, frontend calls this endpoint
    to execute the pending action.
    """
    pending = conversation_manager.get_pending_action(request.user_id)

    if not pending:
        return PendingActionResponse(has_pending=False)

    # Execute the pending action
    action = pending["action"]
    parameters = pending.get("parameters", {})
    transcript = pending.get("transcript", "")
    language = request.language or "en"

    print(f"🔄 Executing pending action: {action} with params: {parameters}")

    # Execute the action
    result = await execute_action(
        action,
        request.user_id,
        request.current_page,
        db,
        transcript,
        parameters,
        language,
    )

    # Generate a message for the action
    message = generate_conversational_response(
        'execute',
        action,
        results=result,
        context=None,
        current_page=request.current_page,
        language=language,
    )

    return PendingActionResponse(
        has_pending=True,
        action=action,
        parameters=parameters,
        transcript=transcript,
        message=sanitize_speech(message),
    )


class ConverseRequest(BaseModel):
    transcript: str
    context: Optional[List[str]] = None
    user_id: Optional[int] = None
    current_page: Optional[str] = None
    language: Optional[str] = "en"  # 'en' or 'es' - determines response language
    # Phase 2: Rich page context for smarter LLM intent detection
    available_tabs: Optional[List[str]] = None  # e.g., ["create", "manage", "sessions", "advanced"]
    available_buttons: Optional[List[str]] = None  # e.g., ["create-course", "go-live", "submit"]
    active_course_name: Optional[str] = None  # e.g., "Statistics 101"
    active_session_name: Optional[str] = None  # e.g., "Week 3 Discussion"
    is_session_live: Optional[bool] = None  # Whether current session is live
    copilot_active: Optional[bool] = None  # Whether AI copilot is running


class ActionResponse(BaseModel):
    type: str  # 'navigate', 'execute', 'info'
    target: Optional[str] = None
    executed: Optional[bool] = None


class ConverseResponse(BaseModel):
    message: str
    action: Optional[ActionResponse] = None
    results: Optional[List[Any]] = None
    suggestions: Optional[List[str]] = None


# =============================================================================
# BILINGUAL RESPONSE TEMPLATES
# =============================================================================
# These templates are used to generate responses in the user's selected language.
# The language is passed from the frontend and determines which template to use.

RESPONSE_TEMPLATES = {
    'en': {
        # Navigation
        'navigate_to': "Taking you to {destination} now.",
        'navigate_open': "Opening {destination} for you.",
        'switch_tab': "Switching to the {tab} tab.",
        'switching_tabs': "Switching tabs.",

        # Courses
        'no_courses': "You don't have any courses yet. Would you like me to help you create one?",
        'one_course': "You have one course: {name}. Would you like me to open it?",
        'few_courses': "You have {count} courses: {names}. Which one would you like to work with?",
        'many_courses': "You have {count} courses, including {names}, and {more} more. Would you like to see them all?",
        'create_course': "Opening course creation. Tell me the course title, or I can help you set it up step by step.",
        'select_course': "Opening {name}. What would you like to do with it?",
        'selecting_course': "Selecting the course for you.",

        # Sessions
        'no_sessions': "No sessions found. Would you like to create a new session?",
        'live_sessions': "There {verb} {count} live session{plural}: {names}. Would you like to join one?",
        'sessions_none_live': "You have {count} sessions. None are live right now. Would you like to start one?",
        'create_session': "Opening session creation. What topic will this session cover?",
        'select_session': "Opening {name}. Status: {status}.",
        'selecting_session': "Selecting the session for you.",
        'session_live': "Session is now live! Students can join and start participating.",
        'session_ended': "Session has ended. Would you like me to generate a report?",
        'session_draft': "Session has been set to draft. You can edit it or go live when ready.",
        'session_completed': "Session has been marked as completed.",
        'session_scheduled': "Session has been scheduled.",

        # Actions
        'click_button': "Clicking {button}.",
        'clicking_button': "Clicking the button.",
        'opening_materials': "Opening the course materials. You can view and download uploaded files here.",

        # Confirmations
        'confirm_proceed': "Would you like me to proceed?",
        'confirm_yes': "Done!",
        'confirm_cancel': "Okay, cancelled.",

        # Errors
        'error_generic': "Sorry, there was an issue: {reason}",
        'error_not_found': "I couldn't find that. Please try again.",

        # Greetings
        'greeting': "Hello! How can I help you?",
        'ready': "I'm ready to help. What would you like to do?",

        # Dropdown
        'dropdown_options': "Your options are: {options}. Which would you like to select?",
        'dropdown_selected': "Selected {name}.",

        # Forum
        'forum_post_offer': "Would you like me to help you post something?",
        'forum_posting': "Posting to the forum.",

        # Polls
        'poll_create_offer': "Would you like to create a poll?",
        'poll_creating': "Creating the poll.",

        # AI Features
        'generating_summary': "Generating a summary of the discussion.",
        'generating_questions': "Generating quiz questions from the discussion.",
        'creating_groups': "Creating AI-powered student groups.",

        # Form filling
        'form_cancelled': "Form cancelled. What would you like to do?",
        'form_complete': "I've filled in all the required fields. Would you like me to submit the form?",
        'confirm_yes_no': "Please say 'yes' to confirm or 'no' to cancel.",
        'got_it_continue': "Got it! {prompt}",
        'skipped_syllabus_offer': "Skipped. Now for the syllabus. Would you like me to generate one, or would you prefer to dictate it? You can also say 'skip'.",
        'skipped_objectives_offer': "Skipped. Now for learning objectives. Would you like me to generate them, or would you prefer to dictate? You can also say 'skip'.",
        'skipped_session_plan_offer': "Skipped. Now for the session description. Would you like me to generate a session plan, or would you prefer to dictate it?",
        'syllabus_generate_offer': "I can generate a syllabus for '{course_name}'. Would you like me to create one?",
        'objectives_generate_offer': "I can generate learning objectives for '{course_name}'. Would you like me to create them?",
        'session_plan_generate_offer': "I can generate a session plan for '{topic}' including discussion prompts and a case study. Would you like me to create it?",
        'syllabus_dictate': "Okay, please dictate the syllabus now. Say what you'd like to include.",
        'objectives_dictate': "Okay, please dictate the learning objectives now.",
        'syllabus_generate_confirm': "Would you like me to generate a syllabus for you? Say 'yes' to generate, 'no' to dictate it yourself, or 'skip' to move on.",
        'objectives_generate_confirm': "Would you like me to generate learning objectives? Say 'yes' to generate, 'no' to dictate, or 'skip' to move on.",
        'syllabus_saved': "Syllabus saved! {next_prompt}",
        'syllabus_saved_objectives_offer': "Syllabus saved! Now for learning objectives. Would you like me to generate learning objectives based on the syllabus?",
        'syllabus_saved_ready': "Syllabus saved! The form is ready to submit. Would you like me to create the course?",
        'objectives_saved': "Objectives saved! {next_prompt}",
        'objectives_saved_ready': "Objectives saved! The course is ready to create. Would you like me to create it now and generate session plans?",
        'syllabus_edit': "The syllabus is in the form. You can edit it manually, or dictate a new one. Say 'done' when finished or 'skip' to move on.",
        'post_cancelled': "Post cancelled. What else can I help you with?",
        'poll_confirm': "Would you like to create a poll? Say yes or no.",
        'poll_cancelled': "Poll creation cancelled. What else can I help you with?",
        'cancelling_selection': "Cancelling selection. {nav_message}",
        'cancelling_form': "Cancelling form. {nav_message}",
        'cancelling_post': "Cancelling post. {nav_message}",
        'cancelling_poll': "Cancelling poll creation. {nav_message}",
        'cancelling_case': "Cancelling case creation. {nav_message}",
        'submitting_form': "Submitting the form. Clicking {button}.",
    },
    'es': {
        # Navigation
        'navigate_to': "Llevandote a {destination} ahora.",
        'navigate_open': "Abriendo {destination} para ti.",
        'switch_tab': "Cambiando a la pestana {tab}.",
        'switching_tabs': "Cambiando de pestana.",

        # Courses
        'no_courses': "Aun no tienes cursos. Te gustaria que te ayude a crear uno?",
        'one_course': "Tienes un curso: {name}. Te gustaria que lo abra?",
        'few_courses': "Tienes {count} cursos: {names}. Con cual te gustaria trabajar?",
        'many_courses': "Tienes {count} cursos, incluyendo {names}, y {more} mas. Te gustaria ver todos?",
        'create_course': "Abriendo creacion de curso. Dime el titulo del curso, o puedo ayudarte paso a paso.",
        'select_course': "Abriendo {name}. Que te gustaria hacer con el?",
        'selecting_course': "Seleccionando el curso para ti.",

        # Sessions
        'no_sessions': "No se encontraron sesiones. Te gustaria crear una nueva?",
        'live_sessions': "Hay {count} sesion{plural} en vivo: {names}. Te gustaria unirte a una?",
        'sessions_none_live': "Tienes {count} sesiones. Ninguna esta en vivo ahora. Te gustaria iniciar una?",
        'create_session': "Abriendo creacion de sesion. Cual sera el tema de esta sesion?",
        'select_session': "Abriendo {name}. Estado: {status}.",
        'selecting_session': "Seleccionando la sesion para ti.",
        'session_live': "La sesion esta en vivo! Los estudiantes pueden unirse y participar.",
        'session_ended': "La sesion ha terminado. Te gustaria que genere un reporte?",
        'session_draft': "La sesion se ha establecido como borrador. Puedes editarla o ponerla en vivo cuando estes listo.",
        'session_completed': "La sesion ha sido marcada como completada.",
        'session_scheduled': "La sesion ha sido programada.",

        # Actions
        'click_button': "Haciendo clic en {button}.",
        'clicking_button': "Haciendo clic en el boton.",
        'opening_materials': "Abriendo los materiales del curso. Puedes ver y descargar archivos aqui.",

        # Confirmations
        'confirm_proceed': "Te gustaria que proceda?",
        'confirm_yes': "Listo!",
        'confirm_cancel': "Esta bien, cancelado.",

        # Errors
        'error_generic': "Lo siento, hubo un problema: {reason}",
        'error_not_found': "No pude encontrar eso. Por favor intenta de nuevo.",

        # Greetings
        'greeting': "Hola! Como puedo ayudarte?",
        'ready': "Estoy listo para ayudar. Que te gustaria hacer?",

        # Dropdown
        'dropdown_options': "Tus opciones son: {options}. Cual te gustaria seleccionar?",
        'dropdown_selected': "Seleccionado {name}.",

        # Forum
        'forum_post_offer': "Te gustaria que te ayude a publicar algo?",
        'forum_posting': "Publicando en el foro.",

        # Polls
        'poll_create_offer': "Te gustaria crear una encuesta?",
        'poll_creating': "Creando la encuesta.",

        # AI Features
        'generating_summary': "Generando un resumen de la discusion.",
        'generating_questions': "Generando preguntas del cuestionario de la discusion.",
        'creating_groups': "Creando grupos de estudiantes con IA.",

        # Form filling
        'form_cancelled': "Formulario cancelado. Que te gustaria hacer?",
        'form_complete': "He completado todos los campos requeridos. Te gustaria que envie el formulario?",
        'confirm_yes_no': "Por favor di 'si' para confirmar o 'no' para cancelar.",
        'got_it_continue': "Entendido! {prompt}",
        'skipped_syllabus_offer': "Saltado. Ahora el programa de estudios. Te gustaria que genere uno, o prefieres dictarlo? Tambien puedes decir 'saltar'.",
        'skipped_objectives_offer': "Saltado. Ahora los objetivos de aprendizaje. Te gustaria que los genere, o prefieres dictarlos? Tambien puedes decir 'saltar'.",
        'skipped_session_plan_offer': "Saltado. Ahora la descripcion de la sesion. Te gustaria que genere un plan de sesion, o prefieres dictarlo?",
        'syllabus_generate_offer': "Puedo generar un programa de estudios para '{course_name}'. Te gustaria que cree uno?",
        'objectives_generate_offer': "Puedo generar objetivos de aprendizaje para '{course_name}'. Te gustaria que los cree?",
        'session_plan_generate_offer': "Puedo generar un plan de sesion para '{topic}' incluyendo temas de discusion y un caso de estudio. Te gustaria que lo cree?",
        'syllabus_dictate': "Bien, por favor dicta el programa de estudios ahora. Di lo que te gustaria incluir.",
        'objectives_dictate': "Bien, por favor dicta los objetivos de aprendizaje ahora.",
        'syllabus_generate_confirm': "Te gustaria que genere un programa de estudios? Di 'si' para generar, 'no' para dictarlo tu mismo, o 'saltar' para continuar.",
        'objectives_generate_confirm': "Te gustaria que genere objetivos de aprendizaje? Di 'si' para generar, 'no' para dictar, o 'saltar' para continuar.",
        'syllabus_saved': "Programa guardado! {next_prompt}",
        'syllabus_saved_objectives_offer': "Programa guardado! Ahora los objetivos de aprendizaje. Te gustaria que genere objetivos basados en el programa?",
        'syllabus_saved_ready': "Programa guardado! El formulario esta listo para enviar. Te gustaria que cree el curso?",
        'objectives_saved': "Objetivos guardados! {next_prompt}",
        'objectives_saved_ready': "Objetivos guardados! El curso esta listo para crear. Te gustaria que lo cree ahora y genere planes de sesion?",
        'syllabus_edit': "El programa esta en el formulario. Puedes editarlo manualmente, o dictar uno nuevo. Di 'listo' cuando termines o 'saltar' para continuar.",
        'post_cancelled': "Publicacion cancelada. En que mas puedo ayudarte?",
        'poll_confirm': "Te gustaria crear una encuesta? Di si o no.",
        'poll_cancelled': "Creacion de encuesta cancelada. En que mas puedo ayudarte?",
        'cancelling_selection': "Cancelando seleccion. {nav_message}",
        'cancelling_form': "Cancelando formulario. {nav_message}",
        'cancelling_post': "Cancelando publicacion. {nav_message}",
        'cancelling_poll': "Cancelando creacion de encuesta. {nav_message}",
        'cancelling_case': "Cancelando creacion de caso. {nav_message}",
        'submitting_form': "Enviando el formulario. Haciendo clic en {button}.",
    }
}

# Page names in both languages
PAGE_NAMES = {
    'en': {
        '/courses': 'courses',
        '/sessions': 'sessions',
        '/forum': 'forum',
        '/console': 'instructor console',
        '/reports': 'reports',
        '/integrations': 'integrations',
        '/platform-guide': 'introduction',
        '/dashboard': 'dashboard',
    },
    'es': {
        '/courses': 'cursos',
        '/sessions': 'sesiones',
        '/forum': 'foro',
        '/console': 'consola del instructor',
        '/reports': 'reportes',
        '/integrations': 'integraciones',
        '/platform-guide': 'introduccion',
        '/dashboard': 'panel principal',
    }
}

# Status translations
STATUS_NAMES = {
    'en': {
        'draft': 'draft',
        'live': 'live',
        'completed': 'completed',
        'scheduled': 'scheduled',
    },
    'es': {
        'draft': 'borrador',
        'live': 'en vivo',
        'completed': 'completada',
        'scheduled': 'programada',
    }
}


def get_response(key: str, language: str = 'en', **kwargs) -> str:
    """Get a response template in the specified language with formatting."""
    lang = language if language in RESPONSE_TEMPLATES else 'en'
    templates = RESPONSE_TEMPLATES[lang]

    if key not in templates:
        # Fall back to English if key not found in target language
        templates = RESPONSE_TEMPLATES['en']

    if key not in templates:
        return kwargs.get('fallback', f"[Missing template: {key}]")

    try:
        return templates[key].format(**kwargs)
    except KeyError:
        return templates[key]


def get_page_name(path: str, language: str = 'en') -> str:
    """Get page name in the specified language."""
    lang = language if language in PAGE_NAMES else 'en'
    return PAGE_NAMES[lang].get(path, path)


def get_status_name(status: str, language: str = 'en') -> str:
    """Get status name in the specified language."""
    lang = language if language in STATUS_NAMES else 'en'
    return STATUS_NAMES[lang].get(status, status)


# =============================================================================
# DEPRECATED PATTERNS REMOVED - Phase 5 Cleanup
# =============================================================================
# NAVIGATION_PATTERNS and ACTION_PATTERNS have been removed.
# The system now uses 100% LLM-based intent detection via voice_intent_classifier.py
# For navigation, use: detect_navigation_intent_llm()
# For actions, use: classify_intent() from voice_intent_classifier
# =============================================================================

# Legacy placeholder for backward compatibility (to be fully removed) 
# ACTION_PATTERNS and CONFIRMATION_PATTERNS have been removed in Phase 5 cleanup.
# The system now uses 100% LLM-based intent detection.
ACTION_PATTERNS = {}  # Empty - kept for backward compatibility only


def detect_navigation_intent(text: str, context: Optional[List[str]] = None, current_page: Optional[str] = None) -> Optional[str]:
    """Detect if user wants to navigate somewhere using LLM.

    This function has been updated to use LLM-based detection instead of regex patterns.
    The old NAVIGATION_PATTERNS have been removed in Phase 5 cleanup.
    """
    # Use LLM-based navigation detection
    return detect_navigation_intent_llm(text, context, current_page)


def build_confirmation_message(steps: List[Dict[str, Any]]) -> str:
    """Build a confirmation prompt for write actions."""
    summaries = []
    for step in steps:
        tool_name = step.get("tool_name", "unknown_tool")
        args = step.get("args", {})
        if args:
            arg_preview = ", ".join(f"{key}={value!r}" for key, value in list(args.items())[:3])
            summaries.append(f"{tool_name} ({arg_preview})")
        else:
            summaries.append(tool_name)
    actions = "; ".join(summaries) if summaries else "the requested action"
    return f"I can proceed with: {actions}. Would you like me to go ahead?"


def detect_navigation_intent_llm(
    text: str,
    context: Optional[List[str]],
    current_page: Optional[str],
) -> Optional[str]:
    llm, model_name = get_llm_with_tracking()
    if not llm:
        return None

    available_routes = {
        "/courses": "Courses list",
        "/sessions": "Sessions list",
        "/forum": "Forum discussions",
        "/console": "Instructor console",
        "/reports": "Reports",
        "/dashboard": "Dashboard home",
    }
    routes_description = "\n".join([f"- {route}: {desc}" for route, desc in available_routes.items()])

    prompt = (
        "You are routing a voice request to a known page in the AristAI app.\n"
        "Select the best matching route for the instructor request.\n"
        "If none apply, return null.\n\n"
        f"Available routes:\n{routes_description}\n\n"
        f"Current page: {current_page or 'unknown'}\n"
        f"Conversation context: {context or []}\n"
        f"Transcript: \"{text}\"\n\n"
        "Respond with ONLY valid JSON matching:\n"
        "{\"route\": \"/courses|/sessions|/forum|/console|/reports|/dashboard|null\","
        " \"confidence\": 0.0-1.0, \"reason\": \"short\"}"
    )

    response = invoke_llm_with_metrics(llm, prompt, model_name)
    if not response.success:
        return None

    parsed = parse_json_response(response.content or "")
    if not parsed:
        return None

    route = parsed.get("route")
    confidence = parsed.get("confidence", 0)
    if route in available_routes and isinstance(confidence, (int, float)) and confidence >= 0.5:
        return route

    return None


def _validate_tool_args(tool_name: str, args: dict, schema: dict) -> Optional[str]:
    required = schema.get("required", [])
    properties = schema.get("properties", {})

    for field in required:
        if field not in args:
            return f"Missing required field '{field}' for tool '{tool_name}'"

    for field, value in args.items():
        expected = properties.get(field, {}).get("type")
        if not expected:
            continue
        if expected == "integer" and not isinstance(value, int):
            return f"Field '{field}' must be integer"
        if expected == "string" and not isinstance(value, str):
            return f"Field '{field}' must be string"
        if expected == "array" and not isinstance(value, list):
            return f"Field '{field}' must be array"
        if expected == "boolean" and not isinstance(value, bool):
            return f"Field '{field}' must be boolean"
    return None


def generate_conversational_response(
    intent_type: str,
    intent_value: str,
    results: Optional[Any] = None,
    context: Optional[List[str]] = None,
    current_page: Optional[str] = None,
    language: str = 'en',
) -> str:
    """Generate a natural conversational response using LLM.

    This function uses LLM to generate responses in the user's selected language,
    ensuring all responses are properly localized regardless of what language
    the user spoke in.

    Args:
        intent_type: Type of intent ('navigate', 'execute', etc.)
        intent_value: The specific intent value
        results: Optional results from action execution
        context: Optional conversation context
        current_page: Current page path
        language: Response language ('en' or 'es')
    """
    lang = language if language in ['en', 'es'] else 'en'

    # Build situation description for LLM
    situation = _build_response_situation(intent_type, intent_value, results)

    # Build context string
    context_str = f"Page: {current_page or 'unknown'}"
    if context:
        context_str += f", Recent: {', '.join(context[:3])}"

    # Build data dict for LLM
    data = None
    if isinstance(results, dict):
        data = results
    elif isinstance(results, list):
        data = {"items": results[:5], "total_count": len(results)}

    # Use LLM to generate response in the correct language
    return generate_llm_response(
        situation=situation,
        language=lang,
        context=context_str,
        data=data
    )


def _build_response_situation(intent_type: str, intent_value: str, results: Any) -> str:
    """Build a situation description for LLM response generation.

    Returns a description of what happened that the LLM will use to generate
    a natural language response in the user's selected language.
    """

    if intent_type == 'navigate':
        return f"User is being navigated to the {intent_value} page. Confirm the navigation."

    if intent_type == 'execute':
        # Handle result that might be a dict with message/error
        if isinstance(results, dict):
            if results.get("error"):
                return f"An error occurred: {results['error']}"

        # === UI INTERACTIONS ===
        if intent_value == 'ui_select_course':
            return "Selecting a course for the user"
        if intent_value == 'ui_select_session':
            return "Selecting a session for the user"
        if intent_value == 'ui_switch_tab':
            tab_name = ""
            if isinstance(results, dict):
                tab_name = results.get("ui_actions", [{}])[0].get("payload", {}).get("tabName", "")
            return f"Switching to the {tab_name or 'requested'} tab"
        if intent_value == 'ui_click_button':
            button_label = ""
            if isinstance(results, dict):
                button_label = results.get("ui_actions", [{}])[0].get("payload", {}).get("buttonLabel", "")
            return f"Clicking the {button_label or 'requested'} button"

        # === COURSES ===
        if intent_value == 'list_courses':
            if isinstance(results, list):
                if len(results) == 0:
                    return "User has no courses yet. Offer to help create one."
                names = [c.get('title', 'Untitled') for c in results[:5]]
                return f"User has {len(results)} courses: {', '.join(names)}. Ask which one they want to work with."
            return "Unable to retrieve courses"
        if intent_value == 'create_course':
            return "Opening course creation form. Ask user for the course title."
        if intent_value == 'select_course':
            if isinstance(results, dict) and results.get("course"):
                course = results["course"]
                return f"Opening course '{course.get('title', 'the course')}'. Ask what they want to do with it."
            return "Selecting the course"
        if intent_value == 'view_course_details':
            if isinstance(results, dict) and results.get("title"):
                return f"Showing course '{results['title']}' which has {results.get('session_count', 0)} sessions"
            return "Could not find the course"

        # === SESSIONS ===
        if intent_value == 'list_sessions':
            if isinstance(results, list):
                if len(results) == 0:
                    return "No sessions found. Offer to create a new one."
                live = [s for s in results if s.get('status') == 'live']
                if live:
                    names = [s.get('title', 'Untitled') for s in live[:3]]
                    return f"Found {len(live)} live sessions: {', '.join(names)}. Ask if they want to join one."
                return f"User has {len(results)} sessions, but none are live. Offer to start one."
            return "Unable to retrieve sessions"
        if intent_value == 'create_session':
            return "Opening session creation. Ask what topic the session will cover."
        if intent_value == 'select_session':
            if isinstance(results, dict) and results.get("session"):
                session = results["session"]
                return f"Opening session '{session.get('title', 'the session')}' with status '{session.get('status', 'unknown')}'"
            return "Selecting the session"
        if intent_value == 'go_live':
            return "Session is now live! Students can join and participate."
        if intent_value == 'end_session':
            return "Session has ended. Offer to generate a report."
        if intent_value == 'view_materials':
            return "Opening course materials where user can view and download files."

        # === SESSION STATUS ===
        if intent_value == 'set_session_draft':
            return "Session has been set to draft mode. User can edit it or go live when ready."
        if intent_value == 'set_session_live':
            return "Session is now live! Students can join and start participating."
        if intent_value == 'set_session_completed':
            return "Session has been marked as completed."
        if intent_value == 'schedule_session':
            return "Session has been scheduled."
        if intent_value == 'edit_session':
            return "Opening the edit session dialog where user can change session title and details."
        if intent_value == 'delete_session':
            return "User wants to delete session. Ask for confirmation - this cannot be undone."

        # === REPORTS ===
        if intent_value == 'refresh_report':
            return "Refreshing the report to show the latest data."
        if intent_value == 'regenerate_report':
            return "Regenerating the report, which may take a moment."
        if intent_value == 'generate_report':
            return "Generating the session report by analyzing all discussion posts."

        # === THEME/UI ===
        if intent_value == 'toggle_theme':
            return "Toggling between light and dark mode."
        if intent_value == 'open_user_menu':
            return "Opening the user menu."
        if intent_value == 'view_voice_guide':
            return "Opening the voice command guide to show available voice commands."
        if intent_value == 'forum_instructions':
            return "Opening the platform instructions to show how to use AristAI."
        if intent_value == 'open_profile':
            return "Opening user's profile settings."
        if intent_value == 'sign_out':
            return "Signing the user out. Say goodbye."
        if intent_value == 'close_modal':
            return "Closing the window/modal."

        # === COPILOT ===
        if intent_value == 'start_copilot':
            return "Copilot is now active and will monitor discussion and provide suggestions every 90 seconds."
        if intent_value == 'stop_copilot':
            return "Copilot has been stopped. User can restart it anytime."
        if intent_value == 'refresh_interventions':
            return "Refreshing interventions from the copilot."
        if intent_value == 'get_interventions':
            if isinstance(results, list) and len(results) > 0:
                latest = results[0]
                suggestion = latest.get('suggestion_json', {})
                summary = suggestion.get('rolling_summary', '')
                confusion = suggestion.get('confusion_points', [])
                details = f"Summary: {summary}" if summary else "Has suggestions"
                if confusion:
                    details += f". {len(confusion)} confusion points detected."
                return f"Copilot insight: {details}"
            return "No suggestions yet. Copilot analyzes every 90 seconds when active."

        # === POLLS ===
        if intent_value == 'create_poll':
            return "Starting poll creation. Ask what question they want to ask in the poll."

        # === ENROLLMENT ===
        if intent_value == 'list_enrollments':
            if isinstance(results, list):
                return f"There are {len(results)} students enrolled. Offer to list them or show participation stats."
            return "Could not retrieve enrollment information."
        if intent_value == 'manage_enrollments':
            return "Opening enrollment management where user can add students by email or upload a roster."
        if intent_value == 'list_student_pool':
            if isinstance(results, dict) and results.get("students"):
                count = len(results.get("students", []))
                return f"There are {count} students available in the pool. Ask user to say a name to select."
            return "Showing available students."
        if intent_value == 'select_student':
            return "Student selected. User can say another name to select more, or 'enroll selected' to enroll them."
        if intent_value == 'enroll_selected':
            return "Enrolling the selected students."
        if intent_value == 'enroll_all':
            return "Enrolling all available students."

        # === FORUM ===
        if intent_value == 'post_case':
            return "Opening case study creation. Ask what scenario students should discuss."
        if intent_value == 'post_to_discussion':
            if isinstance(results, dict):
                if results.get("error") == "no_session":
                    return "Cannot post - need to select a live session first."
            return "Ask if user wants to post something to the discussion."
        if intent_value == 'view_posts':
            if isinstance(results, dict) and results.get("posts"):
                posts = results["posts"]
                if len(posts) > 0:
                    preview = posts[0].get('content', '')[:50]
                    return f"There are {len(posts)} forum posts. Latest is about: {preview}..."
            return "No posts yet in this session's forum."
        if intent_value == 'get_pinned_posts':
            if isinstance(results, dict):
                count = results.get("count", 0)
                if count > 0:
                    return f"There are {count} pinned posts - important discussions highlighted by the instructor."
                return "No pinned posts yet. User can pin important posts to highlight them."
            return "No pinned posts found."
        if intent_value == 'summarize_discussion':
            if isinstance(results, dict):
                if results.get("summary"):
                    return f"Discussion summary: {results['summary']}"
                if results.get("error"):
                    return f"Could not summarize: {results['error']}"
            return "Could not summarize discussion. Need to be in a live session."
        if intent_value == 'get_student_questions':
            if isinstance(results, dict):
                count = results.get("count", 0)
                if count > 0:
                    questions = results.get("questions", [])
                    first_q = questions[0].get('content', '')[:80] if questions else ""
                    return f"Found {count} questions from students. Most recent: {first_q}..."
                return "No questions from students yet."
            return "Could not find any questions."

        # === STATUS/HELP ===
        if intent_value == 'get_status':
            if isinstance(results, dict):
                message = results.get("message", "")
                actions = results.get("available_actions", [])
                if actions:
                    return f"Status: {message}. Available actions: {', '.join(actions[:4])}"
                return message
            return "Not sure what page user is on."
        if intent_value == 'get_help':
            return "User needs help. Explain what the voice assistant can help with: navigation, courses, sessions, polls, forum, reports."

        # === UNDO/CONTEXT ===
        if intent_value == 'undo_action':
            if isinstance(results, dict) and results.get("message"):
                return results["message"]
            return "Undid the last action."
        if intent_value == 'get_context':
            if isinstance(results, dict):
                course = results.get("course_name", "none")
                session = results.get("session_name", "none")
                return f"Active course: {course}, Active session: {session}"
            return "No active context set."
        if intent_value == 'clear_context':
            return "Context cleared! Starting fresh."

    # Default fallback
    return "Voice assistant ready to help with navigation, courses, sessions, polls, reports, and more."


@router.post("/converse", response_model=ConverseResponse)
async def voice_converse(request: ConverseRequest, db: Session = Depends(get_db)):
    """
    Conversational voice endpoint that processes natural language
    and returns appropriate responses with actions.

    CONVERSATIONAL FLOW:
    1. Check conversation state (awaiting input, confirmation, dropdown selection)
    2. Process based on state if active
    3. Regex navigation check (instant)
    4. Regex action check (instant)
    5. LLM orchestrator (only for complex requests)
    6. Template-based summary (no LLM)
    """
    transcript = request.transcript.strip()
    language = request.language or 'en'  # Default to English

    if not transcript:
        no_catch_msg = get_response('error_not_found', language) if language == 'es' else "I didn't catch that. Could you say it again?"
        suggestions = ["Mostrar mis cursos", "Iniciar sesion", "Abrir foro"] if language == 'es' else ["Show my courses", "Start a session", "Open forum"]
        return ConverseResponse(
            message=sanitize_speech(no_catch_msg),
            suggestions=suggestions
        )

    # === CHECK CONVERSATION STATE FIRST ===
    # Handle ongoing conversational flows (form filling, dropdown selection, confirmation)
    conv_context = conversation_manager.get_context(request.user_id)
    print(f"🔍 VOICE STATE: user_id={request.user_id}, state={conv_context.state}, transcript='{transcript[:50]}...'")

    # --- Handle confirmation state ---
    if conv_context.state == ConversationState.AWAITING_CONFIRMATION:
        # Check if user confirmed or denied
        confirmed = is_confirmation(transcript)
        # English + Spanish denial words (non-accented for speech-to-text compatibility)
        denial_words = ['no', 'nope', 'cancel', 'stop', 'never mind', 'nevermind',
                        'cancelar', 'parar', 'detener', 'no gracias', 'dejalo']
        denied = any(word in normalize_spanish_text(transcript.lower()) for word in denial_words)

        if confirmed or denied:
            result = conversation_manager.process_confirmation(request.user_id, confirmed)
            if result["confirmed"] and result["action"]:
                # For ui_click_button, use action_data directly instead of execute_action
                # (because process_confirmation already cleared pending_action_data)
                if result["action"] == "ui_click_button" and result.get("action_data"):
                    action_data = result["action_data"]
                    button_target = action_data.get("voice_id")
                    form_name = action_data.get("form_name", "")
                    button_label = form_name.replace("_", " ").title() if form_name else "Submit"

                    # Debug logging
                    print(f"🔘 CONFIRMATION: Clicking button '{button_target}' for form '{form_name}'")
                    print(f"🔘 action_data: {action_data}")

                    conversation_manager.reset_retry_count(request.user_id)
                    submit_msg = generate_voice_response(
                        f"Submitting the form by clicking the {button_label} button. Confirm the action.",
                        language=language
                    )
                    suggestions = ["What's next?", "Go to another page"] if language == 'en' else ["¿Qué sigue?", "Ir a otra página"]
                    return ConverseResponse(
                        message=sanitize_speech(submit_msg),
                        action=ActionResponse(type='execute', executed=True),
                        results=[{
                            "action": "click_button",
                            "ui_actions": [
                                {"type": "ui.clickButton", "payload": {"target": button_target}},
                                {"type": "ui.toast", "payload": {"message": f"{button_label} submitted", "type": "success"}},
                            ],
                        }],
                        suggestions=suggestions,
                    )

                # For other actions, use execute_action
                action_result = await execute_action(
                    result["action"],
                    request.user_id,
                    request.current_page,
                    db,
                    transcript,
                    None,  # llm_params
                    language,
                )
                conversation_manager.reset_retry_count(request.user_id)
                return ConverseResponse(
                    message=sanitize_speech(result["message"]),
                    action=ActionResponse(type='execute', executed=True),
                    results=[action_result] if action_result else None,
                    suggestions=get_action_suggestions(result["action"], language),
                )
            else:
                suggestions = ["Show my courses", "Go to forum", "What can I do?"] if language == 'en' else ["Mostrar mis cursos", "Ir al foro", "¿Qué puedo hacer?"]
                return ConverseResponse(
                    message=sanitize_speech(result["message"]),
                    action=ActionResponse(type='info'),
                    suggestions=suggestions,
                )
        # If not clear confirmation/denial, ask again
        confirm_msg = generate_voice_response(
            "Ask user to confirm or cancel. Tell them to say 'yes' to confirm or 'no' to cancel.",
            language=language
        )
        suggestions = ["Yes, proceed", "No, cancel"] if language == 'en' else ["Sí, continuar", "No, cancelar"]
        return ConverseResponse(
            message=sanitize_speech(confirm_msg),
            action=ActionResponse(type='info'),
            suggestions=suggestions,
        )

    # --- Handle dropdown selection state ---
    if conv_context.state == ConversationState.AWAITING_DROPDOWN_SELECTION:
        print(f"🔍 DROPDOWN STATE: Checking cancel for transcript: '{transcript}'")
        print(f"🔍 DROPDOWN STATE: active_dropdown={conv_context.active_dropdown}, options_count={len(conv_context.dropdown_options)}")

        # Check for explicit cancel/exit/skip intent using LLM
        transcript_lower = normalize_spanish_text(transcript.lower())
        confirmation_type = get_confirmation_type(transcript)
        is_cancel_intent = confirmation_type in ("no", "skip", "cancel")
        print(f"🔍 DROPDOWN STATE: Confirmation type: {confirmation_type}, is_cancel: {is_cancel_intent}")

        if is_cancel_intent:
            result = conversation_manager.cancel_dropdown_selection(request.user_id)
            return ConverseResponse(
                message=sanitize_speech(result["message"]),
                action=ActionResponse(type='info'),
                suggestions=["Go to sessions", "View courses", "Help"],
            )

        # Check for navigation intent - user wants to go somewhere else
        nav_path = detect_navigation_intent(transcript, request.context, request.current_page)
        if nav_path:
            conversation_manager.cancel_dropdown_selection(request.user_id)
            message = sanitize_speech(f"Cancelling selection. {generate_conversational_response('navigate', nav_path, language=language)}")
            return ConverseResponse(
                message=message,
                action=ActionResponse(type='navigate', target=nav_path),
                results=[{
                    "ui_actions": [
                        {"type": "ui.navigate", "payload": {"path": nav_path}},
                    ]
                }],
                suggestions=["What's next?", "Go back", "Help me"],
            )

        result = conversation_manager.select_dropdown_option(request.user_id, transcript)
        if result["success"]:
            selected = result["selected"]
            voice_id = result["voice_id"]
            conversation_manager.reset_retry_count(request.user_id)

            # Update context memory based on what was selected
            if request.user_id and selected.value:
                try:
                    selected_id = int(selected.value)
                    if voice_id and 'course' in voice_id.lower():
                        # Course was selected - update active course
                        context_store.update_context(request.user_id, active_course_id=selected_id)
                        print(f"🔍 Updated active_course_id to {selected_id} for user {request.user_id}")
                    elif voice_id and 'session' in voice_id.lower():
                        # Session was selected - update active session
                        context_store.update_context(request.user_id, active_session_id=selected_id)
                        print(f"🔍 Updated active_session_id to {selected_id} for user {request.user_id}")
                except (ValueError, TypeError):
                    pass  # Value wasn't a numeric ID

            return ConverseResponse(
                message=sanitize_speech(result["message"]),
                action=ActionResponse(type='execute', executed=True),
                results=[{
                    "ui_actions": [
                        {"type": "ui.selectDropdown", "payload": {
                            "target": voice_id,
                            "value": selected.value,
                            "optionName": selected.label,
                        }},
                        {"type": "ui.toast", "payload": {"message": f"Selected: {selected.label}", "type": "success"}},
                    ]
                }],
                suggestions=["What's next?", "Go to another page", "Help me"],
            )
        else:
            # Couldn't match selection, offer options again
            return ConverseResponse(
                message=sanitize_speech(result["message"]),
                action=ActionResponse(type='info'),
                suggestions=["Say the number", "Say the name", "Cancel"],
            )

    # --- Handle form field input state ---
    if conv_context.state == ConversationState.AWAITING_FIELD_INPUT:
        current_field = conversation_manager.get_current_field(request.user_id)
        if current_field:
            # FIRST: Check if user wants to navigate away or switch tabs (escape from form)
            # Check for navigation intent
            nav_path = detect_navigation_intent(transcript, request.context, request.current_page)
            if nav_path:
                # User wants to navigate - cancel form and navigate
                conversation_manager.cancel_form(request.user_id)
                message = sanitize_speech(f"Cancelling form. {generate_conversational_response('navigate', nav_path, language=language)}")
                return ConverseResponse(
                    message=message,
                    action=ActionResponse(type='navigate', target=nav_path),
                    results=[{
                        "ui_actions": [
                            {"type": "ui.navigate", "payload": {"path": nav_path}},
                        ]
                    }],
                    suggestions=get_page_suggestions(nav_path, language)
                )

            # Check for tab switching intent using LLM-based classification
            # Available tabs depend on the page - using common course/session tabs
            available_tabs = ['create', 'manage', 'sessions', 'advanced', 'instructor', 'enrollment']
            tab_result = classify_tab_switch(transcript, available_tabs, language)
            if tab_result.element_type == UIElementType.TAB and tab_result.element_name:
                tab_name = tab_result.element_name
                # User wants to switch tabs - cancel form and switch
                conversation_manager.cancel_form(request.user_id)

                # Special handling for manage status tab - offer status options
                if tab_name == 'manage':
                    manage_msg = generate_voice_response(
                        "Form cancelled. Switching to manage status tab. Tell user they can say 'go live', 'set to draft', 'complete', or 'schedule' to change session status.",
                        language=language
                    )
                    toast_msg = "Switched to manage status" if language == 'en' else "Cambiado a administrar estado"
                    suggestions = ["Go live", "Set to draft", "Complete session", "Schedule"] if language == 'en' else ["Iniciar en vivo", "Establecer borrador", "Completar sesión", "Programar"]
                    return ConverseResponse(
                        message=sanitize_speech(manage_msg),
                        action=ActionResponse(type='execute', executed=True),
                        results=[{
                            "ui_actions": [
                                {"type": "ui.switchTab", "payload": {"tabName": tab_name}},
                                {"type": "ui.toast", "payload": {"message": toast_msg, "type": "info"}},
                            ]
                        }],
                        suggestions=suggestions,
                    )

                switch_msg = generate_voice_response(
                    f"Form cancelled. Switching to {tab_name} tab. Confirm briefly.",
                    language=language
                )
                toast_msg = f"Switched to {tab_name}" if language == 'en' else f"Cambiado a {tab_name}"
                suggestions = ["Go live", "View sessions", "Create session"] if language == 'en' else ["Iniciar en vivo", "Ver sesiones", "Crear sesión"]
                return ConverseResponse(
                    message=sanitize_speech(switch_msg),
                    action=ActionResponse(type='execute', executed=True),
                    results=[{
                        "ui_actions": [
                            {"type": "ui.switchTab", "payload": {"tabName": tab_name}},
                            {"type": "ui.toast", "payload": {"message": toast_msg, "type": "info"}},
                        ]
                    }],
                    suggestions=suggestions,
                )

            # Check for cancel/exit keywords
            cancel_words = ['cancel', 'stop', 'exit', 'quit', 'abort', 'nevermind', 'never mind']
            if any(word in transcript.lower() for word in cancel_words):
                conversation_manager.cancel_form(request.user_id)
                return ConverseResponse(
                    message=sanitize_speech(get_response('form_cancelled', language)),
                    action=ActionResponse(type='info'),
                    suggestions=get_page_suggestions(request.current_page, language),
                )

            # Check for skip/next keywords
            skip_words = ['skip', 'next', 'pass', 'later', 'none', 'nothing']
            if any(word in transcript.lower() for word in skip_words):
                skip_result = conversation_manager.skip_current_field(request.user_id)
                # Check if next field supports AI generation and offer it
                next_field = conversation_manager.get_current_field(request.user_id)
                if next_field:
                    if next_field.voice_id == "syllabus":
                        conv_context = conversation_manager.get_context(request.user_id)
                        conv_context.state = ConversationState.AWAITING_SYLLABUS_GENERATION_CONFIRM
                        conversation_manager.save_context(request.user_id, conv_context)
                        return ConverseResponse(
                            message=sanitize_speech(get_response('skipped_syllabus_offer', language)),
                            action=ActionResponse(type='info'),
                            suggestions=["Yes, generate it", "No, I'll dictate", "Skip"] if language == 'en' else ["Si, generalo", "No, lo dictare", "Saltar"],
                        )
                    elif next_field.voice_id == "learning-objectives":
                        conv_context = conversation_manager.get_context(request.user_id)
                        conv_context.state = ConversationState.AWAITING_OBJECTIVES_GENERATION_CONFIRM
                        conversation_manager.save_context(request.user_id, conv_context)
                        return ConverseResponse(
                            message=sanitize_speech(get_response('skipped_objectives_offer', language)),
                            action=ActionResponse(type='info'),
                            suggestions=["Yes, generate them", "No, I'll dictate", "Skip"] if language == 'en' else ["Si, generalos", "No, los dictare", "Saltar"],
                        )
                    elif next_field.voice_id == "textarea-session-description":
                        conv_context = conversation_manager.get_context(request.user_id)
                        conv_context.state = ConversationState.AWAITING_SESSION_PLAN_GENERATION_CONFIRM
                        conversation_manager.save_context(request.user_id, conv_context)
                        return ConverseResponse(
                            message=sanitize_speech(get_response('skipped_session_plan_offer', language)),
                            action=ActionResponse(type='info'),
                            suggestions=["Yes, generate it", "No, I'll dictate", "Skip"] if language == 'en' else ["Si, generalo", "No, lo dictare", "Saltar"],
                        )
                return ConverseResponse(
                    message=sanitize_speech(skip_result["message"]),
                    action=ActionResponse(type='info'),
                    suggestions=["Continue", "Cancel form", "Help"],
                )

            # --- LLM-BASED INTELLIGENT INPUT CLASSIFICATION ---
            # Use the LLM to determine if the user's input is:
            # - CONTENT: actual data to be entered into the field
            # - META: meta-conversation (hesitation, thinking, questions)
            # - COMMAND: commands (cancel, skip, help, navigate)
            # - CONFIRM: yes/no confirmations
            #
            # This is smarter than pattern matching because it understands context.
            # "Let me consider it" = META (hesitation), not a course title
            # "Consider All Options" = CONTENT (could be a valid course title)

            field_prompt = current_field.prompt if hasattr(current_field, 'prompt') else f"provide {current_field.name}"
            field_type = current_field.voice_id if hasattr(current_field, 'voice_id') else current_field.name
            workflow_name = conv_context.action if hasattr(conv_context, 'action') else "form_filling"

            input_classification = classify_form_input(
                user_input=transcript,
                field_prompt=field_prompt,
                field_type=field_type,
                workflow_name=workflow_name
            )

            import logging
            logger = logging.getLogger(__name__)
            logger.info(f"[FormInputClassification] Input: '{transcript}' -> Type: {input_classification.input_type}, Confidence: {input_classification.confidence}, Reason: {input_classification.reason}")

            # Handle based on classification
            if input_classification.input_type == InputType.COMMAND:
                # User wants to execute a command instead of providing content
                command = input_classification.command or "cancel"

                if command == "cancel":
                    conversation_manager.cancel_form(request.user_id)
                    if language == 'es':
                        cancel_msg = "Entendido. He cancelado el formulario. Dime cuando quieras continuar o hacer algo más."
                    else:
                        cancel_msg = "Understood. I've cancelled the form. Let me know when you're ready to continue or do something else."
                    return ConverseResponse(
                        message=sanitize_speech(cancel_msg),
                        action=ActionResponse(type='info'),
                        suggestions=get_page_suggestions(request.current_page, language),
                    )
                elif command == "skip":
                    skip_result = conversation_manager.skip_current_field(request.user_id)
                    return ConverseResponse(
                        message=sanitize_speech(skip_result["message"]),
                        action=ActionResponse(type='info'),
                        suggestions=["Continue", "Cancel form", "Help"],
                    )
                elif command == "help":
                    if language == 'es':
                        help_msg = f"Estoy esperando que proporciones: {field_prompt}. Puedes decirlo directamente, o decir 'saltar' para omitir este campo, o 'cancelar' para salir del formulario."
                    else:
                        help_msg = f"I'm waiting for you to provide: {field_prompt}. You can say it directly, or say 'skip' to skip this field, or 'cancel' to exit the form."
                    return ConverseResponse(
                        message=sanitize_speech(help_msg),
                        action=ActionResponse(type='info'),
                        suggestions=["Skip", "Cancel", "Continue"] if language == 'en' else ["Saltar", "Cancelar", "Continuar"],
                    )
                else:
                    # Other commands (navigate, etc.) - cancel form and let main handler process
                    conversation_manager.cancel_form(request.user_id)
                    if language == 'es':
                        cancel_msg = "He cancelado el formulario para procesar tu comando."
                    else:
                        cancel_msg = "I've cancelled the form to process your command."
                    # Don't return here - let the main intent handler process the command
                    # This is a fallthrough case

            elif input_classification.input_type == InputType.META:
                # User is hesitating, thinking, or asking about the process - re-prompt
                if language == 'es':
                    hesitation_response = f"Tómate tu tiempo. Cuando estés listo, dime {field_prompt.lower()}. O di 'cancelar' para salir, o 'saltar' para omitir este campo."
                else:
                    hesitation_response = f"Take your time. When you're ready, tell me {field_prompt.lower()}. Or say 'cancel' to exit, or 'skip' to skip this field."
                return ConverseResponse(
                    message=sanitize_speech(hesitation_response),
                    action=ActionResponse(type='info'),
                    suggestions=["Skip", "Cancel", "Help"] if language == 'en' else ["Saltar", "Cancelar", "Ayuda"],
                )

            elif input_classification.input_type == InputType.CONFIRM:
                # User is just confirming - re-prompt for actual content
                return ConverseResponse(
                    message=sanitize_speech(get_response('got_it_continue', language, prompt=field_prompt)),
                    action=ActionResponse(type='info'),
                    suggestions=["Skip", "Cancel form", "Help"] if language == 'en' else ["Saltar", "Cancelar formulario", "Ayuda"],
                )

            # If we get here, input_classification.input_type == InputType.CONTENT
            # Continue with normal field value recording below

            # Check if this is the course title field - save it for later generation
            if current_field.voice_id == "course-title":
                # Save the course name for potential AI generation
                conv_context = conversation_manager.get_context(request.user_id)
                conv_context.course_name_for_generation = transcript.strip().rstrip('.!?,')
                conversation_manager.save_context(request.user_id, conv_context)

            # Check if we're on the syllabus field - offer AI generation
            if current_field.voice_id == "syllabus":
                # Check if user wants AI to generate it
                generate_words = ['generate', 'create', 'make', 'write', 'ai', 'auto', 'automatic', 'yes please', 'help me']
                if any(word in transcript.lower() for word in generate_words):
                    conv_context = conversation_manager.get_context(request.user_id)
                    course_name = conv_context.course_name_for_generation or conv_context.collected_values.get("course-title", "this course")
                    conv_context.state = ConversationState.AWAITING_SYLLABUS_GENERATION_CONFIRM
                    conversation_manager.save_context(request.user_id, conv_context)
                    return ConverseResponse(
                        message=sanitize_speech(get_response('syllabus_generate_offer', language, course_name=course_name)),
                        action=ActionResponse(type='info'),
                        suggestions=["Yes, generate it", "No, I'll dictate", "Skip"] if language == 'en' else ["Si, generalo", "No, lo dictare", "Saltar"],
                    )

            # Check if we're on the learning objectives field - offer AI generation
            if current_field.voice_id == "learning-objectives":
                # Check if user wants AI to generate it
                generate_words = ['generate', 'create', 'make', 'write', 'ai', 'auto', 'automatic', 'yes please', 'help me']
                if any(word in transcript.lower() for word in generate_words):
                    conv_context = conversation_manager.get_context(request.user_id)
                    course_name = conv_context.course_name_for_generation or conv_context.collected_values.get("course-title", "this course")
                    conv_context.state = ConversationState.AWAITING_OBJECTIVES_GENERATION_CONFIRM
                    conversation_manager.save_context(request.user_id, conv_context)
                    return ConverseResponse(
                        message=sanitize_speech(get_response('objectives_generate_offer', language, course_name=course_name)),
                        action=ActionResponse(type='info'),
                        suggestions=["Yes, generate them", "No, I'll dictate", "Skip"] if language == 'en' else ["Si, generalos", "No, los dictare", "Saltar"],
                    )

            # Check if we're on session description field - offer AI session plan generation
            if current_field.voice_id == "textarea-session-description":
                generate_words = ['generate', 'create', 'make', 'write', 'ai', 'auto', 'automatic', 'yes please', 'help me', 'session plan', 'case study', 'discussion']
                if any(word in transcript.lower() for word in generate_words):
                    conv_context = conversation_manager.get_context(request.user_id)
                    session_topic = conv_context.collected_values.get("input-session-title", "this session")
                    conv_context.state = ConversationState.AWAITING_SESSION_PLAN_GENERATION_CONFIRM
                    conversation_manager.save_context(request.user_id, conv_context)
                    return ConverseResponse(
                        message=sanitize_speech(get_response('session_plan_generate_offer', language, topic=session_topic)),
                        action=ActionResponse(type='info'),
                        suggestions=["Yes, generate it", "No, I'll dictate", "Skip"] if language == 'en' else ["Si, generalo", "No, lo dictare", "Saltar"],
                    )

            # Record the user's answer and fill the field
            result = conversation_manager.record_field_value(request.user_id, transcript)
            field_to_fill = result["field_to_fill"]

            ui_actions = []
            if field_to_fill:
                # Use sanitized value from all_values (trailing punctuation removed)
                sanitized_value = result["all_values"].get(field_to_fill.voice_id, transcript)
                ui_actions.append({
                    "type": "ui.fillInput",
                    "payload": {
                        "target": field_to_fill.voice_id,
                        "value": sanitized_value,
                    }
                })
                ui_actions.append({
                    "type": "ui.toast",
                    "payload": {"message": f"{field_to_fill.name} filled", "type": "success"}
                })

            if result["done"]:
                conversation_manager.reset_retry_count(request.user_id)

            return ConverseResponse(
                message=sanitize_speech(result["next_prompt"] or "Form complete!"),
                action=ActionResponse(type='execute', executed=True),
                results=[{"ui_actions": ui_actions, "all_values": result["all_values"]}],
                suggestions=["Submit", "Cancel", "Go back"] if result["done"] else ["Skip", "Cancel"],
            )

    # --- Handle forum post offer response state ---
    if conv_context.state == ConversationState.AWAITING_POST_OFFER_RESPONSE:
        # Use LLM-based input classification
        input_classification = classify_form_input(
            user_input=transcript,
            field_prompt="Would you like to post something to the discussion?",
            field_type="post_offer_response",
            workflow_name="forum_post"
        )

        import logging
        logger = logging.getLogger(__name__)
        logger.info(f"[PostOfferResponse] Input: '{transcript}' -> Type: {input_classification.input_type}, Command: {input_classification.command}, Confirm: {input_classification.confirm_value}")

        # Handle COMMAND type
        if input_classification.input_type == InputType.COMMAND:
            command = input_classification.command or "cancel"
            if command == "cancel":
                result = conversation_manager.handle_post_offer_response(request.user_id, False)
                return ConverseResponse(
                    message=sanitize_speech(result["message"]),
                    action=ActionResponse(type='info'),
                    suggestions=get_page_suggestions(request.current_page, language),
                )

        # Handle META type
        if input_classification.input_type == InputType.META:
            if language == 'es':
                hesitation_msg = "Tómate tu tiempo. Di 'sí' si quieres publicar algo, o 'no' si no."
            else:
                hesitation_msg = generate_voice_response(
                    "User is hesitating. Gently ask if they'd like to post to the discussion. Tell them to say 'yes' to post or 'no' if not.",
                    language=language
                )
            suggestions = ["Yes, I'd like to post", "No thanks", "Cancel"] if language == 'en' else ["Sí, quiero publicar", "No gracias", "Cancelar"]
            return ConverseResponse(
                message=sanitize_speech(hesitation_msg),
                action=ActionResponse(type='info'),
                suggestions=suggestions,
            )

        # Handle CONFIRM type
        if input_classification.input_type == InputType.CONFIRM:
            if input_classification.confirm_value == "yes":
                result = conversation_manager.handle_post_offer_response(request.user_id, True)
                suggestions = ["I'm done", "Cancel"] if language == 'en' else ["Terminé", "Cancelar"]
                return ConverseResponse(
                    message=sanitize_speech(result["message"]),
                    action=ActionResponse(type='info'),
                    suggestions=suggestions,
                )
            else:
                result = conversation_manager.handle_post_offer_response(request.user_id, False)
                suggestions = ["Switch to case studies", "Select another session", "Go to courses"] if language == 'en' else ["Cambiar a casos de estudio", "Seleccionar otra sesión", "Ir a cursos"]
                return ConverseResponse(
                    message=sanitize_speech(result["message"]),
                    action=ActionResponse(type='info'),
                    suggestions=suggestions,
                )

        # Handle CONTENT type - user might be starting to dictate the post directly
        if input_classification.input_type == InputType.CONTENT:
            # Accept offer and use this as the first part of the post
            result = conversation_manager.handle_post_offer_response(request.user_id, True)
            # Record this content as part of the post
            conv_context.partial_post_content = transcript
            conversation_manager.save_context(request.user_id, conv_context)
            continue_msg = generate_voice_response(
                "Got the start of user's post. Tell them to continue dictating or say 'done' when finished.",
                language=language
            )
            suggestions = ["I'm done", "Cancel"] if language == 'en' else ["Terminé", "Cancelar"]
            return ConverseResponse(
                message=sanitize_speech(continue_msg),
                action=ActionResponse(type='info'),
                suggestions=suggestions,
            )

        # Fallback - re-prompt
        fallback_msg = generate_voice_response(
            "Ask user if they want to post to the discussion. Tell them to say 'yes' or 'no'.",
            language=language
        )
        suggestions = ["Yes, I'd like to post", "No thanks"] if language == 'en' else ["Sí, quiero publicar", "No gracias"]
        return ConverseResponse(
            message=sanitize_speech(fallback_msg),
            action=ActionResponse(type='info'),
            suggestions=suggestions,
        )

    # --- Handle forum post dictation state ---
    if conv_context.state == ConversationState.AWAITING_POST_DICTATION:
        transcript_lower = transcript.lower().strip()

        # Check for navigation/escape intent first
        nav_path = detect_navigation_intent(transcript, request.context, request.current_page)
        if nav_path:
            conversation_manager.reset_post_offer(request.user_id)
            message = sanitize_speech(f"Cancelling post. {generate_conversational_response('navigate', nav_path, language=language)}")
            return ConverseResponse(
                message=message,
                action=ActionResponse(type='navigate', target=nav_path),
                results=[{
                    "ui_actions": [
                        {"type": "ui.navigate", "payload": {"path": nav_path}},
                    ]
                }],
                suggestions=get_page_suggestions(nav_path, language)
            )

        # Check for cancel keywords
        cancel_words = ['cancel', 'stop', 'abort', 'quit', 'nevermind', 'never mind']
        if any(word in transcript_lower for word in cancel_words):
            conversation_manager.reset_post_offer(request.user_id)
            cancel_msg = generate_voice_response(
                "Post has been cancelled. Ask what else user would like to do.",
                language=language
            )
            suggestions = ["Switch to case studies", "Select another session"] if language == 'en' else ["Cambiar a casos de estudio", "Seleccionar otra sesión"]
            return ConverseResponse(
                message=sanitize_speech(cancel_msg),
                action=ActionResponse(type='execute', executed=True),
                results=[{
                    "ui_actions": [
                        {"type": "ui.clearInput", "payload": {"target": "textarea-post-content"}},
                    ]
                }],
                suggestions=suggestions,
            )

        # Check for "I'm done" / "finished" using LLM extraction
        extraction_result = extract_full_context(
            transcript=transcript,
            conversation_state="awaiting_dictation_completion",
            language=language,
        )

        # Detect completion signals: done, finished, that's it, etc.
        is_done_signal = (
            extraction_result.dictation
            and extraction_result.dictation.is_command
            and extraction_result.dictation.command_type in ("done", "finished", "complete", "end")
        ) or (
            extraction_result.is_confirmation
            and extraction_result.confirmation_type == "yes"
            and extraction_result.intent_category == "confirm"
        )

        # Extract any content before the completion signal
        content_before_done = None
        if is_done_signal and extraction_result.dictation and extraction_result.dictation.content:
            content_before_done = extraction_result.dictation.content.rstrip('.,;:!? ')

        if is_done_signal:
            # If there's content before the "done" keyword, save it first!
            if content_before_done:
                conversation_manager.append_post_content(request.user_id, content_before_done)

            result = conversation_manager.finish_post_dictation(request.user_id)
            if result["has_content"]:
                # Fill the textarea with the accumulated content before asking for confirmation
                return ConverseResponse(
                    message=sanitize_speech(result["message"]),
                    action=ActionResponse(type='execute', executed=True),
                    results=[{
                        "ui_actions": [
                            {"type": "ui.fillInput", "payload": {"target": "textarea-post-content", "value": result["content"]}},
                        ]
                    }],
                    suggestions=["Yes, post it", "No, cancel"],
                )
            else:
                return ConverseResponse(
                    message=sanitize_speech(result["message"]),
                    action=ActionResponse(type='info'),
                    suggestions=["Yes, let me try again", "No, cancel"],
                )

        # Otherwise, this is dictation content - append it
        result = conversation_manager.append_post_content(request.user_id, transcript)

        # Update the textarea with current accumulated content
        return ConverseResponse(
            message=sanitize_speech(result["message"]),
            action=ActionResponse(type='execute', executed=True),
            results=[{
                "ui_actions": [
                    {"type": "ui.fillInput", "payload": {"target": "textarea-post-content", "value": result["content"]}},
                ]
            }],
            suggestions=["I'm done", "Cancel"],
        )

    # --- Handle forum post submit confirmation state ---
    if conv_context.state == ConversationState.AWAITING_POST_SUBMIT_CONFIRMATION:
        # Use LLM-based input classification
        input_classification = classify_form_input(
            user_input=transcript,
            field_prompt="Should I post this?",
            field_type="post_submit_confirm",
            workflow_name="forum_post"
        )

        import logging
        logger = logging.getLogger(__name__)
        logger.info(f"[PostSubmitConfirm] Input: '{transcript}' -> Type: {input_classification.input_type}, Command: {input_classification.command}, Confirm: {input_classification.confirm_value}")

        # Handle COMMAND type
        if input_classification.input_type == InputType.COMMAND:
            command = input_classification.command or "cancel"
            if command == "cancel":
                conversation_manager.handle_post_submit_response(request.user_id, False)
                cleared_msg = generate_voice_response(
                    "Post cleared/cancelled. Acknowledge briefly.",
                    language=language
                )
                return ConverseResponse(
                    message=sanitize_speech(cleared_msg),
                    action=ActionResponse(type='execute', executed=True),
                    results=[{"ui_actions": [{"type": "ui.clearInput", "payload": {"target": "textarea-post-content"}}]}],
                    suggestions=get_page_suggestions(request.current_page, language),
                )

        # Handle META type
        if input_classification.input_type == InputType.META:
            hesitation_msg = generate_voice_response(
                "User is hesitating about posting. Gently ask if they want to post or cancel.",
                language=language
            )
            suggestions = ["Yes, post it", "No, cancel"] if language == 'en' else ["Sí, publicar", "No, cancelar"]
            return ConverseResponse(
                message=sanitize_speech(hesitation_msg),
                action=ActionResponse(type='info'),
                suggestions=suggestions,
            )

        # Handle CONFIRM type
        if input_classification.input_type == InputType.CONFIRM:
            if input_classification.confirm_value == "yes":
                result = conversation_manager.handle_post_submit_response(request.user_id, True)
                toast_msg = "Post submitted!" if language == 'en' else "¡Publicación enviada!"
                suggestions = ["View posts", "Switch to case studies", "Select another session"] if language == 'en' else ["Ver publicaciones", "Cambiar a casos", "Seleccionar otra sesión"]
                return ConverseResponse(
                    message=sanitize_speech(result["message"]),
                    action=ActionResponse(type='execute', executed=True),
                    results=[{
                        "ui_actions": [
                            {"type": "ui.clickButton", "payload": {"target": "submit-post"}},
                            {"type": "ui.toast", "payload": {"message": toast_msg, "type": "success"}},
                        ]
                    }],
                    suggestions=suggestions,
                )
            else:
                conversation_manager.handle_post_submit_response(request.user_id, False)
                offer_prompt = conversation_manager.offer_forum_post(request.user_id)
                cleared_msg = generate_voice_response(
                    "Post cleared. Ask if user wants to try again.",
                    language=language
                )
                toast_msg = "Post cleared" if language == 'en' else "Publicación borrada"
                suggestions = ["Yes, let me try again", "No thanks"] if language == 'en' else ["Sí, intentar de nuevo", "No gracias"]
                return ConverseResponse(
                    message=sanitize_speech(cleared_msg),
                    action=ActionResponse(type='execute', executed=True),
                    results=[{
                        "ui_actions": [
                            {"type": "ui.clearInput", "payload": {"target": "textarea-post-content"}},
                            {"type": "ui.toast", "payload": {"message": toast_msg, "type": "info"}},
                        ]
                    }],
                    suggestions=suggestions,
                )

        # Fallback - re-prompt
        fallback_msg = generate_voice_response(
            "Ask user to confirm posting. Tell them to say 'yes' to post or 'no' to cancel.",
            language=language
        )
        suggestions = ["Yes, post it", "No, cancel"] if language == 'en' else ["Sí, publicar", "No, cancelar"]
        return ConverseResponse(
            message=sanitize_speech(fallback_msg),
            action=ActionResponse(type='info'),
            suggestions=suggestions,
        )

    # --- Handle poll offer response state ---
    if conv_context.state == ConversationState.AWAITING_POLL_OFFER_RESPONSE:
        # Use LLM-based input classification
        input_classification = classify_form_input(
            user_input=transcript,
            field_prompt="Would you like to create a poll?",
            field_type="poll_offer_response",
            workflow_name="create_poll"
        )

        import logging
        logger = logging.getLogger(__name__)
        logger.info(f"[PollOfferResponse] Input: '{transcript}' -> Type: {input_classification.input_type}, Command: {input_classification.command}, Confirm: {input_classification.confirm_value}")

        # Handle COMMAND type
        if input_classification.input_type == InputType.COMMAND:
            command = input_classification.command or "cancel"
            if command == "cancel":
                result = conversation_manager.handle_poll_offer_response(request.user_id, False)
                return ConverseResponse(
                    message=sanitize_speech(result["message"]),
                    action=ActionResponse(type='info'),
                    suggestions=get_page_suggestions(request.current_page, language),
                )

        # Handle META type
        if input_classification.input_type == InputType.META:
            hesitation_msg = generate_voice_response(
                "User is hesitating. Gently ask if they'd like to create a poll. Tell them to say 'yes' to create or 'no' if not.",
                language=language
            )
            suggestions = ["Yes, create a poll", "No thanks", "Cancel"] if language == 'en' else ["Sí, crear encuesta", "No gracias", "Cancelar"]
            return ConverseResponse(
                message=sanitize_speech(hesitation_msg),
                action=ActionResponse(type='info'),
                suggestions=suggestions,
            )

        # Handle CONFIRM type
        if input_classification.input_type == InputType.CONFIRM:
            if input_classification.confirm_value == "yes":
                result = conversation_manager.handle_poll_offer_response(request.user_id, True)
                suggestions = ["Cancel"] if language == 'en' else ["Cancelar"]
                return ConverseResponse(
                    message=sanitize_speech(result["message"]),
                    action=ActionResponse(type='info'),
                    suggestions=suggestions,
                )
            else:
                result = conversation_manager.handle_poll_offer_response(request.user_id, False)
                suggestions = ["Switch to copilot", "Switch to roster", "Go to courses"] if language == 'en' else ["Cambiar a copiloto", "Cambiar a lista", "Ir a cursos"]
                return ConverseResponse(
                    message=sanitize_speech(result["message"]),
                    action=ActionResponse(type='info'),
                    suggestions=suggestions,
                )

        # Handle CONTENT type - user might be providing a poll question directly
        if input_classification.input_type == InputType.CONTENT:
            # Accept offer and use this as the poll question
            result = conversation_manager.handle_poll_offer_response(request.user_id, True)
            conv_context.poll_question = transcript
            conversation_manager.save_context(request.user_id, conv_context)
            question_msg = generate_voice_response(
                f"Got user's poll question: '{transcript}'. Now ask for the first option.",
                language=language
            )
            suggestions = ["Cancel"] if language == 'en' else ["Cancelar"]
            return ConverseResponse(
                message=sanitize_speech(question_msg),
                action=ActionResponse(type='info'),
                suggestions=suggestions,
            )

        # Fallback - re-prompt
        fallback_msg = generate_voice_response(
            "Ask user if they want to create a poll. Tell them to say 'yes' or 'no'.",
            language=language
        )
        suggestions = ["Yes, create a poll", "No thanks"] if language == 'en' else ["Sí, crear encuesta", "No gracias"]
        return ConverseResponse(
            message=sanitize_speech(fallback_msg),
            action=ActionResponse(type='info'),
            suggestions=suggestions,
        )

    # --- Handle poll question state ---
    if conv_context.state == ConversationState.AWAITING_POLL_QUESTION:
        transcript_lower = transcript.lower().strip()

        # Check for navigation/escape intent first
        nav_path = detect_navigation_intent(transcript, request.context, request.current_page)
        if nav_path:
            conversation_manager.reset_poll_offer(request.user_id)
            message = sanitize_speech(f"Cancelling poll creation. {generate_conversational_response('navigate', nav_path, language=language)}")
            return ConverseResponse(
                message=message,
                action=ActionResponse(type='navigate', target=nav_path),
                results=[{
                    "ui_actions": [
                        {"type": "ui.navigate", "payload": {"path": nav_path}},
                    ]
                }],
                suggestions=get_page_suggestions(nav_path, language)
            )

        # Check for cancel keywords
        cancel_words = ['cancel', 'stop', 'abort', 'quit', 'nevermind', 'never mind']
        if any(word in transcript_lower for word in cancel_words):
            conversation_manager.reset_poll_offer(request.user_id)
            cancel_msg = generate_voice_response(
                "Poll creation cancelled. Ask what else user would like to do.",
                language=language
            )
            suggestions = ["Switch to copilot", "Switch to roster"] if language == 'en' else ["Cambiar a copiloto", "Cambiar a lista"]
            return ConverseResponse(
                message=sanitize_speech(cancel_msg),
                action=ActionResponse(type='info'),
                suggestions=suggestions,
            )

        # This is the poll question
        result = conversation_manager.set_poll_question(request.user_id, transcript)
        ui_actions = []
        for action_item in result.get("ui_actions", []):
            ui_actions.append({
                "type": f"ui.{action_item['action']}",
                "payload": {"target": action_item["voiceId"], "value": action_item.get("value", "")}
            })

        return ConverseResponse(
            message=sanitize_speech(result["message"]),
            action=ActionResponse(type='execute', executed=True),
            results=[{"ui_actions": ui_actions}],
            suggestions=["Cancel"],
        )

    # --- Handle poll option state ---
    if conv_context.state == ConversationState.AWAITING_POLL_OPTION:
        transcript_lower = transcript.lower().strip()

        # Check for navigation/escape intent first
        nav_path = detect_navigation_intent(transcript, request.context, request.current_page)
        if nav_path:
            conversation_manager.reset_poll_offer(request.user_id)
            message = sanitize_speech(f"Cancelling poll creation. {generate_conversational_response('navigate', nav_path, language=language)}")
            return ConverseResponse(
                message=message,
                action=ActionResponse(type='navigate', target=nav_path),
                results=[{
                    "ui_actions": [
                        {"type": "ui.navigate", "payload": {"path": nav_path}},
                    ]
                }],
                suggestions=get_page_suggestions(nav_path, language)
            )

        # Check for cancel keywords
        cancel_words = ['cancel', 'stop', 'abort', 'quit', 'nevermind', 'never mind']
        if any(word in transcript_lower for word in cancel_words):
            conversation_manager.reset_poll_offer(request.user_id)
            cancel_msg = generate_voice_response(
                "Poll creation cancelled. Ask what else user would like to do.",
                language=language
            )
            suggestions = ["Switch to copilot", "Switch to roster"] if language == 'en' else ["Cambiar a copiloto", "Cambiar a lista"]
            return ConverseResponse(
                message=sanitize_speech(cancel_msg),
                action=ActionResponse(type='info'),
                suggestions=suggestions,
            )

        # This is a poll option
        result = conversation_manager.add_poll_option(request.user_id, transcript)
        ui_actions = []
        for action_item in result.get("ui_actions", []):
            ui_actions.append({
                "type": f"ui.{action_item['action']}",
                "payload": {"target": action_item["voiceId"], "value": action_item.get("value", "")}
            })

        if language == 'en':
            suggestions = ["Cancel"]
            if result.get("ask_for_more"):
                suggestions = ["Yes, add more", "No, that's enough", "Cancel"]
        else:
            suggestions = ["Cancelar"]
            if result.get("ask_for_more"):
                suggestions = ["Sí, agregar más", "No, es suficiente", "Cancelar"]

        return ConverseResponse(
            message=sanitize_speech(result["message"]),
            action=ActionResponse(type='execute', executed=True),
            results=[{"ui_actions": ui_actions}],
            suggestions=suggestions,
        )

    # --- Handle poll more options response state ---
    if conv_context.state == ConversationState.AWAITING_POLL_MORE_OPTIONS:
        # Use LLM-based input classification
        input_classification = classify_form_input(
            user_input=transcript,
            field_prompt="Would you like to add another poll option?",
            field_type="poll_more_options",
            workflow_name="create_poll"
        )

        import logging
        logger = logging.getLogger(__name__)
        logger.info(f"[PollMoreOptions] Input: '{transcript}' -> Type: {input_classification.input_type}, Command: {input_classification.command}, Confirm: {input_classification.confirm_value}")

        # Handle COMMAND type
        if input_classification.input_type == InputType.COMMAND:
            command = input_classification.command or "cancel"
            if command == "cancel":
                conversation_manager.reset_poll_offer(request.user_id)
                cancel_msg = generate_voice_response(
                    "Poll creation cancelled. Acknowledge briefly.",
                    language=language
                )
                return ConverseResponse(
                    message=sanitize_speech(cancel_msg),
                    action=ActionResponse(type='info'),
                    suggestions=get_page_suggestions(request.current_page, language),
                )
            elif command == "skip":
                # Treat skip as "no more options"
                result = conversation_manager.handle_more_options_response(request.user_id, False)
                suggestions = ["Yes, create it", "No, cancel"] if language == 'en' else ["Sí, créala", "No, cancelar"]
                return ConverseResponse(
                    message=sanitize_speech(result["message"]),
                    action=ActionResponse(type='info'),
                    suggestions=suggestions,
                )

        # Handle META type
        if input_classification.input_type == InputType.META:
            hesitation_msg = generate_voice_response(
                "User is hesitating about adding another poll option. Gently ask if they want to add more or if they're done.",
                language=language
            )
            suggestions = ["Yes, add more", "No, that's enough", "Cancel"] if language == 'en' else ["Sí, agregar más", "No, es suficiente", "Cancelar"]
            return ConverseResponse(
                message=sanitize_speech(hesitation_msg),
                action=ActionResponse(type='info'),
                suggestions=suggestions,
            )

        # Handle CONFIRM type
        if input_classification.input_type == InputType.CONFIRM:
            if input_classification.confirm_value == "yes":
                result = conversation_manager.handle_more_options_response(request.user_id, True)
                ui_actions = []
                for action_item in result.get("ui_actions", []):
                    ui_actions.append({
                        "type": f"ui.{action_item['action']}",
                        "payload": {"target": action_item["voiceId"]}
                    })
                suggestions = ["Cancel"] if language == 'en' else ["Cancelar"]
                return ConverseResponse(
                    message=sanitize_speech(result["message"]),
                    action=ActionResponse(type='execute', executed=True),
                    results=[{"ui_actions": ui_actions}],
                    suggestions=suggestions,
                )
            else:
                result = conversation_manager.handle_more_options_response(request.user_id, False)
                suggestions = ["Yes, create it", "No, cancel"] if language == 'en' else ["Sí, créala", "No, cancelar"]
                return ConverseResponse(
                    message=sanitize_speech(result["message"]),
                    action=ActionResponse(type='info'),
                    suggestions=suggestions,
                )

        # Handle CONTENT type - user is providing the next poll option directly
        if input_classification.input_type == InputType.CONTENT:
            result = conversation_manager.add_poll_option(request.user_id, transcript)
            ui_actions = []
            for action_item in result.get("ui_actions", []):
                ui_actions.append({
                    "type": f"ui.{action_item['action']}",
                    "payload": {"target": action_item["voiceId"], "value": action_item.get("value", "")}
                })
            suggestions = ["Cancel"]
            if result.get("ask_for_more"):
                suggestions = ["Yes, add more", "No, that's enough", "Cancel"]
            return ConverseResponse(
                message=sanitize_speech(result["message"]),
                action=ActionResponse(type='execute', executed=True),
                results=[{"ui_actions": ui_actions}],
                suggestions=suggestions,
            )

        # Fallback - re-prompt
        fallback_msg = generate_voice_response(
            "Ask user if they want to add another poll option. Tell them to say 'yes' or 'no'.",
            language=language
        )
        suggestions = ["Yes, add more", "No, that's enough"] if language == 'en' else ["Sí, agregar más", "No, es suficiente"]
        return ConverseResponse(
            message=sanitize_speech(fallback_msg),
            action=ActionResponse(type='info'),
            suggestions=suggestions,
        )

    # --- Handle poll confirmation state ---
    if conv_context.state == ConversationState.AWAITING_POLL_CONFIRM:
        # Use LLM-based input classification
        input_classification = classify_form_input(
            user_input=transcript,
            field_prompt="Should I create this poll?",
            field_type="poll_confirm",
            workflow_name="create_poll"
        )

        import logging
        logger = logging.getLogger(__name__)
        logger.info(f"[PollConfirm] Input: '{transcript}' -> Type: {input_classification.input_type}, Command: {input_classification.command}, Confirm: {input_classification.confirm_value}")

        # Handle COMMAND type
        if input_classification.input_type == InputType.COMMAND:
            command = input_classification.command or "cancel"
            if command == "cancel":
                conversation_manager.reset_poll_offer(request.user_id)
                cancel_msg = generate_voice_response(
                    "Poll creation cancelled. Ask what else user would like to do.",
                    language=language
                )
                suggestions = ["Create a new poll", "Switch to copilot", "View roster"] if language == 'en' else ["Crear nueva encuesta", "Cambiar a copiloto", "Ver lista"]
                return ConverseResponse(
                    message=sanitize_speech(cancel_msg),
                    action=ActionResponse(type='info'),
                    suggestions=suggestions,
                )

        # Handle META type
        if input_classification.input_type == InputType.META:
            hesitation_msg = generate_voice_response(
                "User is hesitating about poll creation. Gently ask if they want to create it or cancel.",
                language=language
            )
            suggestions = ["Yes, create it", "No, cancel"] if language == 'en' else ["Sí, créala", "No, cancelar"]
            return ConverseResponse(
                message=sanitize_speech(hesitation_msg),
                action=ActionResponse(type='info'),
                suggestions=suggestions,
            )

        # Handle CONFIRM type
        if input_classification.input_type == InputType.CONFIRM:
            if input_classification.confirm_value == "yes":
                result = conversation_manager.handle_poll_confirm(request.user_id, True)
                ui_actions = []
                for action_item in result.get("ui_actions", []):
                    ui_actions.append({
                        "type": f"ui.{action_item['action']}",
                        "payload": {"target": action_item["voiceId"]}
                    })
                toast_msg = "Poll created!" if language == 'en' else "¡Encuesta creada!"
                ui_actions.append({"type": "ui.toast", "payload": {"message": toast_msg, "type": "success"}})
                suggestions = ["Create another poll", "Switch to copilot", "View roster"] if language == 'en' else ["Crear otra encuesta", "Cambiar a copiloto", "Ver lista"]
                return ConverseResponse(
                    message=sanitize_speech(result["message"]),
                    action=ActionResponse(type='execute', executed=True),
                    results=[{"ui_actions": ui_actions}],
                    suggestions=suggestions,
                )
            else:
                conversation_manager.reset_poll_offer(request.user_id)
                cancel_msg = generate_voice_response(
                    "Poll creation cancelled. Ask what else user would like to do.",
                    language=language
                )
                suggestions = ["Create a new poll", "Switch to copilot", "View roster"] if language == 'en' else ["Crear nueva encuesta", "Cambiar a copiloto", "Ver lista"]
                return ConverseResponse(
                    message=sanitize_speech(cancel_msg),
                    action=ActionResponse(type='info'),
                    suggestions=suggestions,
                )

        # Handle CONTENT type - unclear in this context, re-prompt
        # Fallback - re-prompt
        fallback_msg = generate_voice_response(
            "Ask user to confirm poll creation. Tell them to say 'yes' to create or 'no' to cancel.",
            language=language
        )
        suggestions = ["Yes, create it", "No, cancel"] if language == 'en' else ["Sí, créala", "No, cancelar"]
        return ConverseResponse(
            message=sanitize_speech(fallback_msg),
            action=ActionResponse(type='info'),
            suggestions=suggestions,
        )

    # --- Handle case offer response state ---
    if conv_context.state == ConversationState.AWAITING_CASE_OFFER_RESPONSE:
        # Use LLM-based input classification
        input_classification = classify_form_input(
            user_input=transcript,
            field_prompt="Would you like to post a case study?",
            field_type="case_offer_response",
            workflow_name="post_case"
        )

        import logging
        logger = logging.getLogger(__name__)
        logger.info(f"[CaseOfferResponse] Input: '{transcript}' -> Type: {input_classification.input_type}, Command: {input_classification.command}, Confirm: {input_classification.confirm_value}")

        # Handle COMMAND type
        if input_classification.input_type == InputType.COMMAND:
            command = input_classification.command or "cancel"
            if command == "cancel":
                result = conversation_manager.handle_case_offer_response(request.user_id, False)
                return ConverseResponse(
                    message=sanitize_speech(result["message"]),
                    action=ActionResponse(type='info'),
                    suggestions=get_page_suggestions(request.current_page, language),
                )

        # Handle META type
        if input_classification.input_type == InputType.META:
            if language == 'es':
                hesitation_msg = generate_voice_response(
                    "User is hesitating. Gently ask if they'd like to post a case study. Tell them to say 'yes' or 'no'.",
                    language=language
                )
            suggestions = ["Yes, post a case", "No thanks", "Cancel"] if language == 'en' else ["Sí, publicar caso", "No gracias", "Cancelar"]
            return ConverseResponse(
                message=sanitize_speech(hesitation_msg),
                action=ActionResponse(type='info'),
                suggestions=suggestions,
            )

        # Handle CONFIRM type
        if input_classification.input_type == InputType.CONFIRM:
            if input_classification.confirm_value == "yes":
                result = conversation_manager.handle_case_offer_response(request.user_id, True)
                suggestions = ["Cancel"] if language == 'en' else ["Cancelar"]
                return ConverseResponse(
                    message=sanitize_speech(result["message"]),
                    action=ActionResponse(type='info'),
                    suggestions=suggestions,
                )
            else:
                result = conversation_manager.handle_case_offer_response(request.user_id, False)
                suggestions = ["Switch to polls", "Switch to copilot", "Go to forum"] if language == 'en' else ["Cambiar a encuestas", "Cambiar a copiloto", "Ir al foro"]
                return ConverseResponse(
                    message=sanitize_speech(result["message"]),
                    action=ActionResponse(type='info'),
                    suggestions=suggestions,
                )

        # Handle CONTENT type - user might be providing case content directly
        if input_classification.input_type == InputType.CONTENT:
            result = conversation_manager.handle_case_offer_response(request.user_id, True)
            conv_context.partial_case_content = transcript
            conversation_manager.save_context(request.user_id, conv_context)
            continue_msg = generate_voice_response(
                "Got the start of user's case study. Tell them to continue dictating or say 'done' when finished.",
                language=language
            )
            suggestions = ["I'm done", "Cancel"] if language == 'en' else ["Terminé", "Cancelar"]
            return ConverseResponse(
                message=sanitize_speech(continue_msg),
                action=ActionResponse(type='info'),
                suggestions=suggestions,
            )

        # Fallback - re-prompt
        fallback_msg = generate_voice_response(
            "Ask user if they want to post a case study. Tell them to say 'yes' or 'no'.",
            language=language
        )
        suggestions = ["Yes, post a case", "No thanks"] if language == 'en' else ["Sí, publicar caso", "No gracias"]
        return ConverseResponse(
            message=sanitize_speech(fallback_msg),
            action=ActionResponse(type='info'),
            suggestions=suggestions,
        )

    # --- Handle case prompt dictation state ---
    if conv_context.state == ConversationState.AWAITING_CASE_PROMPT:
        transcript_lower = transcript.lower().strip()

        # Check for navigation/escape intent first
        nav_path = detect_navigation_intent(transcript, request.context, request.current_page)
        if nav_path:
            conversation_manager.reset_case_offer(request.user_id)
            message = sanitize_speech(f"Cancelling case creation. {generate_conversational_response('navigate', nav_path, language=language)}")
            return ConverseResponse(
                message=message,
                action=ActionResponse(type='navigate', target=nav_path),
                results=[{
                    "ui_actions": [
                        {"type": "ui.navigate", "payload": {"path": nav_path}},
                    ]
                }],
                suggestions=get_page_suggestions(nav_path, language)
            )

        # Check for cancel keywords
        cancel_words = ['cancel', 'stop', 'abort', 'quit', 'nevermind', 'never mind']
        if any(word in transcript_lower for word in cancel_words):
            conversation_manager.reset_case_offer(request.user_id)
            cancel_msg = generate_voice_response(
                "Case creation cancelled. Ask what else user would like to do.",
                language=language
            )
            suggestions = ["Switch to polls", "Switch to copilot"] if language == 'en' else ["Cambiar a encuestas", "Cambiar a copiloto"]
            return ConverseResponse(
                message=sanitize_speech(cancel_msg),
                action=ActionResponse(type='info'),
                suggestions=suggestions,
            )

        # Check for "done" or "finished" keywords to finish dictation
        done_words = ['done', "i'm done", "that's it", "that is it", 'finished', 'post it', 'submit', "that's all", "that is all"]
        if any(word in transcript_lower for word in done_words):
            result = conversation_manager.finish_case_dictation(request.user_id)

            if result.get("ready_to_confirm"):
                return ConverseResponse(
                    message=sanitize_speech(result["message"]),
                    action=ActionResponse(type='info'),
                    suggestions=["Yes, post it", "No, cancel"],
                )
            else:
                # No content yet - ask again
                return ConverseResponse(
                    message=sanitize_speech(result["message"]),
                    action=ActionResponse(type='info'),
                    suggestions=["Cancel"],
                )

        # This is case content - append it
        result = conversation_manager.append_case_content(request.user_id, transcript)
        ui_actions = []
        for action_item in result.get("ui_actions", []):
            ui_actions.append({
                "type": f"ui.{action_item['action']}",
                "payload": {"target": action_item["voiceId"], "value": action_item.get("value", "")}
            })

        return ConverseResponse(
            message=sanitize_speech(result["message"]),
            action=ActionResponse(type='execute', executed=True),
            results=[{"ui_actions": ui_actions}],
            suggestions=["Done", "Cancel"],
        )

    # --- Handle case confirmation state ---
    if conv_context.state == ConversationState.AWAITING_CASE_CONFIRM:
        # Use LLM-based input classification
        input_classification = classify_form_input(
            user_input=transcript,
            field_prompt="Should I post this case study?",
            field_type="case_confirm",
            workflow_name="post_case"
        )

        import logging
        logger = logging.getLogger(__name__)
        logger.info(f"[CaseConfirm] Input: '{transcript}' -> Type: {input_classification.input_type}, Command: {input_classification.command}, Confirm: {input_classification.confirm_value}")

        # Handle COMMAND type
        if input_classification.input_type == InputType.COMMAND:
            command = input_classification.command or "cancel"
            if command == "cancel":
                conversation_manager.reset_case_offer(request.user_id)
                cancel_msg = generate_voice_response(
                    "Case posting cancelled. Tell user the content is still in the form if they want to edit it.",
                    language=language
                )
                suggestions = ["Post a new case", "Switch to polls", "View forum"] if language == 'en' else ["Publicar nuevo caso", "Cambiar a encuestas", "Ver foro"]
                return ConverseResponse(
                    message=sanitize_speech(cancel_msg),
                    action=ActionResponse(type='info'),
                    suggestions=suggestions,
                )

        # Handle META type
        if input_classification.input_type == InputType.META:
            hesitation_msg = generate_voice_response(
                "User is hesitating about posting the case study. Gently ask if they want to post it or cancel.",
                language=language
            )
            suggestions = ["Yes, post it", "No, cancel"] if language == 'en' else ["Sí, publicar", "No, cancelar"]
            return ConverseResponse(
                message=sanitize_speech(hesitation_msg),
                action=ActionResponse(type='info'),
                suggestions=suggestions,
            )

        # Handle CONFIRM type
        if input_classification.input_type == InputType.CONFIRM:
            if input_classification.confirm_value == "yes":
                result = conversation_manager.handle_case_confirm(request.user_id, True)
                ui_actions = []
                for action_item in result.get("ui_actions", []):
                    ui_actions.append({
                        "type": f"ui.{action_item['action']}",
                        "payload": {"target": action_item["voiceId"]}
                    })
                toast_msg = "Case study posted!" if language == 'en' else "¡Caso de estudio publicado!"
                ui_actions.append({"type": "ui.toast", "payload": {"message": toast_msg, "type": "success"}})
                suggestions = ["Post another case", "Switch to polls", "View forum"] if language == 'en' else ["Publicar otro caso", "Cambiar a encuestas", "Ver foro"]
                return ConverseResponse(
                    message=sanitize_speech(result["message"]),
                    action=ActionResponse(type='execute', executed=True),
                    results=[{"ui_actions": ui_actions}],
                    suggestions=suggestions,
                )
            else:
                conversation_manager.reset_case_offer(request.user_id)
                cancel_msg = generate_voice_response(
                    "Case posting cancelled. Tell user the content is still in the form if they want to edit it.",
                    language=language
                )
                suggestions = ["Post a new case", "Switch to polls", "View forum"] if language == 'en' else ["Publicar nuevo caso", "Cambiar a encuestas", "Ver foro"]
                return ConverseResponse(
                    message=sanitize_speech(cancel_msg),
                    action=ActionResponse(type='info'),
                    suggestions=suggestions,
                )

        # Fallback - re-prompt
        fallback_msg = generate_voice_response(
            "Ask user to confirm case study posting. Tell them to say 'yes' to post or 'no' to cancel.",
            language=language
        )
        suggestions = ["Yes, post it", "No, cancel"] if language == 'en' else ["Sí, publicar", "No, cancelar"]
        return ConverseResponse(
            message=sanitize_speech(fallback_msg),
            action=ActionResponse(type='info'),
            suggestions=suggestions,
        )

    # --- Handle AI syllabus generation confirmation state ---
    if conv_context.state == ConversationState.AWAITING_SYLLABUS_GENERATION_CONFIRM:
        # Use LLM-based input classification for smarter intent detection
        input_classification = classify_form_input(
            user_input=transcript,
            field_prompt="Would you like me to generate a syllabus?",
            field_type="syllabus_generation_confirm",
            workflow_name="create_course"
        )

        import logging
        logger = logging.getLogger(__name__)
        logger.info(f"[SyllabusConfirm] Input: '{transcript}' -> Type: {input_classification.input_type}, Command: {input_classification.command}, Confirm: {input_classification.confirm_value}")

        # Handle COMMAND type (cancel, skip, etc.)
        if input_classification.input_type == InputType.COMMAND:
            command = input_classification.command or "cancel"
            if command == "cancel":
                # User wants to cancel the entire form
                conversation_manager.cancel_form(request.user_id)
                cancel_msg = generate_voice_response(
                    "Course creation cancelled. Tell user to let you know when they're ready to continue.",
                    language=language
                )
                return ConverseResponse(
                    message=sanitize_speech(cancel_msg),
                    action=ActionResponse(type='info'),
                    suggestions=get_page_suggestions(request.current_page, language),
                )
            elif command == "skip":
                skip_result = conversation_manager.skip_current_field(request.user_id)
                # Check if next field is learning-objectives and offer AI generation
                next_field = conversation_manager.get_current_field(request.user_id)
                if next_field and next_field.voice_id == "learning-objectives":
                    conv_context.state = ConversationState.AWAITING_OBJECTIVES_GENERATION_CONFIRM
                    conversation_manager.save_context(request.user_id, conv_context)
                    skip_msg = generate_voice_response(
                        "Skipped syllabus. Ask user if they want to generate learning objectives for the course.",
                        language=language
                    )
                    suggestions = ["Yes, generate them", "No, I'll dictate", "Skip"] if language == 'en' else ["Sí, generar", "No, dictaré", "Saltar"]
                    return ConverseResponse(
                        message=sanitize_speech(skip_msg),
                        action=ActionResponse(type='info'),
                        suggestions=suggestions,
                    )
                suggestions = ["Continue", "Cancel form"] if language == 'en' else ["Continuar", "Cancelar formulario"]
                return ConverseResponse(
                    message=sanitize_speech(skip_result["message"]),
                    action=ActionResponse(type='info'),
                    suggestions=suggestions,
                )

        # Handle META type (hesitation, thinking)
        if input_classification.input_type == InputType.META:
            hesitation_msg = generate_voice_response(
                "User is hesitating about syllabus generation. Tell them they can say 'yes' to generate, 'no' to dictate, 'skip' to move on, or 'cancel' to exit.",
                language=language
            )
            suggestions = ["Yes, generate it", "No, I'll dictate", "Skip", "Cancel"] if language == 'en' else ["Sí, generar", "No, dictaré", "Saltar", "Cancelar"]
            return ConverseResponse(
                message=sanitize_speech(hesitation_msg),
                action=ActionResponse(type='info'),
                suggestions=suggestions,
            )

        # Handle CONFIRM type
        if input_classification.input_type == InputType.CONFIRM:
            if input_classification.confirm_value == "yes":
                # Generate syllabus using AI
                course_name = conv_context.course_name_for_generation or "the course"

                # Call the content generation tool via MCP registry
                try:
                    gen_result = _execute_tool(db, 'generate_syllabus', {"course_name": course_name})
                except Exception as e:
                    logging.getLogger(__name__).error(f"Syllabus generation error: {e}")
                    gen_result = None

                if gen_result and gen_result.get("success") and gen_result.get("syllabus"):
                    syllabus = gen_result["syllabus"]
                    # Save the generated syllabus
                    conv_context.generated_syllabus = syllabus
                    conv_context.state = ConversationState.AWAITING_SYLLABUS_REVIEW
                    conversation_manager.save_context(request.user_id, conv_context)

                    # Preview (first 150 chars)
                    preview = syllabus[:150] + "..." if len(syllabus) > 150 else syllabus

                    gen_msg = generate_voice_response(
                        f"Generated a syllabus for '{course_name}'. Give a brief preview and ask if user wants to use it. Preview: {preview}",
                        language=language
                    )
                    suggestions = ["Yes, use it", "No, let me edit", "Skip syllabus"] if language == 'en' else ["Sí, úsalo", "No, déjame editar", "Saltar programa"]
                    return ConverseResponse(
                        message=sanitize_speech(gen_msg),
                        action=ActionResponse(type='info'),
                        results=[{
                            "ui_actions": [
                                {"type": "ui.fillInput", "payload": {"target": "syllabus", "value": syllabus}},
                            ]
                        }],
                        suggestions=suggestions,
                    )
                else:
                    # Generation failed - fallback to manual
                    conv_context.state = ConversationState.AWAITING_FIELD_INPUT
                    conversation_manager.save_context(request.user_id, conv_context)
                    error_msg = gen_result.get("error", "Generation failed") if gen_result else "Tool not available"
                    error_response = generate_voice_response(
                        f"Syllabus generation failed with error: {error_msg}. Ask user to dictate the syllabus or say 'skip'.",
                        language=language
                    )
                    suggestions = ["Skip", "Cancel form"] if language == 'en' else ["Saltar", "Cancelar formulario"]
                    return ConverseResponse(
                        message=sanitize_speech(error_response),
                        action=ActionResponse(type='info'),
                        suggestions=suggestions,
                    )
            else:
                # User said no - they want to dictate
                conv_context.state = ConversationState.AWAITING_FIELD_INPUT
                conversation_manager.save_context(request.user_id, conv_context)
                dictate_msg = generate_voice_response(
                    "User wants to dictate the syllabus. Ask them to start dictating what they want to include.",
                    language=language
                )
                suggestions = ["Skip", "Cancel form"] if language == 'en' else ["Saltar", "Cancelar formulario"]
                return ConverseResponse(
                    message=sanitize_speech(dictate_msg),
                    action=ActionResponse(type='info'),
                    suggestions=suggestions,
                )

        # Handle CONTENT type - treat as if they want to dictate their own syllabus
        if input_classification.input_type == InputType.CONTENT:
            conv_context.state = ConversationState.AWAITING_FIELD_INPUT
            conversation_manager.save_context(request.user_id, conv_context)
            # Record the content they just spoke as the syllabus value
            result = conversation_manager.record_field_value(request.user_id, transcript)
            ui_actions = []
            if result.get("field_to_fill"):
                sanitized_value = result["all_values"].get(result["field_to_fill"].voice_id, transcript)
                ui_actions.append({
                    "type": "ui.fillInput",
                    "payload": {"target": result["field_to_fill"].voice_id, "value": sanitized_value}
                })
            return ConverseResponse(
                message=sanitize_speech(result.get("next_prompt", "Got it! What's next?")),
                action=ActionResponse(type='execute', executed=True),
                results=[{"ui_actions": ui_actions, "all_values": result.get("all_values", {})}],
                suggestions=["Continue", "Skip", "Cancel"],
            )

        # Fallback - re-prompt
        fallback_msg = generate_voice_response(
            "Ask user if they want to generate a syllabus with AI, dictate it themselves, skip, or cancel.",
            language=language
        )
        suggestions = ["Yes, generate it", "No, I'll dictate", "Skip", "Cancel"] if language == 'en' else ["Sí, generar", "No, dictaré", "Saltar", "Cancelar"]
        return ConverseResponse(
            message=sanitize_speech(fallback_msg),
            action=ActionResponse(type='info'),
            suggestions=suggestions,
        )

    # --- Handle syllabus review state ---
    if conv_context.state == ConversationState.AWAITING_SYLLABUS_REVIEW:
        # Use LLM-based input classification
        input_classification = classify_form_input(
            user_input=transcript,
            field_prompt="Should I use this generated syllabus?",
            field_type="syllabus_review",
            workflow_name="create_course"
        )

        import logging
        logger = logging.getLogger(__name__)
        logger.info(f"[SyllabusReview] Input: '{transcript}' -> Type: {input_classification.input_type}, Command: {input_classification.command}, Confirm: {input_classification.confirm_value}")

        # Handle COMMAND type (cancel, skip, edit, etc.)
        if input_classification.input_type == InputType.COMMAND:
            command = input_classification.command or "cancel"
            if command == "cancel":
                conversation_manager.cancel_form(request.user_id)
                cancel_msg = generate_voice_response(
                    "Course creation cancelled. Acknowledge briefly.",
                    language=language
                )
                return ConverseResponse(
                    message=sanitize_speech(cancel_msg),
                    action=ActionResponse(type='info'),
                    suggestions=get_page_suggestions(request.current_page, language),
                )
            elif command == "skip":
                skip_result = conversation_manager.skip_current_field(request.user_id)
                conv_context.generated_syllabus = ""
                conversation_manager.save_context(request.user_id, conv_context)
                next_field = conversation_manager.get_current_field(request.user_id)
                if next_field and next_field.voice_id == "learning-objectives":
                    conv_context.state = ConversationState.AWAITING_OBJECTIVES_GENERATION_CONFIRM
                    conversation_manager.save_context(request.user_id, conv_context)
                    skip_msg = generate_voice_response(
                        "Skipped syllabus. Ask user if they want to generate learning objectives for the course.",
                        language=language
                    )
                    suggestions = ["Yes, generate them", "No, I'll dictate", "Skip"] if language == 'en' else ["Sí, generar", "No, dictaré", "Saltar"]
                    return ConverseResponse(
                        message=sanitize_speech(skip_msg),
                        action=ActionResponse(type='info'),
                        results=[{"ui_actions": [{"type": "ui.clearInput", "payload": {"target": "syllabus"}}]}],
                        suggestions=suggestions,
                    )
                suggestions = ["Continue", "Cancel form"] if language == 'en' else ["Continuar", "Cancelar formulario"]
                return ConverseResponse(
                    message=sanitize_speech(skip_result["message"]),
                    action=ActionResponse(type='info'),
                    results=[{"ui_actions": [{"type": "ui.clearInput", "payload": {"target": "syllabus"}}]}],
                    suggestions=suggestions,
                )

        # Handle META type (hesitation, thinking)
        if input_classification.input_type == InputType.META:
            hesitation_msg = generate_voice_response(
                "User is hesitating about using the generated syllabus. Tell them they can say 'yes' to use it, 'no' to edit, or 'skip' to move on.",
                language=language
            )
            suggestions = ["Yes, use it", "No, edit", "Skip", "Cancel"] if language == 'en' else ["Sí, usar", "No, editar", "Saltar", "Cancelar"]
            return ConverseResponse(
                message=sanitize_speech(hesitation_msg),
                action=ActionResponse(type='info'),
                suggestions=suggestions,
            )

        # Handle CONFIRM type
        if input_classification.input_type == InputType.CONFIRM:
            if input_classification.confirm_value == "yes":
                # Accept the generated syllabus and move to next field
                conv_context.collected_values["syllabus"] = conv_context.generated_syllabus
                conv_context.current_field_index += 1
                conv_context.generated_syllabus = ""
                conv_context.state = ConversationState.AWAITING_FIELD_INPUT
                conversation_manager.save_context(request.user_id, conv_context)

                next_field = conversation_manager.get_current_field(request.user_id)
                if next_field:
                    if next_field.voice_id == "learning-objectives":
                        conv_context.state = ConversationState.AWAITING_OBJECTIVES_GENERATION_CONFIRM
                        conversation_manager.save_context(request.user_id, conv_context)
                        saved_msg = generate_voice_response(
                            "Syllabus saved. Now asking about learning objectives - offer to generate them based on the syllabus.",
                            language=language
                        )
                        suggestions = ["Yes, generate them", "No, I'll dictate", "Skip"] if language == 'en' else ["Sí, generar", "No, dictaré", "Saltar"]
                        return ConverseResponse(
                            message=sanitize_speech(saved_msg),
                            action=ActionResponse(type='info'),
                            suggestions=suggestions,
                        )
                    saved_msg = generate_voice_response(
                        f"Syllabus saved. Now asking for: {next_field.prompt.get(language, next_field.prompt.get('en', 'the next field'))}",
                        language=language
                    )
                    suggestions = ["Skip", "Cancel form"] if language == 'en' else ["Saltar", "Cancelar formulario"]
                    return ConverseResponse(
                        message=sanitize_speech(saved_msg),
                        action=ActionResponse(type='info'),
                        suggestions=suggestions,
                    )
                else:
                    ready_msg = generate_voice_response(
                        "Syllabus saved. Form is ready to submit. Ask user if they want to create the course now.",
                        language=language
                    )
                    suggestions = ["Yes, create course", "No, cancel"] if language == 'en' else ["Sí, crear curso", "No, cancelar"]
                    return ConverseResponse(
                        message=sanitize_speech(ready_msg),
                        action=ActionResponse(type='info'),
                        suggestions=suggestions,
                    )
            else:
                # User said no - they want to edit
                conv_context.state = ConversationState.AWAITING_FIELD_INPUT
                conversation_manager.save_context(request.user_id, conv_context)
                edit_msg = generate_voice_response(
                    "Syllabus is in the form. Tell user they can edit it manually or dictate a new one. Say 'done' when finished or 'skip' to move on.",
                    language=language
                )
                suggestions = ["Skip", "Cancel form"] if language == 'en' else ["Saltar", "Cancelar formulario"]
                return ConverseResponse(
                    message=sanitize_speech(edit_msg),
                    action=ActionResponse(type='info'),
                    suggestions=suggestions,
                )

        # Handle CONTENT type - user is providing new syllabus content
        if input_classification.input_type == InputType.CONTENT:
            # User is dictating new syllabus content - replace the generated one
            conv_context.state = ConversationState.AWAITING_FIELD_INPUT
            conv_context.generated_syllabus = ""
            conversation_manager.save_context(request.user_id, conv_context)
            result = conversation_manager.record_field_value(request.user_id, transcript)
            ui_actions = []
            if result.get("field_to_fill"):
                sanitized_value = result["all_values"].get(result["field_to_fill"].voice_id, transcript)
                ui_actions.append({"type": "ui.fillInput", "payload": {"target": result["field_to_fill"].voice_id, "value": sanitized_value}})
            return ConverseResponse(
                message=sanitize_speech(result.get("next_prompt", "Got it! What's next?")),
                action=ActionResponse(type='execute', executed=True),
                results=[{"ui_actions": ui_actions, "all_values": result.get("all_values", {})}],
                suggestions=["Continue", "Skip", "Cancel"],
            )

        # Fallback - re-prompt
        fallback_msg = generate_voice_response(
            "Ask user to confirm using the generated syllabus. Options: 'yes' to use it, 'no' to edit, 'skip' to move on, 'cancel' to exit.",
            language=language
        )
        suggestions = ["Yes, use it", "No, edit", "Skip", "Cancel"] if language == 'en' else ["Sí, usar", "No, editar", "Saltar", "Cancelar"]
        return ConverseResponse(
            message=sanitize_speech(fallback_msg),
            action=ActionResponse(type='info'),
            suggestions=suggestions,
        )

    # --- Handle AI objectives generation confirmation state ---
    if conv_context.state == ConversationState.AWAITING_OBJECTIVES_GENERATION_CONFIRM:
        # Use LLM-based input classification
        input_classification = classify_form_input(
            user_input=transcript,
            field_prompt="Would you like me to generate learning objectives?",
            field_type="objectives_generation_confirm",
            workflow_name="create_course"
        )

        import logging
        logger = logging.getLogger(__name__)
        logger.info(f"[ObjectivesConfirm] Input: '{transcript}' -> Type: {input_classification.input_type}, Command: {input_classification.command}, Confirm: {input_classification.confirm_value}")

        # Handle COMMAND type (cancel, skip, etc.)
        if input_classification.input_type == InputType.COMMAND:
            command = input_classification.command or "cancel"
            if command == "cancel":
                conversation_manager.cancel_form(request.user_id)
                cancel_msg = generate_voice_response(
                    "Course creation cancelled. Acknowledge briefly.",
                    language=language
                )
                return ConverseResponse(
                    message=sanitize_speech(cancel_msg),
                    action=ActionResponse(type='info'),
                    suggestions=get_page_suggestions(request.current_page, language),
                )
            elif command == "skip":
                skip_result = conversation_manager.skip_current_field(request.user_id)
                suggestions = ["Continue", "Cancel form"] if language == 'en' else ["Continuar", "Cancelar formulario"]
                return ConverseResponse(
                    message=sanitize_speech(skip_result["message"]),
                    action=ActionResponse(type='info'),
                    suggestions=suggestions,
                )

        # Handle META type (hesitation, thinking)
        if input_classification.input_type == InputType.META:
            hesitation_msg = generate_voice_response(
                "User is hesitating about objectives generation. Tell them they can say 'yes' to generate, 'no' to dictate, or 'skip' to move on.",
                language=language
            )
            suggestions = ["Yes, generate them", "No, I'll dictate", "Skip", "Cancel"] if language == 'en' else ["Sí, generar", "No, dictaré", "Saltar", "Cancelar"]
            return ConverseResponse(
                message=sanitize_speech(hesitation_msg),
                action=ActionResponse(type='info'),
                suggestions=suggestions,
            )

        # Handle CONFIRM type
        if input_classification.input_type == InputType.CONFIRM:
            if input_classification.confirm_value == "yes":
                # Generate objectives using AI
                course_name = conv_context.course_name_for_generation or "the course"
                syllabus = conv_context.collected_values.get("syllabus", "")

                try:
                    gen_result = _execute_tool(db, 'generate_objectives', {"course_name": course_name, "syllabus": syllabus})
                except Exception as e:
                    logging.getLogger(__name__).error(f"Objectives generation error: {e}")
                    gen_result = None

                if gen_result and gen_result.get("success") and gen_result.get("objectives"):
                    objectives = gen_result["objectives"]
                    objectives_text = "\n".join(f"- {obj}" for obj in objectives)

                    conv_context.generated_objectives = objectives
                    conv_context.state = ConversationState.AWAITING_OBJECTIVES_REVIEW
                    conversation_manager.save_context(request.user_id, conv_context)

                    preview = ", ".join(objectives[:3])
                    if len(objectives) > 3:
                        preview += f", and {len(objectives) - 3} more"

                    return ConverseResponse(
                        message=sanitize_speech(f"I've generated {len(objectives)} learning objectives. Here are the first few: {preview}. Should I use these objectives?"),
                        action=ActionResponse(type='info'),
                        results=[{"ui_actions": [{"type": "ui.fillInput", "payload": {"target": "learning-objectives", "value": objectives_text}}]}],
                        suggestions=["Yes, use them", "No, let me edit", "Skip objectives"],
                    )
                else:
                    conv_context.state = ConversationState.AWAITING_FIELD_INPUT
                    conversation_manager.save_context(request.user_id, conv_context)
                    error_msg = gen_result.get("error", "Generation failed") if gen_result else "Tool not available"
                    return ConverseResponse(
                        message=sanitize_speech(f"Sorry, I couldn't generate objectives: {error_msg}. Please dictate them or say 'skip'."),
                        action=ActionResponse(type='info'),
                        suggestions=["Skip", "Cancel form"],
                    )
            else:
                # User said no - they want to dictate
                conv_context.state = ConversationState.AWAITING_FIELD_INPUT
                conversation_manager.save_context(request.user_id, conv_context)
                dictate_msg = generate_voice_response(
                    "User wants to dictate the learning objectives. Ask them to start dictating.",
                    language=language
                )
                suggestions = ["Skip", "Cancel form"] if language == 'en' else ["Saltar", "Cancelar formulario"]
                return ConverseResponse(
                    message=sanitize_speech(dictate_msg),
                    action=ActionResponse(type='info'),
                    suggestions=suggestions,
                )

        # Handle CONTENT type - user is providing objectives content directly
        if input_classification.input_type == InputType.CONTENT:
            conv_context.state = ConversationState.AWAITING_FIELD_INPUT
            conversation_manager.save_context(request.user_id, conv_context)
            result = conversation_manager.record_field_value(request.user_id, transcript)
            ui_actions = []
            if result.get("field_to_fill"):
                sanitized_value = result["all_values"].get(result["field_to_fill"].voice_id, transcript)
                ui_actions.append({"type": "ui.fillInput", "payload": {"target": result["field_to_fill"].voice_id, "value": sanitized_value}})
            suggestions = ["Continue", "Skip", "Cancel"] if language == 'en' else ["Continuar", "Saltar", "Cancelar"]
            return ConverseResponse(
                message=sanitize_speech(result.get("next_prompt", "Got it! What's next?")),
                action=ActionResponse(type='execute', executed=True),
                results=[{"ui_actions": ui_actions, "all_values": result.get("all_values", {})}],
                suggestions=suggestions,
            )

        # Fallback - re-prompt
        fallback_msg = generate_voice_response(
            "Ask user if they want to generate learning objectives with AI, dictate them, skip, or cancel.",
            language=language
        )
        suggestions = ["Yes, generate them", "No, I'll dictate", "Skip", "Cancel"] if language == 'en' else ["Sí, generar", "No, dictaré", "Saltar", "Cancelar"]
        return ConverseResponse(
            message=sanitize_speech(fallback_msg),
            action=ActionResponse(type='info'),
            suggestions=suggestions,
        )

    # --- Handle objectives review state ---
    if conv_context.state == ConversationState.AWAITING_OBJECTIVES_REVIEW:
        # Use LLM-based input classification
        input_classification = classify_form_input(
            user_input=transcript,
            field_prompt="Should I use these generated learning objectives?",
            field_type="objectives_review",
            workflow_name="create_course"
        )

        import logging
        logger = logging.getLogger(__name__)
        logger.info(f"[ObjectivesReview] Input: '{transcript}' -> Type: {input_classification.input_type}, Command: {input_classification.command}, Confirm: {input_classification.confirm_value}")

        # Handle COMMAND type
        if input_classification.input_type == InputType.COMMAND:
            command = input_classification.command or "cancel"
            if command == "cancel":
                conversation_manager.cancel_form(request.user_id)
                cancel_msg = generate_voice_response(
                    "Course creation cancelled. Acknowledge briefly.",
                    language=language
                )
                return ConverseResponse(
                    message=sanitize_speech(cancel_msg),
                    action=ActionResponse(type='info'),
                    suggestions=get_page_suggestions(request.current_page, language),
                )
            elif command == "skip":
                skip_result = conversation_manager.skip_current_field(request.user_id)
                conv_context.generated_objectives = []
                conversation_manager.save_context(request.user_id, conv_context)
                suggestions = ["Continue", "Cancel form"] if language == 'en' else ["Continuar", "Cancelar formulario"]
                return ConverseResponse(
                    message=sanitize_speech(skip_result["message"]),
                    action=ActionResponse(type='info'),
                    results=[{"ui_actions": [{"type": "ui.clearInput", "payload": {"target": "learning-objectives"}}]}],
                    suggestions=suggestions,
                )

        # Handle META type (hesitation)
        if input_classification.input_type == InputType.META:
            hesitation_msg = generate_voice_response(
                "User is hesitating about using the generated objectives. Tell them they can say 'yes' to use them, 'no' to edit, or 'skip' to move on.",
                language=language
            )
            suggestions = ["Yes, use them", "No, edit", "Skip", "Cancel"] if language == 'en' else ["Sí, usar", "No, editar", "Saltar", "Cancelar"]
            return ConverseResponse(
                message=sanitize_speech(hesitation_msg),
                action=ActionResponse(type='info'),
                suggestions=suggestions,
            )

        # Handle CONFIRM type
        if input_classification.input_type == InputType.CONFIRM:
            if input_classification.confirm_value == "yes":
                # Accept the generated objectives
                objectives_text = "\n".join(f"- {obj}" for obj in conv_context.generated_objectives)
                conv_context.collected_values["learning-objectives"] = objectives_text
                conv_context.current_field_index += 1
                conv_context.generated_objectives = []
                conv_context.state = ConversationState.AWAITING_CONFIRMATION
                conv_context.pending_action = "ui_click_button"
                conv_context.pending_action_data = {
                    "voice_id": "create-course-with-plans",
                    "form_name": "create_course",
                }
                conversation_manager.save_context(request.user_id, conv_context)

                ready_msg = generate_voice_response(
                    "Objectives saved. Course is ready to create. Ask user if they want to create it now and generate session plans.",
                    language=language
                )
                suggestions = ["Yes, create it", "No, cancel"] if language == 'en' else ["Sí, crear", "No, cancelar"]
                return ConverseResponse(
                    message=sanitize_speech(ready_msg),
                    action=ActionResponse(type='info'),
                    suggestions=suggestions,
                )
            else:
                # User said no - they want to edit
                conv_context.state = ConversationState.AWAITING_FIELD_INPUT
                conversation_manager.save_context(request.user_id, conv_context)
                edit_msg = generate_voice_response(
                    "Objectives are in the form. Tell user they can edit them manually or dictate new ones. Say 'done' when finished or 'skip' to move on.",
                    language=language
                )
                suggestions = ["Skip", "Cancel form"] if language == 'en' else ["Saltar", "Cancelar formulario"]
                return ConverseResponse(
                    message=sanitize_speech(edit_msg),
                    action=ActionResponse(type='info'),
                    suggestions=suggestions,
                )

        # Handle CONTENT type - user is providing new objectives directly
        if input_classification.input_type == InputType.CONTENT:
            conv_context.state = ConversationState.AWAITING_FIELD_INPUT
            conv_context.generated_objectives = []
            conversation_manager.save_context(request.user_id, conv_context)
            result = conversation_manager.record_field_value(request.user_id, transcript)
            ui_actions = []
            if result.get("field_to_fill"):
                sanitized_value = result["all_values"].get(result["field_to_fill"].voice_id, transcript)
                ui_actions.append({"type": "ui.fillInput", "payload": {"target": result["field_to_fill"].voice_id, "value": sanitized_value}})
            return ConverseResponse(
                message=sanitize_speech(result.get("next_prompt", "Got it! What's next?")),
                action=ActionResponse(type='execute', executed=True),
                results=[{"ui_actions": ui_actions, "all_values": result.get("all_values", {})}],
                suggestions=["Continue", "Skip", "Cancel"],
            )

        # Fallback - re-prompt
        fallback_msg = generate_voice_response(
            "Ask user to confirm using the generated objectives. Options: 'yes' to use them, 'no' to edit, 'skip' to move on, 'cancel' to exit.",
            language=language
        )
        suggestions = ["Yes, use them", "No, edit", "Skip", "Cancel"] if language == 'en' else ["Sí, usar", "No, editar", "Saltar", "Cancelar"]
        return ConverseResponse(
            message=sanitize_speech(fallback_msg),
            action=ActionResponse(type='info'),
            suggestions=suggestions,
        )

    # --- Handle AI session plan generation confirmation state ---
    if conv_context.state == ConversationState.AWAITING_SESSION_PLAN_GENERATION_CONFIRM:
        # Use LLM-based input classification
        input_classification = classify_form_input(
            user_input=transcript,
            field_prompt="Would you like me to generate a session plan with discussion prompts and a case study?",
            field_type="session_plan_generation_confirm",
            workflow_name="create_session"
        )

        import logging
        logger = logging.getLogger(__name__)
        logger.info(f"[SessionPlanConfirm] Input: '{transcript}' -> Type: {input_classification.input_type}, Command: {input_classification.command}, Confirm: {input_classification.confirm_value}")

        # Handle COMMAND type
        if input_classification.input_type == InputType.COMMAND:
            command = input_classification.command or "cancel"
            if command == "cancel":
                conversation_manager.cancel_form(request.user_id)
                cancel_msg = generate_voice_response(
                    "Session creation cancelled. Acknowledge briefly.",
                    language=language
                )
                return ConverseResponse(
                    message=sanitize_speech(cancel_msg),
                    action=ActionResponse(type='info'),
                    suggestions=get_page_suggestions(request.current_page, language),
                )
            elif command == "skip":
                skip_result = conversation_manager.skip_current_field(request.user_id)
                suggestions = ["Create session", "Cancel form"] if language == 'en' else ["Crear sesión", "Cancelar formulario"]
                return ConverseResponse(
                    message=sanitize_speech(skip_result["message"]),
                    action=ActionResponse(type='info'),
                    suggestions=suggestions,
                )

        # Handle META type
        if input_classification.input_type == InputType.META:
            hesitation_msg = generate_voice_response(
                "User is hesitating about session plan generation. Tell them they can say 'yes' to generate, 'no' to dictate, or 'skip' to move on.",
                language=language
            )
            suggestions = ["Yes, generate it", "No, I'll dictate", "Skip", "Cancel"] if language == 'en' else ["Sí, generar", "No, dictaré", "Saltar", "Cancelar"]
            return ConverseResponse(
                message=sanitize_speech(hesitation_msg),
                action=ActionResponse(type='info'),
                suggestions=suggestions,
            )

        # Handle CONFIRM type
        if input_classification.input_type == InputType.CONFIRM:
            if input_classification.confirm_value == "yes":
                # Generate session plan using AI
                session_topic = conv_context.collected_values.get("input-session-title", "the session")
                course_id = context_store.get_context(request.user_id).get("active_course_id") if request.user_id else None
                course_name = "the course"
                syllabus = None

                if course_id and db:
                    course = db.query(Course).filter(Course.id == course_id).first()
                    if course:
                        course_name = course.title
                        syllabus = course.syllabus_text

                try:
                    gen_result = _execute_tool(db, 'generate_session_plan', {
                        "course_name": course_name,
                        "session_topic": session_topic,
                        "syllabus": syllabus,
                    })
                except Exception as e:
                    logging.getLogger(__name__).error(f"Session plan generation error: {e}")
                    gen_result = None

                if gen_result and gen_result.get("success") and gen_result.get("plan"):
                    plan = gen_result["plan"]
                    description_parts = []
                    if plan.get("goals"):
                        description_parts.append("Learning Goals:\n" + "\n".join(f"- {g}" for g in plan["goals"]))
                    if plan.get("key_concepts"):
                        description_parts.append("\nKey Concepts:\n" + "\n".join(f"- {c}" for c in plan["key_concepts"]))
                    if plan.get("discussion_prompts"):
                        description_parts.append("\nDiscussion Prompts:\n" + "\n".join(f"- {p}" for p in plan["discussion_prompts"]))
                    if plan.get("case_prompt"):
                        description_parts.append(f"\nCase Study:\n{plan['case_prompt']}")

                    description = "\n".join(description_parts)
                    conv_context.generated_session_plan = plan
                    conv_context.state = ConversationState.AWAITING_SESSION_PLAN_REVIEW
                    conversation_manager.save_context(request.user_id, conv_context)

                    prompt_count = len(plan.get("discussion_prompts", []))
                    summary = f"I've generated a session plan for '{session_topic}' with {prompt_count} discussion prompts"
                    if plan.get("case_prompt"):
                        summary += " and a case study"
                    summary += ". Should I use this plan?"

                    return ConverseResponse(
                        message=sanitize_speech(summary),
                        action=ActionResponse(type='info'),
                        results=[{"ui_actions": [{"type": "ui.fillInput", "payload": {"target": "textarea-session-description", "value": description}}]}],
                        suggestions=["Yes, use it", "No, let me edit", "Skip"],
                    )
                else:
                    conv_context.state = ConversationState.AWAITING_FIELD_INPUT
                    conversation_manager.save_context(request.user_id, conv_context)
                    error_msg = gen_result.get("error", "Generation failed") if gen_result else "Tool not available"
                    return ConverseResponse(
                        message=sanitize_speech(f"Sorry, I couldn't generate the session plan: {error_msg}. Please dictate a description or say 'skip'."),
                        action=ActionResponse(type='info'),
                        suggestions=["Skip", "Cancel form"],
                    )
            else:
                # User said no - they want to dictate
                conv_context.state = ConversationState.AWAITING_FIELD_INPUT
                conversation_manager.save_context(request.user_id, conv_context)
                dictate_msg = generate_voice_response(
                    "User wants to dictate the session description. Ask them to start dictating.",
                    language=language
                )
                suggestions = ["Skip", "Cancel form"] if language == 'en' else ["Saltar", "Cancelar formulario"]
                return ConverseResponse(
                    message=sanitize_speech(dictate_msg),
                    action=ActionResponse(type='info'),
                    suggestions=suggestions,
                )

        # Handle CONTENT type - user is providing description directly
        if input_classification.input_type == InputType.CONTENT:
            conv_context.state = ConversationState.AWAITING_FIELD_INPUT
            conversation_manager.save_context(request.user_id, conv_context)
            result = conversation_manager.record_field_value(request.user_id, transcript)
            ui_actions = []
            if result.get("field_to_fill"):
                sanitized_value = result["all_values"].get(result["field_to_fill"].voice_id, transcript)
                ui_actions.append({"type": "ui.fillInput", "payload": {"target": result["field_to_fill"].voice_id, "value": sanitized_value}})
            suggestions = ["Continue", "Skip", "Cancel"] if language == 'en' else ["Continuar", "Saltar", "Cancelar"]
            return ConverseResponse(
                message=sanitize_speech(result.get("next_prompt", "Got it! What's next?")),
                action=ActionResponse(type='execute', executed=True),
                results=[{"ui_actions": ui_actions, "all_values": result.get("all_values", {})}],
                suggestions=suggestions,
            )

        # Fallback - re-prompt
        fallback_msg = generate_voice_response(
            "Ask user if they want to generate a session plan with AI, dictate it, skip, or cancel.",
            language=language
        )
        suggestions = ["Yes, generate it", "No, I'll dictate", "Skip", "Cancel"] if language == 'en' else ["Sí, generar", "No, dictaré", "Saltar", "Cancelar"]
        return ConverseResponse(
            message=sanitize_speech(fallback_msg),
            action=ActionResponse(type='info'),
            suggestions=suggestions,
        )

    # --- Handle session plan review state ---
    if conv_context.state == ConversationState.AWAITING_SESSION_PLAN_REVIEW:
        # Use LLM-based input classification
        input_classification = classify_form_input(
            user_input=transcript,
            field_prompt="Should I use this generated session plan?",
            field_type="session_plan_review",
            workflow_name="create_session"
        )

        import logging
        logger = logging.getLogger(__name__)
        logger.info(f"[SessionPlanReview] Input: '{transcript}' -> Type: {input_classification.input_type}, Command: {input_classification.command}, Confirm: {input_classification.confirm_value}")

        # Handle COMMAND type
        if input_classification.input_type == InputType.COMMAND:
            command = input_classification.command or "cancel"
            if command == "cancel":
                conversation_manager.cancel_form(request.user_id)
                if language == 'es':
                    cancel_msg = "Entendido. He cancelado la creación de la sesión."
                else:
                    cancel_msg = "Understood. I've cancelled session creation."
                return ConverseResponse(
                    message=sanitize_speech(cancel_msg),
                    action=ActionResponse(type='info'),
                    suggestions=get_page_suggestions(request.current_page, language),
                )
            elif command == "skip":
                skip_result = conversation_manager.skip_current_field(request.user_id)
                conv_context.generated_session_plan = {}
                conversation_manager.save_context(request.user_id, conv_context)
                return ConverseResponse(
                    message=sanitize_speech(skip_result["message"]),
                    action=ActionResponse(type='info'),
                    results=[{"ui_actions": [{"type": "ui.clearInput", "payload": {"target": "textarea-session-description"}}]}],
                    suggestions=["Create session", "Cancel form"],
                )

        # Handle META type
        if input_classification.input_type == InputType.META:
            if language == 'es':
                hesitation_msg = "Tómate tu tiempo. Di 'sí' para usar este plan, 'no' para editarlo, o 'saltar' para continuar."
            else:
                hesitation_msg = "Take your time. Say 'yes' to use this plan, 'no' to edit it, or 'skip' to move on."
            return ConverseResponse(
                message=sanitize_speech(hesitation_msg),
                action=ActionResponse(type='info'),
                suggestions=["Yes, use it", "No, edit", "Skip", "Cancel"],
            )

        # Handle CONFIRM type
        if input_classification.input_type == InputType.CONFIRM:
            if input_classification.confirm_value == "yes":
                # Accept the generated plan
                plan = conv_context.generated_session_plan
                description_parts = []
                if plan.get("goals"):
                    description_parts.append("Learning Goals:\n" + "\n".join(f"- {g}" for g in plan["goals"]))
                if plan.get("key_concepts"):
                    description_parts.append("\nKey Concepts:\n" + "\n".join(f"- {c}" for c in plan["key_concepts"]))
                if plan.get("discussion_prompts"):
                    description_parts.append("\nDiscussion Prompts:\n" + "\n".join(f"- {p}" for p in plan["discussion_prompts"]))
                if plan.get("case_prompt"):
                    description_parts.append(f"\nCase Study:\n{plan['case_prompt']}")
                description = "\n".join(description_parts)

                conv_context.collected_values["textarea-session-description"] = description
                conv_context.current_field_index += 1
                conv_context.generated_session_plan = {}
                conv_context.state = ConversationState.AWAITING_CONFIRMATION
                conv_context.pending_action = "ui_click_button"
                conv_context.pending_action_data = {
                    "voice_id": "create-session",
                    "form_name": "create_session",
                }
                conversation_manager.save_context(request.user_id, conv_context)

                ready_msg = generate_voice_response(
                    "Session plan saved. Session is ready to create. Ask user if they want to create it now.",
                    language=language
                )
                suggestions = ["Yes, create it", "No, cancel"] if language == 'en' else ["Sí, crear", "No, cancelar"]
                return ConverseResponse(
                    message=sanitize_speech(ready_msg),
                    action=ActionResponse(type='info'),
                    suggestions=suggestions,
                )
            else:
                # User said no - they want to edit
                conv_context.state = ConversationState.AWAITING_FIELD_INPUT
                conversation_manager.save_context(request.user_id, conv_context)
                edit_msg = generate_voice_response(
                    "Session plan is in the form. Tell user they can edit it manually or dictate a new description. Say 'done' when finished or 'skip'.",
                    language=language
                )
                suggestions = ["Skip", "Cancel form"] if language == 'en' else ["Saltar", "Cancelar formulario"]
                return ConverseResponse(
                    message=sanitize_speech(edit_msg),
                    action=ActionResponse(type='info'),
                    suggestions=suggestions,
                )

        # Handle CONTENT type - user is providing new content directly
        if input_classification.input_type == InputType.CONTENT:
            conv_context.state = ConversationState.AWAITING_FIELD_INPUT
            conv_context.generated_session_plan = {}
            conversation_manager.save_context(request.user_id, conv_context)
            result = conversation_manager.record_field_value(request.user_id, transcript)
            ui_actions = []
            if result.get("field_to_fill"):
                sanitized_value = result["all_values"].get(result["field_to_fill"].voice_id, transcript)
                ui_actions.append({"type": "ui.fillInput", "payload": {"target": result["field_to_fill"].voice_id, "value": sanitized_value}})
            suggestions = ["Continue", "Skip", "Cancel"] if language == 'en' else ["Continuar", "Saltar", "Cancelar"]
            return ConverseResponse(
                message=sanitize_speech(result.get("next_prompt", "Got it! What's next?")),
                action=ActionResponse(type='execute', executed=True),
                results=[{"ui_actions": ui_actions, "all_values": result.get("all_values", {})}],
                suggestions=suggestions,
            )

        # Fallback - re-prompt
        fallback_msg = generate_voice_response(
            "Ask user to confirm using the generated session plan. Options: 'yes' to use it, 'no' to edit, 'skip' to move on, 'cancel' to exit.",
            language=language
        )
        suggestions = ["Yes, use it", "No, edit", "Skip", "Cancel"] if language == 'en' else ["Sí, usar", "No, editar", "Saltar", "Cancelar"]
        return ConverseResponse(
            message=sanitize_speech(fallback_msg),
            action=ActionResponse(type='info'),
            suggestions=suggestions,
        )

    # =========================================================================
    # INTENT DETECTION: LLM-first or Regex-based (configurable)
    # =========================================================================

    # Fast-path workspace search intent so this works reliably even if the LLM
    # classifies it as a generic query.
    search_query = _extract_search_query(transcript)
    if search_query:
        search_result = await execute_action(
            'ui_search_navigate',
            request.user_id,
            request.current_page,
            db,
            transcript,
            {"searchQuery": search_query},
            language,
        )
        if search_result:
            return ConverseResponse(
                message=sanitize_speech(f"Searching for {search_query}."),
                action=ActionResponse(type='execute', executed=True),
                results=[search_result],
                suggestions=["Open notifications", "Switch tab", "Go back"],
            )

    if USE_LLM_INTENT_DETECTION:
        # =====================================================================
        # LLM-FIRST INTENT DETECTION (Natural Language Understanding)
        # =====================================================================
        # This approach understands user intent regardless of exact phrasing.
        # "I want to go to the course page" works just as well as "go to courses"

        # Build page context for smarter decisions (Phase 2: rich context from frontend)
        page_context = build_page_context(
            current_page=request.current_page,
            available_tabs=request.available_tabs,
            available_buttons=request.available_buttons,
            active_course_name=request.active_course_name,
            active_session_name=request.active_session_name,
            is_session_live=request.is_session_live,
            copilot_active=request.copilot_active,
        )

        # Classify intent using LLM (all confirmations go through LLM)
        print(f"🎯 [VOICE] Classifying intent for: '{transcript}'")
        print(f"🎯 [VOICE] Page context: page={request.current_page}, tabs={request.available_tabs}, buttons={request.available_buttons}")
        intent = classify_intent(transcript, page_context)
        print(f"🎯 [VOICE] LLM classification: category={intent.category}, action={intent.action}, confidence={intent.confidence}")
        print(f"🎯 [VOICE] Parameters: {intent.parameters}")

        # Convert to legacy format for compatibility with existing action execution
        intent_result = intent_to_legacy_format(intent)
        print(f"🎯 [VOICE] Legacy format: type={intent_result.get('type')}, value={intent_result.get('value')}")

        # Handle low confidence - ask for intelligent clarification (no regex fallback)
        # Phase 1: Trust LLM fully, provide helpful context-aware suggestions
        if intent.confidence < LLM_INTENT_CONFIDENCE_THRESHOLD or intent.clarification_needed:
            # Build helpful suggestions based on what the LLM partially understood
            suggestions = []
            if intent.category == IntentCategory.NAVIGATE:
                suggestions = ["Go to courses", "Go to sessions", "Go to forum"] if language == 'en' else ["Ir a cursos", "Ir a sesiones", "Ir a foro"]
            elif intent.category == IntentCategory.CREATE:
                suggestions = ["Create a course", "Create a session", "Create a poll"] if language == 'en' else ["Crear un curso", "Crear una sesion", "Crear una encuesta"]
            elif intent.category == IntentCategory.QUERY:
                suggestions = ["Show my courses", "Who needs help?", "Class status"] if language == 'en' else ["Mostrar mis cursos", "Quien necesita ayuda?", "Estado de la clase"]
            else:
                suggestions = get_page_suggestions(request.current_page, language)

            # Provide context-aware clarification message
            if intent.clarification_message:
                clarification_msg = intent.clarification_message
            elif language == 'es':
                clarification_msg = f"Escuche '{transcript}'. No estoy completamente seguro de lo que te gustaria hacer. ¿Podrias ser mas especifico?"
            else:
                clarification_msg = f"I heard '{transcript}'. I'm not quite sure what you'd like to do. Could you be more specific?"

            return ConverseResponse(
                message=sanitize_speech(clarification_msg),
                action=ActionResponse(type='info'),
                suggestions=suggestions,
            )

        # Handle navigation intent
        if intent_result["type"] == "navigate":
            nav_path = intent_result["value"]
            print(f"✅ [VOICE] NAVIGATION INTENT MATCHED! Navigating to: {nav_path}")
            message = sanitize_speech(generate_conversational_response('navigate', nav_path, language=language))
            # Generate toast message in correct language
            page_name = nav_path.strip('/').replace('-', ' ').title()
            toast_msg = f"Navegando a {page_name}" if language == 'es' else f"Navigating to {page_name}"
            response_data = {
                "message": message,
                "action": {"type": "navigate", "target": nav_path},
                "results": [{
                    "ui_actions": [
                        {"type": "ui.navigate", "payload": {"path": nav_path}},
                        {"type": "ui.toast", "payload": {"message": toast_msg, "type": "info"}},
                    ]
                }],
                "suggestions": get_page_suggestions(nav_path, language)
            }
            print(f"✅ [VOICE] FULL RESPONSE DATA: {response_data}")
            return ConverseResponse(
                message=message,
                action=ActionResponse(type='navigate', target=nav_path),
                results=[{
                    "ui_actions": [
                        {"type": "ui.navigate", "payload": {"path": nav_path}},
                        {"type": "ui.toast", "payload": {"message": toast_msg, "type": "info"}},
                    ]
                }],
                suggestions=get_page_suggestions(nav_path, language)
            )

        # Handle action intent (UI actions, queries, creates, controls)
        if intent_result["type"] == "action":
            action = intent_result["value"]

            # Phase 2.5: Check if auto-navigation is needed for cross-page commands
            nav_target = get_auto_navigation(action, request.current_page)
            if nav_target:
                # User is on wrong page - navigate first, then switch to correct tab
                # Check if this action also requires a specific tab
                target_tab = ACTION_TARGET_TABS.get(action)

                # Build UI actions - always navigate, optionally switch tab
                ui_actions = [
                    {"type": "ui.navigate", "payload": {"path": nav_target}},
                ]
                if target_tab:
                    ui_actions.append({"type": "ui.switchTab", "payload": {"tabName": target_tab, "target": f"tab-{target_tab}"}})

                # Use LLM to generate navigation message in correct language
                action_name = action.replace("_", " ").replace("flow", "").strip()
                tab_context = f" and switching to {target_tab} tab" if target_tab else ""
                nav_message = generate_voice_response(
                    f"Navigating to {nav_target}{tab_context} to help user {action_name}. Confirm briefly.",
                    language=language
                )

                # Store the pending action so it executes after navigation completes
                conversation_manager.set_pending_action(
                    request.user_id,
                    action=action,
                    parameters=intent_result.get("parameters"),
                    transcript=transcript,
                )

                return ConverseResponse(
                    message=sanitize_speech(nav_message),
                    action=ActionResponse(type='navigate', target=nav_target),
                    results=[{
                        "ui_actions": ui_actions,
                        "pending_action": {
                            "action": action,
                            "parameters": intent_result.get("parameters"),
                        }
                    }],
                    suggestions=[],  # No suggestions during auto-navigation
                )

            # Pass extracted parameters to execute_action via transcript context
            # The LLM has already extracted tab names, button names, etc.
            result = await execute_action(action, request.user_id, request.current_page, db, transcript, intent_result.get("parameters"), language)
            results_list = [result] if result and not isinstance(result, list) else result
            return ConverseResponse(
                message=sanitize_speech(generate_conversational_response(
                    'execute',
                    action,
                    results=result,
                    context=request.context,
                    current_page=request.current_page,
                    language=language,
                )),
                action=ActionResponse(type='execute', executed=True),
                results=results_list,
                suggestions=get_action_suggestions(action, language),
            )

        # Handle confirmation intent (yes/no/cancel/skip)
        # This is typically handled by conversation state handlers above,
        # but if we reach here, provide a helpful response
        if intent_result["type"] == "confirm":
            confirm_type = intent_result["value"]
            if confirm_type == "yes":
                ready_msg = generate_voice_response(
                    "User said yes but no action pending. Say ready to help and ask what they want to confirm.",
                    language=language
                )
                return ConverseResponse(
                    message=sanitize_speech(ready_msg),
                    action=ActionResponse(type='info'),
                    suggestions=get_page_suggestions(request.current_page, language),
                )
            elif confirm_type in ["no", "cancel"]:
                cancel_msg = generate_voice_response(
                    "Cancelled. Ask what else user would like to do.",
                    language=language
                )
                return ConverseResponse(
                    message=sanitize_speech(cancel_msg),
                    action=ActionResponse(type='info'),
                    suggestions=get_page_suggestions(request.current_page, language),
                )

        # Handle dictation intent
        if intent_result["type"] == "dictate":
            # User is providing content - this should be handled by conversation state
            no_form_msg = generate_voice_response(
                "Heard user's input but no form is active. Tell them to start a form or select an input field first.",
                language=language
            )
            suggestions = ["Create course", "Create session", "Post to forum"] if language == 'en' else ["Crear curso", "Crear sesión", "Publicar en foro"]
            return ConverseResponse(
                message=sanitize_speech(no_form_msg),
                action=ActionResponse(type='info'),
                suggestions=suggestions,
            )

        # Fallback for unclear intent
        print(f"⚠️ [VOICE] FALLBACK: No intent matched for '{transcript}' - type={intent_result.get('type')}, value={intent_result.get('value')}")
        fallback_message = generate_fallback_response(transcript, request.context, request.current_page, language)

    # NOTE: Legacy regex-based intent detection (else branch) has been removed in Phase 1 refactor.
    # The system now uses LLM-only intent detection for better natural language understanding.
    # USE_LLM_INTENT_DETECTION is always True - regex patterns are deprecated.

    # Get page-specific suggestions instead of generic ones
    page_suggestions = get_page_suggestions(request.current_page, language)

    return ConverseResponse(
        message=sanitize_speech(fallback_message),
        action=ActionResponse(type='info'),
        suggestions=page_suggestions,
    )


def _parse_ids_from_path(current_page: Optional[str]) -> Tuple[Optional[int], Optional[int]]:
    """Extract course/session IDs from the current URL path."""
    if not current_page:
        return None, None
    course_match = re.search(r"/courses/(\d+)", current_page)
    session_match = re.search(r"/sessions/(\d+)", current_page)
    course_id = int(course_match.group(1)) if course_match else None
    session_id = int(session_match.group(1)) if session_match else None
    return course_id, session_id


def _resolve_course_id(db: Session, current_page: Optional[str], user_id: Optional[int] = None) -> Optional[int]:
    """Resolve course ID from URL, context memory, or database.

    Priority:
    1. Course ID in URL path
    2. Active course from user context memory
    3. Most recently created course (fallback)
    """
    course_id, _ = _parse_ids_from_path(current_page)
    if course_id:
        # Update context with this course
        if user_id:
            context_store.update_context(user_id, active_course_id=course_id)
        return course_id

    # Check context memory for active course
    if user_id:
        active_course_id = context_store.get_active_course_id(user_id)
        if active_course_id:
            return active_course_id

    # Fallback to most recent course
    course = db.query(Course).order_by(Course.created_at.desc()).first()
    return course.id if course else None


def _resolve_session_id(db: Session, current_page: Optional[str], user_id: Optional[int] = None, course_id: Optional[int] = None) -> Optional[int]:
    """Resolve session ID from URL, context memory, or database.

    Priority:
    1. Session ID in URL path
    2. Active session from user context memory
    3. Live session (filtered by course_id if provided)
    4. Most recently created session (filtered by course_id if provided)

    Args:
        db: Database session
        current_page: Current URL path
        user_id: User ID for context memory lookup
        course_id: Optional course ID to filter sessions by
    """
    _, session_id = _parse_ids_from_path(current_page)
    if session_id:
        # Update context with this session
        if user_id:
            context_store.update_context(user_id, active_session_id=session_id)
        return session_id

    # Check context memory for active session
    if user_id:
        active_session_id = context_store.get_active_session_id(user_id)
        if active_session_id:
            return active_session_id

    # Try to find a live session (filtered by course if provided)
    query = db.query(SessionModel).filter(SessionModel.status == SessionStatus.live)
    if course_id:
        query = query.filter(SessionModel.course_id == course_id)
    session = query.order_by(SessionModel.created_at.desc()).first()
    if session:
        return session.id

    # Fallback to most recent session (filtered by course if provided)
    query = db.query(SessionModel)
    if course_id:
        query = query.filter(SessionModel.course_id == course_id)
    session = query.order_by(SessionModel.created_at.desc()).first()
    return session.id if session else None


def _execute_tool(db: Session, tool_name: str, args: Dict[str, Any]) -> Optional[Any]:
    tool_info = TOOL_REGISTRY.get(tool_name)
    if not tool_info:
        return None
    handler = tool_info["handler"]
    return invoke_tool_handler(handler, args, db=db)


def _get_page_context(db: Session, current_page: Optional[str]) -> Dict[str, Any]:
    """Get intelligent context about the current page and available actions."""
    page = current_page or "/dashboard"

    # Determine page type
    if "/courses" in page:
        course_id = _resolve_course_id(db, current_page)
        if course_id:
            course = _execute_tool(db, 'get_course', {"course_id": course_id})
            result = _execute_tool(db, 'list_sessions', {"course_id": course_id})
            sessions = result.get("sessions", []) if isinstance(result, dict) else []
            return {
                "page": "course_detail",
                "course": course,
                "session_count": len(sessions),
                "message": f"You're viewing {course.get('title', 'a course')} with {len(sessions)} sessions.",
                "available_actions": ["Create session", "View sessions", "Manage enrollments", "Go to forum"],
            }
        else:
            result = _execute_tool(db, 'list_courses', {"skip": 0, "limit": 100})
            courses = result.get("courses", []) if isinstance(result, dict) else []
            return {
                "page": "courses_list",
                "course_count": len(courses),
                "message": f"You're on the courses page. You have {len(courses)} courses.",
                "available_actions": ["Create course", "Select a course", "View sessions"],
            }

    elif "/sessions" in page:
        course_id = _resolve_course_id(db, current_page, user_id)
        session_id = _resolve_session_id(db, current_page, user_id, course_id)
        if session_id:
            session = _execute_tool(db, 'get_session', {"session_id": session_id})
            status = session.get('status', 'unknown') if session else 'unknown'
            return {
                "page": "session_detail",
                "session": session,
                "status": status,
                "message": f"You're viewing a session. Status: {status}.",
                "available_actions": ["Go live", "End session", "Start copilot", "Create poll", "Go to forum"] if status != 'live'
                                     else ["End session", "Start copilot", "Create poll", "View suggestions"],
            }
        return {
            "page": "sessions_list",
            "message": "You're on the sessions page. Select a course to view sessions.",
            "available_actions": ["Select course", "Create session", "Go to courses"],
        }

    elif "/forum" in page:
        course_id = _resolve_course_id(db, current_page, user_id)
        session_id = _resolve_session_id(db, current_page, user_id, course_id)
        if session_id:
            posts = _execute_tool(db, 'get_session_posts', {"session_id": session_id})
            pinned = [p for p in posts if p.get('pinned')] if posts else []
            return {
                "page": "forum",
                "post_count": len(posts) if posts else 0,
                "pinned_count": len(pinned),
                "message": f"You're in the forum with {len(posts) if posts else 0} posts and {len(pinned)} pinned.",
                "available_actions": ["View posts", "Show pinned", "Summarize discussion", "Post case", "Show questions"],
            }
        return {
            "page": "forum",
            "message": "You're on the forum page. Select a live session to view discussions.",
            "available_actions": ["Select session", "Go to sessions"],
        }

    elif "/console" in page:
        course_id = _resolve_course_id(db, current_page, user_id)
        session_id = _resolve_session_id(db, current_page, user_id, course_id)
        copilot_status = _execute_tool(db, 'get_copilot_status', {"session_id": session_id}) if session_id else None
        is_active = copilot_status.get('is_active', False) if copilot_status else False
        return {
            "page": "console",
            "copilot_active": is_active,
            "message": f"You're in the console. Copilot is {'active' if is_active else 'inactive'}.",
            "available_actions": ["Stop copilot", "View suggestions", "Create poll"] if is_active
                                 else ["Start copilot", "Create poll", "Go to forum"],
        }

    elif "/reports" in page:
        return {
            "page": "reports",
            "message": "You're on the reports page. Select a session to view or generate reports.",
            "available_actions": ["Generate report", "View analytics", "Go to sessions"],
        }

    # Default dashboard
    result = _execute_tool(db, 'list_courses', {"skip": 0, "limit": 100})
    courses = result.get("courses", []) if isinstance(result, dict) else []
    return {
        "page": "dashboard",
        "course_count": len(courses),
        "message": f"You're on the dashboard. You have {len(courses)} courses.",
        "available_actions": ["Show courses", "Go to sessions", "Go to forum", "Go to console"],
    }


async def execute_action(
    action: str,
    user_id: Optional[int],
    current_page: Optional[str],
    db: Session,
    transcript: Optional[str] = None,
    llm_params: Optional[Dict[str, Any]] = None,
    language: str = 'en',
) -> Optional[Any]:
    """Execute an MCP tool and return results, including UI actions for frontend.

    Args:
        action: The action to execute (e.g., 'ui_switch_tab', 'create_course')
        user_id: The user ID making the request
        current_page: The current page path
        db: Database session
        transcript: The original voice transcript
        llm_params: Optional parameters extracted by the LLM intent classifier
                   (e.g., tabName, buttonName, selectionIndex, inputValue)
        language: Response language ('en' or 'es')
    """
    # Use LLM-extracted parameters if available, otherwise fall back to regex extraction
    llm_params = llm_params or {}
    try:
        # === CONVERSATIONAL INSTRUCTOR TOOL FORMS ===
        # Route these through the frontend form flow so voice asks for missing fields
        # and then clicks the exact UI controls (instead of backend-only execution).
        if action in {'create_breakout_groups', 'start_timer'}:
            course_id = _resolve_course_id(db, current_page, user_id)
            session_id = _resolve_session_id(db, current_page, user_id, course_id)

            if not session_id:
                missing_target = "create breakout groups" if action == "create_breakout_groups" else "start a timer"
                missing_msg = generate_voice_response(
                    f"No session selected. Ask user to select a session first so you can {missing_target}.",
                    language=language
                )
                return {
                    "action": action,
                    "message": missing_msg,
                    "ui_actions": [
                        {"type": "ui.navigate", "payload": {"path": "/console"}},
                        {"type": "ui.switchTab", "payload": {"tabName": "tools", "target": "tab-tools"}},
                        {"type": "ui.expandDropdown", "payload": {"target": "select-session"}},
                    ],
                }

            if action == 'create_breakout_groups':
                first_question = conversation_manager.start_form_filling(
                    user_id, "create_breakout_groups", "/console"
                )
                if not first_question:
                    first_question = generate_voice_response(
                        "Opening breakout groups form. Ask user how many groups they would like to create.",
                        language=language
                    )
                return {
                    "action": "create_breakout_groups",
                    "session_id": session_id,
                    "ui_actions": [
                        {"type": "ui.navigate", "payload": {"path": "/console"}},
                        {"type": "ui.switchTab", "payload": {"tabName": "tools", "target": "tab-tools"}},
                        {"type": "ui.clickButton", "payload": {"target": "open-breakout-form", "buttonLabel": "Create Breakout Groups"}},
                    ],
                    "message": first_question,
                    "conversation_state": "form_filling",
                }

            if action == 'start_timer':
                first_question = conversation_manager.start_form_filling(
                    user_id, "start_timer", "/console"
                )
                if not first_question:
                    first_question = generate_voice_response(
                        "Opening timer setup form. Ask user how many minutes the timer should run.",
                        language=language
                    )
                return {
                    "action": "start_timer",
                    "session_id": session_id,
                    "ui_actions": [
                        {"type": "ui.navigate", "payload": {"path": "/console"}},
                        {"type": "ui.switchTab", "payload": {"tabName": "tools", "target": "tab-tools"}},
                        {"type": "ui.clickButton", "payload": {"target": "open-timer-form", "buttonLabel": "Start Timer"}},
                    ],
                    "message": first_question,
                    "conversation_state": "form_filling",
                }

        # === INSTRUCTOR ENHANCEMENT FEATURES ===
        # Try to handle instructor-specific voice commands first
        # Resolve session and course IDs from context
        session_id = None
        course_id = None
        if user_id:
            ctx = context_store.get_context(user_id)
            session_id = ctx.get("active_session_id") if ctx else None
            course_id = ctx.get("active_course_id") if ctx else None

        instructor_result = handle_instructor_feature(
            action=action,
            user_id=user_id,
            session_id=session_id,
            course_id=course_id,
            transcript=transcript or "",
            db=db,
            llm_params=llm_params,
        )
        if instructor_result is not None:
            return instructor_result

        # === UNIVERSAL UI ELEMENT INTERACTIONS ===
        # All UI actions now use universal handlers that work across all pages

        # === UNIVERSAL FORM DICTATION ===
        # Works for ANY input field - title, syllabus, objectives, poll question, post content, etc.
        if action == 'ui_dictate_input':
            extracted = _extract_universal_dictation(transcript or "")
            if extracted:
                field_name = extracted.get("field", "input")
                value = extracted.get("value", "")
                fill_msg = generate_voice_response(
                    f"Setting {field_name} field to the provided value. Confirm briefly.",
                    language=language
                )
                toast_msg = f"{field_name.title()} establecido" if language == 'es' else f"{field_name.title()} set"
                return {
                    "action": "fill_input",
                    "message": fill_msg,
                    "ui_actions": [
                        {"type": "ui.fillInput", "payload": {"target": field_name, "value": value}},
                        {"type": "ui.toast", "payload": {"message": toast_msg, "type": "success"}},
                    ],
                }
            no_input_msg = generate_voice_response(
                "Could not understand input. Ask user to specify what they would like to fill in.",
                language=language
            )
            return {"message": no_input_msg}

        # === UNIVERSAL DROPDOWN EXPANSION ===
        # Works for ANY dropdown on any page - fetches options and reads them verbally
        if action == 'ui_expand_dropdown':
            # Extract which dropdown from transcript, or default to finding any dropdown
            dropdown_hint = _extract_dropdown_hint(transcript or "")
            is_integrations_page = bool(current_page and '/integrations' in current_page)
            is_integration_dropdown = any(
                key in (dropdown_hint or "")
                for key in [
                    "select-integration-provider",
                    "select-provider-connection",
                    "select-integration-mapping",
                    "select-external-course",
                    "select-target-course",
                    "select-target-session",
                ]
            )

            # Fetch options based on dropdown type
            options: list[DropdownOption] = []
            if is_integrations_page and (is_integration_dropdown or not dropdown_hint):
                # Integrations page dropdowns: provide concrete verbal options.
                if not dropdown_hint or "select-integration-provider" in dropdown_hint:
                    providers = [p for p in list_supported_providers() if p]
                    options = [DropdownOption(label=p.upper(), value=p) for p in providers]
                    dropdown_hint = "select-integration-provider"
                elif "select-provider-connection" in dropdown_hint:
                    is_admin = bool(
                        db.query(User.is_admin).filter(User.id == user_id).scalar()
                    ) if user_id else False
                    q = db.query(IntegrationProviderConnection).filter(
                        IntegrationProviderConnection.is_active.is_(True)
                    )
                    if not is_admin and user_id is not None:
                        q = q.filter(IntegrationProviderConnection.created_by == user_id)
                    rows = q.order_by(
                        IntegrationProviderConnection.is_default.desc(),
                        IntegrationProviderConnection.updated_at.desc()
                    ).limit(20).all()
                    options = [
                        DropdownOption(
                            label=f"{r.provider.upper()} - {r.label}{' [default]' if r.is_default else ''}",
                            value=str(r.id)
                        )
                        for r in rows
                    ]
                elif "select-integration-mapping" in dropdown_hint:
                    is_admin = bool(
                        db.query(User.is_admin).filter(User.id == user_id).scalar()
                    ) if user_id else False
                    q = db.query(IntegrationCourseMapping).filter(
                        IntegrationCourseMapping.is_active.is_(True)
                    )
                    if not is_admin and user_id is not None:
                        q = q.filter(IntegrationCourseMapping.created_by == user_id)
                    rows = q.order_by(IntegrationCourseMapping.updated_at.desc()).limit(20).all()
                    options = [
                        DropdownOption(
                            label=f"{(r.external_course_name or r.external_course_id)} -> course {r.target_course_id}",
                            value=str(r.id)
                        )
                        for r in rows
                    ]
                elif "select-target-course" in dropdown_hint or "select-target-session" in dropdown_hint:
                    result = _execute_tool(db, 'list_courses', {"skip": 0, "limit": 20})
                    courses = result.get("courses", []) if isinstance(result, dict) else []
                    options = [DropdownOption(label=c.get('title', f"Course {c['id']}"), value=str(c['id'])) for c in courses]
                    if "select-target-course" in dropdown_hint:
                        dropdown_hint = "select-target-course"
                elif "select-external-course" in dropdown_hint:
                    is_admin = bool(
                        db.query(User.is_admin).filter(User.id == user_id).scalar()
                    ) if user_id else False
                    q = db.query(IntegrationCourseMapping).filter(
                        IntegrationCourseMapping.is_active.is_(True)
                    )
                    if not is_admin and user_id is not None:
                        q = q.filter(IntegrationCourseMapping.created_by == user_id)
                    rows = q.order_by(IntegrationCourseMapping.updated_at.desc()).limit(20).all()
                    options = [
                        DropdownOption(
                            label=(r.external_course_name or r.external_course_id),
                            value=r.external_course_id
                        )
                        for r in rows
                    ]
            elif 'course' in dropdown_hint or not dropdown_hint:
                # Fetch courses - result is {"courses": [...]}
                result = _execute_tool(db, 'list_courses', {"skip": 0, "limit": 10})
                courses = result.get("courses", []) if isinstance(result, dict) else []
                if courses:
                    options = [DropdownOption(label=c.get('title', f"Course {c['id']}"), value=str(c['id'])) for c in courses]
                    dropdown_hint = dropdown_hint or "select-course"
            elif 'session' in dropdown_hint:
                # Fetch sessions for active course - result is {"sessions": [...]}
                course_id = _resolve_course_id(db, current_page, user_id)
                if course_id:
                    # Check if user wants only live sessions
                    # Note: "live" can be pronounced two ways and transcribed differently
                    transcript_lower = (transcript or "").lower()
                    status_filter = None
                    # Check for "live" - various transcriptions for both pronunciations
                    live_keywords = ['live', 'alive', 'active', 'ongoing', 'running', 'in progress', 'current']
                    if any(kw in transcript_lower for kw in live_keywords):
                        status_filter = 'live'
                    elif 'draft' in transcript_lower:
                        status_filter = 'draft'
                    elif 'completed' in transcript_lower or 'complete' in transcript_lower or 'ended' in transcript_lower:
                        status_filter = 'completed'
                    elif 'scheduled' in transcript_lower:
                        status_filter = 'scheduled'

                    list_params = {"course_id": course_id}
                    if status_filter:
                        list_params["status"] = status_filter

                    result = _execute_tool(db, 'list_sessions', list_params)
                    sessions = result.get("sessions", []) if isinstance(result, dict) else []
                    if sessions:
                        # Include status in label for clarity
                        options = []
                        for s in sessions:
                            session_id = s['id']
                            title = s.get('title', f'Session {session_id}')
                            status = s.get('status', 'unknown')
                            options.append(DropdownOption(label=f"{title} ({status})", value=str(session_id)))
                else:
                    # No course selected - prompt user to select course first
                    no_course_msg = generate_voice_response(
                        "No course selected. Ask user to select a course first before choosing a session.",
                        language=language
                    )
                    return {
                        "action": "expand_dropdown",
                        "message": no_course_msg,
                        "ui_actions": [],
                        "needs_course": True,
                    }

            if options:
                # Start dropdown selection flow with verbal listing
                prompt = conversation_manager.start_dropdown_selection(
                    user_id, dropdown_hint, options, current_page or "/dashboard"
                )
                return {
                    "action": "expand_dropdown",
                    "message": prompt,
                    "ui_actions": [
                        {"type": "ui.expandDropdown", "payload": {"target": dropdown_hint, "findAny": True}},
                    ],
                    "options": [{"label": o.label, "value": o.value} for o in options],
                    "conversation_state": "dropdown_selection",
                }
            else:
                empty_msg = generate_voice_response(
                    "The dropdown is empty with no options available. Tell user.",
                    language=language
                )
                return {
                    "action": "expand_dropdown",
                    "message": empty_msg,
                    "ui_actions": [
                        {"type": "ui.expandDropdown", "payload": {"target": dropdown_hint, "findAny": True}},
                    ],
                }

        # === UNIVERSAL TAB SWITCHING ===
        # The ui_switch_tab action now works universally for any tab name
        if action == 'ui_switch_tab':
            # Use LLM-extracted tab name if available, otherwise fall back to regex
            if llm_params.get("tabName"):
                tab_name = llm_params["tabName"]
            else:
                tab_info = _extract_tab_info(transcript or "")
                tab_name = tab_info.get("tabName", "")

            # Special handling for forum discussion tab - offer to help post
            if current_page and '/forum' in current_page and tab_name == 'discussion':
                # Check if user hasn't already declined the offer
                conv_context = conversation_manager.get_context(user_id)
                if not conv_context.post_offer_declined:
                    # Offer to help post after switching to discussion tab
                    offer_prompt = conversation_manager.offer_forum_post(user_id)
                    if offer_prompt:
                        switch_msg = generate_voice_response(
                            f"Switching to discussion tab. {offer_prompt}",
                            language=language
                        )
                        return {
                            "action": "switch_tab_with_post_offer",
                            "message": switch_msg,
                            "ui_actions": [
                                {"type": "ui.switchTab", "payload": {"tabName": tab_name, "target": f"tab-{tab_name}"}},
                            ],
                            "post_offer": True,
                        }

            # Special handling for console polls tab - offer to help create poll
            if current_page and '/console' in current_page and tab_name == 'polls':
                # Check if user hasn't already declined the offer
                conv_context = conversation_manager.get_context(user_id)
                if not conv_context.poll_offer_declined:
                    # Offer to help create poll after switching to polls tab
                    offer_prompt = conversation_manager.offer_poll_creation(user_id)
                    if offer_prompt:
                        switch_msg = generate_voice_response(
                            f"Switching to polls tab. {offer_prompt}",
                            language=language
                        )
                        return {
                            "action": "switch_tab_with_poll_offer",
                            "message": switch_msg,
                            "ui_actions": [
                                {"type": "ui.switchTab", "payload": {"tabName": tab_name, "target": f"tab-{tab_name}"}},
                            ],
                            "poll_offer": True,
                        }

            # Special handling for sessions page manage status tab - offer status options
            if current_page and '/sessions' in current_page and tab_name in ['manage', 'management', 'manage status', 'managestatus']:
                status_msg = generate_voice_response(
                    "Switching to manage status tab. Tell user they can say 'go live', 'set to draft', 'complete', or 'schedule' to change session status.",
                    language=language
                )
                toast_msg = "Administrar estado" if language == 'es' else "Manage status"
                return {
                    "action": "switch_tab_with_status_offer",
                    "message": status_msg,
                    "ui_actions": [
                        {"type": "ui.switchTab", "payload": {"tabName": "manage", "target": "tab-manage"}},
                        {"type": "ui.toast", "payload": {"message": toast_msg, "type": "info"}},
                    ],
                    "status_offer": True,
                }

            # Default tab switch with LLM-generated message
            switch_msg = generate_voice_response(
                f"Switching to {tab_name} tab. Confirm briefly.",
                language=language
            )
            toast_msg = f"Cambiado a {tab_name}" if language == 'es' else f"Switched to {tab_name}"
            return {
                "action": "switch_tab",
                "message": switch_msg,
                "ui_actions": [
                    {"type": "ui.switchTab", "payload": {"tabName": tab_name, "target": f"tab-{tab_name}"}},
                    {"type": "ui.toast", "payload": {"message": toast_msg, "type": "info"}},
                ],
            }

        # === UNIVERSAL DROPDOWN SELECTION ===
        if action == 'ui_select_dropdown':
            transcript_text = transcript or ""
            transcript_lower = transcript_text.lower()

            # Parse transcript first because phrases like "number five" are 1-indexed.
            selection_info = _extract_dropdown_selection(transcript_text)

            # Merge LLM extraction if present.
            if llm_params.get("selectionIndex") is not None:
                try:
                    llm_index = int(llm_params["selectionIndex"])
                except (TypeError, ValueError):
                    llm_index = None
                if llm_index is not None and "optionIndex" not in selection_info:
                    selection_info["optionIndex"] = llm_index
                selection_info["optionName"] = llm_params.get("ordinal", selection_info.get("optionName", "option"))
            elif llm_params.get("selectionValue"):
                selection_info["optionName"] = llm_params["selectionValue"]
            elif llm_params.get("ordinal"):
                ordinal_map = {"first": 0, "second": 1, "third": 2, "fourth": 3, "last": -1,
                              "primero": 0, "segundo": 1, "tercero": 2, "cuarto": 3, "ultimo": -1}
                ordinal = llm_params["ordinal"].lower()
                selection_info["optionIndex"] = ordinal_map.get(ordinal, 0)
                selection_info["optionName"] = ordinal

            # Infer target dropdown to avoid selecting the wrong <select>.
            target_hint = llm_params.get("target") or llm_params.get("dropdownTarget")
            if target_hint:
                selection_info["target"] = target_hint
            elif any(phrase in transcript_lower for phrase in ["provider connection", "connection", "conexion"]):
                selection_info["target"] = "select-provider-connection"
            elif any(phrase in transcript_lower for phrase in ["source provider", "provider", "proveedor"]):
                selection_info["target"] = "select-integration-provider"
            elif any(phrase in transcript_lower for phrase in ["saved mapping", "mapping", "mapeo"]):
                selection_info["target"] = "select-integration-mapping"
            elif any(phrase in transcript_lower for phrase in ["external course", "source course", "curso externo"]):
                selection_info["target"] = "select-external-course"
            elif any(phrase in transcript_lower for phrase in ["target course", "aristai course", "curso objetivo"]):
                selection_info["target"] = "select-target-course"
            elif any(phrase in transcript_lower for phrase in ["target session", "session optional", "sesion objetivo"]):
                selection_info["target"] = "select-target-session"
            elif any(word in transcript_lower for word in ["course", "courses", "curso", "cursos", "class"]):
                selection_info["target"] = "select-course"
            elif any(word in transcript_lower for word in ["session", "sessions", "sesion", "sesiones"]):
                selection_info["target"] = "select-session"
            elif current_page and any(page in current_page for page in ["/reports", "/forum", "/console", "/sessions"]):
                # Course is first-level selector on these pages.
                selection_info["target"] = "select-course"

            return {
                "action": "select_dropdown",
                "message": f"Selecting {selection_info.get('optionName', 'option')}",
                "ui_actions": [
                    {"type": "ui.selectDropdown", "payload": selection_info},
                ],
            }

        # === UNIVERSAL BUTTON CLICK ===
        # Handles button clicks from form submission confirmations and direct commands
        if action == 'ui_click_button':
            # Get button target from conversation context (for confirmations) or extract from transcript
            conv_context = conversation_manager.get_context(user_id)
            button_target = None
            button_label = None

            # Check if we have action_data from confirmation flow
            if conv_context.pending_action_data and conv_context.pending_action_data.get("voice_id"):
                button_target = conv_context.pending_action_data.get("voice_id")
                form_name = conv_context.pending_action_data.get("form_name", "")
                button_label = form_name.replace("_", " ").title() if form_name else "Submit"
            # Use LLM-extracted button name if available
            elif llm_params.get("buttonName"):
                raw_button_name = str(llm_params["buttonName"]).strip()
                normalized_button_name = raw_button_name.lower().replace("_", " ").replace("-", " ")
                button_aliases = {
                    "get started": "intro-get-started",
                    "start now": "intro-get-started",
                    "voice commands": "intro-voice-commands",
                    "open voice commands": "intro-voice-commands",
                    "notifications": "notifications-button",
                    "notification": "notifications-button",
                    "open notifications": "notifications-button",
                    "open notification": "notifications-button",
                    "language": "toggle-language",
                    "change language": "toggle-language",
                    "switch language": "toggle-language",
                    "toggle language": "toggle-language",
                    "notificaciones": "notifications-button",
                    "notificacion": "notifications-button",
                    "comandos de voz": "intro-voice-commands",
                    "cambiar idioma": "toggle-language",
                    "refresh poll results": "refresh-poll-results",
                    "refresh instructor requests": "refresh-instructor-requests",
                    "approve request": "approve-instructor-request",
                    "reject request": "reject-instructor-request",
                    "add connection": "add-provider-connection",
                    "connect canvas": "connect-canvas-oauth",
                    "connect upp": "connect-canvas-oauth",
                    "connect provider": "connect-canvas-oauth",
                    "test selected": "test-provider-connection",
                    "set default": "activate-provider-connection",
                    "create forum course": "import-external-course",
                    "save mapping": "save-course-mapping",
                    "sync all": "sync-all-materials",
                    "sync students": "sync-roster",
                    "import selected materials": "import-external-materials",
                    "import materials": "import-external-materials",
                    "select all materials": "select-all-external-materials",
                    "clear materials": "clear-external-materials",
                }
                button_target = button_aliases.get(normalized_button_name, raw_button_name)
                button_label = raw_button_name
            else:
                # Extract from transcript using regex
                button_info = _extract_button_info(transcript or "")
                button_target = button_info.get("target")
                button_label = button_info.get("label", "button")

            if button_target:
                # Clear confirmation state after clicking
                conv_context.state = ConversationState.IDLE
                conv_context.pending_action = None
                conv_context.pending_action_data = {}
                conv_context.active_form = None
                conversation_manager.save_context(user_id, conv_context)

                return {
                    "action": "click_button",
                    "message": f"Clicking {button_label}.",
                    "ui_actions": [
                        {"type": "ui.clickButton", "payload": {"target": button_target, "buttonLabel": button_label}},
                        {"type": "ui.toast", "payload": {"message": f"{button_label} clicked", "type": "success"}},
                    ],
                }
            no_button_msg = generate_voice_response(
                "Could not determine which button to click. Ask user to clarify.",
                language=language
            )
            return {"message": no_button_msg}

        # === WORKSPACE SEARCH + NAVIGATE ===
        if action == 'ui_search_navigate':
            query = llm_params.get("searchQuery") if llm_params else None
            if not query:
                query = _extract_search_query(transcript or "")
            if not query:
                no_query_msg = generate_voice_response(
                    "Ask user what they would like to search for.",
                    language=language
                )
                return {"message": no_query_msg}

            return {
                "action": "search_navigate",
                "message": f"Searching for {query}.",
                "ui_actions": [
                    {"type": "ui.searchAndNavigate", "payload": {"query": query}},
                ],
            }

        # Note: Specific tab handlers (open_enrollment_tab, open_create_tab, open_manage_tab)
        # are now handled by the universal ui_switch_tab action above

        # === UNDO/CONTEXT ACTIONS ===
        if action == 'undo_action':
            if not user_id:
                return {"error": "Cannot undo without user context."}

            last_action = context_store.get_last_undoable_action(user_id)
            if not last_action:
                no_undo_msg = generate_voice_response(
                    "Nothing to undo. Recent actions don't have undo data. Tell user.",
                    language=language
                )
                toast_msg = "Nada que deshacer" if language == 'es' else "Nothing to undo"
                return {
                    "message": no_undo_msg,
                    "ui_actions": [{"type": "ui.toast", "payload": {"message": toast_msg, "type": "info"}}],
                }

            action_type = last_action.get("action_type", "unknown")
            undo_data = last_action.get("undo_data", {})

            # Mark as undone
            context_store.mark_action_undone(user_id, last_action.get("timestamp", 0))

            return {
                "message": f"Undone: {action_type}. The action has been reversed.",
                "undone_action": action_type,
                "undo_data": undo_data,
                "ui_actions": [
                    {"type": "ui.toast", "payload": {"message": f"Undone: {action_type}", "type": "success"}},
                ],
            }

        if action == 'get_context':
            if not user_id:
                return {"message": "No user context available."}

            context = context_store.get_context(user_id)
            summary = context_store.get_context_summary(user_id)

            # Get names for the IDs
            course_name = None
            session_name = None

            if context.get("active_course_id"):
                course = _execute_tool(db, 'get_course', {"course_id": context["active_course_id"]})
                course_name = course.get("title") if course else None

            if context.get("active_session_id"):
                session = _execute_tool(db, 'get_session', {"session_id": context["active_session_id"]})
                session_name = session.get("title") if session else None

            return {
                "message": f"Your current context: {summary}",
                "context": context,
                "course_name": course_name,
                "session_name": session_name,
                "ui_actions": [{"type": "ui.toast", "payload": {"message": summary, "type": "info"}}],
            }

        if action == 'clear_context':
            if user_id:
                context_store.clear_context(user_id)
            clear_msg = generate_voice_response(
                "Context has been cleared. Starting fresh. Confirm briefly.",
                language=language
            )
            toast_msg = "Contexto borrado" if language == 'es' else "Context cleared"
            return {
                "message": clear_msg,
                "ui_actions": [{"type": "ui.toast", "payload": {"message": toast_msg, "type": "success"}}],
            }

        # === CONTEXT/STATUS ACTIONS ===
        if action == 'get_status':
            return _get_page_context(db, current_page)

        if action == 'get_help':
            help_msg = generate_voice_response(
                "Tell user what you can help with: navigating pages, listing courses and sessions, "
                "starting copilot, creating polls, viewing forum discussions, pinning posts, "
                "generating reports, and managing enrollments. Invite them to ask for help.",
                language=language
            )
            commands_en = [
                "Show my courses", "Go to forum", "Start copilot",
                "Create a poll", "Show pinned posts", "Summarize discussion",
                "Generate report", "Go live", "End session"
            ]
            commands_es = [
                "Mostrar mis cursos", "Ir al foro", "Iniciar copiloto",
                "Crear encuesta", "Ver publicaciones fijadas", "Resumir discusión",
                "Generar informe", "Ir en vivo", "Terminar sesión"
            ]
            return {
                "message": help_msg,
                "available_commands": commands_es if language == 'es' else commands_en
            }

        # === OPEN-ENDED QUESTIONS (LLM-based) ===
        if action == 'open_question':
            return await _handle_open_question(transcript or "", current_page)

        # === COURSE ACTIONS ===
        if action == 'list_courses':
            return _execute_tool(db, 'list_courses', {"skip": 0, "limit": 100})

        if action == 'create_course':
            # Start conversational form-filling flow
            first_question = conversation_manager.start_form_filling(
                user_id, "create_course", "/courses"
            )
            # Generate language-aware message
            if not first_question:
                first_question = generate_voice_response(
                    "Opening course creation form. Ask user what they would like to name the course.",
                    language=language
                )
            return {
                "action": "create_course",
                "ui_actions": [
                    {"type": "ui.navigate", "payload": {"path": "/courses"}},
                    {"type": "ui.switchTab", "payload": {"tabName": "create", "target": "tab-create"}},
                ],
                "message": first_question,
                "conversation_state": "form_filling",
            }

        if action == 'select_course':
            result = _execute_tool(db, 'list_courses', {"skip": 0, "limit": 10})
            courses = result.get("courses", []) if isinstance(result, dict) else []
            if courses and len(courses) > 0:
                first_course = courses[0]
                # Update context memory with selected course
                if user_id:
                    context_store.update_context(user_id, active_course_id=first_course['id'])
                return {
                    "action": "select_course",
                    "course": first_course,
                    "ui_actions": [
                        {"type": "ui.navigate", "payload": {"path": f"/courses/{first_course['id']}"}},
                        {"type": "ui.toast", "payload": {"message": f"Selected: {first_course.get('title', 'course')}", "type": "success"}},
                    ],
                }
            no_courses_msg = generate_voice_response(
                "No courses found. Ask user to create a course first.",
                language=language
            )
            return {"error": no_courses_msg}

        if action == 'view_course_details':
            course_id = _resolve_course_id(db, current_page, user_id)
            if course_id:
                return _execute_tool(db, 'get_course', {"course_id": course_id})
            no_course_msg = generate_voice_response(
                "No course selected. Ask user to navigate to or select a course first.",
                language=language
            )
            return {"error": no_course_msg}

        # === SESSION ACTIONS ===
        if action == 'list_sessions':
            course_id = _resolve_course_id(db, current_page, user_id)
            if not course_id:
                no_course_msg = generate_voice_response(
                    "No course selected. Ask user to select a course first to view sessions.",
                    language=language
                )
                return {"message": no_course_msg, "sessions": []}

            # Check if user wants only live sessions
            # Note: "live" can be pronounced two ways and transcribed differently
            transcript_lower = (transcript or "").lower()
            status_filter = None
            live_keywords = ['live', 'alive', 'active', 'ongoing', 'running', 'in progress', 'current']
            if any(kw in transcript_lower for kw in live_keywords):
                status_filter = 'live'

            list_params = {"course_id": course_id}
            if status_filter:
                list_params["status"] = status_filter

            return _execute_tool(db, 'list_sessions', list_params)

        if action == 'create_session':
            course_id = _resolve_course_id(db, current_page, user_id)
            # Start conversational form-filling flow
            first_question = conversation_manager.start_form_filling(
                user_id, "create_session", "/sessions"
            )
            if not first_question:
                first_question = generate_voice_response(
                    "Opening session creation form. Ask user what they would like to name the session.",
                    language=language
                )
            return {
                "action": "create_session",
                "course_id": course_id,
                "ui_actions": [
                    {"type": "ui.navigate", "payload": {"path": "/sessions"}},
                    {"type": "ui.switchTab", "payload": {"tabName": "create", "target": "tab-create"}},
                ],
                "message": first_question,
                "conversation_state": "form_filling",
            }

        if action == 'select_session':
            course_id = _resolve_course_id(db, current_page, user_id)
            if not course_id:
                no_course_msg = generate_voice_response(
                    "No course selected. Ask user to select a course first before choosing a session.",
                    language=language
                )
                return {"message": no_course_msg}

            # Check if user wants only live sessions
            # Note: "live" can be pronounced two ways and transcribed differently
            transcript_lower = (transcript or "").lower()
            status_filter = None
            live_keywords = ['live', 'alive', 'active', 'ongoing', 'running', 'in progress', 'current']
            if any(kw in transcript_lower for kw in live_keywords):
                status_filter = 'live'
            elif 'draft' in transcript_lower:
                status_filter = 'draft'

            list_params = {"course_id": course_id}
            if status_filter:
                list_params["status"] = status_filter

            result = _execute_tool(db, 'list_sessions', list_params)
            sessions = result.get("sessions", []) if isinstance(result, dict) else []

            if not sessions:
                no_sessions_msg = generate_voice_response(
                    f"No sessions found{' with status ' + status_filter if status_filter else ''} for this course. Tell user.",
                    language=language
                )
                return {"message": no_sessions_msg}

            # If only one session, select it directly
            if len(sessions) == 1:
                session = sessions[0]
                if user_id:
                    context_store.update_context(user_id, active_session_id=session['id'])
                return {
                    "action": "select_session",
                    "session": session,
                    "ui_actions": [
                        {"type": "ui.selectDropdown", "payload": {"target": "select-session", "value": str(session['id'])}},
                        {"type": "ui.toast", "payload": {"message": f"Selected: {session.get('title', 'session')}", "type": "success"}},
                    ],
                }

            # Multiple sessions - start dropdown selection flow
            options = []
            for s in sessions:
                session_id = s['id']
                title = s.get('title', f'Session {session_id}')
                status = s.get('status', 'unknown')
                options.append(DropdownOption(label=f"{title} ({status})", value=str(session_id)))
            prompt = conversation_manager.start_dropdown_selection(
                user_id, "select-session", options, current_page or "/sessions"
            )
            return {
                "action": "select_session",
                "message": prompt,
                "ui_actions": [
                    {"type": "ui.expandDropdown", "payload": {"target": "select-session"}},
                ],
                "options": [{"label": o.label, "value": o.value} for o in options],
                "conversation_state": "dropdown_selection",
            }

        if action == 'go_live' or action == 'set_session_live':
            # If on sessions page manage tab, just click the button - frontend handles API call
            if current_page and '/sessions' in current_page:
                go_live_msg = generate_voice_response(
                    "Setting session to live now. Confirm briefly.",
                    language=language
                )
                return {
                    "action": "set_session_live",
                    "message": go_live_msg,
                    "ui_actions": [
                        {"type": "ui.clickButton", "payload": {"target": "go-live"}},
                    ],
                }
            # On other pages, update via backend and navigate to console
            course_id = _resolve_course_id(db, current_page, user_id)
            session_id = _resolve_session_id(db, current_page, user_id, course_id)
            if session_id:
                result = _execute_tool(db, 'update_session_status', {"session_id": session_id, "status": "live"})
                if result:
                    # Record action for undo
                    if user_id:
                        context_store.record_action(
                            user_id,
                            action_type="go_live",
                            action_data={"session_id": session_id},
                            undo_data={"session_id": session_id, "previous_status": "draft"},
                        )
                    toast_msg = "¡Sesión EN VIVO!" if language == 'es' else "Session is now LIVE!"
                    result["ui_actions"] = [
                        {"type": "ui.navigate", "payload": {"path": f"/console?session={session_id}"}},
                        {"type": "ui.toast", "payload": {"message": toast_msg, "type": "success"}},
                    ]
                return result
            no_session_msg = generate_voice_response(
                "No session found to go live. Ask user to select a session first.",
                language=language
            )
            return {"error": no_session_msg}

        if action == 'end_session' or action == 'set_session_completed':
            # If on sessions page manage tab, just click the button - frontend handles API call
            if current_page and '/sessions' in current_page:
                complete_msg = generate_voice_response(
                    "Completing session now. Confirm briefly.",
                    language=language
                )
                return {
                    "action": "set_session_completed",
                    "message": complete_msg,
                    "ui_actions": [
                        {"type": "ui.clickButton", "payload": {"target": "complete-session"}},
                    ],
                }
            # On other pages, use confirmation flow
            course_id = _resolve_course_id(db, current_page, user_id)
            session_id = _resolve_session_id(db, current_page, user_id, course_id)
            if not session_id:
                no_session_msg = generate_voice_response(
                    "No active session found to end. Ask user to select a session first.",
                    language=language
                )
                return {"error": no_session_msg}

            # Check if already confirmed (from confirmation flow)
            conv_context = conversation_manager.get_context(user_id)
            if conv_context.state != ConversationState.IDLE or not conv_context.pending_action:
                # Request confirmation first (destructive action)
                confirmation_prompt = conversation_manager.request_confirmation(
                    user_id,
                    "end_session",
                    {"session_id": session_id, "voice_id": "btn-end-session"},
                    current_page or "/console"
                )
                return {
                    "action": "end_session",
                    "message": confirmation_prompt,
                    "ui_actions": [],
                    "needs_confirmation": True,
                    "conversation_state": "awaiting_confirmation",
                }

            # Execute the action (already confirmed)
            result = _execute_tool(db, 'update_session_status', {"session_id": session_id, "status": "completed"})
            if result and user_id:
                context_store.record_action(
                    user_id,
                    action_type="end_session",
                    action_data={"session_id": session_id},
                    undo_data={"session_id": session_id, "previous_status": "live"},
                )
                result["ui_actions"] = [
                    {"type": "ui.toast", "payload": {"message": "Session ended", "type": "info"}},
                ]
            return result

        # === MATERIALS ACTIONS ===
        if action == 'view_materials':
            # Navigate to sessions page with materials tab
            materials_msg = generate_voice_response(
                "Opening course materials where user can view and download files. Confirm briefly.",
                language=language
            )
            return {
                "action": "view_materials",
                "message": materials_msg,
                "ui_actions": [
                    {"type": "ui.openModal", "payload": {"modal": "viewMaterials"}},
                ],
            }

        # === COPILOT ACTIONS ===
        if action == 'get_interventions':
            course_id = _resolve_course_id(db, current_page, user_id)
            session_id = _resolve_session_id(db, current_page, user_id, course_id)
            if not session_id:
                return []
            return _execute_tool(db, 'get_copilot_suggestions', {"session_id": session_id})

        if action == 'start_copilot':
            course_id = _resolve_course_id(db, current_page, user_id)
            session_id = _resolve_session_id(db, current_page, user_id, course_id)
            if not session_id:
                return None
            result = _execute_tool(db, 'start_copilot', {"session_id": session_id})
            if result and user_id:
                context_store.record_action(
                    user_id,
                    action_type="start_copilot",
                    action_data={"session_id": session_id},
                    undo_data={"session_id": session_id},
                )
            if result:
                result["ui_actions"] = [
                    {"type": "ui.clickButton", "payload": {"target": "start-copilot"}},
                    {"type": "ui.toast", "payload": {"message": "Copilot is now active!", "type": "success"}},
                ]
            return result

        if action == 'stop_copilot':
            course_id = _resolve_course_id(db, current_page, user_id)
            session_id = _resolve_session_id(db, current_page, user_id, course_id)
            if not session_id:
                return None

            # Check if already confirmed (from confirmation flow)
            conv_context = conversation_manager.get_context(user_id)
            if conv_context.state != ConversationState.IDLE or not conv_context.pending_action:
                # Request confirmation first (destructive action)
                confirmation_prompt = conversation_manager.request_confirmation(
                    user_id,
                    "stop_copilot",
                    {"session_id": session_id, "voice_id": "stop-copilot"},
                    current_page or "/console"
                )
                return {
                    "action": "stop_copilot",
                    "message": confirmation_prompt,
                    "ui_actions": [],
                    "needs_confirmation": True,
                    "conversation_state": "awaiting_confirmation",
                }

            # Execute the action (already confirmed)
            result = _execute_tool(db, 'stop_copilot', {"session_id": session_id})
            if result and user_id:
                context_store.record_action(
                    user_id,
                    action_type="stop_copilot",
                    action_data={"session_id": session_id},
                    undo_data={"session_id": session_id},
                )
            if result:
                result["ui_actions"] = [
                    {"type": "ui.clickButton", "payload": {"target": "stop-copilot"}},
                    {"type": "ui.toast", "payload": {"message": "Copilot stopped", "type": "info"}},
                ]
            return result

        if action == 'refresh_interventions':
            refresh_msg = generate_voice_response(
                "Refreshing copilot interventions now. Confirm briefly.",
                language=language
            )
            toast_msg = "Intervenciones actualizadas" if language == 'es' else "Interventions refreshed"
            return {
                "action": "refresh_interventions",
                "message": refresh_msg,
                "ui_actions": [
                    {"type": "ui.clickButton", "payload": {"target": "refresh-interventions"}},
                    {"type": "ui.toast", "payload": {"message": toast_msg, "type": "success"}},
                ],
            }

        # === SESSION STATUS MANAGEMENT (on sessions page) ===
        if action == 'set_session_draft':
            draft_msg = generate_voice_response(
                "Setting session to draft status. Confirm briefly.",
                language=language
            )
            return {
                "action": "set_session_draft",
                "message": draft_msg,
                "ui_actions": [
                    {"type": "ui.clickButton", "payload": {"target": "set-to-draft"}},
                ],
            }

        if action == 'schedule_session':
            schedule_msg = generate_voice_response(
                "Scheduling session now. Confirm briefly.",
                language=language
            )
            toast_msg = "Sesión programada" if language == 'es' else "Session scheduled"
            return {
                "action": "schedule_session",
                "message": schedule_msg,
                "ui_actions": [
                    {"type": "ui.clickButton", "payload": {"target": "schedule-session"}},
                    {"type": "ui.toast", "payload": {"message": toast_msg, "type": "success"}},
                ],
            }

        # === REPORT ACTIONS ===
        if action == 'refresh_report':
            refresh_msg = generate_voice_response(
                "Refreshing report now. Confirm briefly.",
                language=language
            )
            return {
                "action": "refresh_report",
                "message": refresh_msg,
                "ui_actions": [
                    {"type": "ui.clickButton", "payload": {"target": "refresh-report"}},
                ],
            }

        if action == 'regenerate_report':
            regen_msg = generate_voice_response(
                "Regenerating report. This may take a moment. Tell user to wait.",
                language=language
            )
            return {
                "action": "regenerate_report",
                "message": regen_msg,
                "ui_actions": [
                    {"type": "ui.clickButton", "payload": {"target": "regenerate-report"}},
                ],
            }

        # === THEME AND USER MENU ACTIONS ===
        if action == 'toggle_theme':
            theme_msg = generate_voice_response(
                "Toggling theme now. Confirm briefly.",
                language=language
            )
            return {
                "action": "toggle_theme",
                "message": theme_msg,
                "ui_actions": [
                    {"type": "ui.clickButton", "payload": {"target": "toggle-theme"}},
                ],
            }

        if action == 'open_user_menu':
            menu_msg = generate_voice_response(
                "Opening user menu now. Confirm briefly.",
                language=language
            )
            return {
                "action": "open_user_menu",
                "message": menu_msg,
                "ui_actions": [
                    {"type": "ui.clickButton", "payload": {"target": "user-menu"}},
                ],
            }

        if action == 'view_voice_guide':
            guide_msg = generate_voice_response(
                "Opening voice commands guide. Confirm briefly.",
                language=language
            )
            return {
                "action": "view_voice_guide",
                "message": guide_msg,
                "ui_actions": [
                    {"type": "voice-menu-action", "payload": {"action": "view-voice-guide"}},
                ],
            }

        if action == 'open_profile':
            profile_msg = generate_voice_response(
                "Opening profile settings. Confirm briefly.",
                language=language
            )
            return {
                "action": "open_profile",
                "message": profile_msg,
                "ui_actions": [
                    {"type": "voice-menu-action", "payload": {"action": "open-profile"}},
                ],
            }

        if action == 'sign_out':
            signout_msg = generate_voice_response(
                "Signing out now. Confirm briefly.",
                language=language
            )
            return {
                "action": "sign_out",
                "message": signout_msg,
                "ui_actions": [
                    {"type": "voice-menu-action", "payload": {"action": "sign-out"}},
                ],
            }

        if action == 'forum_instructions':
            instr_msg = generate_voice_response(
                "Opening platform instructions. Confirm briefly.",
                language=language
            )
            return {
                "action": "forum_instructions",
                "message": instr_msg,
                "ui_actions": [
                    {"type": "voice-menu-action", "payload": {"action": "forum-instructions"}},
                ],
            }

        if action == 'close_modal':
            # Try to click "Got It" buttons in any open modal
            close_msg = generate_voice_response(
                "Closing modal. Confirm briefly.",
                language=language
            )
            return {
                "action": "close_modal",
                "message": close_msg,
                "ui_actions": [
                    {"type": "ui.clickButton", "payload": {"target": "got-it-voice-guide"}},
                    {"type": "ui.clickButton", "payload": {"target": "got-it-platform-guide"}},
                ],
            }

        # === HIGH-IMPACT VOICE INTELLIGENCE FEATURES ===

        # "How's the class doing?" - Quick class status summary
        if action == 'class_status':
            course_id = _resolve_course_id(db, current_page, user_id)
            session_id = _resolve_session_id(db, current_page, user_id, course_id)

            if not session_id:
                no_session_msg = generate_voice_response(
                    "No session selected. Ask user to select a session first to check class status.",
                    language=language
                )
                return {
                    "action": "class_status",
                    "message": no_session_msg,
                }

            # Gather data from multiple sources
            status_parts = []

            # Get session info
            session = db.query(SessionModel).filter(SessionModel.id == session_id).first()
            if session:
                status_parts.append(f"Session '{session.title}' is {session.status.value if hasattr(session.status, 'value') else session.status}.")

            # Get participation stats
            participation_result = _execute_tool(db, 'get_participation_stats', {"session_id": session_id})
            if participation_result and not participation_result.get("error"):
                participated = participation_result.get("participated_count", 0)
                total = participation_result.get("enrolled_count", 0)
                rate = participation_result.get("participation_rate", 0)
                if total > 0:
                    status_parts.append(f"{participated} of {total} students have participated ({rate}%).")
                non_participants = participation_result.get("non_participants", [])
                if non_participants and len(non_participants) <= 3:
                    names = [s.get("name", "Unknown") for s in non_participants[:3]]
                    status_parts.append(f"Still waiting on: {', '.join(names)}.")
                elif non_participants:
                    status_parts.append(f"{len(non_participants)} students haven't posted yet.")

            # Get post count
            posts_result = _execute_tool(db, 'get_session_posts', {"session_id": session_id, "include_content": False})
            if posts_result and not posts_result.get("error"):
                post_count = posts_result.get("count", 0)
                student_posts = posts_result.get("student_posts", 0)
                if post_count > 0:
                    status_parts.append(f"There are {post_count} posts total, {student_posts} from students.")

            # Get copilot status if available
            if session and session.copilot_active == 1:
                copilot_result = _execute_tool(db, 'get_copilot_suggestions', {"session_id": session_id, "count": 1})
                if copilot_result and not copilot_result.get("error"):
                    latest = copilot_result.get("latest")
                    if latest:
                        # Check engagement level
                        engagement = latest.get("engagement_level")
                        understanding = latest.get("understanding_level")
                        if engagement:
                            status_parts.append(f"Engagement level: {engagement}.")
                        if understanding:
                            status_parts.append(f"Understanding level: {understanding}.")
                        # Check confusion points
                        confusion_points = latest.get("confusion_points", [])
                        if confusion_points:
                            status_parts.append(f"Copilot detected {len(confusion_points)} confusion point{'s' if len(confusion_points) != 1 else ''}.")
                        # Get recommendation
                        recommendation = latest.get("recommendation")
                        if recommendation:
                            status_parts.append(f"Recommendation: {recommendation}")

            message = " ".join(status_parts) if status_parts else "No status information available for this session."

            return {
                "action": "class_status",
                "message": message,
                "session_id": session_id,
                "ui_actions": [
                    {"type": "ui.toast", "payload": {"message": "Class status retrieved", "type": "info"}},
                ],
            }

        # "Who needs help?" - Identify struggling students
        if action == 'who_needs_help':
            course_id = _resolve_course_id(db, current_page, user_id)
            session_id = _resolve_session_id(db, current_page, user_id, course_id)

            if not session_id:
                no_session_msg = generate_voice_response(
                    "No session selected. Ask user to select a session first to identify students who need help.",
                    language=language
                )
                return {
                    "action": "who_needs_help",
                    "message": no_session_msg,
                }

            help_parts = []
            students_needing_help = []

            # Get non-participants
            participation_result = _execute_tool(db, 'get_participation_stats', {"session_id": session_id})
            if participation_result and not participation_result.get("error"):
                non_participants = participation_result.get("non_participants", [])
                if non_participants:
                    names = [s.get("name", "Unknown") for s in non_participants[:5]]
                    help_parts.append(f"Students who haven't participated: {', '.join(names)}")
                    if len(non_participants) > 5:
                        help_parts.append(f"and {len(non_participants) - 5} more.")
                    students_needing_help.extend(non_participants)

            # Get confusion points from copilot
            copilot_result = _execute_tool(db, 'get_copilot_suggestions', {"session_id": session_id, "count": 1})
            if copilot_result and not copilot_result.get("error"):
                latest = copilot_result.get("latest")
                if latest and latest.get("confusion_points"):
                    confusion_points = latest["confusion_points"]
                    help_parts.append(f"Copilot detected {len(confusion_points)} area{'s' if len(confusion_points) != 1 else ''} of confusion:")
                    for i, cp in enumerate(confusion_points[:3], 1):
                        issue = cp.get("issue", "Unknown issue")
                        help_parts.append(f"{i}. {issue[:100]}")

            # Get low scorers if report exists
            scores_result = _execute_tool(db, 'get_student_scores', {"session_id": session_id})
            if scores_result and not scores_result.get("error") and scores_result.get("has_scores"):
                furthest = scores_result.get("furthest_from_correct", {})
                if furthest.get("user_name"):
                    help_parts.append(f"Lowest scorer: {furthest['user_name']} with {furthest.get('score', 0)} points.")

                # Check for students below 50
                student_scores = scores_result.get("student_scores", [])
                low_scorers = [s for s in student_scores if s.get("score", 100) < 50]
                if low_scorers:
                    names = [s.get("user_name", "Unknown") for s in low_scorers[:3]]
                    help_parts.append(f"Students scoring below 50: {', '.join(names)}")

            if not help_parts:
                message = "Good news! No immediate concerns detected. All students seem to be on track."
            else:
                message = " ".join(help_parts)

            return {
                "action": "who_needs_help",
                "message": message,
                "session_id": session_id,
                "students_needing_help": students_needing_help,
                "ui_actions": [
                    {"type": "ui.toast", "payload": {"message": "Help analysis complete", "type": "info"}},
                ],
            }

        # "What were the misconceptions?" - Report Q&A about misconceptions
        if action == 'ask_misconceptions':
            course_id = _resolve_course_id(db, current_page, user_id)
            session_id = _resolve_session_id(db, current_page, user_id, course_id)

            if not session_id:
                no_session_msg = generate_voice_response(
                    "No session selected. Ask user to select a session first to view misconceptions.",
                    language=language
                )
                return {
                    "action": "ask_misconceptions",
                    "message": no_session_msg,
                }

            # Get report data
            report_result = _execute_tool(db, 'get_report', {"session_id": session_id})
            if report_result and report_result.get("error"):
                return report_result

            if not report_result or not report_result.get("has_report"):
                # Try to get from copilot instead
                copilot_result = _execute_tool(db, 'get_copilot_suggestions', {"session_id": session_id, "count": 1})
                if copilot_result and not copilot_result.get("error"):
                    latest = copilot_result.get("latest")
                    if latest and latest.get("confusion_points"):
                        confusion_points = latest["confusion_points"]
                        parts = [f"From copilot analysis, {len(confusion_points)} confusion point{'s' if len(confusion_points) != 1 else ''} detected:"]
                        for i, cp in enumerate(confusion_points[:5], 1):
                            issue = cp.get("issue", "Unknown")
                            parts.append(f"{i}. {issue}")
                        return {
                            "action": "ask_misconceptions",
                            "message": " ".join(parts),
                            "source": "copilot",
                            "confusion_points": confusion_points,
                        }

                return {
                    "action": "ask_misconceptions",
                    "message": "No report available for this session yet. Generate a report first or start the copilot for real-time analysis.",
                }

            misconceptions = report_result.get("misconceptions", [])
            if not misconceptions:
                return {
                    "action": "ask_misconceptions",
                    "message": "No misconceptions were identified in this session's report. Students seem to have understood the material well.",
                }

            parts = [f"The report identified {len(misconceptions)} misconception{'s' if len(misconceptions) != 1 else ''}:"]
            for i, misc in enumerate(misconceptions[:5], 1):
                misconception = misc.get("misconception", "Unknown")
                parts.append(f"{i}. {misconception[:150]}")

            return {
                "action": "ask_misconceptions",
                "message": " ".join(parts),
                "misconceptions": misconceptions,
                "count": len(misconceptions),
            }

        # "How did students score?" - Report Q&A about scores
        if action == 'ask_scores':
            course_id = _resolve_course_id(db, current_page, user_id)
            session_id = _resolve_session_id(db, current_page, user_id, course_id)

            if not session_id:
                no_session_msg = generate_voice_response(
                    "No session selected. Ask user to select a session first to view scores.",
                    language=language
                )
                return {
                    "action": "ask_scores",
                    "message": no_session_msg,
                }

            scores_result = _execute_tool(db, 'get_student_scores', {"session_id": session_id})
            if scores_result and scores_result.get("error"):
                return scores_result

            if not scores_result or not scores_result.get("has_scores"):
                no_scores_msg = generate_voice_response(
                    "No scores available yet. Tell user to generate a report for this session first.",
                    language=language
                )
                return {
                    "action": "ask_scores",
                    "message": no_scores_msg,
                }

            parts = []
            avg = scores_result.get("average_score")
            if avg is not None:
                parts.append(f"The class average is {avg} out of 100.")

            highest = scores_result.get("highest_score")
            lowest = scores_result.get("lowest_score")
            if highest is not None and lowest is not None:
                parts.append(f"Scores range from {lowest} to {highest}.")

            closest = scores_result.get("closest_to_correct", {})
            if closest.get("user_name"):
                parts.append(f"Top performer: {closest['user_name']} with {closest.get('score', 0)}.")

            furthest = scores_result.get("furthest_from_correct", {})
            if furthest.get("user_name"):
                parts.append(f"Lowest scorer: {furthest['user_name']} with {furthest.get('score', 0)}.")

            # Score distribution
            distribution = scores_result.get("score_distribution", {})
            if distribution:
                high_performers = sum(v for k, v in distribution.items() if int(k.split('-')[0]) >= 80)
                low_performers = sum(v for k, v in distribution.items() if int(k.split('-')[0]) < 50)
                if high_performers:
                    parts.append(f"{high_performers} student{'s' if high_performers != 1 else ''} scored 80 or above.")
                if low_performers:
                    parts.append(f"{low_performers} student{'s' if low_performers != 1 else ''} scored below 50.")

            return {
                "action": "ask_scores",
                "message": " ".join(parts) if parts else "Score information is available in the report.",
                "average_score": avg,
                "student_scores": scores_result.get("student_scores", []),
            }

        # "How was participation?" - Report Q&A about participation
        if action == 'ask_participation':
            course_id = _resolve_course_id(db, current_page, user_id)
            session_id = _resolve_session_id(db, current_page, user_id, course_id)

            if not session_id:
                no_session_msg = generate_voice_response(
                    "No session selected. Ask user to select a session first to view participation stats.",
                    language=language
                )
                return {
                    "action": "ask_participation",
                    "message": no_session_msg,
                }

            result = _execute_tool(db, 'get_participation_stats', {"session_id": session_id})
            if result and result.get("error"):
                return result

            # The tool already returns a voice-friendly message
            return {
                "action": "ask_participation",
                "message": result.get("message", "Participation data retrieved."),
                "participation_rate": result.get("participation_rate"),
                "participants": result.get("participants", []),
                "non_participants": result.get("non_participants", []),
            }

        # "Read the latest posts" - Read posts aloud
        if action == 'read_posts':
            course_id = _resolve_course_id(db, current_page, user_id)
            session_id = _resolve_session_id(db, current_page, user_id, course_id)

            if not session_id:
                no_session_msg = generate_voice_response(
                    "No session selected. Ask user to select a session first to read posts.",
                    language=language
                )
                return {
                    "action": "read_posts",
                    "message": no_session_msg,
                }

            result = _execute_tool(db, 'get_latest_posts', {"session_id": session_id, "count": 3})
            if result and result.get("error"):
                return result

            posts = result.get("posts", [])
            if not posts:
                no_posts_msg = generate_voice_response(
                    "No posts in this discussion yet. Tell user.",
                    language=language
                )
                return {
                    "action": "read_posts",
                    "message": no_posts_msg,
                }

            # Format posts for voice reading
            parts = [f"Here are the {len(posts)} most recent posts:"]
            for i, post in enumerate(posts, 1):
                name = post.get("user_name", "Someone")
                content = post.get("content", "")[:200]
                # Clean content for speech
                content = content.replace("\n", " ").strip()
                parts.append(f"{i}. {name} wrote: {content}")

            return {
                "action": "read_posts",
                "message": " ".join(parts),
                "posts": posts,
                "count": len(posts),
            }

        # "What did copilot suggest?" - Copilot suggestions summary
        if action == 'copilot_suggestions':
            course_id = _resolve_course_id(db, current_page, user_id)
            session_id = _resolve_session_id(db, current_page, user_id, course_id)

            if not session_id:
                no_session_msg = generate_voice_response(
                    "No session selected. Ask user to select a session first to get copilot suggestions.",
                    language=language
                )
                return {
                    "action": "copilot_suggestions",
                    "message": no_session_msg,
                }

            # Check if copilot is active
            session = db.query(SessionModel).filter(SessionModel.id == session_id).first()

            result = _execute_tool(db, 'get_copilot_suggestions', {"session_id": session_id, "count": 1})
            if result and result.get("error"):
                return result

            if not result or not result.get("suggestions"):
                if session and session.copilot_active != 1:
                    copilot_off_msg = generate_voice_response(
                        "Copilot is not running. Tell user to say 'start copilot' to begin monitoring.",
                        language=language
                    )
                    return {
                        "action": "copilot_suggestions",
                        "message": copilot_off_msg,
                    }
                no_suggestions_msg = generate_voice_response(
                    "No copilot suggestions yet. Tell user it analyzes the discussion every 90 seconds.",
                    language=language
                )
                return {
                    "action": "copilot_suggestions",
                    "message": no_suggestions_msg,
                }

            latest = result.get("latest", {})
            parts = ["Here's what the copilot suggests:"]

            # Rolling summary
            summary = latest.get("summary")
            if summary:
                parts.append(f"Discussion summary: {summary[:200]}")

            # Confusion points
            confusion_points = latest.get("confusion_points", [])
            if confusion_points:
                parts.append(f"Confusion detected in {len(confusion_points)} area{'s' if len(confusion_points) != 1 else ''}.")
                first_cp = confusion_points[0]
                parts.append(f"Main issue: {first_cp.get('issue', 'Unknown')[:100]}")

            # Suggested prompts
            prompts = latest.get("instructor_prompts", [])
            if prompts:
                parts.append("Suggested question to ask:")
                first_prompt = prompts[0]
                parts.append(f"\"{first_prompt.get('prompt', '')[:150]}\"")

            # Poll suggestion
            poll = latest.get("poll_suggestion")
            if poll:
                parts.append(f"Poll idea: {poll.get('question', '')[:100]}")

            # Overall recommendation
            recommendation = latest.get("recommendation")
            if recommendation:
                parts.append(f"Recommendation: {recommendation}")

            return {
                "action": "copilot_suggestions",
                "message": " ".join(parts),
                "latest": latest,
            }

        # Student lookup - "How is [student] doing?"
        if action == 'student_lookup':
            course_id = _resolve_course_id(db, current_page, user_id)
            session_id = _resolve_session_id(db, current_page, user_id, course_id)

            # Try to extract student name from transcript using LLM
            student_name = _extract_student_name(transcript)

            if not student_name:
                return {
                    "action": "student_lookup",
                    "message": "Which student would you like to know about? Say 'How is [name] doing?'",
                }

            if not session_id:
                return {
                    "action": "student_lookup",
                    "message": f"Please select a session first to check on {student_name}.",
                }

            # Search for student in participation data
            participation_result = _execute_tool(db, 'get_participation_stats', {"session_id": session_id})
            participants = participation_result.get("participants", []) if participation_result else []
            non_participants = participation_result.get("non_participants", []) if participation_result else []

            # Find the student (fuzzy match)
            student_name_lower = student_name.lower()
            found_participant = None
            found_non_participant = None

            for p in participants:
                if student_name_lower in p.get("name", "").lower():
                    found_participant = p
                    break

            for np in non_participants:
                if student_name_lower in np.get("name", "").lower():
                    found_non_participant = np
                    break

            parts = []

            if found_participant:
                name = found_participant.get("name", student_name)
                post_count = found_participant.get("post_count", 0)
                parts.append(f"{name} has participated with {post_count} post{'s' if post_count != 1 else ''}.")

                # Check if they have a score in the report
                scores_result = _execute_tool(db, 'get_student_scores', {"session_id": session_id})
                if scores_result and scores_result.get("has_scores"):
                    student_scores = scores_result.get("student_scores", [])
                    for s in student_scores:
                        if student_name_lower in s.get("user_name", "").lower():
                            parts.append(f"Their score is {s.get('score', 'N/A')} out of 100.")
                            break
            elif found_non_participant:
                name = found_non_participant.get("name", student_name)
                parts.append(f"{name} has not participated in this session yet.")
            else:
                parts.append(f"I couldn't find a student named '{student_name}' in this session.")

            return {
                "action": "student_lookup",
                "message": " ".join(parts),
                "student_name": student_name,
            }

        # Summarize discussion (enhanced version)
        if action == 'summarize_discussion':
            course_id = _resolve_course_id(db, current_page, user_id)
            session_id = _resolve_session_id(db, current_page, user_id, course_id)

            if not session_id:
                no_session_msg = generate_voice_response(
                    "No session selected. Ask user to select a session first to summarize the discussion.",
                    language=language
                )
                return {
                    "action": "summarize_discussion",
                    "message": no_session_msg,
                }

            # Try to get summary from copilot first (most up-to-date)
            copilot_result = _execute_tool(db, 'get_copilot_suggestions', {"session_id": session_id, "count": 1})
            if copilot_result and not copilot_result.get("error"):
                latest = copilot_result.get("latest")
                if latest and latest.get("summary"):
                    return {
                        "action": "summarize_discussion",
                        "message": f"Discussion summary: {latest['summary']}",
                        "source": "copilot",
                    }

            # Fall back to report themes
            report_result = _execute_tool(db, 'get_report', {"session_id": session_id})
            if report_result and report_result.get("has_report"):
                themes = report_result.get("themes", [])
                if themes:
                    theme_names = [t.get("theme", "") for t in themes[:5]]
                    parts = [f"Main themes discussed: {', '.join(theme_names)}."]

                    # Add misconceptions if any
                    misconceptions = report_result.get("misconceptions", [])
                    if misconceptions:
                        parts.append(f"Key misconception: {misconceptions[0].get('misconception', '')[:100]}")

                    return {
                        "action": "summarize_discussion",
                        "message": " ".join(parts),
                        "source": "report",
                        "themes": themes,
                    }

            # Fall back to post count
            posts_result = _execute_tool(db, 'get_session_posts', {"session_id": session_id, "include_content": False})
            if posts_result and not posts_result.get("error"):
                count = posts_result.get("count", 0)
                student_posts = posts_result.get("student_posts", 0)
                return {
                    "action": "summarize_discussion",
                    "message": f"There are {count} posts in this discussion, {student_posts} from students. Start the copilot for a detailed summary.",
                    "source": "posts",
                }

            no_content_msg = generate_voice_response(
                "No discussion content to summarize yet. Tell user.",
                language=language
            )
            return {
                "action": "summarize_discussion",
                "message": no_content_msg,
            }

        # === POLL ACTIONS ===
        if action == 'create_poll':
            course_id = _resolve_course_id(db, current_page, user_id)
            session_id = _resolve_session_id(db, current_page, user_id, course_id)
            # Start conversational poll creation flow
            # First, offer to create a poll (or go directly to asking for question)
            conv_context = conversation_manager.get_context(user_id)
            conv_context.state = ConversationState.AWAITING_POLL_QUESTION
            conv_context.poll_question = ""
            conv_context.poll_options = []
            conv_context.poll_current_option_index = 1
            conversation_manager.save_context(user_id, conv_context)

            poll_msg = generate_voice_response(
                "Opening poll creator. Ask user what question they would like to ask in the poll.",
                language=language
            )
            toast_msg = "Abriendo creador de encuestas..." if language == 'es' else "Opening poll creator..."
            return {
                "action": "create_poll",
                "session_id": session_id,
                "ui_actions": [
                    {"type": "ui.switchTab", "payload": {"tabName": "polls", "target": "tab-polls"}},
                    {"type": "ui.toast", "payload": {"message": toast_msg, "type": "info"}},
                ],
                "message": poll_msg,
                "conversation_state": "poll_creation",
            }

        # === REPORT ACTIONS ===
        if action == 'generate_report':
            course_id = _resolve_course_id(db, current_page, user_id)
            session_id = _resolve_session_id(db, current_page, user_id, course_id)
            if not session_id:
                return None
            result = _execute_tool(db, 'generate_report', {"session_id": session_id})
            if result and user_id:
                context_store.record_action(
                    user_id,
                    action_type="generate_report",
                    action_data={"session_id": session_id},
                    undo_data=None,  # Reports can't be undone
                )
            if result:
                toast_msg = "Generando informe..." if language == 'es' else "Generating report..."
                result["ui_actions"] = [
                    {"type": "ui.navigate", "payload": {"path": "/reports"}},
                    {"type": "ui.toast", "payload": {"message": toast_msg, "type": "info"}},
                ]
            return result

        # === ENROLLMENT ACTIONS ===
        if action == 'list_enrollments':
            course_id = _resolve_course_id(db, current_page, user_id)
            if not course_id:
                return []
            return _execute_tool(db, 'get_enrolled_students', {"course_id": course_id})

        if action == 'manage_enrollments':
            course_id = _resolve_course_id(db, current_page, user_id)

            # If no course selected, navigate to courses page and prompt user to select one
            if not course_id:
                no_course_msg = generate_voice_response(
                    "No course selected. Navigating to courses page and advanced tab. Tell user to select a course first to manage enrollments.",
                    language=language
                )
                return {
                    "action": "manage_enrollments",
                    "course_id": None,
                    "ui_actions": [
                        {"type": "ui.navigate", "payload": {"path": "/courses"}},
                        {"type": "ui.switchTab", "payload": {"tabName": "advanced", "target": "tab-advanced"}},
                    ],
                    "message": no_course_msg,
                }

            # Course is selected - navigate to course page and switch to advanced/enrollment tab
            enroll_msg = generate_voice_response(
                "Opening enrollment management. Tell user they can add or remove students from this course.",
                language=language
            )
            return {
                "action": "manage_enrollments",
                "course_id": course_id,
                "ui_actions": [
                    {"type": "ui.navigate", "payload": {"path": "/courses"}},
                    {"type": "ui.switchTab", "payload": {"tabName": "advanced", "target": "tab-advanced"}},
                ],
                "message": enroll_msg,
            }

        if action == 'list_student_pool':
            # List available students (not enrolled) for selection
            course_id = _resolve_course_id(db, current_page, user_id)
            if not course_id:
                no_course_msg = generate_voice_response(
                    "No course selected. Ask user to select a course first to see the student pool.",
                    language=language
                )
                return {"message": no_course_msg}

            # Get all students using get_users with role=student
            result = _execute_tool(db, 'get_users', {"role": "student"})
            all_students = result.get("users", []) if isinstance(result, dict) else (result if isinstance(result, list) else [])

            # Get enrolled students
            enrolled_result = _execute_tool(db, 'get_enrolled_students', {"course_id": course_id})
            enrolled_students = enrolled_result.get("students", []) if isinstance(enrolled_result, dict) else (enrolled_result if isinstance(enrolled_result, list) else [])
            enrolled_ids = {s.get("user_id") or s.get("id") for s in enrolled_students}

            # Filter to available (not enrolled) students
            available_students = [s for s in all_students if s.get("id") not in enrolled_ids]

            if not available_students:
                pool_empty_msg = generate_voice_response(
                    "Student pool is empty. All students are already enrolled in this course. Tell user.",
                    language=language
                )
                return {"message": pool_empty_msg}

            # Create options for dropdown-style selection
            options = [DropdownOption(label=s.get("name") or s.get("email", f"Student {s['id']}"), value=str(s["id"])) for s in available_students[:10]]

            # Start selection flow
            prompt = conversation_manager.start_dropdown_selection(
                user_id, "student-pool", options, current_page or "/courses"
            )

            return {
                "action": "list_student_pool",
                "message": prompt,
                "students": available_students[:10],
                "ui_actions": [
                    {"type": "ui.toast", "payload": {"message": f"{len(available_students)} students available", "type": "info"}},
                ],
            }

        if action == 'enroll_selected':
            enroll_msg = generate_voice_response(
                "Enrolling the selected students now. Confirm briefly.",
                language=language
            )
            return {
                "action": "enroll_selected",
                "message": enroll_msg,
                "ui_actions": [
                    {"type": "ui.clickButton", "payload": {"target": "enroll-selected"}},
                ],
            }

        if action == 'enroll_all':
            enroll_all_msg = generate_voice_response(
                "Enrolling all available students now. Confirm briefly.",
                language=language
            )
            return {
                "action": "enroll_all",
                "message": enroll_all_msg,
                "ui_actions": [
                    {"type": "ui.clickButton", "payload": {"target": "enroll-all"}},
                ],
            }

        if action == 'select_student':
            # Extract student name from transcript
            student_name = _extract_student_name(transcript or "")
            if not student_name:
                return {"message": "I couldn't hear the student name. Please say the student's name clearly."}

            return {
                "action": "select_student",
                "message": f"Selected {student_name}. Say another student name to select more, or say 'enroll selected' to enroll them.",
                "ui_actions": [
                    {"type": "ui.selectListItem", "payload": {"itemName": student_name, "target": "student-pool"}},
                ],
            }

        # === FORUM/CASE ACTIONS ===
        if action == 'post_case':
            course_id = _resolve_course_id(db, current_page, user_id)
            session_id = _resolve_session_id(db, current_page, user_id, course_id)

            # Check if we're on the console page - offer conversational case creation
            if current_page and '/console' in current_page:
                # Offer to help create a case using conversational flow
                offer_prompt = conversation_manager.offer_case_posting(user_id)
                if offer_prompt:
                    switch_msg = generate_voice_response(
                        f"Switching to Post Case tab. {offer_prompt}",
                        language=language
                    )
                    return {
                        "action": "post_case",
                        "session_id": session_id,
                        "ui_actions": [
                            {"type": "ui.switchTab", "payload": {"tabName": "cases", "target": "tab-cases"}},
                        ],
                        "message": switch_msg,
                        "case_offer": True,
                    }
                else:
                    # User already declined the offer - just switch tab
                    switch_msg = generate_voice_response(
                        "Switching to Post Case tab. User can type their case study here.",
                        language=language
                    )
                    toast_msg = "Cambiado a Publicar Caso" if language == 'es' else "Switched to Post Case tab"
                    return {
                        "action": "post_case",
                        "session_id": session_id,
                        "ui_actions": [
                            {"type": "ui.switchTab", "payload": {"tabName": "cases", "target": "tab-cases"}},
                            {"type": "ui.toast", "payload": {"message": toast_msg, "type": "info"}},
                        ],
                        "message": switch_msg,
                    }

            # If on forum page, switch to cases tab there
            if current_page and '/forum' in current_page:
                switch_msg = generate_voice_response(
                    "Switching to Case Studies tab. Confirm briefly.",
                    language=language
                )
                toast_msg = "Cambiado a Estudios de Caso" if language == 'es' else "Switched to Case Studies tab"
                return {
                    "action": "post_case",
                    "session_id": session_id,
                    "ui_actions": [
                        {"type": "ui.switchTab", "payload": {"tabName": "cases", "target": "tab-cases"}},
                        {"type": "ui.toast", "payload": {"message": toast_msg, "type": "info"}},
                    ],
                    "message": switch_msg,
                }

            # Otherwise navigate to console page and switch to cases tab with offer
            offer_prompt = conversation_manager.offer_case_posting(user_id)
            console_msg = generate_voice_response(
                f"Opening the console. {offer_prompt or 'User can type their case study here.'}",
                language=language
            )
            return {
                "action": "post_case",
                "session_id": session_id,
                "ui_actions": [
                    {"type": "ui.navigate", "payload": {"path": "/console"}},
                    {"type": "ui.switchTab", "payload": {"tabName": "cases", "target": "tab-cases"}},
                ],
                "message": console_msg,
                "case_offer": bool(offer_prompt),
            }

        if action == 'post_to_discussion':
            # Check if we have a session selected
            course_id = _resolve_course_id(db, current_page, user_id)
            session_id = _resolve_session_id(db, current_page, user_id, course_id)
            if not session_id:
                no_session_msg = generate_voice_response(
                    "No live session selected. Ask user to select a live session first before posting to the discussion.",
                    language=language
                )
                return {
                    "action": "post_to_discussion",
                    "error": "no_session",
                    "message": no_session_msg,
                    "ui_actions": [
                        {"type": "ui.navigate", "payload": {"path": "/forum"}},
                    ],
                }

            # Trigger the forum post offer flow
            offer_prompt = conversation_manager.offer_forum_post(user_id)
            if offer_prompt:
                return {
                    "action": "post_to_discussion",
                    "session_id": session_id,
                    "message": offer_prompt,
                    "ui_actions": [
                        {"type": "ui.switchTab", "payload": {"tabName": "discussion", "target": "tab-discussion"}},
                    ],
                    "post_offer": True,
                }
            else:
                # User already declined the offer this session
                declined_msg = generate_voice_response(
                    "User already declined to post earlier. Tell them to let you know if they change their mind.",
                    language=language
                )
                return {
                    "action": "post_to_discussion",
                    "message": declined_msg,
                }

        if action == 'view_posts':
            course_id = _resolve_course_id(db, current_page, user_id)
            session_id = _resolve_session_id(db, current_page, user_id, course_id)
            if session_id:
                posts = _execute_tool(db, 'get_session_posts', {"session_id": session_id})
                if posts:
                    posts_result = {"posts": posts, "count": len(posts)}
                    posts_result["ui_actions"] = [{"type": "ui.navigate", "payload": {"path": "/forum"}}]
                    return posts_result
            return {
                "posts": [],
                "ui_actions": [{"type": "ui.navigate", "payload": {"path": "/forum"}}],
            }

        if action == 'get_pinned_posts':
            course_id = _resolve_course_id(db, current_page, user_id)
            session_id = _resolve_session_id(db, current_page, user_id, course_id)
            if session_id:
                pinned = _execute_tool(db, 'get_pinned_posts', {"session_id": session_id})
                return {
                    "pinned_posts": pinned or [],
                    "count": len(pinned) if pinned else 0,
                    "ui_actions": [{"type": "ui.navigate", "payload": {"path": "/forum"}}],
                }
            return {"pinned_posts": [], "count": 0}

        if action == 'summarize_discussion':
            course_id = _resolve_course_id(db, current_page, user_id)
            session_id = _resolve_session_id(db, current_page, user_id, course_id)
            if session_id:
                posts = _execute_tool(db, 'get_session_posts', {"session_id": session_id})
                if posts and len(posts) > 0:
                    # Extract key info from posts
                    total = len(posts)
                    # Find posts with labels
                    questions = [p for p in posts if p.get('labels_json') and 'question' in p.get('labels_json', [])]
                    misconceptions = [p for p in posts if p.get('labels_json') and 'misconception' in p.get('labels_json', [])]
                    insightful = [p for p in posts if p.get('labels_json') and 'insightful' in p.get('labels_json', [])]
                    pinned = [p for p in posts if p.get('pinned')]

                    return {
                        "total_posts": total,
                        "questions": len(questions),
                        "misconceptions": len(misconceptions),
                        "insightful": len(insightful),
                        "pinned": len(pinned),
                        "latest_topic": posts[0].get('content', '')[:100] if posts else None,
                        "summary": f"The discussion has {total} posts. "
                                   f"{len(questions)} questions, {len(misconceptions)} misconceptions identified, "
                                   f"and {len(insightful)} insightful contributions.",
                    }
                return {"summary": "No posts in this discussion yet.", "total_posts": 0}
            return {"error": "No active session. Select a live session first."}

        if action == 'get_student_questions':
            course_id = _resolve_course_id(db, current_page, user_id)
            session_id = _resolve_session_id(db, current_page, user_id, course_id)
            if session_id:
                posts = _execute_tool(db, 'get_session_posts', {"session_id": session_id})
                if posts:
                    # Filter for posts labeled as questions or containing question marks
                    questions = [
                        p for p in posts
                        if (p.get('labels_json') and 'question' in p.get('labels_json', []))
                        or '?' in p.get('content', '')
                    ]
                    return {
                        "questions": questions,
                        "count": len(questions),
                        "message": f"Found {len(questions)} questions from students."
                    }
                return {"questions": [], "count": 0, "message": "No questions found yet."}
            return {"error": "No active session. Select a live session first."}

        # For actions that need more info, return guidance
        return {"message": f"Action '{action}' recognized but needs more details."}

    except Exception as e:
        print(f"Action execution failed: {e}")
        # Record error and check if we should retry
        if user_id:
            retry_result = conversation_manager.record_error(user_id, str(e))
            if retry_result["should_retry"]:
                return {
                    "error": str(e),
                    "message": retry_result["message"],
                    "retry_count": retry_result["retry_count"],
                    "should_retry": True,
                }
            else:
                return {
                    "error": str(e),
                    "message": retry_result["message"],
                    "retry_count": retry_result["retry_count"],
                    "should_retry": False,
                }
        return {"error": str(e)}


def execute_plan_steps(steps: List[Dict[str, Any]], db: Session) -> tuple[list[dict], str]:
    results = []
    for step in steps:
        tool_name = step.get("tool_name")
        args = step.get("args", {})
        tool_entry = TOOL_REGISTRY.get(tool_name)
        if not tool_entry:
            normalized = normalize_tool_result({"error": f"Unknown tool: {tool_name}"}, tool_name)
            results.append({"tool": tool_name, "success": False, **normalized})
            continue

        error = _validate_tool_args(tool_name, args, tool_entry.get("parameters", {}))
        if error:
            normalized = normalize_tool_result({"error": error}, tool_name)
            results.append({"tool": tool_name, "success": False, **normalized})
            continue

        try:
            normalized = normalize_tool_result(
                invoke_tool_handler(tool_entry["handler"], args, db=db),
                tool_name,
            )
            results.append({"tool": tool_name, "success": normalized.get("ok", True), **normalized})
        except Exception as exc:
            normalized = normalize_tool_result({"error": str(exc)}, tool_name)
            results.append({"tool": tool_name, "success": False, **normalized})

    summary = generate_summary(results)
    return results, summary


# ============================================================================
# OPEN QUESTION HANDLER - LLM-based responses for open-ended questions
# ============================================================================

OPEN_QUESTION_PROMPT = """You are AristAI, an intelligent voice assistant for an educational platform.
You help instructors manage their courses, sessions, students, and classroom activities.

The user asked an open-ended question. Provide a helpful, concise answer suitable for text-to-speech playback.
Keep responses under 3 sentences for most questions. Be conversational and friendly.

PLATFORM CAPABILITIES (mention these when relevant):
- Navigation: Navigate to any page (courses, sessions, forum, console, reports)
- Course Management: Create courses with AI-generated plans, manage enrollments
- Session Management: Create sessions, go live, track participation
- Live Class Tools: Real-time engagement heatmap, session timers, breakout groups
- Copilot: AI teaching assistant that monitors discussions and provides suggestions
- Facilitation: AI suggestions for who to call on next, poll suggestions
- Forum: Discussion posts, pinning, summarizing discussions
- Reports: Participation analytics, scoring, session comparison
- Student Progress: Track individual and class-level progress over time
- AI Draft Responses: Generate draft responses to student questions
- Post-Class: Session summaries, unresolved topic tracking

RECENT FEATURE ENHANCEMENTS (if asked about new features or updates):
- Real-time engagement heatmap showing student participation at a glance
- Session timer for timed activities
- Breakout groups for collaborative learning
- Facilitation suggestions for who to call on next
- Poll suggestions based on discussion topics
- Student progress tracking across sessions
- AI-generated draft responses for student questions
- Pre-class readiness insights
- Post-class session summaries
- Course analytics and session comparison

RULES:
1. Be concise - answers should be speakable in under 15 seconds
2. Be helpful and informative
3. Don't mention specific vendor names (ElevenLabs, OpenAI, etc.)
4. If you don't know something specific, offer related helpful information
5. Suggest related actions the user could take

Current page: {current_page}
User question: "{question}"

Provide a helpful response:"""


async def _handle_open_question(question: str, current_page: Optional[str] = None) -> Dict[str, Any]:
    """
    Handle open-ended questions using LLM to generate contextual responses.
    This enables the voice assistant to answer questions about features,
    capabilities, and general inquiries that don't map to specific actions.
    """
    from workflows.llm_utils import get_llm_with_tracking, invoke_llm_with_metrics

    llm, model_name = get_llm_with_tracking()

    if not llm:
        return {
            "message": "I'm having trouble accessing my knowledge base right now. "
                       "You can ask me to navigate to any page, list your courses, "
                       "or help with specific tasks like creating sessions or polls.",
            "action": "open_question",
        }

    prompt = OPEN_QUESTION_PROMPT.format(
        current_page=current_page or "unknown",
        question=question,
    )

    try:
        response = invoke_llm_with_metrics(llm, prompt, model_name)

        if response.success and response.content:
            # Clean up the response for TTS
            answer = response.content.strip()
            # Remove any markdown formatting
            answer = answer.replace("**", "").replace("*", "").replace("`", "")
            # Limit length for TTS
            if len(answer) > 500:
                # Find a good breakpoint
                sentences = answer.split(". ")
                answer = ". ".join(sentences[:3]) + "."

            return {
                "message": answer,
                "action": "open_question",
            }
        else:
            return {
                "message": "I couldn't process that question. Could you try rephrasing it?",
                "action": "open_question",
            }
    except Exception as e:
        print(f"Error in _handle_open_question: {e}")
        return {
            "message": "I encountered an error while processing your question. "
                       "Please try asking again or ask about a specific feature.",
            "action": "open_question",
        }


def get_page_suggestions(path: str, language: str = 'en') -> List[str]:
    """Get contextual suggestions for a page in the specified language"""
    suggestions = {
        'en': {
            '/courses': ["Create a new course", "Generate session plans", "View enrollments"],
            '/sessions': ["Start a session", "View session details", "Check copilot status"],
            '/forum': ["Post a case study", "View recent posts", "Pin a post"],
            '/console': ["Start copilot", "Create a poll", "View suggestions"],
            '/reports': ["Generate a report", "View participation", "Check scores"],
        },
        'es': {
            '/courses': ["Crear un curso", "Generar planes de sesion", "Ver inscripciones"],
            '/sessions': ["Iniciar sesion", "Ver detalles", "Ver estado del copiloto"],
            '/forum': ["Publicar caso de estudio", "Ver publicaciones recientes", "Fijar publicacion"],
            '/console': ["Iniciar copiloto", "Crear encuesta", "Ver sugerencias"],
            '/reports': ["Generar reporte", "Ver participacion", "Ver calificaciones"],
        }
    }
    lang = language if language in suggestions else 'en'
    default = ["Como puedo ayudarte?"] if lang == 'es' else ["How can I help?"]
    return suggestions[lang].get(path, default)


def get_action_suggestions(action: str, language: str = 'en') -> List[str]:
    """Get follow-up suggestions after an action in the specified language"""
    suggestions_en = {
        # UI interaction suggestions
        'ui_select_course': ["Select a session", "Go to advanced tab", "Generate report"],
        'ui_select_session': ["Go live", "Start copilot", "View forum"],
        'ui_switch_tab': ["What's on this page?", "Go back", "Help me"],
        'ui_click_button': ["What happened?", "What's next?", "Go to another page"],
        # Undo/context suggestions
        'undo_action': ["What's my context?", "Show my courses", "Continue where I was"],
        'get_context': ["Clear context", "Change course", "Change session"],
        'clear_context': ["Show my courses", "Go to sessions", "Help me"],
        # Context/status suggestions
        'get_status': ["Show my courses", "Go to forum", "Start copilot"],
        'get_help': ["Show my courses", "Go to forum", "Create poll"],
        'open_question': ["Tell me more", "Show me an example", "What else can you do?"],
        # Course suggestions
        'list_courses': ["Open a course", "Create new course", "View sessions"],
        'create_course': ["Add syllabus", "Set objectives", "Add students"],
        'select_course': ["View sessions", "Manage enrollments", "Create session"],
        'view_course_details': ["Create session", "View sessions", "Go to forum"],
        # Session suggestions
        'list_sessions': ["Start a session", "Go live", "View details"],
        'create_session': ["Go live", "Set schedule", "View sessions"],
        'select_session': ["Go live", "View details", "Start copilot"],
        'go_live': ["Start copilot", "Create poll", "Post case"],
        'end_session': ["Generate report", "View posts", "Create new session"],
        'view_materials': ["Download file", "View sessions", "Go to forum"],
        # Copilot suggestions
        'start_copilot': ["View suggestions", "Create a poll", "Post case"],
        'stop_copilot': ["Generate report", "View interventions", "Go to forum"],
        'get_interventions': ["Create suggested poll", "Post to forum", "View details"],
        # Poll suggestions
        'create_poll': ["View responses", "Create another poll", "Post case"],
        # Report suggestions
        'generate_report': ["View analytics", "Export report", "Start new session"],
        # Enrollment suggestions
        'list_enrollments': ["Add students", "View participation", "Go to sessions"],
        'manage_enrollments': ["Add by email", "Upload roster", "View enrolled"],
        # Forum suggestions
        'post_case': ["View responses", "Pin post", "Create poll"],
        'post_to_discussion': ["View posts", "Switch to case studies", "Select another session"],
        'view_posts': ["Pin a post", "Label post", "Summarize discussion"],
        'get_pinned_posts': ["View all posts", "Post case", "Create poll"],
        'summarize_discussion': ["Show questions", "View pinned", "Create poll"],
        'get_student_questions': ["View posts", "Create poll", "Pin a post"],
        # High-impact intelligence features
        'class_status': ["Who needs help?", "What did copilot suggest?", "Read latest posts"],
        'who_needs_help': ["Check on a student", "Summarize discussion", "Create poll"],
        'ask_misconceptions': ["How did students score?", "Who needs help?", "Create poll"],
        'ask_scores': ["Who needs help?", "View participation", "Generate report"],
        'ask_participation': ["Who needs help?", "Read latest posts", "Create poll"],
        'read_posts': ["Summarize discussion", "Pin a post", "Create poll"],
        'copilot_suggestions': ["Create suggested poll", "Post to discussion", "Who needs help?"],
        'student_lookup': ["Check another student", "Who needs help?", "View participation"],
    }

    suggestions_es = {
        # UI interaction suggestions
        'ui_select_course': ["Seleccionar sesion", "Ir a pestana avanzada", "Generar reporte"],
        'ui_select_session': ["Iniciar en vivo", "Iniciar copiloto", "Ver foro"],
        'ui_switch_tab': ["Que hay en esta pagina?", "Volver", "Ayudame"],
        'ui_click_button': ["Que paso?", "Que sigue?", "Ir a otra pagina"],
        # Course suggestions
        'list_courses': ["Abrir un curso", "Crear curso nuevo", "Ver sesiones"],
        'create_course': ["Agregar programa", "Definir objetivos", "Agregar estudiantes"],
        'select_course': ["Ver sesiones", "Gestionar inscripciones", "Crear sesion"],
        # Session suggestions
        'list_sessions': ["Iniciar sesion", "Ir en vivo", "Ver detalles"],
        'create_session': ["Ir en vivo", "Programar", "Ver sesiones"],
        'select_session': ["Ir en vivo", "Ver detalles", "Iniciar copiloto"],
        'go_live': ["Iniciar copiloto", "Crear encuesta", "Publicar caso"],
        'end_session': ["Generar reporte", "Ver publicaciones", "Crear nueva sesion"],
        # Copilot suggestions
        'start_copilot': ["Ver sugerencias", "Crear encuesta", "Publicar caso"],
        'stop_copilot': ["Generar reporte", "Ver intervenciones", "Ir al foro"],
        # Poll suggestions
        'create_poll': ["Ver respuestas", "Crear otra encuesta", "Publicar caso"],
        # Report suggestions
        'generate_report': ["Ver analiticas", "Exportar reporte", "Nueva sesion"],
    }

    if language == 'es':
        return suggestions_es.get(action, ["En que mas puedo ayudarte?"])
    return suggestions_en.get(action, ["What else can I help with?"])


def generate_fallback_response(transcript: str, context: Optional[List[str]], current_page: Optional[str] = None, language: str = 'en') -> str:
    """Generate a helpful response when intent is unclear.

    Provides page-specific suggestions based on the user's current location.
    """
    lang = language if language in ['en', 'es'] else 'en'
    # Normalize transcript for matching
    transcript_lower = normalize_spanish_text(transcript.lower())

    # Check for greetings (English + Spanish)
    greetings = ['hi', 'hello', 'hey', 'good morning', 'good afternoon',
                 'hola', 'buenos dias', 'buenas tardes', 'buenas noches']
    if any(g in transcript_lower for g in greetings):
        suggestions = get_page_suggestions(current_page, lang)
        if lang == 'es':
            return f"Hola! Como puedo ayudarte hoy? En esta pagina puedes: {', '.join(suggestions)}."
        return f"Hello! How can I help you today? On this page you can: {', '.join(suggestions)}."

    # Check for thanks (English + Spanish)
    thanks = ['thank', 'thanks', 'appreciate', 'gracias', 'muchas gracias']
    if any(t in transcript_lower for t in thanks):
        if lang == 'es':
            return "De nada! Hay algo mas en que pueda ayudarte?"
        return "You're welcome! Is there anything else I can help you with?"

    # Check for help (English + Spanish)
    help_words = ['help', 'ayuda', 'ayudame']
    if any(h in transcript_lower for h in help_words):
        suggestions = get_page_suggestions(current_page, lang)
        if lang == 'es':
            return f"En esta pagina puedes: {', '.join(suggestions)}. Que te gustaria hacer?"
        return f"On this page, you can: {', '.join(suggestions)}. What would you like to do?"

    # Page-specific fallback suggestions
    page_specific_hints = {
        'en': {
            '/courses': "Try saying 'create a course', 'show my courses', or 'view materials'.",
            '/sessions': "Try saying 'create a session', 'go live', or 'select a session'.",
            '/forum': "Try saying 'post to discussion', 'view posts', or 'switch to case studies'.",
            '/console': "Try saying 'start copilot', 'create a poll', or 'view roster'.",
            '/reports': "Try saying 'generate report', 'view participation', or 'check scores'.",
            '/dashboard': "Try saying 'go to courses', 'go to sessions', or 'go to forum'.",
        },
        'es': {
            '/courses': "Intenta decir 'crear un curso', 'mostrar mis cursos', o 'ver materiales'.",
            '/sessions': "Intenta decir 'crear una sesion', 'iniciar transmision', o 'seleccionar sesion'.",
            '/forum': "Intenta decir 'publicar en discusion', 'ver publicaciones', o 'cambiar a casos'.",
            '/console': "Intenta decir 'iniciar copilot', 'crear encuesta', o 'ver lista'.",
            '/reports': "Intenta decir 'generar informe', 'ver participacion', o 'ver puntuaciones'.",
            '/dashboard': "Intenta decir 'ir a cursos', 'ir a sesiones', o 'ir a foro'.",
        }
    }

    default_hint = {
        'en': "Try saying 'show my courses', 'go to forum', or 'start copilot'.",
        'es': "Intenta decir 'mostrar mis cursos', 'ir a foro', o 'iniciar copilot'.",
    }

    hint = page_specific_hints.get(lang, {}).get(current_page, default_hint.get(lang, default_hint['en']))

    if lang == 'es':
        return f"Escuche '{transcript}', pero no estoy seguro de que te gustaria que hiciera. {hint}"
    return f"I heard '{transcript}', but I'm not sure what you'd like me to do. {hint}"
