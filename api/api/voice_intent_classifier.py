"""
LLM-based Intent Classification for Voice Commands

This module provides intelligent natural language understanding for voice commands,
replacing the rigid regex-based pattern matching with flexible LLM-based intent detection.

The LLM understands user intent regardless of phrasing, language (English/Spanish),
or exact wording, making voice interactions more natural and intuitive.
"""

from typing import Optional, Dict, Any, List
from dataclasses import dataclass
from pydantic import BaseModel, Field
from enum import Enum
import json
import logging

from workflows.llm_utils import get_llm_with_tracking, get_fast_voice_llm, invoke_llm_with_metrics, parse_json_response

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
    # Enhanced AI Features
    GET_LIVE_SUMMARY = "get_live_summary"
    GET_QUESTION_BANK = "get_question_bank"
    GET_PARTICIPATION_INSIGHTS = "get_participation_insights"
    GET_OBJECTIVE_COVERAGE = "get_objective_coverage"
    GET_PEER_REVIEWS = "get_peer_reviews"
    GET_MY_PEER_REVIEWS = "get_my_peer_reviews"
    GET_FOLLOWUPS = "get_followups"
    GET_AI_ASSISTANT_MESSAGES = "get_ai_assistant_messages"
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
    # Enhanced AI Features
    GENERATE_LIVE_SUMMARY = "generate_live_summary"
    GENERATE_AI_GROUPS = "generate_ai_groups"
    GENERATE_FOLLOWUPS = "generate_followups"
    GENERATE_QUESTIONS = "generate_questions"
    ANALYZE_PARTICIPATION = "analyze_participation"
    ANALYZE_OBJECTIVES = "analyze_objectives"
    CREATE_PEER_REVIEWS = "create_peer_reviews"
    TRANSLATE_POSTS = "translate_posts"
    ASK_AI_ASSISTANT = "ask_ai_assistant"


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
- Courses page: courses, create, join, advanced, ai-insights
- Sessions page: sessions, materials, create, manage, insights, ai-features
- Reports page: summary, participation, scoring, analytics, my-performance, best-practice

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
- "ai insights" / "AI insights" / "participation insights" / "objective coverage" → ai-insights
- "ai features" / "AI features" / "enhanced features" / "AI tools" → ai-features
- "summary" / "report summary" / "overview" → summary
- "participation" / "participation tab" → participation
- "scoring" / "scores" / "grades" / "answer scores" → scoring
- "analytics" / "analytics tab" / "data analytics" → analytics
- "my performance" / "my progress" / "student performance" → my-performance
- "best practice" / "best practices" / "best answer" → best-practice
- "manage" / "manage status" / "session status" → manage
- "create" / "create new" → create

Examples of switch_tab (use category=ui_action, action=switch_tab):
- "go to the discussion tab" → switch_tab with tab_name="discussion"
- "take me to advanced" → switch_tab with tab_name="advanced"
- "show me engagement" → switch_tab with tab_name="engagement"
- "show me performance" → switch_tab with tab_name="performance"
- "switch to post a case" → switch_tab with tab_name="cases"
- "open the polls tab" → switch_tab with tab_name="polls"
- "show instructor tools" → switch_tab with tab_name="tools"
- "go to materials" → switch_tab with tab_name="materials"
- "show AI insights" → switch_tab with tab_name="ai-insights"
- "take me to session insights" → switch_tab with tab_name="insights"
- "open manage tab" → switch_tab with tab_name="manage"

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
         get_live_summary, get_question_bank, get_participation_insights, get_objective_coverage,
         get_peer_reviews, get_my_peer_reviews, get_followups, get_ai_assistant_messages,
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
- "show the live summary" / "what's the discussion about?" / "mostrar resumen en vivo" → get_live_summary
- "show the question bank" / "quiz questions" / "mostrar banco de preguntas" → get_question_bank
- "show participation insights" / "participation analysis" / "analisis de participacion" → get_participation_insights
- "show learning objective coverage" / "how well are we covering objectives?" / "cobertura de objetivos" → get_objective_coverage
- "show peer reviews" / "peer review assignments" / "revisiones de pares" → get_peer_reviews
- "my peer reviews" / "reviews assigned to me" / "mis revisiones" → get_my_peer_reviews
- "show student followups" / "personalized feedback" / "seguimientos personalizados" → get_followups
- "show AI assistant messages" / "student questions to AI" / "mensajes del asistente" → get_ai_assistant_messages

For questions about the platform, features, capabilities, or general knowledge that don't fit
into specific data queries above, use action "open_question":
- "what features did you add?" / "que funciones agregaste?"
- "what can you do?" / "que puedes hacer?"
- "tell me about the new updates" / "cuentame sobre las nuevas actualizaciones"
- "how does the heatmap work?" / "como funciona el mapa de calor?"
- "what is this platform for?" / "para que es esta plataforma?"
- "can you explain the analytics?" / "puedes explicar las analiticas?"

### CREATE (category: "create")
Create new content like courses, sessions, polls, or manage enrollments.
Actions: create_course, create_session, create_poll, post_case, post_to_discussion,
         generate_report, manage_enrollments

Examples:
- "create a new course" / "crear un curso nuevo"
- "start a poll" / "hacer una encuesta"
- "post to the discussion" / "publicar en la discusion"
- "generate the report" / "generar el reporte"
- "enroll students" / "enroll some students" / "inscribir estudiantes" → manage_enrollments
- "add students to this course" / "agregar estudiantes" → manage_enrollments
- "manage enrollments" / "manage student enrollment" / "gestionar inscripciones" → manage_enrollments
- "I want to enroll students" / "quiero inscribir estudiantes" → manage_enrollments

### CONTROL (category: "control")
Control application features and session state.
Actions: start_copilot, stop_copilot, toggle_theme, go_live, end_session,
         set_session_draft, set_session_completed, refresh_report, sign_out,
         open_user_menu, undo_action, clear_context, start_timer, pause_timer,
         resume_timer, stop_timer, create_breakout_groups, dissolve_breakout_groups,
         save_template, clone_session, generate_ai_draft, approve_ai_draft, reject_ai_draft,
         send_session_summary, push_to_canvas, generate_live_summary, generate_ai_groups,
         generate_followups, generate_questions, analyze_participation, analyze_objectives,
         create_peer_reviews, translate_posts, ask_ai_assistant

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
- "generate a live summary" / "update the summary" / "generar resumen en vivo" → generate_live_summary
- "create AI groups" / "group students by AI" / "crear grupos con IA" → generate_ai_groups
- "generate followups" / "create personalized feedback" / "generar seguimientos" → generate_followups
- "generate quiz questions" / "create questions from discussion" / "generar preguntas" → generate_questions
- "analyze participation" / "check participation metrics" / "analizar participacion" → analyze_participation
- "analyze objective coverage" / "check learning objectives" / "analizar cobertura" → analyze_objectives
- "create peer review assignments" / "set up peer reviews" / "crear revisiones de pares" → create_peer_reviews
- "translate the posts" / "translate to Spanish" / "traducir publicaciones" → translate_posts
- "ask the AI assistant" / "ask the teaching assistant" / "preguntar al asistente" → ask_ai_assistant

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
    "manage_enrollments": "manage_enrollments",

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
            # Common tab names and related words that might be mistaken for pages
            TAB_NAMES = {
                'advanced', 'enrollment', 'enrollments', 'enroll', 'students', 'instructor',
                'create', 'join', 'manage', 'insights', 'materials',
                'summary', 'participation', 'scoring', 'analytics',
                'copilot', 'polls', 'cases', 'tools', 'requests', 'roster', 'discussion',
                'switch_tab'
            }

            # Actions that should not be navigation (common misclassifications)
            NON_NAVIGATION_ACTIONS = {
                'manage_enrollments', 'enroll_students', 'list_enrollments',
            }
            action_lower = intent.action.lower() if intent.action else ''

            # Check if this is actually a non-navigation action that was misclassified
            if action_lower in NON_NAVIGATION_ACTIONS:
                logger.warning(f"Correcting misclassified navigation to action: {intent.action}")
                result["type"] = "action"
                result["value"] = INTENT_TO_LEGACY_ACTION.get(action_lower, action_lower)
            elif action_lower in TAB_NAMES or (intent.parameters.tab_name):
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


# ============================================================================
# INPUT TYPE CLASSIFICATION FOR FORM FILLING
# ============================================================================
# This classifier determines whether user input during form-filling is:
# - CONTENT: actual data to be entered into a field
# - META: meta-conversation (hesitation, thinking, questions about process)
# - COMMAND: commands like cancel, skip, navigate
# - CONFIRM: yes/no confirmation responses

class InputType(str, Enum):
    """Types of user input during form-filling"""
    CONTENT = "content"  # Actual field content to be saved
    META = "meta"        # Meta-conversation: hesitation, questions, thinking
    COMMAND = "command"  # Commands: cancel, skip, help, navigate
    CONFIRM = "confirm"  # Confirmation: yes/no


class InputTypeResult(BaseModel):
    """Result of input type classification"""
    input_type: InputType
    confidence: float = Field(ge=0.0, le=1.0)
    command: Optional[str] = None  # If COMMAND: cancel, skip, help, etc.
    confirm_value: Optional[str] = None  # If CONFIRM: yes, no
    reason: Optional[str] = None  # Explanation for the classification


INPUT_TYPE_CLASSIFICATION_PROMPT = '''You are an intelligent input classifier for a voice-driven form-filling system.
The user is currently being asked to provide content for a form field. Your job is to determine
whether their response is:

1. **CONTENT** - They are providing actual content/data for the field
2. **META** - They are NOT providing content, but instead:
   - Hesitating ("let me think", "um", "hold on")
   - Asking about the process ("what should I say?", "can you repeat that?")
   - Thinking out loud ("I'm not sure", "let me consider")
   - Stalling ("give me a second", "wait a moment")
3. **COMMAND** - They want to give a command instead of content:
   - Cancel/abort ("cancel", "I don't want to", "never mind", "forget it")
   - Skip ("skip this", "next", "move on")
   - Help ("help", "what can I say?", "what are my options?")
   - Navigate ("go back", "take me to courses")
   - Undo ("undo", "go back")
4. **CONFIRM** - They are responding yes/no to something:
   - Yes ("yes", "yeah", "sure", "okay")
   - No ("no", "nope", "not yet")

## Context:
- The user is being asked: "{field_prompt}"
- Field type: {field_type} (e.g., course title, syllabus, description)
- Current form/workflow: {workflow_name}

## User Input:
"{user_input}"

## Key Distinctions:

### CONTENT vs META
- "Let me think about it" → META (hesitation, not providing a title)
- "Introduction to AI" → CONTENT (actual course title)
- "Let me consider it" → META (not a course title)
- "What should I put here?" → META (question about process)
- "Machine Learning Fundamentals" → CONTENT (actual course title)
- "Hmm, I'm not sure yet" → META (thinking)
- "Give me a moment" → META (stalling)

### CONTENT vs COMMAND
- "I don't want to do this now" → COMMAND (cancel intent)
- "I don't want to miss any details" → could be CONTENT for objectives
- "Cancel" → COMMAND
- "Calculus" → CONTENT (could be a course name)
- "Skip this part" → COMMAND
- "Let's skip to the main topics" → could be CONTENT for syllabus

### Important Context Clues:
- Very short responses (<5 words) that aren't proper nouns are likely META or COMMAND
- Responses with filler words (um, uh, well, hmm) are likely META
- Responses phrased as questions are likely META
- Responses with clear hesitation markers are META
- Responses with task-related verbs (cancel, skip, help, go to) are COMMAND

## Response Format:
Return a JSON object:
{{
    "input_type": "content" | "meta" | "command" | "confirm",
    "confidence": 0.0 to 1.0,
    "command": "cancel" | "skip" | "help" | "navigate" | "undo" | null,
    "confirm_value": "yes" | "no" | null,
    "reason": "Brief explanation of why this classification"
}}

Respond with only the JSON object.
'''


class FormInputClassifier:
    """
    LLM-based classifier for determining input type during form-filling.

    This is more intelligent than pattern matching because it understands context:
    - "Let me consider it" in a course name field = META (hesitation)
    - "Consider All Options" in a course name field = CONTENT (actual title)
    """

    def __init__(self):
        self._llm = None
        self._model_name = None

    def _ensure_llm(self):
        """Lazy-load the LLM"""
        if self._llm is None:
            llm_result = get_llm_with_tracking()
            if llm_result[0] is None:
                logger.error("[FormInputClassifier] No LLM available - check API keys")
                return False
            self._llm, self._model_name = llm_result
            logger.info(f"[FormInputClassifier] Initialized with model: {self._model_name}")
        return True

    def classify_input(
        self,
        user_input: str,
        field_prompt: str,
        field_type: str,
        workflow_name: str = "form_filling"
    ) -> InputTypeResult:
        """
        Classify whether user input is actual content or meta-conversation.

        Args:
            user_input: What the user said
            field_prompt: The prompt shown to the user (e.g., "What would you like to name your course?")
            field_type: Type of field (e.g., "course_title", "syllabus", "description")
            workflow_name: Name of the current workflow

        Returns:
            InputTypeResult with classification
        """
        logger.info(f"[FormInputClassifier] Classifying: '{user_input}' for field '{field_type}'")

        # Quick checks for obvious cases before using LLM
        quick_result = self._quick_classify(user_input)
        if quick_result:
            logger.info(f"[FormInputClassifier] Quick classification: {quick_result.input_type}")
            return quick_result

        # Use LLM for ambiguous cases
        if not self._ensure_llm():
            # Fallback: assume content if LLM unavailable
            return InputTypeResult(
                input_type=InputType.CONTENT,
                confidence=0.5,
                reason="LLM unavailable, defaulting to content"
            )

        prompt = INPUT_TYPE_CLASSIFICATION_PROMPT.format(
            field_prompt=field_prompt,
            field_type=field_type,
            workflow_name=workflow_name,
            user_input=user_input,
        )

        try:
            response = invoke_llm_with_metrics(self._llm, prompt, self._model_name)

            if not response.success:
                logger.warning(f"[FormInputClassifier] LLM call failed: {response.metrics.error_message}")
                return self._fallback_result(user_input)

            parsed = parse_json_response(response.content or "")
            if not parsed:
                logger.warning(f"[FormInputClassifier] Failed to parse: {response.content}")
                return self._fallback_result(user_input)

            result = InputTypeResult(
                input_type=InputType(parsed.get("input_type", "content")),
                confidence=float(parsed.get("confidence", 0.7)),
                command=parsed.get("command"),
                confirm_value=parsed.get("confirm_value"),
                reason=parsed.get("reason"),
            )

            logger.info(f"[FormInputClassifier] Result: {result.input_type} (confidence: {result.confidence}) - {result.reason}")
            return result

        except Exception as e:
            logger.error(f"[FormInputClassifier] Error: {e}", exc_info=True)
            return self._fallback_result(user_input)

    def _quick_classify(self, user_input: str) -> Optional[InputTypeResult]:
        """
        Quick pattern-based classification for obvious cases.
        Returns None if ambiguous (needs LLM).
        """
        text = user_input.lower().strip()

        # Very short single-word confirmations
        if len(text.split()) <= 2:
            # Clear confirmations
            if text in {'yes', 'yeah', 'yep', 'sure', 'okay', 'ok', 'si', 'sí', 'claro', 'dale'}:
                return InputTypeResult(
                    input_type=InputType.CONFIRM,
                    confidence=0.95,
                    confirm_value="yes",
                    reason="Clear affirmative response"
                )
            if text in {'no', 'nope', 'nah', 'not yet', 'no gracias'}:
                return InputTypeResult(
                    input_type=InputType.CONFIRM,
                    confidence=0.95,
                    confirm_value="no",
                    reason="Clear negative response"
                )

            # Clear commands
            if text in {'cancel', 'cancelar', 'abort', 'stop', 'quit', 'exit'}:
                return InputTypeResult(
                    input_type=InputType.COMMAND,
                    confidence=0.95,
                    command="cancel",
                    reason="Clear cancel command"
                )
            if text in {'skip', 'next', 'pass', 'saltar', 'siguiente'}:
                return InputTypeResult(
                    input_type=InputType.COMMAND,
                    confidence=0.95,
                    command="skip",
                    reason="Clear skip command"
                )
            if text in {'help', 'ayuda', 'help me'}:
                return InputTypeResult(
                    input_type=InputType.COMMAND,
                    confidence=0.95,
                    command="help",
                    reason="Clear help request"
                )

            # Clear hesitation fillers
            if text in {'um', 'uh', 'hmm', 'umm', 'uhh', 'eh', 'este', 'pues'}:
                return InputTypeResult(
                    input_type=InputType.META,
                    confidence=0.95,
                    reason="Filler word/hesitation"
                )

        # None = needs LLM classification
        return None

    def _fallback_result(self, user_input: str) -> InputTypeResult:
        """Fallback when LLM fails - conservative approach"""
        # If we can't classify, lean toward treating as content
        # but with low confidence so caller can decide to re-prompt
        return InputTypeResult(
            input_type=InputType.CONTENT,
            confidence=0.4,
            reason="Classification failed, assuming content with low confidence"
        )


# Global form input classifier instance
_form_input_classifier: Optional[FormInputClassifier] = None


def get_form_input_classifier() -> FormInputClassifier:
    """Get or create the global form input classifier"""
    global _form_input_classifier
    if _form_input_classifier is None:
        _form_input_classifier = FormInputClassifier()
    return _form_input_classifier


def classify_form_input(
    user_input: str,
    field_prompt: str,
    field_type: str = "text",
    workflow_name: str = "form_filling"
) -> InputTypeResult:
    """
    Convenience function to classify form input.

    Usage:
        result = classify_form_input(
            user_input="Let me think about it",
            field_prompt="What would you like to name your course?",
            field_type="course_title",
            workflow_name="create_course"
        )

        if result.input_type == InputType.META:
            # Re-prompt the user, don't use this as the field value
            pass
        elif result.input_type == InputType.CONTENT:
            # Use as field value
            pass
        elif result.input_type == InputType.COMMAND:
            # Handle command (cancel, skip, etc.)
            pass
    """
    classifier = get_form_input_classifier()
    return classifier.classify_input(user_input, field_prompt, field_type, workflow_name)


# =============================================================================
# PHASE 6: LLM-BASED UI INTERACTION CLASSIFIERS
# =============================================================================
# These classifiers use LLM to intelligently identify UI elements without
# relying on hard-coded pattern matching.

class UIElementType(str, Enum):
    """Types of UI elements that can be identified"""
    TAB = "tab"
    BUTTON = "button"
    DROPDOWN = "dropdown"
    INPUT = "input"
    NAVIGATION = "navigation"
    NONE = "none"


@dataclass
class UIElementResult:
    """Result of UI element identification"""
    element_type: UIElementType
    element_name: Optional[str] = None  # The identified element (e.g., "advanced", "create poll")
    confidence: float = 0.0
    voice_id: Optional[str] = None  # The data-voice-id if known
    reason: Optional[str] = None


TAB_IDENTIFICATION_PROMPT = '''You are identifying tab names from voice commands in an educational platform.

Available tabs on the current page:
{available_tabs}

User's voice command: "{user_input}"

Determine if the user wants to switch to a specific tab.

Examples:
- "go to the advanced tab" → tab: "advanced"
- "switch to manage status" → tab: "manage" (matches "manage status")
- "open the discussion section" → tab: "discussion"
- "let me see the polling" → tab: "polls"
- "show me the roster" → tab: "roster"
- "ir a la pestaña avanzada" → tab: "advanced" (Spanish)
- "cambiar a discusión" → tab: "discussion" (Spanish)

Respond with ONLY valid JSON:
{{
    "identified": true/false,
    "tab_name": "exact_tab_name_from_list" or null,
    "confidence": 0.0-1.0,
    "reason": "brief explanation"
}}

If the user is NOT trying to switch tabs, set identified=false.'''


BUTTON_IDENTIFICATION_PROMPT = '''You are identifying button actions from voice commands in an educational platform.

Available buttons on the current page:
{available_buttons}

User's voice command: "{user_input}"

Determine if the user wants to click a specific button.

Examples:
- "click create course" → button: "create-course"
- "submit the form" → button matching "submit" or "create"
- "go live" → button: "go-live" or "start-session"
- "launch the poll" → button: "launch-poll" or "create-poll"
- "crear curso" → button: "create-course" (Spanish)
- "publicar caso" → button: "post-case" (Spanish)

Respond with ONLY valid JSON:
{{
    "identified": true/false,
    "button_name": "exact_button_voice_id" or null,
    "confidence": 0.0-1.0,
    "reason": "brief explanation"
}}

If the user is NOT trying to click a button, set identified=false.'''


DROPDOWN_SELECTION_PROMPT = '''You are selecting dropdown options from voice commands in an educational platform.

Dropdown: {dropdown_name}
Available options:
{available_options}

User's voice command: "{user_input}"

Determine which option the user wants to select.

Examples:
- "the first one" → ordinal selection (1st item)
- "select Introduction to AI" → match by name
- "pick the third option" → ordinal selection (3rd item)
- "el segundo" → ordinal selection (2nd, Spanish)
- "seleccionar el curso de matemáticas" → match by name (Spanish)

Respond with ONLY valid JSON:
{{
    "identified": true/false,
    "selection_type": "ordinal" or "name" or null,
    "ordinal_index": 0-based index or null,
    "matched_name": "exact option name" or null,
    "confidence": 0.0-1.0,
    "reason": "brief explanation"
}}

If the user is NOT making a selection, set identified=false.'''


class UIElementClassifier:
    """LLM-based classifier for UI elements."""

    def __init__(self):
        self._llm = None
        self._model_name = None

    def _ensure_llm(self) -> bool:
        """Ensure LLM is initialized."""
        if self._llm is None:
            self._llm, self._model_name = get_llm_with_tracking()
        return self._llm is not None

    def identify_tab(
        self,
        user_input: str,
        available_tabs: List[str],
        language: str = "en"
    ) -> UIElementResult:
        """
        Identify which tab the user wants to switch to.

        Args:
            user_input: The user's voice command
            available_tabs: List of tab names available on the current page
            language: Current language for context

        Returns:
            UIElementResult with identified tab
        """
        if not available_tabs:
            return UIElementResult(element_type=UIElementType.NONE, reason="No tabs available")

        if not self._ensure_llm():
            return UIElementResult(element_type=UIElementType.NONE, reason="LLM unavailable")

        tabs_str = "\n".join([f"- {tab}" for tab in available_tabs])
        prompt = TAB_IDENTIFICATION_PROMPT.format(
            available_tabs=tabs_str,
            user_input=user_input
        )

        try:
            response = invoke_llm_with_metrics(self._llm, prompt, self._model_name)
            if not response.success:
                return UIElementResult(element_type=UIElementType.NONE, reason="LLM call failed")

            parsed = parse_json_response(response.content or "")
            if not parsed or not parsed.get("identified"):
                return UIElementResult(element_type=UIElementType.NONE, reason="Not a tab switch request")

            tab_name = parsed.get("tab_name")
            if tab_name and tab_name in available_tabs:
                return UIElementResult(
                    element_type=UIElementType.TAB,
                    element_name=tab_name,
                    confidence=float(parsed.get("confidence", 0.7)),
                    reason=parsed.get("reason")
                )

            # Fuzzy match - find closest tab
            tab_lower = (tab_name or "").lower()
            for avail_tab in available_tabs:
                if tab_lower in avail_tab.lower() or avail_tab.lower() in tab_lower:
                    return UIElementResult(
                        element_type=UIElementType.TAB,
                        element_name=avail_tab,
                        confidence=float(parsed.get("confidence", 0.6)),
                        reason=f"Fuzzy matched '{tab_name}' to '{avail_tab}'"
                    )

            return UIElementResult(element_type=UIElementType.NONE, reason="Tab not found in available options")

        except Exception as e:
            logger.error(f"[UIElementClassifier] Tab identification error: {e}", exc_info=True)
            return UIElementResult(element_type=UIElementType.NONE, reason=str(e))

    def identify_button(
        self,
        user_input: str,
        available_buttons: List[Dict[str, str]],  # [{"voice_id": "...", "label": "..."}]
        language: str = "en"
    ) -> UIElementResult:
        """
        Identify which button the user wants to click.

        Args:
            user_input: The user's voice command
            available_buttons: List of button info with voice_id and label
            language: Current language for context

        Returns:
            UIElementResult with identified button
        """
        if not available_buttons:
            return UIElementResult(element_type=UIElementType.NONE, reason="No buttons available")

        if not self._ensure_llm():
            return UIElementResult(element_type=UIElementType.NONE, reason="LLM unavailable")

        buttons_str = "\n".join([
            f"- {btn.get('voice_id', 'unknown')}: {btn.get('label', btn.get('voice_id', ''))}"
            for btn in available_buttons
        ])
        prompt = BUTTON_IDENTIFICATION_PROMPT.format(
            available_buttons=buttons_str,
            user_input=user_input
        )

        try:
            response = invoke_llm_with_metrics(self._llm, prompt, self._model_name)
            if not response.success:
                return UIElementResult(element_type=UIElementType.NONE, reason="LLM call failed")

            parsed = parse_json_response(response.content or "")
            if not parsed or not parsed.get("identified"):
                return UIElementResult(element_type=UIElementType.NONE, reason="Not a button click request")

            button_name = parsed.get("button_name")
            # Find matching button by voice_id
            for btn in available_buttons:
                if btn.get("voice_id") == button_name:
                    return UIElementResult(
                        element_type=UIElementType.BUTTON,
                        element_name=btn.get("label", button_name),
                        voice_id=button_name,
                        confidence=float(parsed.get("confidence", 0.7)),
                        reason=parsed.get("reason")
                    )

            # Fuzzy match
            btn_lower = (button_name or "").lower()
            for btn in available_buttons:
                voice_id = btn.get("voice_id", "").lower()
                label = btn.get("label", "").lower()
                if btn_lower in voice_id or btn_lower in label or voice_id in btn_lower:
                    return UIElementResult(
                        element_type=UIElementType.BUTTON,
                        element_name=btn.get("label"),
                        voice_id=btn.get("voice_id"),
                        confidence=float(parsed.get("confidence", 0.6)),
                        reason=f"Fuzzy matched to '{btn.get('voice_id')}'"
                    )

            return UIElementResult(element_type=UIElementType.NONE, reason="Button not found")

        except Exception as e:
            logger.error(f"[UIElementClassifier] Button identification error: {e}", exc_info=True)
            return UIElementResult(element_type=UIElementType.NONE, reason=str(e))

    def identify_dropdown_selection(
        self,
        user_input: str,
        dropdown_name: str,
        available_options: List[Dict[str, str]],  # [{"value": "...", "label": "..."}]
        language: str = "en"
    ) -> UIElementResult:
        """
        Identify which dropdown option the user wants to select.

        Args:
            user_input: The user's voice command
            dropdown_name: Name of the dropdown (e.g., "course", "session")
            available_options: List of option info with value and label
            language: Current language for context

        Returns:
            UIElementResult with selection info
        """
        if not available_options:
            return UIElementResult(element_type=UIElementType.NONE, reason="No options available")

        if not self._ensure_llm():
            return UIElementResult(element_type=UIElementType.NONE, reason="LLM unavailable")

        options_str = "\n".join([
            f"{i+1}. {opt.get('label', opt.get('value', 'Unknown'))}"
            for i, opt in enumerate(available_options)
        ])
        prompt = DROPDOWN_SELECTION_PROMPT.format(
            dropdown_name=dropdown_name,
            available_options=options_str,
            user_input=user_input
        )

        try:
            response = invoke_llm_with_metrics(self._llm, prompt, self._model_name)
            if not response.success:
                return UIElementResult(element_type=UIElementType.NONE, reason="LLM call failed")

            parsed = parse_json_response(response.content or "")
            if not parsed or not parsed.get("identified"):
                return UIElementResult(element_type=UIElementType.NONE, reason="Not a selection request")

            selection_type = parsed.get("selection_type")

            if selection_type == "ordinal":
                idx = parsed.get("ordinal_index")
                if idx is not None and 0 <= idx < len(available_options):
                    selected = available_options[idx]
                    return UIElementResult(
                        element_type=UIElementType.DROPDOWN,
                        element_name=selected.get("label"),
                        voice_id=selected.get("value"),
                        confidence=float(parsed.get("confidence", 0.8)),
                        reason=f"Ordinal selection: item {idx + 1}"
                    )

            elif selection_type == "name":
                matched_name = parsed.get("matched_name", "").lower()
                for opt in available_options:
                    if matched_name in opt.get("label", "").lower():
                        return UIElementResult(
                            element_type=UIElementType.DROPDOWN,
                            element_name=opt.get("label"),
                            voice_id=opt.get("value"),
                            confidence=float(parsed.get("confidence", 0.7)),
                            reason=f"Name matched: {opt.get('label')}"
                        )

            return UIElementResult(element_type=UIElementType.NONE, reason="Could not match selection")

        except Exception as e:
            logger.error(f"[UIElementClassifier] Dropdown selection error: {e}", exc_info=True)
            return UIElementResult(element_type=UIElementType.NONE, reason=str(e))


# Global UI element classifier instance
_ui_element_classifier: Optional[UIElementClassifier] = None


def get_ui_element_classifier() -> UIElementClassifier:
    """Get or create the global UI element classifier"""
    global _ui_element_classifier
    if _ui_element_classifier is None:
        _ui_element_classifier = UIElementClassifier()
    return _ui_element_classifier


def classify_tab_switch(
    user_input: str,
    available_tabs: List[str],
    language: str = "en"
) -> UIElementResult:
    """
    Convenience function to identify tab switch intent.

    Usage:
        result = classify_tab_switch(
            user_input="go to the advanced settings",
            available_tabs=["create", "manage", "advanced", "instructor"],
            language="en"
        )

        if result.element_type == UIElementType.TAB:
            switch_to_tab(result.element_name)
    """
    classifier = get_ui_element_classifier()
    return classifier.identify_tab(user_input, available_tabs, language)


def classify_button_click(
    user_input: str,
    available_buttons: List[Dict[str, str]],
    language: str = "en"
) -> UIElementResult:
    """
    Convenience function to identify button click intent.

    Usage:
        result = classify_button_click(
            user_input="click create course",
            available_buttons=[
                {"voice_id": "create-course", "label": "Create Course"},
                {"voice_id": "import-course", "label": "Import Course"}
            ],
            language="en"
        )

        if result.element_type == UIElementType.BUTTON:
            click_button(result.voice_id)
    """
    classifier = get_ui_element_classifier()
    return classifier.identify_button(user_input, available_buttons, language)


def classify_dropdown_selection(
    user_input: str,
    dropdown_name: str,
    available_options: List[Dict[str, str]],
    language: str = "en"
) -> UIElementResult:
    """
    Convenience function to identify dropdown selection.

    Usage:
        result = classify_dropdown_selection(
            user_input="the second one",
            dropdown_name="course",
            available_options=[
                {"value": "1", "label": "Introduction to AI"},
                {"value": "2", "label": "Machine Learning Basics"}
            ],
            language="en"
        )

        if result.element_type == UIElementType.DROPDOWN:
            select_option(result.voice_id, result.element_name)
    """
    classifier = get_ui_element_classifier()
    return classifier.identify_dropdown_selection(user_input, dropdown_name, available_options, language)


# =============================================================================
# PHASE 6: LLM-BASED RESPONSE GENERATOR
# =============================================================================
# Instead of hardcoded response templates, use LLM to generate natural responses
# in the user's selected language.

RESPONSE_GENERATION_PROMPT = '''You are a friendly voice assistant for AristAI, a classroom management platform.
Generate a natural, conversational response for the given situation.

=== CRITICAL LANGUAGE RULE ===
The user has SELECTED {language_name} as their interface language.
You MUST respond ENTIRELY in {language_name}.

STRICT REQUIREMENTS:
- Every single word of your response MUST be in {language_name}.
- Do NOT detect or auto-switch based on what language the user spoke.
- Do NOT mix languages under any circumstances.
- If user spoke in a different language, still respond in {language_name}.

Examples for {language_name}:
- If {language_name} is Spanish: "Llevándote a la página de cursos." (NOT "Taking you...")
- If {language_name} is English: "Taking you to the courses page." (NOT "Llevándote...")
=== END LANGUAGE RULE ===

Situation: {situation}
Context: {context}
Data: {data}

Requirements:
1. Keep the response concise (1-2 sentences max for voice)
2. Be friendly and helpful
3. Use natural spoken language (this will be read aloud by text-to-speech)
4. Include relevant details from the data if provided
5. If suggesting next actions, limit to 2-3 options

Respond with ONLY the message text in {language_name}, no JSON or formatting.'''


class LLMResponseGenerator:
    """LLM-based response generator for voice commands."""

    def __init__(self):
        self._llm = None
        self._model_name = None

    def _ensure_llm(self) -> bool:
        """Ensure LLM is initialized with fast voice settings."""
        if self._llm is None:
            # Use fast voice LLM (lower temperature, max_tokens) for quicker responses
            self._llm, self._model_name = get_fast_voice_llm()
        return self._llm is not None

    def generate_response(
        self,
        situation: str,
        language: str = "en",
        context: Optional[str] = None,
        data: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Generate a natural language response using LLM.

        Args:
            situation: Description of what happened or needs to be communicated
            language: Target language code ('en' or 'es')
            context: Additional context about the conversation
            data: Any relevant data to include in the response

        Returns:
            Generated response string in the target language
        """
        if not self._ensure_llm():
            # Fallback to simple response if LLM unavailable
            return situation

        language_name = "Spanish" if language == "es" else "English"

        prompt = RESPONSE_GENERATION_PROMPT.format(
            language_name=language_name,
            situation=situation,
            context=context or "Voice assistant interaction",
            data=json.dumps(data) if data else "None"
        )

        try:
            response = invoke_llm_with_metrics(self._llm, prompt, self._model_name)
            if response.success and response.content:
                return response.content.strip()
            return situation  # Fallback
        except Exception as e:
            logger.error(f"[LLMResponseGenerator] Error: {e}", exc_info=True)
            return situation  # Fallback


# Global response generator instance
_response_generator: Optional[LLMResponseGenerator] = None


def get_response_generator() -> LLMResponseGenerator:
    """Get or create the global response generator"""
    global _response_generator
    if _response_generator is None:
        _response_generator = LLMResponseGenerator()
    return _response_generator


def generate_llm_response(
    situation: str,
    language: str = "en",
    context: Optional[str] = None,
    data: Optional[Dict[str, Any]] = None,
) -> str:
    """
    Convenience function to generate LLM-based responses.

    Usage:
        # Simple response
        response = generate_llm_response(
            situation="User wants to navigate to the courses page",
            language="es"
        )
        # → "Llevándote a la página de cursos."

        # Response with data
        response = generate_llm_response(
            situation="Tell the user about their courses",
            language="en",
            data={"count": 3, "names": ["Statistics 101", "AI Basics", "Data Science"]}
        )
        # → "You have 3 courses: Statistics 101, AI Basics, and Data Science. Which would you like to open?"

        # Response with context
        response = generate_llm_response(
            situation="Confirm the action was completed",
            language="es",
            context="User just created a new course"
        )
        # → "¡Listo! El curso ha sido creado exitosamente."
    """
    generator = get_response_generator()
    return generator.generate_response(situation, language, context, data)

