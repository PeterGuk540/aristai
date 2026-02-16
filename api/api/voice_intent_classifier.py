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
    INTRODUCTION = "/platform-guide"
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
    # New instructor feature queries
    GET_ENGAGEMENT_HEATMAP = "get_engagement_heatmap"
    GET_DISENGAGED_STUDENTS = "get_disengaged_students"
    GET_FACILITATION_SUGGESTIONS = "get_facilitation_suggestions"
    SUGGEST_NEXT_STUDENT = "suggest_next_student"
    GET_POLL_SUGGESTIONS = "get_poll_suggestions"
    LIST_TEMPLATES = "list_templates"
    GET_STUDENT_PROGRESS = "get_student_progress"
    GET_CLASS_PROGRESS = "get_class_progress"
    GET_BREAKOUT_GROUPS = "get_breakout_groups"
    GET_PRECLASS_STATUS = "get_preclass_status"
    GET_SESSION_SUMMARY = "get_session_summary"
    GET_UNRESOLVED_TOPICS = "get_unresolved_topics"
    COMPARE_SESSIONS = "compare_sessions"
    GET_COURSE_ANALYTICS = "get_course_analytics"
    GET_TIMER_STATUS = "get_timer_status"
    GET_AI_DRAFTS = "get_ai_drafts"
    # Open-ended questions that require LLM reasoning
    OPEN_QUESTION = "open_question"


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
    # New instructor feature controls
    START_TIMER = "start_timer"
    PAUSE_TIMER = "pause_timer"
    RESUME_TIMER = "resume_timer"
    STOP_TIMER = "stop_timer"
    CREATE_BREAKOUT_GROUPS = "create_breakout_groups"
    DISSOLVE_BREAKOUT_GROUPS = "dissolve_breakout_groups"
    SAVE_TEMPLATE = "save_template"
    CLONE_SESSION = "clone_session"
    GENERATE_AI_DRAFT = "generate_ai_draft"
    APPROVE_AI_DRAFT = "approve_ai_draft"
    REJECT_AI_DRAFT = "reject_ai_draft"
    SEND_SESSION_SUMMARY = "send_session_summary"
    # Canvas integration
    PUSH_TO_CANVAS = "push_to_canvas"


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
Go to different PAGES in the application. ONLY these pages exist:
Actions: courses, sessions, forum, console, reports, integrations, introduction, platform_guide, dashboard, profile, voice_guide

CRITICAL: The ONLY valid navigation targets are: courses, sessions, forum, console, reports, integrations, introduction, platform_guide, dashboard, profile, voice_guide
ANYTHING ELSE is NOT a page - it's either a TAB (use UI_ACTION with switch_tab) or a FEATURE (use QUERY).

TABS ARE NOT PAGES! These are tabs within pages, use UI_ACTION category with action=switch_tab:
- advanced, create, join, manage, insights, materials → TABS, not pages
- summary, participation, scoring, analytics → TABS on reports page, not pages
- copilot, polls, cases, tools, requests, roster, discussion → TABS, not pages

Examples of NAVIGATE (going to a whole page):
- "go to courses" / "show me my courses" / "llevame a los cursos" → navigate to courses
- "open the forum" / "ir al foro" → navigate to forum
- "navigate to reports" / "ver reportes" → navigate to reports
- "go to console" / "ir a la consola" → navigate to console
- "open integrations" / "ir a integraciones" → navigate to integrations
- "take me to the introduction page" / "llevame a la introduccion" → navigate to introduction

Examples that are NOT navigation (use UI_ACTION or QUERY instead):
- "take me to advanced" → UI_ACTION switch_tab with tab_name="advanced"
- "go to the analytics tab" → UI_ACTION switch_tab with tab_name="analytics"
- "show me participation" → UI_ACTION switch_tab with tab_name="participation"
- "open the scoring tab" → UI_ACTION switch_tab with tab_name="scoring"
- "show me the engagement heatmap" → QUERY get_engagement_heatmap
- "take me to breakout groups" → QUERY get_breakout_groups

### UI_ACTION (category: "ui_action")
Interact with UI elements like tabs, buttons, forms.
Actions: switch_tab, click_button, select_dropdown, expand_dropdown, fill_input, close_modal

CRITICAL: When the user wants to go to a TAB (not a page), use category=ui_action with action=switch_tab.
Use "take me to X", "go to X", "open X", "show X" with tabs → switch_tab (NOT navigate!)

Available tabs by page (use EXACT tab_name value):
- Console page: copilot, polls, cases, tools, requests, roster
- Forum page: cases, discussion
- Courses page: courses, create, join, advanced
- Sessions page: sessions, materials, create, manage, insights
- Reports page: summary, participation, scoring, analytics

Tab name mapping (spoken phrase → tab_name value):
- "post a case" / "cases" / "case study" / "case studies" → cases
- "discussion" / "post" / "posts" / "forum discussion" → discussion
- "copilot" / "AI copilot" / "assistant" → copilot
- "polls" / "polling" / "create poll" → polls
- "instructor tools" / "tools" / "features" → tools
- "requests" / "instructor requests" / "student requests" → requests
- "roster" / "student roster" / "class list" → roster
- "advanced" / "enrollment" / "instructor access" / "manage enrollment" / "students" → advanced
- "insights" / "session insights" → insights
- "materials" / "session materials" / "class materials" → materials
- "summary" / "report summary" → summary
- "participation" / "engagement" / "participation tab" → participation
- "scoring" / "scores" / "grades" / "answer scores" → scoring
- "analytics" / "analytics tab" / "data analytics" → analytics
- "manage" / "manage status" / "session status" → manage
- "create" / "create new" → create

Examples of switch_tab (use category=ui_action, action=switch_tab):
- "go to the discussion tab" → switch_tab with tab_name="discussion"
- "take me to advanced" → switch_tab with tab_name="advanced"
- "open the analytics tab" → switch_tab with tab_name="analytics"
- "show me participation" → switch_tab with tab_name="participation"
- "switch to post a case" → switch_tab with tab_name="cases"
- "open the polls tab" → switch_tab with tab_name="polls"
- "show instructor tools" → switch_tab with tab_name="tools"
- "go to scoring" → switch_tab with tab_name="scoring"
- "take me to answer scores" → switch_tab with tab_name="scoring"

Examples of click_button:
- "click submit" / "press the create button" / "presionar enviar"
- "click get started" / "open notifications" / "change language"
- "click voice commands" / "open the voice commands button"

Examples of expand_dropdown (open dropdown and list options):
- "select a course" / "select the course" → expand_dropdown (opens dropdown, lists options)
- "show me my courses" / "what courses do I have" → expand_dropdown
- "open the course dropdown" / "show course options" → expand_dropdown
- "select a session" / "choose a session" → expand_dropdown
- "what sessions are available" → expand_dropdown

Examples of select_dropdown (pick a specific option from open dropdown):
- "select the first one" / "choose the second option" → select_dropdown
- "pick the third course" / "use the last one" → select_dropdown
- "seleccionar el primero" / "el segundo" → select_dropdown

Examples of fill_input:
- "the title is Introduction to AI" / "set the description to..." / "el titulo es..."

### QUERY (category: "query")
Ask for information about the class, students, or system.
Actions: class_status, who_needs_help, get_scores, get_participation, get_misconceptions,
         get_interventions, copilot_suggestions, list_courses, list_sessions, list_enrollments,
         view_posts, pinned_posts, summarize_discussion, student_questions, read_posts,
         get_status, get_help, get_context, student_lookup, view_course_details,
         get_engagement_heatmap, get_disengaged_students, get_facilitation_suggestions,
         suggest_next_student, get_poll_suggestions, list_templates, get_student_progress,
         get_class_progress, get_breakout_groups, get_preclass_status, get_session_summary,
         get_unresolved_topics, compare_sessions, get_course_analytics, get_timer_status, get_ai_drafts,
         open_question

Examples:
- "how's the class doing?" / "como va la clase?"
- "who needs help?" / "quien necesita ayuda?"
- "what are the scores?" / "cuales son los puntajes?"
- "how's Maria doing?" / "como esta Juan?"
- "what did the copilot suggest?" / "que sugiere el copilot?"
- "show me the engagement heatmap" / "take me to the heatmap" / "mostrar el mapa de participacion" → get_engagement_heatmap
- "who's not participating?" / "quienes no estan participando?" → get_disengaged_students
- "who should I call on next?" / "a quien deberia llamar?" → suggest_next_student
- "suggest a poll" / "sugerir una encuesta" → get_poll_suggestions
- "how much time is left?" / "show me the timer" / "cuanto tiempo queda?" → get_timer_status
- "how has Maria been doing this semester?" / "como le ha ido a Maria este semestre?" → get_student_progress
- "compare the last three sessions" / "comparar las ultimas tres sesiones" → compare_sessions
- "show me my templates" / "mostrar mis plantillas" → list_templates
- "did students complete the pre-reading?" / "completaron los estudiantes la lectura?" → get_preclass_status
- "what topics need follow-up?" / "que temas necesitan seguimiento?" → get_unresolved_topics
- "show me breakout groups" / "take me to breakout groups" → get_breakout_groups
- "show facilitation suggestions" / "who should speak next?" → get_facilitation_suggestions
- "show me AI drafts" / "draft responses" → get_ai_drafts

For questions about the platform, features, capabilities, or general knowledge that don't fit
into specific data queries above, use action "open_question":
- "what features did you add?" / "que funciones agregaste?"
- "what can you do?" / "que puedes hacer?"
- "tell me about the new updates" / "cuentame sobre las nuevas actualizaciones"
- "how does the heatmap work?" / "como funciona el mapa de calor?"
- "what is this platform for?" / "para que es esta plataforma?"
- "can you explain the analytics?" / "puedes explicar las analiticas?"

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
         open_user_menu, undo_action, clear_context, start_timer, pause_timer,
         resume_timer, stop_timer, create_breakout_groups, dissolve_breakout_groups,
         save_template, clone_session, generate_ai_draft, approve_ai_draft, reject_ai_draft,
         send_session_summary, push_to_canvas

Examples:
- "start the copilot" / "iniciar el copilot"
- "go live" / "make the session live" / "poner en vivo"
- "toggle dark mode" / "cambiar tema"
- "sign me out" / "cerrar sesion"
- "start a 5 minute timer" / "iniciar un temporizador de 5 minutos"
- "pause the timer" / "pausar el temporizador"
- "split into 4 groups" / "dividir en 4 grupos"
- "dissolve the groups" / "disolver los grupos"
- "save this as a template" / "guardar como plantilla"
- "clone this session" / "clonar esta sesion"
- "draft a response to that question" / "escribir una respuesta a esa pregunta"
- "send the session summary to students" / "enviar el resumen a los estudiantes"
- "push to canvas" / "push this session to canvas" / "enviar a canvas" / "publicar en canvas" → push_to_canvas
- "create a canvas announcement" / "post to canvas" / "send to canvas" → push_to_canvas

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

    def __init__(self):
        """
        Initialize the classifier.
        Uses the LLM configured in get_llm_with_tracking() (gpt-4o-mini or claude-3-haiku).
        """
        self._llm = None
        self._model_name = None

    def _ensure_llm(self):
        """Lazy-load the LLM"""
        if self._llm is None:
            llm_result = get_llm_with_tracking()
            if llm_result[0] is None:
                logger.error("[IntentClassifier] No LLM available - check API keys")
                return False
            self._llm, self._model_name = llm_result
            logger.info(f"[IntentClassifier] Initialized with model: {self._model_name}")
        return True

    @property
    def llm(self):
        """Get the LLM instance"""
        self._ensure_llm()
        return self._llm

    @property
    def model_name(self):
        """Get the model name"""
        self._ensure_llm()
        return self._model_name or "unknown"

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
        logger.info(f"[IntentClassifier] Classifying input: '{user_input}'")

        # Ensure LLM is available
        if not self._ensure_llm():
            logger.error("[IntentClassifier] No LLM available, returning fallback")
            return self._fallback_intent(user_input)

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
            logger.info(f"[IntentClassifier] Invoking LLM with model: {self.model_name}")
            response = invoke_llm_with_metrics(self._llm, prompt, self.model_name)

            if not response.success:
                logger.warning(f"[IntentClassifier] LLM call failed: {response.metrics.error_message}")
                return self._fallback_intent(user_input)

            logger.info(f"[IntentClassifier] LLM response (first 500 chars): {response.content[:500] if response.content else 'None'}")

            # Parse the JSON response
            parsed = parse_json_response(response.content or "")
            if not parsed:
                logger.warning(f"[IntentClassifier] Failed to parse JSON from response: {response.content}")
                return self._fallback_intent(user_input)

            logger.info(f"[IntentClassifier] Parsed intent: category={parsed.get('category')}, action={parsed.get('action')}, confidence={parsed.get('confidence')}")

            # Build the ClassifiedIntent from parsed response
            intent = self._build_intent(parsed, user_input)
            logger.info(f"[IntentClassifier] Final intent: {intent.category.value}/{intent.action} (confidence: {intent.confidence})")
            return intent

        except Exception as e:
            logger.error(f"[IntentClassifier] Exception during classification: {e}", exc_info=True)
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
    "integrations": "/integrations",
    "introduction": "/platform-guide",
    "platform_guide": "/platform-guide",
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

    # Instructor Enhancement Feature Query mappings
    "get_engagement_heatmap": "get_engagement_heatmap",
    "get_disengaged_students": "get_disengaged_students",
    "get_facilitation_suggestions": "get_facilitation_suggestions",
    "suggest_next_student": "suggest_next_student",
    "get_poll_suggestions": "get_poll_suggestions",
    "list_templates": "list_templates",
    "get_student_progress": "get_student_progress",
    "get_class_progress": "get_class_progress",
    "get_breakout_groups": "get_breakout_groups",
    "get_preclass_status": "get_preclass_status",
    "get_session_summary": "get_session_summary",
    "get_unresolved_topics": "get_unresolved_topics",
    "compare_sessions": "compare_sessions",
    "get_course_analytics": "get_course_analytics",
    "get_timer_status": "get_timer_status",
    "get_ai_drafts": "get_ai_drafts",
    # Open-ended questions
    "open_question": "open_question",

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

    # Instructor Enhancement Feature Control mappings
    "start_timer": "start_timer",
    "pause_timer": "pause_timer",
    "resume_timer": "resume_timer",
    "stop_timer": "stop_timer",
    "create_breakout_groups": "create_breakout_groups",
    "dissolve_breakout_groups": "dissolve_breakout_groups",
    "save_template": "save_template",
    "clone_session": "clone_session",
    "generate_ai_draft": "generate_ai_draft",
    "approve_ai_draft": "approve_ai_draft",
    "reject_ai_draft": "reject_ai_draft",
    "send_session_summary": "send_session_summary",
    # Canvas integration
    "push_to_canvas": "push_to_canvas",
}

# Navigation targets
NAVIGATION_TARGETS = {
    "courses", "sessions", "forum", "console", "reports", "integrations", "introduction", "platform_guide", "dashboard", "profile", "voice_guide"
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
        action_name = (intent.action or "").strip().lower()
        if action_name in {"/platform-guide", "platform-guide", "/introduction", "introduction", "intro"}:
            action_name = "introduction"
        elif action_name in {"platform guide", "platform_guide"}:
            action_name = "platform_guide"

        # Normalize common page aliases returned by the LLM.
        target_page = (intent.parameters.target_page or "").strip().lower()
        if target_page in {"/platform-guide", "platform-guide", "/introduction", "introduction", "intro"}:
            target_page = "introduction"
        elif target_page in {"platform guide", "platform_guide"}:
            target_page = "platform_guide"

        # Get navigation path from action or parameters
        if action_name in NAVIGATION_TARGETS:
            result["type"] = "navigate"
            result["value"] = INTENT_TO_LEGACY_ACTION.get(action_name, f"/{action_name}")
        elif target_page and target_page.lstrip('/') in NAVIGATION_TARGETS:
            result["type"] = "navigate"
            mapped = INTENT_TO_LEGACY_ACTION.get(target_page.lstrip('/'))
            result["value"] = mapped or target_page
        else:
            # Safety check: If the action is not a valid page, it might be a tab
            # Common tab names that might be mistaken for pages
            TAB_NAMES = {
                'advanced', 'enrollment', 'instructor', 'create', 'join', 'manage', 'insights', 'materials',
                'summary', 'participation', 'scoring', 'analytics',
                'copilot', 'polls', 'cases', 'tools', 'requests', 'roster', 'discussion',
                'switch_tab'
            }
            action_lower = intent.action.lower() if intent.action else ''
            if action_lower in TAB_NAMES or (intent.parameters.tab_name):
                # This is actually a tab switch, not navigation
                logger.warning(f"Correcting misclassified navigation to tab switch: {intent.action}")
                result["type"] = "action"
                result["value"] = "ui_switch_tab"
                result["parameters"]["tabName"] = intent.parameters.tab_name or action_lower
            else:
                # Unknown navigation target - default to dashboard
                logger.warning(f"Unknown navigation target: {intent.action}, defaulting to dashboard")
                result["type"] = "navigate"
                result["value"] = "/dashboard"

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

