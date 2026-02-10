"""
LLM-based Intent Classification for Voice Commands

This module provides intelligent natural language understanding for voice commands,
replacing the rigid regex-based pattern matching with flexible LLM-based intent detection.

The LLM understands user intent regardless of phrasing, language (English/Spanish),
or exact wording, making voice interactions more natural and intuitive.
"""

from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field
from enum import Enum
import json
import logging

from workflows.llm_utils import get_llm_with_tracking, invoke_llm_with_metrics, parse_json_response

logger = logging.getLogger(__name__)


# ============================================================================
# INTENT SCHEMA DEFINITIONS
# ============================================================================

class IntentCategory(str, Enum):
    """High-level intent categories"""
    NAVIGATE = "navigate"           # Go to a page
    UI_ACTION = "ui_action"         # Interact with UI elements (tabs, buttons, forms)
    QUERY = "query"                 # Ask for information
    CREATE = "create"               # Create something (course, session, poll)
    CONTROL = "control"             # Control features (copilot, theme)
    CONFIRM = "confirm"             # Yes/no/cancel confirmations
    DICTATE = "dictate"             # User is providing content for a form field
    UNCLEAR = "unclear"             # Intent not clear, needs clarification


class NavigationTarget(str, Enum):
    """Available navigation destinations"""
    COURSES = "/courses"
    SESSIONS = "/sessions"
    FORUM = "/forum"
    CONSOLE = "/console"
    REPORTS = "/reports"
    DASHBOARD = "/dashboard"
    PROFILE = "/profile"
    VOICE_GUIDE = "/voice-guide"


class UIActionType(str, Enum):
    """Types of UI interactions"""
    SWITCH_TAB = "switch_tab"
    CLICK_BUTTON = "click_button"
    SELECT_DROPDOWN = "select_dropdown"
    EXPAND_DROPDOWN = "expand_dropdown"
    FILL_INPUT = "fill_input"
    CLOSE_MODAL = "close_modal"


class QueryType(str, Enum):
    """Types of information queries"""
    CLASS_STATUS = "class_status"
    WHO_NEEDS_HELP = "who_needs_help"
    GET_SCORES = "get_scores"
    GET_PARTICIPATION = "get_participation"
    GET_MISCONCEPTIONS = "get_misconceptions"
    GET_INTERVENTIONS = "get_interventions"
    COPILOT_SUGGESTIONS = "copilot_suggestions"
    LIST_COURSES = "list_courses"
    LIST_SESSIONS = "list_sessions"
    LIST_ENROLLMENTS = "list_enrollments"
    VIEW_POSTS = "view_posts"
    PINNED_POSTS = "pinned_posts"
    SUMMARIZE_DISCUSSION = "summarize_discussion"
    STUDENT_QUESTIONS = "student_questions"
    READ_POSTS = "read_posts"
    GET_STATUS = "get_status"
    GET_HELP = "get_help"
    GET_CONTEXT = "get_context"
    STUDENT_LOOKUP = "student_lookup"
    VIEW_COURSE_DETAILS = "view_course_details"


class CreateType(str, Enum):
    """Types of creation actions"""
    CREATE_COURSE = "create_course"
    CREATE_SESSION = "create_session"
    CREATE_POLL = "create_poll"
    POST_CASE = "post_case"
    POST_TO_DISCUSSION = "post_to_discussion"
    GENERATE_REPORT = "generate_report"
    ENROLL_STUDENTS = "enroll_students"


class ControlType(str, Enum):
    """Types of control actions"""
    START_COPILOT = "start_copilot"
    STOP_COPILOT = "stop_copilot"
    TOGGLE_THEME = "toggle_theme"
    GO_LIVE = "go_live"
    END_SESSION = "end_session"
    SET_SESSION_DRAFT = "set_session_draft"
    SET_SESSION_COMPLETED = "set_session_completed"
    REFRESH_REPORT = "refresh_report"
    SIGN_OUT = "sign_out"
    OPEN_USER_MENU = "open_user_menu"
    UNDO_ACTION = "undo_action"
    CLEAR_CONTEXT = "clear_context"


class ConfirmationType(str, Enum):
    """Types of confirmation responses"""
    YES = "yes"
    NO = "no"
    CANCEL = "cancel"
    SKIP = "skip"


# ============================================================================
# STRUCTURED OUTPUT MODELS
# ============================================================================

class IntentParameters(BaseModel):
    """Parameters extracted from the user's request"""
    # Navigation
    target_page: Optional[str] = Field(None, description="Target page path for navigation")

    # UI Actions
    tab_name: Optional[str] = Field(None, description="Name of tab to switch to")
    button_name: Optional[str] = Field(None, description="Name/label of button to click")
    dropdown_target: Optional[str] = Field(None, description="Dropdown element to interact with")
    selection_index: Optional[int] = Field(None, description="Index for selection (0-based, or ordinal like 'first'=0)")
    selection_value: Optional[str] = Field(None, description="Value to select by name")
    input_field: Optional[str] = Field(None, description="Name of input field to fill")
    input_value: Optional[str] = Field(None, description="Value to fill in the input")

    # Query parameters
    student_name: Optional[str] = Field(None, description="Name of student to look up")

    # Ordinal extraction
    ordinal: Optional[str] = Field(None, description="Ordinal position: first, second, third, last, etc.")


class ClassifiedIntent(BaseModel):
    """The structured output from intent classification"""
    category: IntentCategory = Field(..., description="High-level intent category")
    action: str = Field(..., description="Specific action within the category")
    parameters: IntentParameters = Field(default_factory=IntentParameters, description="Extracted parameters")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence score 0-1")
    clarification_needed: bool = Field(False, description="Whether clarification is needed")
    clarification_message: Optional[str] = Field(None, description="Question to ask for clarification")
    original_text: Optional[str] = Field(None, description="Original user input")


# ============================================================================
# PAGE CONTEXT FOR SMARTER DECISIONS
# ============================================================================

class PageContext(BaseModel):
    """Context about the current page state for smarter intent detection"""
    current_page: Optional[str] = Field(None, description="Current URL path")
    available_tabs: Optional[List[str]] = Field(None, description="Tabs available on current page")
    available_buttons: Optional[List[str]] = Field(None, description="Buttons visible on current page")
    available_dropdowns: Optional[List[str]] = Field(None, description="Dropdown elements available")
    dropdown_options: Optional[Dict[str, List[str]]] = Field(None, description="Options in each dropdown")
    form_fields: Optional[List[str]] = Field(None, description="Form fields on current page")
    active_course_name: Optional[str] = Field(None, description="Name of currently selected course")
    active_session_name: Optional[str] = Field(None, description="Name of currently selected session")
    is_session_live: Optional[bool] = Field(None, description="Whether current session is live")
    copilot_active: Optional[bool] = Field(None, description="Whether copilot is currently active")


# ============================================================================
# INTENT CLASSIFICATION PROMPT
# ============================================================================

INTENT_CLASSIFICATION_PROMPT = '''You are an intelligent intent classifier for AristAI, a classroom management platform.
Your job is to understand what the user wants to do from their natural language input, regardless of exact phrasing.

The user may speak in English or Spanish. Both languages should be understood equally well.

## Available Actions by Category:

### NAVIGATE (category: "navigate")
Go to different pages in the application.
Actions: courses, sessions, forum, console, reports, dashboard, profile, voice_guide

Examples (any phrasing):
- "go to courses" / "show me my courses" / "I want to see the course page" / "llevame a los cursos"
- "open the forum" / "take me to discussions" / "ir al foro"
- "navigate to reports" / "show analytics" / "ver reportes"

### UI_ACTION (category: "ui_action")
Interact with UI elements like tabs, buttons, forms.
Actions: switch_tab, click_button, select_dropdown, expand_dropdown, fill_input, close_modal

Examples:
- "go to the discussion tab" / "switch to participation" / "cambiar a inscripcion"
- "click submit" / "press the create button" / "presionar enviar"
- "select the first course" / "choose the second option" / "seleccionar el primero"
- "the title is Introduction to AI" / "set the description to..." / "el titulo es..."

### QUERY (category: "query")
Ask for information about the class, students, or system.
Actions: class_status, who_needs_help, get_scores, get_participation, get_misconceptions,
         get_interventions, copilot_suggestions, list_courses, list_sessions, list_enrollments,
         view_posts, pinned_posts, summarize_discussion, student_questions, read_posts,
         get_status, get_help, get_context, student_lookup, view_course_details

Examples:
- "how's the class doing?" / "como va la clase?"
- "who needs help?" / "quien necesita ayuda?"
- "what are the scores?" / "cuales son los puntajes?"
- "how's Maria doing?" / "como esta Juan?"
- "what did the copilot suggest?" / "que sugiere el copilot?"

### CREATE (category: "create")
Create new content like courses, sessions, polls.
Actions: create_course, create_session, create_poll, post_case, post_to_discussion,
         generate_report, enroll_students

Examples:
- "create a new course" / "crear un curso nuevo"
- "start a poll" / "hacer una encuesta"
- "post to the discussion" / "publicar en la discusion"
- "generate the report" / "generar el reporte"

### CONTROL (category: "control")
Control application features and session state.
Actions: start_copilot, stop_copilot, toggle_theme, go_live, end_session,
         set_session_draft, set_session_completed, refresh_report, sign_out,
         open_user_menu, undo_action, clear_context

Examples:
- "start the copilot" / "iniciar el copilot"
- "go live" / "make the session live" / "poner en vivo"
- "toggle dark mode" / "cambiar tema"
- "sign me out" / "cerrar sesion"

### CONFIRM (category: "confirm")
User is confirming or denying a pending action.
Actions: yes, no, cancel, skip

Examples:
- "yes" / "si" / "confirm" / "go ahead" / "do it"
- "no" / "cancel" / "never mind" / "stop"
- "skip" / "next" / "pass"

### DICTATE (category: "dictate")
User is providing content to be entered into a form field.
Actions: dictate_content

This is detected when the user appears to be speaking content for a form rather than giving a command.

### UNCLEAR (category: "unclear")
When you can't determine the intent with sufficient confidence.

Set clarification_needed=true and provide a helpful clarification_message.

## Current Page Context:
{page_context}

## Important Rules:
1. Understand the INTENT, not just keywords. "I want to see my classes" = "go to courses"
2. Handle both English and Spanish naturally
3. Extract all relevant parameters (tab names, button names, ordinals, student names, etc.)
4. If multiple interpretations are possible, choose the most likely based on context
5. Set confidence based on how certain you are (0.0-1.0)
6. If confidence < 0.5, set clarification_needed=true and suggest what to ask
7. For ordinals: "first"=0, "second"=1, "third"=2, "last"=-1

## Response Format:
Return a valid JSON object with this structure:
{{
    "category": "<one of: navigate, ui_action, query, create, control, confirm, dictate, unclear>",
    "action": "<specific action from the lists above>",
    "parameters": {{
        "target_page": "<path if navigating>",
        "tab_name": "<tab name if switching tabs>",
        "button_name": "<button if clicking>",
        "dropdown_target": "<dropdown element>",
        "selection_index": <0-based index or null>,
        "selection_value": "<selection by name or null>",
        "input_field": "<field name>",
        "input_value": "<value to enter>",
        "student_name": "<student name if looking up>",
        "ordinal": "<first/second/third/last if mentioned>"
    }},
    "confidence": <0.0 to 1.0>,
    "clarification_needed": <true/false>,
    "clarification_message": "<question to ask if clarification needed>"
}}

## User Input:
"{user_input}"

Respond with only the JSON object, no additional text.
'''


# ============================================================================
# INTENT CLASSIFIER
# ============================================================================

class VoiceIntentClassifier:
    """LLM-based intent classifier for voice commands"""

    def __init__(self, model_name: str = "claude-3-5-haiku-20241022"):
        """
        Initialize the classifier.

        Args:
            model_name: The LLM model to use. Default is Haiku for speed/cost.
                       Use "claude-sonnet-4-20250514" for more complex understanding.
        """
        self.model_name = model_name
        self._llm = None

    @property
    def llm(self):
        """Lazy-load the LLM"""
        if self._llm is None:
            self._llm = get_llm_with_tracking(self.model_name)
        return self._llm

    def classify(
        self,
        user_input: str,
        page_context: Optional[PageContext] = None,
    ) -> ClassifiedIntent:
        """
        Classify the user's intent from their natural language input.

        Args:
            user_input: The user's voice command/transcript
            page_context: Optional context about the current page state

        Returns:
            ClassifiedIntent with the detected intent and parameters
        """
        # Format page context for the prompt
        if page_context:
            context_str = json.dumps(page_context.model_dump(exclude_none=True), indent=2)
        else:
            context_str = "No page context available"

        # Build the prompt
        prompt = INTENT_CLASSIFICATION_PROMPT.format(
            page_context=context_str,
            user_input=user_input,
        )

        try:
            # Invoke the LLM
            response = invoke_llm_with_metrics(self.llm, prompt, self.model_name)

            if not response.success:
                logger.warning(f"LLM intent classification failed: {response.error}")
                return self._fallback_intent(user_input)

            # Parse the JSON response
            parsed = parse_json_response(response.content or "")
            if not parsed:
                logger.warning(f"Failed to parse intent classification response: {response.content}")
                return self._fallback_intent(user_input)

            # Build the ClassifiedIntent from parsed response
            return self._build_intent(parsed, user_input)

        except Exception as e:
            logger.error(f"Intent classification error: {e}")
            return self._fallback_intent(user_input)

    def _build_intent(self, parsed: Dict[str, Any], original_text: str) -> ClassifiedIntent:
        """Build a ClassifiedIntent from the parsed LLM response"""
        try:
            # Extract parameters
            params_dict = parsed.get("parameters", {})
            parameters = IntentParameters(
                target_page=params_dict.get("target_page"),
                tab_name=params_dict.get("tab_name"),
                button_name=params_dict.get("button_name"),
                dropdown_target=params_dict.get("dropdown_target"),
                selection_index=params_dict.get("selection_index"),
                selection_value=params_dict.get("selection_value"),
                input_field=params_dict.get("input_field"),
                input_value=params_dict.get("input_value"),
                student_name=params_dict.get("student_name"),
                ordinal=params_dict.get("ordinal"),
            )

            return ClassifiedIntent(
                category=IntentCategory(parsed.get("category", "unclear")),
                action=parsed.get("action", "unknown"),
                parameters=parameters,
                confidence=float(parsed.get("confidence", 0.5)),
                clarification_needed=parsed.get("clarification_needed", False),
                clarification_message=parsed.get("clarification_message"),
                original_text=original_text,
            )
        except Exception as e:
            logger.error(f"Error building intent from parsed response: {e}")
            return self._fallback_intent(original_text)

    def _fallback_intent(self, original_text: str) -> ClassifiedIntent:
        """Return a fallback intent when classification fails"""
        return ClassifiedIntent(
            category=IntentCategory.UNCLEAR,
            action="unknown",
            parameters=IntentParameters(),
            confidence=0.0,
            clarification_needed=True,
            clarification_message="I'm not sure what you'd like to do. Could you please rephrase that?",
            original_text=original_text,
        )


# ============================================================================
# FAST CONFIRMATION CHECK (Regex fallback for speed)
# ============================================================================

import re

FAST_CONFIRM_PATTERNS = {
    "yes": r"\b(yes|yeah|yep|sure|okay|ok|confirm|go\s*ahead|do\s*it|proceed|si|claro|adelante|hazlo|de\s*acuerdo)\b",
    "no": r"\b(no|nope|cancel|stop|abort|quit|never\s*mind|cancelar|parar|detener)\b",
    "skip": r"\b(skip|next|pass|later|omitir|siguiente|saltar)\b",
}


def fast_confirmation_check(text: str) -> Optional[str]:
    """
    Fast regex check for simple confirmations.
    Use this BEFORE the LLM classifier for instant response on yes/no/cancel.

    Returns:
        "yes", "no", "skip", or None if not a simple confirmation
    """
    text_lower = text.lower().strip()

    # Very short responses are likely confirmations
    if len(text_lower) <= 15:
        for confirm_type, pattern in FAST_CONFIRM_PATTERNS.items():
            if re.search(pattern, text_lower, re.IGNORECASE):
                return confirm_type

    return None


# ============================================================================
# SINGLETON CLASSIFIER INSTANCE
# ============================================================================

# Global classifier instance (lazy loaded)
_classifier: Optional[VoiceIntentClassifier] = None


def get_intent_classifier() -> VoiceIntentClassifier:
    """Get or create the global intent classifier instance"""
    global _classifier
    if _classifier is None:
        _classifier = VoiceIntentClassifier()
    return _classifier


def classify_intent(
    user_input: str,
    page_context: Optional[PageContext] = None,
    use_fast_confirm: bool = True,
) -> ClassifiedIntent:
    """
    Convenience function to classify user intent.

    Args:
        user_input: The user's voice command
        page_context: Optional context about current page
        use_fast_confirm: If True, check for simple confirmations first (faster)

    Returns:
        ClassifiedIntent with the detected intent
    """
    # Fast path for simple confirmations
    if use_fast_confirm:
        confirm_type = fast_confirmation_check(user_input)
        if confirm_type:
            return ClassifiedIntent(
                category=IntentCategory.CONFIRM,
                action=confirm_type,
                parameters=IntentParameters(),
                confidence=0.95,
                clarification_needed=False,
                original_text=user_input,
            )

    # Use LLM classifier for everything else
    classifier = get_intent_classifier()
    return classifier.classify(user_input, page_context)


# ============================================================================
# INTENT TO LEGACY ACTION MAPPER
# ============================================================================

# Map LLM intent actions to the legacy action names used in voice_converse_router.py
INTENT_TO_LEGACY_ACTION = {
    # Navigation mappings
    "courses": "/courses",
    "sessions": "/sessions",
    "forum": "/forum",
    "console": "/console",
    "reports": "/reports",
    "dashboard": "/dashboard",
    "profile": "/profile",
    "voice_guide": "/voice-guide",

    # UI Action mappings
    "switch_tab": "ui_switch_tab",
    "click_button": "ui_click_button",
    "select_dropdown": "ui_select_dropdown",
    "expand_dropdown": "ui_expand_dropdown",
    "fill_input": "ui_dictate_input",
    "close_modal": "close_modal",

    # Query mappings
    "class_status": "class_status",
    "who_needs_help": "who_needs_help",
    "get_scores": "ask_scores",
    "get_participation": "ask_participation",
    "get_misconceptions": "ask_misconceptions",
    "get_interventions": "get_interventions",
    "copilot_suggestions": "copilot_suggestions",
    "list_courses": "list_courses",
    "list_sessions": "list_sessions",
    "list_enrollments": "list_enrollments",
    "view_posts": "view_posts",
    "pinned_posts": "get_pinned_posts",
    "summarize_discussion": "summarize_discussion",
    "student_questions": "get_student_questions",
    "read_posts": "read_posts",
    "get_status": "get_status",
    "get_help": "get_help",
    "get_context": "get_context",
    "student_lookup": "student_lookup",
    "view_course_details": "view_course_details",

    # Create mappings
    "create_course": "create_course",
    "create_session": "create_session",
    "create_poll": "create_poll",
    "post_case": "post_case",
    "post_to_discussion": "post_to_discussion",
    "generate_report": "generate_report",
    "enroll_students": "manage_enrollments",

    # Control mappings
    "start_copilot": "start_copilot",
    "stop_copilot": "stop_copilot",
    "toggle_theme": "toggle_theme",
    "go_live": "go_live",
    "end_session": "end_session",
    "set_session_draft": "set_session_draft",
    "set_session_completed": "set_session_completed",
    "refresh_report": "refresh_report",
    "sign_out": "sign_out",
    "open_user_menu": "open_user_menu",
    "undo_action": "undo_action",
    "clear_context": "clear_context",
}

# Navigation targets
NAVIGATION_TARGETS = {
    "courses", "sessions", "forum", "console", "reports", "dashboard", "profile", "voice_guide"
}


def intent_to_legacy_format(intent: ClassifiedIntent) -> Dict[str, Any]:
    """
    Convert a ClassifiedIntent to the legacy format used by voice_converse_router.py

    This allows gradual migration from regex-based to LLM-based intent detection
    while keeping the existing action execution logic.

    Returns:
        Dict with:
        - type: "navigate" | "action" | "confirm" | "dictate" | "unclear"
        - value: The navigation path or action name
        - parameters: Extracted parameters (tab name, button name, etc.)
        - confidence: Confidence score
        - clarification_needed: Whether to ask for clarification
        - clarification_message: What to ask
    """
    result = {
        "type": None,
        "value": None,
        "parameters": {},
        "confidence": intent.confidence,
        "clarification_needed": intent.clarification_needed,
        "clarification_message": intent.clarification_message,
        "original_text": intent.original_text,
    }

    if intent.category == IntentCategory.NAVIGATE:
        result["type"] = "navigate"
        # Get navigation path from action or parameters
        if intent.action in NAVIGATION_TARGETS:
            result["value"] = INTENT_TO_LEGACY_ACTION.get(intent.action, f"/{intent.action}")
        elif intent.parameters.target_page:
            result["value"] = intent.parameters.target_page
        else:
            result["value"] = f"/{intent.action}"

    elif intent.category == IntentCategory.UI_ACTION:
        result["type"] = "action"
        result["value"] = INTENT_TO_LEGACY_ACTION.get(intent.action, intent.action)

        # Copy relevant parameters
        if intent.parameters.tab_name:
            result["parameters"]["tabName"] = intent.parameters.tab_name
        if intent.parameters.button_name:
            result["parameters"]["buttonName"] = intent.parameters.button_name
        if intent.parameters.selection_index is not None:
            result["parameters"]["selectionIndex"] = intent.parameters.selection_index
        if intent.parameters.selection_value:
            result["parameters"]["selectionValue"] = intent.parameters.selection_value
        if intent.parameters.input_field:
            result["parameters"]["inputField"] = intent.parameters.input_field
        if intent.parameters.input_value:
            result["parameters"]["inputValue"] = intent.parameters.input_value
        if intent.parameters.ordinal:
            result["parameters"]["ordinal"] = intent.parameters.ordinal

    elif intent.category == IntentCategory.QUERY:
        result["type"] = "action"
        result["value"] = INTENT_TO_LEGACY_ACTION.get(intent.action, intent.action)
        if intent.parameters.student_name:
            result["parameters"]["studentName"] = intent.parameters.student_name

    elif intent.category == IntentCategory.CREATE:
        result["type"] = "action"
        result["value"] = INTENT_TO_LEGACY_ACTION.get(intent.action, intent.action)

    elif intent.category == IntentCategory.CONTROL:
        result["type"] = "action"
        result["value"] = INTENT_TO_LEGACY_ACTION.get(intent.action, intent.action)

    elif intent.category == IntentCategory.CONFIRM:
        result["type"] = "confirm"
        result["value"] = intent.action  # yes, no, cancel, skip

    elif intent.category == IntentCategory.DICTATE:
        result["type"] = "dictate"
        result["value"] = intent.parameters.input_value or intent.original_text
        if intent.parameters.input_field:
            result["parameters"]["inputField"] = intent.parameters.input_field

    else:  # UNCLEAR
        result["type"] = "unclear"
        result["value"] = None

    return result


def build_page_context(
    current_page: Optional[str] = None,
    available_tabs: Optional[List[str]] = None,
    available_buttons: Optional[List[str]] = None,
    active_course_name: Optional[str] = None,
    active_session_name: Optional[str] = None,
    is_session_live: Optional[bool] = None,
    copilot_active: Optional[bool] = None,
) -> PageContext:
    """
    Convenience function to build PageContext from available information.
    """
    return PageContext(
        current_page=current_page,
        available_tabs=available_tabs,
        available_buttons=available_buttons,
        active_course_name=active_course_name,
        active_session_name=active_session_name,
        is_session_live=is_session_live,
        copilot_active=copilot_active,
    )
