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
from api.models.course import Course
from api.models.session import Session as SessionModel, SessionStatus
from api.api.mcp_executor import invoke_tool_handler
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

# Initialize context store for voice memory
context_store = ContextStore()

# Initialize conversation state manager for conversational flows
conversation_manager = VoiceConversationManager()

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


class ConverseRequest(BaseModel):
    transcript: str
    context: Optional[List[str]] = None
    user_id: Optional[int] = None
    current_page: Optional[str] = None


class ActionResponse(BaseModel):
    type: str  # 'navigate', 'execute', 'info'
    target: Optional[str] = None
    executed: Optional[bool] = None


class ConverseResponse(BaseModel):
    message: str
    action: Optional[ActionResponse] = None
    results: Optional[List[Any]] = None
    suggestions: Optional[List[str]] = None


# Navigation intent patterns - expanded for better coverage
NAVIGATION_PATTERNS = {
    # Courses
    r'\b(go to|open|show|navigate to|take me to|view)\s+(the\s+)?(courses?|course list|my courses)\b': '/courses',
    r'\bcourses?\s*page\b': '/courses',
    # Sessions
    r'\b(go to|open|show|navigate to|take me to|view)\s+(the\s+)?(sessions?|session list|class)\b': '/sessions',
    r'\bsessions?\s*page\b': '/sessions',
    # Forum
    r'\b(go to|open|show|navigate to|take me to|view)\s+(the\s+)?(forum|discussion|discussions|posts)\b': '/forum',
    r'\bforum\s*page\b': '/forum',
    # Console
    r'\b(go to|open|show|navigate to|take me to|view)\s+(the\s+)?(console|instructor console|control panel)\b': '/console',
    r'\bconsole\s*page\b': '/console',
    # Reports
    r'\b(go to|open|show|navigate to|take me to|view)\s+(the\s+)?(reports?|report page|analytics)\b': '/reports',
    r'\breports?\s*page\b': '/reports',
    # Dashboard
    r'\b(go to|open|show|navigate to|take me to|view)\s+(the\s+)?(dashboard|home|main)\b': '/dashboard',
    r'\bdashboard\s*page\b': '/dashboard',
}

# Action intent patterns - expanded for better voice command coverage
# IMPORTANT: Specific domain actions MUST come BEFORE generic UI actions
# because detect_action_intent returns the first match
ACTION_PATTERNS = {
    # === SPECIFIC DOMAIN ACTIONS (check these FIRST) ===
    # Course actions
    'create_course': [
        r'\bcreate\s+(a\s+)?(new\s+)?course\b',
        r'\bmake\s+(a\s+)?(new\s+)?course\b',
        r'\badd\s+(a\s+)?(new\s+)?course\b',
        r'\bnew\s+course\b',
        r'\bset\s*up\s+(a\s+)?course\b',
        r'\bstart\s+(a\s+)?new\s+course\b',
    ],
    'list_courses': [
        r'\b(list|show|get|what are|display|see)\s+(all\s+)?(my\s+)?courses\b',
        r'\bmy courses\b',
        r'\bcourse list\b',
        r'\bwhat courses\b',
        r'\bhow many courses\b',
    ],
    # Session actions
    'create_session': [
        r'\bcreate\s+(a\s+)?(new\s+)?session\b',
        r'\bmake\s+(a\s+)?(new\s+)?session\b',
        r'\badd\s+(a\s+)?(new\s+)?session\b',
        r'\bnew\s+session\b',
        r'\bschedule\s+(a\s+)?session\b',
        r'\bset\s*up\s+(a\s+)?session\b',
    ],
    'go_live': [
        r'\bgo\s+live\b',
        r'\bstart\s+(the\s+)?(live\s+)?session\b',
        r'\bbegin\s+(the\s+)?session\b',
        r'\blaunch\s+(the\s+)?session\b',
        r'\bmake\s+(the\s+)?session\s+live\b',
        r'\bactivate\s+(the\s+)?session\b',
    ],
    'end_session': [
        r'\bend\s+(the\s+)?(live\s+)?session\b',
        r'\bstop\s+(the\s+)?session\b',
        r'\bclose\s+(the\s+)?session\b',
        r'\bfinish\s+(the\s+)?session\b',
        r'\bterminate\s+(the\s+)?session\b',
    ],
    # Copilot actions
    'start_copilot': [
        r'\bstart\s+(the\s+)?copilot\b',
        r'\bactivate\s+(the\s+)?copilot\b',
        r'\bturn on\s+(the\s+)?copilot\b',
        r'\benable\s+(the\s+)?copilot\b',
        r'\blaunch\s+(the\s+)?copilot\b',
        r'\bcopilot\s+on\b',
        r'\bbegin\s+(the\s+)?copilot\b',
    ],
    'stop_copilot': [
        r'\bstop\s+(the\s+)?copilot\b',
        r'\bdeactivate\s+(the\s+)?copilot\b',
        r'\bturn off\s+(the\s+)?copilot\b',
        r'\bdisable\s+(the\s+)?copilot\b',
        r'\bcopilot\s+off\b',
        r'\bend\s+(the\s+)?copilot\b',
        r'\bpause\s+(the\s+)?copilot\b',
    ],
    # Poll actions
    'create_poll': [
        r'\bcreate\s+(a\s+)?poll\b',
        r'\bmake\s+(a\s+)?poll\b',
        r'\bstart\s+(a\s+)?poll\b',
        r'\bnew\s+poll\b',
        r'\badd\s+(a\s+)?poll\b',
        r'\blaunch\s+(a\s+)?poll\b',
        r'\bquick\s+poll\b',
        r'\bask\s+(the\s+)?(class|students)\s+(a\s+)?question\b',
    ],
    # Forum actions
    'post_case': [
        r'\bpost\s+(a\s+)?case(\s+study)?\b',
        r'\bcreate\s+(a\s+)?case(\s+study)?\b',
        r'\badd\s+(a\s+)?case(\s+study)?\b',
        r'\bnew\s+case(\s+study)?\b',
        r'\bshare\s+(a\s+)?case\b',
    ],
    # Report actions
    'generate_report': [
        r'\bgenerate\s+(a\s+)?(session\s+)?report\b',
        r'\bcreate\s+(a\s+)?(session\s+)?report\b',
        r'\bmake\s+(a\s+)?(session\s+)?report\b',
        r'\bbuild\s+(a\s+)?report\b',
        r'\bget\s+(the\s+)?report\b',
        r'\bshow\s+(the\s+)?report\b',
        r'\breport\s+(please|now)\b',
        r'\bsession\s+summary\b',
        r'\bclass\s+report\b',
    ],

    # === UNIVERSAL UI ELEMENT INTERACTIONS (check these AFTER specific actions) ===
    # Universal dropdown expansion - MUST come BEFORE ui_select_dropdown
    # Matches "select course", "select another course", "change course", "show options", "expand dropdown"
    'ui_expand_dropdown': [
        # Simple "select course" / "select session" / "select live session" (user wants to see options)
        r'^(select|choose|pick)\s+(a\s+)?(live\s+)?(course|session)\.?$',
        r'\b(select|choose|pick)\s+(the\s+)?(live\s+)?session\b',
        r'\b(select|choose|pick)\s+(another|a\s+different|other)\s+(live\s+)?(course|session)\b',
        r'\b(change|switch)\s+(the\s+)?(live\s+)?(course|session)\b',
        r'\bwhat\s+(live\s+)?(courses?|sessions?)\s+(are\s+)?(available|there)\b',
        r'\b(expand|open|show)\s+(the\s+)?(\w+\s+)?(dropdown|menu|list|options|select)\b',
        r'\b(show|see|view|what\s+are)\s+(the\s+)?(available\s+)?(\w+\s+)?(options|choices|items)\b',
        r'\blet\s+me\s+(see|choose|pick)\b',
    ],
    # Universal dropdown selection - direct selection like "select the first course"
    'ui_select_dropdown': [
        r'\b(select|choose|pick)\s+(the\s+)?(first|second|third|last|\d+(?:st|nd|rd|th)?)\s+(\w+)\b',
        r'\buse\s+(the\s+)?(\w+)\s+(.+)',
    ],
    # Universal tab switching - works for ANY tab name
    'ui_switch_tab': [
        # With "tab/panel/section" suffix
        r'\b(go\s+to|open|show|switch\s+to|view)\s+(the\s+)?(.+?)\s*(tab|panel|section)\b',
        r'\b(.+?)\s+(tab|panel|section)\b',
        # Without suffix - for known tab names (must list explicitly to avoid false matches)
        r'\b(go\s+to|open|show|switch\s+to|view)\s+(the\s+)?(discussion|cases|case\s+studies|summary|participation|scoring|enrollment|create|manage|sessions|courses|copilot|polls|requests|roster)\b',
        # Simple "switch to X" for common tabs
        r'^(switch\s+to|go\s+to)\s+(discussion|cases|case\s+studies|summary|participation|scoring|enrollment|create|manage|sessions|copilot|polls)$',
    ],
    # Universal button clicks - works for ANY button
    # Also handles form submission triggers like "submit", "create it", "post it"
    'ui_click_button': [
        r'\b(click|press|hit|tap)\s+(the\s+)?(.+?)\s*(button)?\b',
        r'\b(click|press)\s+(on\s+)?(.+)\b',
        r'\b(submit|confirm|send|post)\s*(it|this|the\s+form|now)?\s*$',
        r'\b(create|make)\s+(it|this|the\s+course|the\s+session|the\s+poll)\s*$',
        r'\byes,?\s*(submit|create|post|do\s+it)\b',
    ],
    # === UNIVERSAL FORM DICTATION ===
    # Detects when user is providing content for ANY input field
    'ui_dictate_input': [
        # "the title is Introduction to AI"
        r'\b(the\s+)?(\w+)\s+(is|should\s+be|will\s+be)\s+(.+)',
        # "set title to Introduction to AI"
        r'\b(set|make|change)\s+(the\s+)?(\w+)\s+(to|as)\s+(.+)',
        # "title: Introduction to AI"
        r'^(\w+):\s*(.+)$',
        # "for title, use Introduction to AI"
        r'\bfor\s+(the\s+)?(\w+),?\s+(use|put|enter|type|write)\s+(.+)',
        # "type Introduction to AI"
        r'\b(type|enter|write|put|input)\s+(.+)',
        # "fill in Introduction to AI"
        r'\b(fill\s+in|fill)\s+(.+)',
    ],
    # === CONTEXT/STATUS ACTIONS ===
    'get_status': [
        r'\b(what|where)\s+(am\s+I|is\s+this|page)\b',
        r'\b(current|this)\s+(page|status|state)\b',
        r'\bwhat\s+can\s+I\s+do\b',
        r'\bwhat\'?s\s+(happening|going\s+on)\b',
        r'\bstatus\s+update\b',
        r'\bgive\s+me\s+(a\s+)?summary\b',
    ],
    'get_help': [
        r'\bhelp(\s+me)?\b',
        r'\bwhat\s+can\s+you\s+do\b',
        r'\bwhat\s+are\s+(my|the)\s+options\b',
        r'\bshow\s+(me\s+)?(the\s+)?commands\b',
    ],
    # === UNDO/CONTEXT ACTIONS ===
    'undo_action': [
        r'\bundo\b',
        r'\bundo\s+(that|this|the\s+last|last\s+action)\b',
        r'\brevert\b',
        r'\bgo\s+back\b',
        r'\bcancel\s+(that|this|the\s+last)\b',
        r'\bnever\s*mind\b',
        r'\btake\s+(that|it)\s+back\b',
    ],
    'get_context': [
        r'\bwhat\s+(course|session)\s+(am\s+I|is)\s+(on|in|using|selected)\b',
        r'\bwhich\s+(course|session)\s+(is\s+)?(active|selected|current)\b',
        r'\bmy\s+(current|active)\s+(course|session)\b',
        r'\bwhat\'?s\s+my\s+context\b',
    ],
    'clear_context': [
        r'\b(clear|reset)\s+(my\s+)?(context|selection|choices)\b',
        r'\bstart\s+(fresh|over|again)\b',
        r'\bforget\s+(everything|all|my\s+selections)\b',
    ],
    # === ADDITIONAL COURSE ACTIONS ===
    'select_course': [
        r'\b(select|choose|pick|open)\s+(the\s+)?(first|second|third|last|\d+(?:st|nd|rd|th)?)\s+course\b',
        r'\b(select|choose|pick|open)\s+course\s+(\d+|one|two|three)\b',
        r'\bgo\s+(to|into)\s+(the\s+)?(first|second|third|last)\s+course\b',
    ],
    'view_course_details': [
        r'\b(view|show|see|display)\s+(the\s+)?course\s+(details?|info|information)\b',
        r'\bcourse\s+(details?|info|information)\b',
        r'\babout\s+(this|the)\s+course\b',
    ],
    # === SESSION ACTIONS ===
    'list_sessions': [
        r'\b(list|show|get|what are|display|see)\s+(the\s+)?(live\s+)?sessions\b',
        r'\blive sessions\b',
        r'\bactive sessions\b',
        r'\bcurrent sessions?\b',
        r'\bwhat sessions\b',
    ],
    'select_session': [
        r'\b(select|choose|pick|open)\s+(the\s+)?(first|second|third|last|\d+(?:st|nd|rd|th)?)\s+session\b',
        r'\b(select|choose|pick|open)\s+session\s+(\d+|one|two|three)\b',
        r'\bgo\s+(to|into)\s+(the\s+)?(first|second|third|last)\s+session\b',
    ],
    # === COPILOT ACTIONS ===
    'get_interventions': [
        r'\b(show|get|what are|display)\s+(the\s+)?(copilot\s+)?suggestions\b',
        r'\binterventions\b',
        r'\bconfusion points\b',
        r'\bcopilot\s+(suggestions|insights|recommendations)\b',
        r'\bwhat does\s+(the\s+)?copilot\s+(suggest|recommend|say)\b',
        r'\bany\s+suggestions\b',
    ],
    # === ENROLLMENT ACTIONS ===
    'list_enrollments': [
        r'\b(list|show|who are|display|get)\s+(the\s+)?(enrolled\s+)?students\b',
        r'\benrollment\s+(list|status)\b',
        r'\bhow many students\b',
        r'\bstudent\s+(list|count|roster)\b',
        r'\bwho\s+is\s+enrolled\b',
        r'\bclass\s+roster\b',
    ],
    'manage_enrollments': [
        r'\bmanage\s+(the\s+)?(student\s+)?enrollments?\b',
        r'\benroll\s+(new\s+)?students?\b',
        r'\badd\s+students?\s+(to|into)\b',
        r'\bstudent\s+management\b',
        r'\benrollment\s+management\b',
    ],
    'list_student_pool': [
        r'\b(select|choose|pick)\s+(a\s+)?student\s+(from\s+)?(the\s+)?(student\s+)?pool\b',
        r'\b(show|list|see)\s+(the\s+)?(student\s+)?pool\b',
        r'\b(available|unenrolled)\s+students\b',
        r'\bwho\s+(can|is available to)\s+enroll\b',
        r'\bstudent\s+pool\b',
    ],
    'enroll_selected': [
        r'\b(click\s+)?(enroll|add)\s+(the\s+)?selected(\s+students?)?\b',
        r'\benroll\s+selected\b',
        r'\badd\s+selected\s+students?\b',
    ],
    'enroll_all': [
        r'\b(click\s+)?(enroll|add)\s+all(\s+students?)?\b',
        r'\benroll\s+all\b',
        r'\badd\s+all\s+students?\b',
    ],
    'select_student': [
        r'\b(select|choose|pick|click|check)\s+(the\s+)?student\s+(.+)\b',
        r'\b(select|choose|pick|click|check)\s+(.+?)\s+(from|in)\s+(the\s+)?(student\s+)?pool\b',
    ],
    # === FORUM ACTIONS ===
    'view_posts': [
        r'\b(show|view|see|display)\s+(the\s+)?(forum\s+)?posts\b',
        r'\b(show|view|see)\s+(the\s+)?discussions?\b',
        r'\bwhat\s+(are\s+)?(students|people)\s+(saying|discussing|posting)\b',
        r'\brecent\s+posts\b',
        r'\blatest\s+posts\b',
    ],
    'get_pinned_posts': [
        r'\b(show|view|get|what are)\s+(the\s+)?pinned\s+(posts|discussions)?\b',
        r'\bpinned\s+(posts|content|discussions)\b',
        r'\bimportant\s+posts\b',
    ],
    'summarize_discussion': [
        r'\bsummarize\s+(the\s+)?(forum|discussion|posts)\b',
        r'\b(discussion|forum)\s+summary\b',
        r'\bwhat\s+are\s+(students|people)\s+talking\s+about\b',
        r'\bkey\s+(points|themes|topics)\b',
        r'\bmain\s+(discussion|points)\b',
    ],
    'get_student_questions': [
        r'\b(show|what are|any)\s+(student\s+)?questions\b',
        r'\bquestions\s+from\s+(students|class)\b',
        r'\bany\s+(confusion|misconceptions)\b',
        r'\bwhat\s+(do\s+)?students\s+(need|want|ask)\b',
    ],
}

CONFIRMATION_PATTERNS = (
    r"\b(yes|yeah|yep|confirm|confirmed|approve|approved|proceed|go ahead|do it|sounds good|ok|okay)\b"
)


def detect_navigation_intent(text: str) -> Optional[str]:
    """Detect if user wants to navigate somewhere"""
    text_lower = text.lower()
    for pattern, path in NAVIGATION_PATTERNS.items():
        if re.search(pattern, text_lower):
            return path
    return None


def detect_action_intent(text: str) -> Optional[str]:
    """Detect if user wants to perform an action"""
    text_lower = text.lower()
    for action, patterns in ACTION_PATTERNS.items():
        for pattern in patterns:
            if re.search(pattern, text_lower):
                return action
    return None


def extract_ui_target(text: str, action: str) -> Dict[str, Any]:
    """Extract the target value from a UI interaction command."""
    text_lower = text.lower().strip()
    result = {"action": action}

    if action == 'ui_select_course':
        # Extract course name or ordinal
        # Try to find the course name after "course"
        match = re.search(r'(course|class)\s+(.+?)(?:\s+please|\s+now|\s*$)', text_lower)
        if match:
            result["target"] = "select-course"
            result["optionName"] = match.group(2).strip()
        # Check for ordinal patterns
        ordinal_match = re.search(r'(first|second|third|last|\d+(?:st|nd|rd|th)?)\s+(course|class)', text_lower)
        if ordinal_match:
            result["target"] = "select-course"
            result["optionName"] = ordinal_match.group(1)

    elif action == 'ui_select_session':
        # Extract session name or ordinal
        match = re.search(r'session\s+(.+?)(?:\s+please|\s+now|\s*$)', text_lower)
        if match:
            result["target"] = "select-session"
            result["optionName"] = match.group(1).strip()
        # Check for ordinal patterns
        ordinal_match = re.search(r'(first|second|third|last|\d+(?:st|nd|rd|th)?)\s+session', text_lower)
        if ordinal_match:
            result["target"] = "select-session"
            result["optionName"] = ordinal_match.group(1)

    elif action == 'ui_switch_tab':
        # Extract tab name - order matters (longer phrases first)
        tab_keywords = [
            'case studies', 'case-studies',  # Two-word tab name - check first
            'summary', 'participation', 'scoring', 'enrollment', 'create',
            'manage', 'sessions', 'courses', 'discussion', 'cases',
            'copilot', 'polls', 'requests', 'roster', 'my-performance', 'best-practice'
        ]
        for keyword in tab_keywords:
            keyword_normalized = keyword.replace('-', ' ')
            if keyword in text_lower or keyword_normalized in text_lower:
                # Normalize "case studies" to "cases" (the actual tab value)
                tab_value = 'cases' if keyword in ['case studies', 'case-studies'] else keyword.replace('-', '')
                result["tabName"] = tab_value
                result["target"] = f"tab-{tab_value}"
                break

    elif action == 'ui_click_button':
        # Extract button target
        button_mappings = {
            'generate report': 'generate-report',
            'regenerate report': 'regenerate-report',
            'refresh': 'refresh',
            'refresh report': 'refresh-report',
            'start copilot': 'start-copilot',
            'stop copilot': 'stop-copilot',
            'create poll': 'create-poll',
            'post case': 'post-case',
            'go live': 'go-live',
            'complete': 'complete-session',
            'complete session': 'complete-session',
            'enroll': 'enroll-students',
            'upload roster': 'upload-roster',
            'submit': 'submit-post',
            'create course': 'create-course',
            'create session': 'create-session',
        }
        for phrase, target in button_mappings.items():
            if phrase in text_lower:
                result["target"] = target
                result["buttonLabel"] = phrase
                break

    return result


def is_confirmation(text: str) -> bool:
    """Return True if transcript is a confirmation to proceed."""
    return bool(re.search(CONFIRMATION_PATTERNS, text.lower()))


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
) -> str:
    """Generate a natural conversational response for various intents."""

    if intent_type == 'navigate':
        page_names = {
            '/courses': 'courses',
            '/sessions': 'sessions',
            '/forum': 'forum',
            '/console': 'instructor console',
            '/reports': 'reports',
            '/dashboard': 'dashboard',
        }
        page_name = page_names.get(intent_value, intent_value)
        responses = [
            f"Taking you to {page_name} now.",
            f"Opening {page_name} for you.",
            f"Let me open the {page_name} page.",
        ]
        return responses[hash(intent_value) % len(responses)]

    if intent_type == 'execute':
        # Handle result that might be a dict with message/error
        if isinstance(results, dict):
            if results.get("message"):
                return results["message"]
            if results.get("error"):
                return f"Sorry, there was an issue: {results['error']}"

        # === UI INTERACTION RESPONSES ===
        if intent_value == 'ui_select_course':
            if isinstance(results, dict):
                available = results.get("available_options", [])
                if available and len(available) > 0:
                    return f"Selecting the course. You have {len(available)} courses available."
            return "Selecting the course for you."

        if intent_value == 'ui_select_session':
            return "Selecting the session for you."

        if intent_value == 'ui_switch_tab':
            if isinstance(results, dict):
                tab_name = results.get("ui_actions", [{}])[0].get("payload", {}).get("tabName", "")
                if tab_name:
                    return f"Switching to the {tab_name} tab."
            return "Switching tabs."

        if intent_value == 'ui_click_button':
            if isinstance(results, dict):
                button_label = results.get("ui_actions", [{}])[0].get("payload", {}).get("buttonLabel", "")
                if button_label:
                    return f"Clicking {button_label}."
            return "Clicking the button."

        # === COURSE RESPONSES ===
        if intent_value == 'list_courses':
            if isinstance(results, list) and len(results) > 0:
                course_names = [c.get('title', 'Untitled') for c in results[:5]]
                if len(results) == 1:
                    return f"You have one course: {course_names[0]}. Would you like me to open it?"
                elif len(results) <= 3:
                    return f"You have {len(results)} courses: {', '.join(course_names)}. Which one would you like to work with?"
                else:
                    return f"You have {len(results)} courses, including {', '.join(course_names[:3])}, and {len(results) - 3} more. Would you like to see them all?"
            return "You don't have any courses yet. Would you like me to help you create one?"

        if intent_value == 'create_course':
            return "Opening course creation. Tell me the course title, or I can help you set it up step by step."

        if intent_value == 'select_course':
            if isinstance(results, dict) and results.get("course"):
                course = results["course"]
                return f"Opening {course.get('title', 'the course')}. What would you like to do with it?"
            return "I'll open the first course for you. You can also say 'open second course' or specify a course name."

        if intent_value == 'view_course_details':
            if isinstance(results, dict) and results.get("title"):
                return f"Here's {results['title']}. It has {results.get('session_count', 0)} sessions."
            return "I couldn't find the course details. Make sure you're on a course page."

        # === SESSION RESPONSES ===
        if intent_value == 'list_sessions':
            if isinstance(results, list) and len(results) > 0:
                live = [s for s in results if s.get('status') == 'live']
                if live:
                    return f"There {'is' if len(live) == 1 else 'are'} {len(live)} live session{'s' if len(live) > 1 else ''}: {', '.join(s.get('title', 'Untitled') for s in live[:3])}. Would you like to join one?"
                return f"You have {len(results)} sessions. None are live right now. Would you like to start one?"
            return "No sessions found. Would you like to create a new session?"

        if intent_value == 'create_session':
            return "Opening session creation. What topic will this session cover?"

        if intent_value == 'select_session':
            if isinstance(results, dict) and results.get("session"):
                session = results["session"]
                return f"Opening {session.get('title', 'the session')}. Status: {session.get('status', 'unknown')}."
            return "Opening the first session. You can also say 'open second session' or specify a session name."

        if intent_value == 'go_live':
            return "Session is now live! Students can join and start participating. The copilot is ready when you need it."

        if intent_value == 'end_session':
            return "Session has ended. Would you like me to generate a report?"

        # === COPILOT RESPONSES ===
        if intent_value == 'start_copilot':
            return "Copilot is now active! It will monitor the discussion and provide suggestions every 90 seconds."

        if intent_value == 'stop_copilot':
            return "Copilot has been stopped. You can restart it anytime by saying 'start copilot'."

        if intent_value == 'get_interventions':
            if isinstance(results, list) and len(results) > 0:
                latest = results[0]
                suggestion = latest.get('suggestion_json', {})
                summary = suggestion.get('rolling_summary', '')
                confusion = suggestion.get('confusion_points', [])
                response = f"Here's the copilot insight: {summary}" if summary else "I have suggestions from the copilot."
                if confusion:
                    response += f" Detected {len(confusion)} confusion point{'s' if len(confusion) > 1 else ''}: {confusion[0].get('issue', 'Unknown')}."
                return response
            return "No suggestions yet. The copilot analyzes every 90 seconds when active."

        # === POLL RESPONSES ===
        if intent_value == 'create_poll':
            return "Opening poll creation. What question would you like to ask your students?"

        # === REPORT RESPONSES ===
        if intent_value == 'generate_report':
            return "Generating the session report. This takes a moment to analyze all discussion posts."

        # === ENROLLMENT RESPONSES ===
        if intent_value == 'list_enrollments':
            if isinstance(results, list):
                return f"There are {len(results)} students enrolled. Would you like me to list them or show participation stats?"
            return "I couldn't retrieve the enrollment information."

        if intent_value == 'manage_enrollments':
            return "Opening enrollment management. You can add students by email or upload a roster."

        if intent_value == 'list_student_pool':
            if isinstance(results, dict) and results.get("students"):
                count = len(results.get("students", []))
                return f"There are {count} students available in the pool. Say a student's name to select them."
            return "I'll show you the available students."

        if intent_value == 'select_student':
            return "Student selected. Say another name to select more, or 'enroll selected' to enroll them."

        if intent_value == 'enroll_selected':
            return "Enrolling the selected students."

        if intent_value == 'enroll_all':
            return "Enrolling all available students."

        # === FORUM RESPONSES ===
        if intent_value == 'post_case':
            return "Opening case study creation. What scenario would you like students to discuss?"

        if intent_value == 'view_posts':
            if isinstance(results, dict) and results.get("posts"):
                posts = results["posts"]
                if len(posts) > 0:
                    return f"There are {len(posts)} posts in the forum. The latest is about: {posts[0].get('content', '')[:50]}..."
            return "No posts yet in this session's forum."

        if intent_value == 'get_pinned_posts':
            if isinstance(results, dict):
                count = results.get("count", 0)
                if count > 0:
                    return f"There are {count} pinned posts. These are the important discussions highlighted by the instructor."
                return "No pinned posts yet. You can pin important posts to highlight them."
            return "No pinned posts found."

        if intent_value == 'summarize_discussion':
            if isinstance(results, dict):
                if results.get("summary"):
                    return results["summary"]
                if results.get("error"):
                    return results["error"]
            return "I couldn't summarize the discussion. Make sure you're in a live session."

        if intent_value == 'get_student_questions':
            if isinstance(results, dict):
                count = results.get("count", 0)
                if count > 0:
                    questions = results.get("questions", [])
                    first_q = questions[0].get('content', '')[:80] if questions else ""
                    return f"Found {count} questions. The most recent: {first_q}..."
                return "No questions from students yet."
            return "I couldn't find any questions."

        if intent_value == 'get_status':
            if isinstance(results, dict):
                message = results.get("message", "")
                actions = results.get("available_actions", [])
                if actions:
                    return f"{message} You can: {', '.join(actions[:4])}."
                return message
            return "I'm not sure what page you're on."

        if intent_value == 'get_help':
            if isinstance(results, dict) and results.get("message"):
                return results["message"]
            return "I can help with navigation, courses, sessions, polls, forum, and reports."

        # === UNDO/CONTEXT RESPONSES ===
        if intent_value == 'undo_action':
            if isinstance(results, dict):
                if results.get("error"):
                    return results["error"]
                if results.get("message"):
                    return results["message"]
            return "I've undone the last action."

        if intent_value == 'get_context':
            if isinstance(results, dict):
                if results.get("message"):
                    return results["message"]
                course = results.get("course_name", "none")
                session = results.get("session_name", "none")
                return f"Your active course is {course} and session is {session}."
            return "You don't have any active context."

        if intent_value == 'clear_context':
            return "Context cleared! Starting fresh."

    # Default fallback
    return "I can help you navigate pages, manage courses and sessions, create polls, generate reports, and more. What would you like to do?"


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

    if not transcript:
        return ConverseResponse(
            message=sanitize_speech("I didn't catch that. Could you say it again?"),
            suggestions=["Show my courses", "Start a session", "Open forum"]
        )

    # === CHECK CONVERSATION STATE FIRST ===
    # Handle ongoing conversational flows (form filling, dropdown selection, confirmation)
    conv_context = conversation_manager.get_context(request.user_id)

    # --- Handle confirmation state ---
    if conv_context.state == ConversationState.AWAITING_CONFIRMATION:
        # Check if user confirmed or denied
        confirmed = is_confirmation(transcript)
        denial_words = ['no', 'nope', 'cancel', 'stop', 'never mind', 'nevermind']
        denied = any(word in transcript.lower() for word in denial_words)

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
                    return ConverseResponse(
                        message=sanitize_speech(f"Submitting the form. Clicking {button_label}."),
                        action=ActionResponse(type='execute', executed=True),
                        results=[{
                            "action": "click_button",
                            "ui_actions": [
                                {"type": "ui.clickButton", "payload": {"target": button_target}},
                                {"type": "ui.toast", "payload": {"message": f"{button_label} submitted", "type": "success"}},
                            ],
                        }],
                        suggestions=["What's next?", "Go to another page"],
                    )

                # For other actions, use execute_action
                action_result = await execute_action(
                    result["action"],
                    request.user_id,
                    request.current_page,
                    db,
                    transcript
                )
                conversation_manager.reset_retry_count(request.user_id)
                return ConverseResponse(
                    message=sanitize_speech(result["message"]),
                    action=ActionResponse(type='execute', executed=True),
                    results=[action_result] if action_result else None,
                    suggestions=get_action_suggestions(result["action"]),
                )
            else:
                return ConverseResponse(
                    message=sanitize_speech(result["message"]),
                    action=ActionResponse(type='info'),
                    suggestions=["Show my courses", "Go to forum", "What can I do?"],
                )
        # If not clear confirmation/denial, ask again
        return ConverseResponse(
            message=sanitize_speech("Please say 'yes' to confirm or 'no' to cancel."),
            action=ActionResponse(type='info'),
            suggestions=["Yes, proceed", "No, cancel"],
        )

    # --- Handle dropdown selection state ---
    if conv_context.state == ConversationState.AWAITING_DROPDOWN_SELECTION:
        result = conversation_manager.select_dropdown_option(request.user_id, transcript)
        if result["success"]:
            selected = result["selected"]
            conversation_manager.reset_retry_count(request.user_id)
            return ConverseResponse(
                message=sanitize_speech(result["message"]),
                action=ActionResponse(type='execute', executed=True),
                results=[{
                    "ui_actions": [
                        {"type": "ui.selectDropdown", "payload": {
                            "target": result["voice_id"],
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
            nav_path = detect_navigation_intent(transcript)
            if nav_path:
                # User wants to navigate - cancel form and navigate
                conversation_manager.cancel_form(request.user_id)
                message = sanitize_speech(f"Cancelling form. {generate_conversational_response('navigate', nav_path)}")
                return ConverseResponse(
                    message=message,
                    action=ActionResponse(type='navigate', target=nav_path),
                    results=[{
                        "ui_actions": [
                            {"type": "ui.navigate", "payload": {"path": nav_path}},
                        ]
                    }],
                    suggestions=get_page_suggestions(nav_path)
                )

            # Check for tab switching intent (e.g., "go to manage status tab")
            tab_patterns = [
                (r'\b(go\s+to|switch\s+to|open)\s+(the\s+)?(manage\s*status|management)\s*(tab)?\b', 'manage'),
                (r'\b(go\s+to|switch\s+to|open)\s+(the\s+)?(create|creation)\s*(tab)?\b', 'create'),
                (r'\b(go\s+to|switch\s+to|open)\s+(the\s+)?(view|sessions?|list)\s*(tab)?\b', 'sessions'),
                (r'\b(go\s+to|switch\s+to|open)\s+(the\s+)?(enrollment|enroll)\s*(tab)?\b', 'enrollment'),
            ]
            for pattern, tab_name in tab_patterns:
                if re.search(pattern, transcript.lower()):
                    # User wants to switch tabs - cancel form and switch
                    conversation_manager.cancel_form(request.user_id)
                    return ConverseResponse(
                        message=sanitize_speech(f"Cancelling form. Switching to {tab_name} tab."),
                        action=ActionResponse(type='execute', executed=True),
                        results=[{
                            "ui_actions": [
                                {"type": "ui.switchTab", "payload": {"tabName": tab_name}},
                                {"type": "ui.toast", "payload": {"message": f"Switched to {tab_name}", "type": "info"}},
                            ]
                        }],
                        suggestions=["Go live", "View sessions", "Create session"],
                    )

            # Check for cancel/exit keywords
            cancel_words = ['cancel', 'stop', 'exit', 'quit', 'abort', 'nevermind', 'never mind']
            if any(word in transcript.lower() for word in cancel_words):
                conversation_manager.cancel_form(request.user_id)
                return ConverseResponse(
                    message=sanitize_speech("Form cancelled. What would you like to do?"),
                    action=ActionResponse(type='info'),
                    suggestions=["Create course", "Create session", "Go to forum"],
                )

            # Check for skip/next keywords
            skip_words = ['skip', 'next', 'pass', 'later', 'none', 'nothing']
            if any(word in transcript.lower() for word in skip_words):
                skip_result = conversation_manager.skip_current_field(request.user_id)
                return ConverseResponse(
                    message=sanitize_speech(skip_result["message"]),
                    action=ActionResponse(type='info'),
                    suggestions=["Continue", "Cancel form", "Help"],
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
        # Check if user accepted or declined
        accept_words = ['yes', 'yeah', 'yep', 'sure', 'okay', 'ok', 'please', 'go ahead', "i'd like to", "i would like"]
        decline_words = ['no', 'nope', 'not now', 'hold on', 'wait', 'no thanks', 'later', 'nevermind', 'never mind']

        transcript_lower = transcript.lower()
        accepted = any(word in transcript_lower for word in accept_words)
        declined = any(word in transcript_lower for word in decline_words)

        if accepted and not declined:
            result = conversation_manager.handle_post_offer_response(request.user_id, True)
            return ConverseResponse(
                message=sanitize_speech(result["message"]),
                action=ActionResponse(type='info'),
                suggestions=["I'm done", "Cancel"],
            )
        elif declined:
            result = conversation_manager.handle_post_offer_response(request.user_id, False)
            return ConverseResponse(
                message=sanitize_speech(result["message"]),
                action=ActionResponse(type='info'),
                suggestions=["Switch to case studies", "Select another session", "Go to courses"],
            )
        else:
            # Unclear response - ask again
            return ConverseResponse(
                message=sanitize_speech("Would you like to post something to the discussion? Say yes or no."),
                action=ActionResponse(type='info'),
                suggestions=["Yes, I'd like to post", "No thanks"],
            )

    # --- Handle forum post dictation state ---
    if conv_context.state == ConversationState.AWAITING_POST_DICTATION:
        transcript_lower = transcript.lower().strip()

        # Check for navigation/escape intent first
        nav_path = detect_navigation_intent(transcript)
        if nav_path:
            conversation_manager.reset_post_offer(request.user_id)
            message = sanitize_speech(f"Cancelling post. {generate_conversational_response('navigate', nav_path)}")
            return ConverseResponse(
                message=message,
                action=ActionResponse(type='navigate', target=nav_path),
                results=[{
                    "ui_actions": [
                        {"type": "ui.navigate", "payload": {"path": nav_path}},
                    ]
                }],
                suggestions=get_page_suggestions(nav_path)
            )

        # Check for cancel keywords
        cancel_words = ['cancel', 'stop', 'abort', 'quit', 'nevermind', 'never mind']
        if any(word in transcript_lower for word in cancel_words):
            conversation_manager.reset_post_offer(request.user_id)
            return ConverseResponse(
                message=sanitize_speech("Post cancelled. What else can I help you with?"),
                action=ActionResponse(type='execute', executed=True),
                results=[{
                    "ui_actions": [
                        {"type": "ui.clearInput", "payload": {"target": "textarea-post-content"}},
                    ]
                }],
                suggestions=["Switch to case studies", "Select another session"],
            )

        # Check for "I'm done" / "finished" patterns
        done_patterns = [
            r'\b(i\'?m\s+done|i\s+am\s+done)\b',
            r'\b(that\'?s\s+it|that\s+is\s+it)\b',
            r'\b(finished|i\'?m\s+finished|i\s+am\s+finished)\b',
            r'\b(it\'?s\s+over|it\s+is\s+over)\b',
            r'\b(end|done|complete|finish)\s*(it|now|dictation|post)?\s*$',
            r'^done\.?$',
            r'^finished\.?$',
        ]
        is_done = any(re.search(pattern, transcript_lower) for pattern in done_patterns)

        if is_done:
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
        transcript_lower = transcript.lower()

        # Check for confirmation or denial
        confirm_words = ['yes', 'yeah', 'yep', 'sure', 'okay', 'ok', 'post it', 'submit', 'go ahead', 'do it']
        deny_words = ['no', 'nope', 'cancel', 'delete', 'clear', 'no thanks', 'nevermind', 'never mind']

        confirmed = any(word in transcript_lower for word in confirm_words)
        denied = any(word in transcript_lower for word in deny_words)

        if confirmed and not denied:
            result = conversation_manager.handle_post_submit_response(request.user_id, True)
            # Click the submit button
            return ConverseResponse(
                message=sanitize_speech(result["message"]),
                action=ActionResponse(type='execute', executed=True),
                results=[{
                    "ui_actions": [
                        {"type": "ui.clickButton", "payload": {"target": "submit-post"}},
                        {"type": "ui.toast", "payload": {"message": "Post submitted!", "type": "success"}},
                    ]
                }],
                suggestions=["View posts", "Switch to case studies", "Select another session"],
            )
        elif denied:
            result = conversation_manager.handle_post_submit_response(request.user_id, False)
            # Clear the textarea
            return ConverseResponse(
                message=sanitize_speech(result["message"]),
                action=ActionResponse(type='execute', executed=True),
                results=[{
                    "ui_actions": [
                        {"type": "ui.clearInput", "payload": {"target": "textarea-post-content"}},
                        {"type": "ui.toast", "payload": {"message": "Post cancelled", "type": "info"}},
                    ]
                }],
                suggestions=["Try again", "Switch to case studies", "Go to courses"],
            )
        else:
            # Unclear response - ask again
            return ConverseResponse(
                message=sanitize_speech("Should I post this? Say yes to post or no to cancel."),
                action=ActionResponse(type='info'),
                suggestions=["Yes, post it", "No, cancel"],
            )

    # 1. Check for navigation intent first (fast regex - instant)
    nav_path = detect_navigation_intent(transcript)
    if nav_path:
        message = sanitize_speech(generate_conversational_response('navigate', nav_path))
        # Include ui_actions for navigation so frontend executes the navigation
        return ConverseResponse(
            message=message,
            action=ActionResponse(type='navigate', target=nav_path),
            results=[{
                "ui_actions": [
                    {"type": "ui.navigate", "payload": {"path": nav_path}},
                    {"type": "ui.toast", "payload": {"message": f"Navigating to {nav_path}", "type": "info"}},
                ]
            }],
            suggestions=get_page_suggestions(nav_path)
        )

    # 2. Check for action intent via regex BEFORE expensive LLM call (fast - instant)
    action = detect_action_intent(transcript)
    if action:
        result = await execute_action(action, request.user_id, request.current_page, db, transcript)
        # Wrap result in a list if it's not already (ConverseResponse.results expects List)
        results_list = [result] if result and not isinstance(result, list) else result
        return ConverseResponse(
            message=sanitize_speech(generate_conversational_response(
                'execute',
                action,
                results=result,  # Pass original for response generation
                context=request.context,
                current_page=request.current_page,
            )),
            action=ActionResponse(type='execute', executed=True),
            results=results_list,  # Pass list for Pydantic validation
            suggestions=get_action_suggestions(action),
        )

    # 3. FAST MODE: Skip slow LLM orchestrator for instant response
    # The regex patterns above should handle 95%+ of commands
    # Only use LLM for truly complex multi-step requests (disabled by default for speed)
    USE_LLM_ORCHESTRATOR = False  # Set to True if you need complex multi-step planning

    if USE_LLM_ORCHESTRATOR:
        plan_result = run_voice_orchestrator(
            transcript,
            context=request.context,
            current_page=request.current_page,
        )
        plan = plan_result.get("plan") if plan_result else None
        if plan and plan.get("steps"):
            steps = plan.get("steps", [])
            required_confirmations = set(plan.get("required_confirmations") or [])
            write_steps = [
                step
                for step in steps
                if step.get("mode") == "write" or step.get("tool_name") in required_confirmations
            ]

            if write_steps and not is_confirmation(transcript):
                pending_results = [
                    {
                        "tool": step.get("tool_name"),
                        "status": "pending_confirmation",
                        "args": step.get("args", {}),
                    }
                    for step in write_steps
                ]
                return ConverseResponse(
                    message=sanitize_speech(build_confirmation_message(write_steps)),
                    action=ActionResponse(type="execute", executed=False),
                    results=pending_results,
                    suggestions=["Yes, proceed", "No, cancel"],
                )

            # Execute and use fast template summary (no LLM call)
            results, summary = execute_plan_steps(steps, db)
            return ConverseResponse(
                message=sanitize_speech(summary),
                action=ActionResponse(type='execute', executed=True),
                results=results,
                suggestions=["Anything else I can help with?"],
            )

    # 4. No clear intent - provide helpful fallback instantly (no LLM call)
    fallback_message = generate_fallback_response(transcript, request.context)

    return ConverseResponse(
        message=sanitize_speech(fallback_message),
        action=ActionResponse(type='info'),
        suggestions=["Show my courses", "Go to forum", "Start copilot", "Create a poll"],
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


def _resolve_session_id(db: Session, current_page: Optional[str], user_id: Optional[int] = None) -> Optional[int]:
    """Resolve session ID from URL, context memory, or database.

    Priority:
    1. Session ID in URL path
    2. Active session from user context memory
    3. Any live session
    4. Most recently created session (fallback)
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

    # Try to find a live session
    session = (
        db.query(SessionModel)
        .filter(SessionModel.status == SessionStatus.live)
        .order_by(SessionModel.created_at.desc())
        .first()
    )
    if session:
        return session.id

    # Fallback to most recent session
    session = db.query(SessionModel).order_by(SessionModel.created_at.desc()).first()
    return session.id if session else None


def _extract_dictated_content(transcript: str, action: str) -> Optional[str]:
    """Extract dictated content from transcript for form filling."""
    text = transcript.strip()

    # Remove common prefixes that indicate dictation
    prefixes_to_remove = [
        r'^(?:the\s+)?(?:course\s+)?(?:title\s+)?(?:is\s+)?(?:called\s+)?',
        r'^(?:the\s+)?(?:session\s+)?(?:title\s+)?(?:is\s+)?(?:called\s+)?',
        r'^(?:name|title|call)\s+(?:it|the\s+\w+)\s+',
        r'^(?:it\'?s?\s+called\s+)',
        r'^(?:the\s+)?(?:poll\s+)?question\s+(?:is|should\s+be)\s+',
        r'^(?:ask|poll)\s+(?:them|students|the\s+class)\s+',
        r'^(?:post\s+(?:this|the\s+following):\s*)',
        r'^(?:the\s+)?(?:post|message|content)\s+(?:is|should\s+be)\s+',
    ]

    for prefix in prefixes_to_remove:
        match = re.match(prefix, text, re.IGNORECASE)
        if match:
            text = text[match.end():].strip()
            break

    # Remove quotes if present
    if text.startswith('"') and text.endswith('"'):
        text = text[1:-1]
    elif text.startswith("'") and text.endswith("'"):
        text = text[1:-1]

    # Return None if the result is too short or looks like a command
    if len(text) < 2:
        return None

    # Check if this looks like an actual dictation (not a command)
    command_indicators = ['go to', 'navigate', 'open', 'show', 'create', 'start', 'stop', 'help']
    text_lower = text.lower()
    for indicator in command_indicators:
        if text_lower.startswith(indicator):
            return None

    return text


def _extract_universal_dictation(transcript: str) -> Optional[Dict[str, str]]:
    """
    UNIVERSAL dictation extraction - works for ANY input field.
    Extracts field name and value from natural speech patterns.
    """
    text = transcript.strip()
    text_lower = text.lower()

    # Pattern: "the [field] is [value]" or "[field] is [value]"
    match = re.match(r'^(?:the\s+)?(\w+(?:\s+\w+)?)\s+(?:is|should\s+be|will\s+be)\s+(.+)$', text, re.IGNORECASE)
    if match:
        field = match.group(1).strip().lower().replace(' ', '-')
        value = match.group(2).strip()
        return {"field": field, "value": value}

    # Pattern: "set [field] to [value]"
    match = re.match(r'^(?:set|make|change)\s+(?:the\s+)?(\w+(?:\s+\w+)?)\s+(?:to|as)\s+(.+)$', text, re.IGNORECASE)
    if match:
        field = match.group(1).strip().lower().replace(' ', '-')
        value = match.group(2).strip()
        return {"field": field, "value": value}

    # Pattern: "[field]: [value]"
    match = re.match(r'^(\w+(?:\s+\w+)?):\s*(.+)$', text)
    if match:
        field = match.group(1).strip().lower().replace(' ', '-')
        value = match.group(2).strip()
        return {"field": field, "value": value}

    # Pattern: "for [field], use [value]"
    match = re.match(r'^for\s+(?:the\s+)?(\w+(?:\s+\w+)?),?\s+(?:use|put|enter|type|write)\s+(.+)$', text, re.IGNORECASE)
    if match:
        field = match.group(1).strip().lower().replace(' ', '-')
        value = match.group(2).strip()
        return {"field": field, "value": value}

    # Pattern: "type/enter/write [value]" - fill focused/first input
    match = re.match(r'^(?:type|enter|write|put|input|fill(?:\s+in)?)\s+(.+)$', text, re.IGNORECASE)
    if match:
        value = match.group(1).strip()
        return {"field": "focused-input", "value": value}

    # If nothing matched but it looks like content (not a command), treat as dictation for focused input
    command_starters = ['go', 'navigate', 'open', 'show', 'create', 'start', 'stop', 'help', 'select', 'choose', 'click', 'switch']
    first_word = text_lower.split()[0] if text_lower.split() else ""
    if first_word not in command_starters and len(text) > 3:
        return {"field": "focused-input", "value": text}

    return None


def _extract_dropdown_hint(transcript: str) -> str:
    """Extract which dropdown the user is referring to, or return empty for any dropdown."""
    text_lower = transcript.lower()

    # Look for specific dropdown mentions
    dropdown_keywords = {
        'course': 'select-course',
        'session': 'select-session',
        'student': 'select-student',
        'instructor': 'select-instructor',
        'status': 'select-status',
        'type': 'select-type',
    }

    for keyword, target in dropdown_keywords.items():
        if keyword in text_lower:
            return target

    return ""  # Empty means find any dropdown on the page


def _extract_button_info(transcript: str) -> Dict[str, str]:
    """Extract button target from transcript for button clicks."""
    text_lower = transcript.lower()

    # Direct button mappings
    button_mappings = {
        'generate report': 'generate-report',
        'regenerate report': 'regenerate-report',
        'refresh': 'refresh',
        'start copilot': 'start-copilot',
        'stop copilot': 'stop-copilot',
        'create poll': 'create-poll',
        'post case': 'post-case',
        'go live': 'go-live',
        'complete session': 'complete-session',
        'enroll': 'enroll-students',
        'upload roster': 'upload-roster',
        'submit': 'submit-post',
        'create course': 'create-course-with-plans',
        'create session': 'create-session',
        'create and generate': 'create-course-with-plans',
        'generate plans': 'create-course-with-plans',
    }

    for phrase, target in button_mappings.items():
        if phrase in text_lower:
            return {"target": target, "label": phrase.title()}

    return {}


def _extract_student_name(transcript: str) -> Optional[str]:
    """Extract student name from transcript for student selection."""
    text = transcript.strip()

    # Remove common prefixes
    prefixes = [
        r'^(select|choose|pick|click|check|enroll)\s+(the\s+)?student\s+',
        r'^(select|choose|pick|click|check|enroll)\s+',
        r'^student\s+',
    ]
    for prefix in prefixes:
        text = re.sub(prefix, '', text, flags=re.IGNORECASE)

    # Remove common suffixes
    suffixes = [
        r'\s+(from|in)\s+(the\s+)?(student\s+)?pool$',
        r'\s+please$',
        r'\s+now$',
    ]
    for suffix in suffixes:
        text = re.sub(suffix, '', text, flags=re.IGNORECASE)

    # Clean up and return
    text = text.strip()
    if text and len(text) > 1:
        return text
    return None


def _extract_tab_info(transcript: str) -> Dict[str, str]:
    """Extract tab name from transcript for universal tab switching."""
    text_lower = transcript.lower()

    # Remove common prefixes
    for prefix in ['go to', 'open', 'show', 'switch to', 'view', 'the']:
        text_lower = re.sub(rf'^{prefix}\s+', '', text_lower)

    # Remove tab/panel/section suffix
    text_lower = re.sub(r'\s*(tab|panel|section)\s*$', '', text_lower)

    # Clean up and extract the tab name
    tab_name = text_lower.strip()

    # Normalize common variations
    tab_aliases = {
        'ai copilot': 'copilot',
        'ai assistant': 'copilot',
        'poll': 'polls',
        'case': 'cases',
        'case study': 'cases',
        'case studies': 'cases',
        'casestudies': 'cases',
        'request': 'requests',
        'post case': 'cases',
        'student roster': 'roster',
        'class roster': 'roster',
        'enroll': 'enrollment',
        'enrollments': 'enrollment',
        'my performance': 'my-performance',
        'best practice': 'best-practice',
        'best practices': 'best-practice',
    }

    return {"tabName": tab_aliases.get(tab_name, tab_name)}


def _extract_dropdown_selection(transcript: str) -> Dict[str, Any]:
    """Extract dropdown selection info from transcript."""
    text_lower = transcript.lower()

    # Extract ordinal or name
    ordinals = {
        'first': 0, 'second': 1, 'third': 2, 'fourth': 3, 'fifth': 4,
        'last': -1, '1st': 0, '2nd': 1, '3rd': 2, '4th': 3, '5th': 4,
        'one': 0, 'two': 1, 'three': 2, 'four': 3, 'five': 4,
    }

    for ordinal, index in ordinals.items():
        if ordinal in text_lower:
            return {"optionIndex": index, "optionName": ordinal}

    # Extract the selection name - remove command words
    for prefix in ['select', 'choose', 'pick', 'use', 'switch to', 'the']:
        text_lower = re.sub(rf'^{prefix}\s+', '', text_lower)

    # Remove type words
    for suffix in ['course', 'session', 'option', 'item']:
        text_lower = re.sub(rf'\s+{suffix}\s*$', '', text_lower)

    option_name = text_lower.strip()
    return {"optionName": option_name} if option_name else {}


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
        session_id = _resolve_session_id(db, current_page)
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
        session_id = _resolve_session_id(db, current_page)
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
        session_id = _resolve_session_id(db, current_page)
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
) -> Optional[Any]:
    """Execute an MCP tool and return results, including UI actions for frontend."""
    try:
        # === UNIVERSAL UI ELEMENT INTERACTIONS ===
        # All UI actions now use universal handlers that work across all pages

        # === UNIVERSAL FORM DICTATION ===
        # Works for ANY input field - title, syllabus, objectives, poll question, post content, etc.
        if action == 'ui_dictate_input':
            extracted = _extract_universal_dictation(transcript or "")
            if extracted:
                field_name = extracted.get("field", "input")
                value = extracted.get("value", "")
                return {
                    "action": "fill_input",
                    "message": f"Setting {field_name} to: {value[:50]}{'...' if len(value) > 50 else ''}",
                    "ui_actions": [
                        {"type": "ui.fillInput", "payload": {"target": field_name, "value": value}},
                        {"type": "ui.toast", "payload": {"message": f"{field_name.title()} set", "type": "success"}},
                    ],
                }
            return {"message": "Please specify what you'd like to fill in."}

        # === UNIVERSAL DROPDOWN EXPANSION ===
        # Works for ANY dropdown on any page - fetches options and reads them verbally
        if action == 'ui_expand_dropdown':
            # Extract which dropdown from transcript, or default to finding any dropdown
            dropdown_hint = _extract_dropdown_hint(transcript or "")

            # Fetch options based on dropdown type
            options: list[DropdownOption] = []
            if 'course' in dropdown_hint or not dropdown_hint:
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
                    result = _execute_tool(db, 'list_sessions', {"course_id": course_id})
                    sessions = result.get("sessions", []) if isinstance(result, dict) else []
                    if sessions:
                        options = [DropdownOption(label=s.get('title', f"Session {s['id']}"), value=str(s['id'])) for s in sessions]

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
                return {
                    "action": "expand_dropdown",
                    "message": "The dropdown is empty. There are no options available.",
                    "ui_actions": [
                        {"type": "ui.expandDropdown", "payload": {"target": dropdown_hint, "findAny": True}},
                    ],
                }

        # === UNIVERSAL TAB SWITCHING ===
        # The ui_switch_tab action now works universally for any tab name
        if action == 'ui_switch_tab':
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
                        return {
                            "action": "switch_tab_with_post_offer",
                            "message": f"Switching to discussion. {offer_prompt}",
                            "ui_actions": [
                                {"type": "ui.switchTab", "payload": {"tabName": tab_name, "target": f"tab-{tab_name}"}},
                            ],
                            "post_offer": True,
                        }

            return {
                "action": "switch_tab",
                "message": f"Switching to {tab_name} tab.",
                "ui_actions": [
                    {"type": "ui.switchTab", "payload": {"tabName": tab_name, "target": f"tab-{tab_name}"}},
                    {"type": "ui.toast", "payload": {"message": f"Switched to {tab_name}", "type": "info"}},
                ],
            }

        # === UNIVERSAL DROPDOWN SELECTION ===
        if action == 'ui_select_dropdown':
            selection_info = _extract_dropdown_selection(transcript or "")
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
            else:
                # Extract from transcript
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
                        {"type": "ui.clickButton", "payload": {"target": button_target}},
                        {"type": "ui.toast", "payload": {"message": f"{button_label} clicked", "type": "success"}},
                    ],
                }
            return {"message": "I couldn't determine which button to click."}

        # Note: Specific tab handlers (open_enrollment_tab, open_create_tab, open_manage_tab)
        # are now handled by the universal ui_switch_tab action above

        # === UNDO/CONTEXT ACTIONS ===
        if action == 'undo_action':
            if not user_id:
                return {"error": "Cannot undo without user context."}

            last_action = context_store.get_last_undoable_action(user_id)
            if not last_action:
                return {
                    "message": "Nothing to undo. Your recent actions don't have undo data.",
                    "ui_actions": [{"type": "ui.toast", "payload": {"message": "Nothing to undo", "type": "info"}}],
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
            return {
                "message": "Context cleared. Starting fresh!",
                "ui_actions": [{"type": "ui.toast", "payload": {"message": "Context cleared", "type": "success"}}],
            }

        # === CONTEXT/STATUS ACTIONS ===
        if action == 'get_status':
            return _get_page_context(db, current_page)

        if action == 'get_help':
            return {
                "message": "I can help you with: navigating pages, listing courses and sessions, "
                           "starting copilot, creating polls, viewing forum discussions, pinning posts, "
                           "generating reports, and managing enrollments. Just ask!",
                "available_commands": [
                    "Show my courses", "Go to forum", "Start copilot",
                    "Create a poll", "Show pinned posts", "Summarize discussion",
                    "Generate report", "Go live", "End session"
                ]
            }

        # === COURSE ACTIONS ===
        if action == 'list_courses':
            return _execute_tool(db, 'list_courses', {"skip": 0, "limit": 100})

        if action == 'create_course':
            # Start conversational form-filling flow
            first_question = conversation_manager.start_form_filling(
                user_id, "create_course", "/courses"
            )
            return {
                "action": "create_course",
                "ui_actions": [
                    {"type": "ui.navigate", "payload": {"path": "/courses"}},
                    {"type": "ui.switchTab", "payload": {"tabName": "create", "target": "tab-create"}},
                ],
                "message": first_question or "Opening course creation. What would you like to name the course?",
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
            return {"error": "No courses found to select."}

        if action == 'view_course_details':
            course_id = _resolve_course_id(db, current_page, user_id)
            if course_id:
                return _execute_tool(db, 'get_course', {"course_id": course_id})
            return {"error": "No course selected. Please navigate to a course first."}

        # === SESSION ACTIONS ===
        if action == 'list_sessions':
            course_id = _resolve_course_id(db, current_page, user_id)
            if not course_id:
                return []
            return _execute_tool(db, 'list_sessions', {"course_id": course_id})

        if action == 'create_session':
            course_id = _resolve_course_id(db, current_page, user_id)
            # Start conversational form-filling flow
            first_question = conversation_manager.start_form_filling(
                user_id, "create_session", "/sessions"
            )
            return {
                "action": "create_session",
                "course_id": course_id,
                "ui_actions": [
                    {"type": "ui.navigate", "payload": {"path": "/sessions"}},
                    {"type": "ui.switchTab", "payload": {"tabName": "create", "target": "tab-create"}},
                ],
                "message": first_question or "Opening session creation. What would you like to call this session?",
                "conversation_state": "form_filling",
            }

        if action == 'select_session':
            course_id = _resolve_course_id(db, current_page, user_id)
            if course_id:
                result = _execute_tool(db, 'list_sessions', {"course_id": course_id})
                sessions = result.get("sessions", []) if isinstance(result, dict) else []
                if sessions and len(sessions) > 0:
                    first_session = sessions[0]
                    # Update context memory with selected session
                    if user_id:
                        context_store.update_context(user_id, active_session_id=first_session['id'])
                    return {
                        "action": "select_session",
                        "session": first_session,
                        "ui_actions": [
                            {"type": "ui.navigate", "payload": {"path": f"/sessions/{first_session['id']}"}},
                            {"type": "ui.toast", "payload": {"message": f"Selected: {first_session.get('title', 'session')}", "type": "success"}},
                        ],
                    }
            return {"error": "No sessions found to select."}

        if action == 'go_live':
            session_id = _resolve_session_id(db, current_page, user_id)
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
                    result["ui_actions"] = [
                        {"type": "ui.navigate", "payload": {"path": f"/console?session={session_id}"}},
                        {"type": "ui.toast", "payload": {"message": "Session is now LIVE!", "type": "success"}},
                    ]
                return result
            return {"error": "No session found to go live."}

        if action == 'end_session':
            session_id = _resolve_session_id(db, current_page, user_id)
            if not session_id:
                return {"error": "No active session found to end."}

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

        # === COPILOT ACTIONS ===
        if action == 'get_interventions':
            session_id = _resolve_session_id(db, current_page, user_id)
            if not session_id:
                return []
            return _execute_tool(db, 'get_copilot_suggestions', {"session_id": session_id})

        if action == 'start_copilot':
            session_id = _resolve_session_id(db, current_page, user_id)
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
                    {"type": "ui.toast", "payload": {"message": "Copilot is now active!", "type": "success"}},
                ]
            return result

        if action == 'stop_copilot':
            session_id = _resolve_session_id(db, current_page, user_id)
            if not session_id:
                return None

            # Check if already confirmed (from confirmation flow)
            conv_context = conversation_manager.get_context(user_id)
            if conv_context.state != ConversationState.IDLE or not conv_context.pending_action:
                # Request confirmation first (destructive action)
                confirmation_prompt = conversation_manager.request_confirmation(
                    user_id,
                    "stop_copilot",
                    {"session_id": session_id, "voice_id": "btn-stop-copilot"},
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
                    {"type": "ui.toast", "payload": {"message": "Copilot stopped", "type": "info"}},
                ]
            return result

        # === POLL ACTIONS ===
        if action == 'create_poll':
            session_id = _resolve_session_id(db, current_page, user_id)
            # Start conversational form-filling flow for poll
            first_question = conversation_manager.start_form_filling(
                user_id, "create_poll", "/console"
            )
            return {
                "action": "create_poll",
                "session_id": session_id,
                "ui_actions": [
                    {"type": "ui.switchTab", "payload": {"tabName": "polls", "target": "tab-polls"}},
                    {"type": "ui.toast", "payload": {"message": "Opening poll creator...", "type": "info"}},
                ],
                "message": first_question or "Opening poll creation. What question would you like to ask your students?",
                "conversation_state": "form_filling",
            }

        # === REPORT ACTIONS ===
        if action == 'generate_report':
            session_id = _resolve_session_id(db, current_page, user_id)
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
                result["ui_actions"] = [
                    {"type": "ui.navigate", "payload": {"path": "/reports"}},
                    {"type": "ui.toast", "payload": {"message": "Generating report...", "type": "info"}},
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
            return {
                "action": "manage_enrollments",
                "course_id": course_id,
                "ui_actions": [
                    {"type": "ui.navigate", "payload": {"path": f"/courses/{course_id}" if course_id else "/courses"}},
                    {"type": "ui.openModal", "payload": {"modal": "manageEnrollments", "courseId": course_id}},
                ],
                "message": "Opening enrollment management.",
            }

        if action == 'list_student_pool':
            # List available students (not enrolled) for selection
            course_id = _resolve_course_id(db, current_page, user_id)
            if not course_id:
                return {"message": "Please select a course first to see the student pool."}

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
                return {"message": "The student pool is empty. All students are already enrolled in this course."}

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
            return {
                "action": "enroll_selected",
                "message": "Enrolling the selected students.",
                "ui_actions": [
                    {"type": "ui.clickButton", "payload": {"target": "enroll-selected"}},
                ],
            }

        if action == 'enroll_all':
            return {
                "action": "enroll_all",
                "message": "Enrolling all available students.",
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

        # === FORUM ACTIONS ===
        if action == 'post_case':
            session_id = _resolve_session_id(db, current_page, user_id)
            return {
                "action": "post_case",
                "session_id": session_id,
                "ui_actions": [
                    {"type": "ui.navigate", "payload": {"path": "/forum"}},
                    {"type": "ui.openModal", "payload": {"modal": "postCase", "sessionId": session_id}},
                ],
                "message": "Opening case study creation. What case would you like to post?",
            }

        if action == 'view_posts':
            session_id = _resolve_session_id(db, current_page, user_id)
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
            session_id = _resolve_session_id(db, current_page, user_id)
            if session_id:
                pinned = _execute_tool(db, 'get_pinned_posts', {"session_id": session_id})
                return {
                    "pinned_posts": pinned or [],
                    "count": len(pinned) if pinned else 0,
                    "ui_actions": [{"type": "ui.navigate", "payload": {"path": "/forum"}}],
                }
            return {"pinned_posts": [], "count": 0}

        if action == 'summarize_discussion':
            session_id = _resolve_session_id(db, current_page, user_id)
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
            session_id = _resolve_session_id(db, current_page, user_id)
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


def get_page_suggestions(path: str) -> List[str]:
    """Get contextual suggestions for a page"""
    suggestions = {
        '/courses': ["Create a new course", "Generate session plans", "View enrollments"],
        '/sessions': ["Start a session", "View session details", "Check copilot status"],
        '/forum': ["Post a case study", "View recent posts", "Pin a post"],
        '/console': ["Start copilot", "Create a poll", "View suggestions"],
        '/reports': ["Generate a report", "View participation", "Check scores"],
    }
    return suggestions.get(path, ["How can I help?"])


def get_action_suggestions(action: str) -> List[str]:
    """Get follow-up suggestions after an action"""
    suggestions = {
        # UI interaction suggestions
        'ui_select_course': ["Select a session", "Go to enrollment tab", "Generate report"],
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
        'view_posts': ["Pin a post", "Label post", "Summarize discussion"],
        'get_pinned_posts': ["View all posts", "Post case", "Create poll"],
        'summarize_discussion': ["Show questions", "View pinned", "Create poll"],
        'get_student_questions': ["View posts", "Create poll", "Pin a post"],
    }
    return suggestions.get(action, ["What else can I help with?"])


def generate_fallback_response(transcript: str, context: Optional[List[str]]) -> str:
    """Generate a helpful response when intent is unclear"""
    
    # Check for greetings
    greetings = ['hi', 'hello', 'hey', 'good morning', 'good afternoon']
    if any(g in transcript.lower() for g in greetings):
        return "Hello! How can I help you today? You can ask me to show your courses, start a session, or navigate to any page."
    
    # Check for thanks
    thanks = ['thank', 'thanks', 'appreciate']
    if any(t in transcript.lower() for t in thanks):
        return "You're welcome! Is there anything else I can help you with?"
    
    # Check for help
    if 'help' in transcript.lower():
        return "I can help you with: navigating pages, listing your courses and sessions, starting the AI copilot, creating polls, and generating reports. What would you like to do?"
    
    # Default
    return f"I heard '{transcript}', but I'm not sure what you'd like me to do. Try saying 'show my courses', 'go to forum', or 'start copilot'."
