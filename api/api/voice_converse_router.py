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
from mcp_server.server import TOOL_REGISTRY
from workflows.voice_orchestrator import run_voice_orchestrator, generate_summary
from workflows.llm_utils import get_llm_with_tracking, invoke_llm_with_metrics, parse_json_response

# Import your existing dependencies
# from .auth import get_current_user
# from .database import get_db
# from ..mcp_server.server import mcp_server

router = APIRouter(prefix="/voice", tags=["voice"])


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
# Includes sub-page actions like create course, select session, etc.
ACTION_PATTERNS = {
    # === COURSE ACTIONS ===
    'list_courses': [
        r'\b(list|show|get|what are|display|see)\s+(all\s+)?(my\s+)?courses\b',
        r'\bmy courses\b',
        r'\bcourse list\b',
        r'\bwhat courses\b',
        r'\bhow many courses\b',
    ],
    'create_course': [
        r'\bcreate\s+(a\s+)?(new\s+)?course\b',
        r'\bmake\s+(a\s+)?(new\s+)?course\b',
        r'\badd\s+(a\s+)?(new\s+)?course\b',
        r'\bnew\s+course\b',
        r'\bset\s*up\s+(a\s+)?course\b',
        r'\bstart\s+(a\s+)?new\s+course\b',
    ],
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
    'create_session': [
        r'\bcreate\s+(a\s+)?(new\s+)?session\b',
        r'\bmake\s+(a\s+)?(new\s+)?session\b',
        r'\badd\s+(a\s+)?(new\s+)?session\b',
        r'\bnew\s+session\b',
        r'\bschedule\s+(a\s+)?session\b',
        r'\bset\s*up\s+(a\s+)?session\b',
    ],
    'select_session': [
        r'\b(select|choose|pick|open)\s+(the\s+)?(first|second|third|last|\d+(?:st|nd|rd|th)?)\s+session\b',
        r'\b(select|choose|pick|open)\s+session\s+(\d+|one|two|three)\b',
        r'\bgo\s+(to|into)\s+(the\s+)?(first|second|third|last)\s+session\b',
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
    # === COPILOT ACTIONS ===
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
    'get_interventions': [
        r'\b(show|get|what are|display)\s+(the\s+)?(copilot\s+)?suggestions\b',
        r'\binterventions\b',
        r'\bconfusion points\b',
        r'\bcopilot\s+(suggestions|insights|recommendations)\b',
        r'\bwhat does\s+(the\s+)?copilot\s+(suggest|recommend|say)\b',
        r'\bany\s+suggestions\b',
    ],
    # === POLL ACTIONS ===
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
    # === REPORT ACTIONS ===
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
    # === FORUM ACTIONS ===
    'post_case': [
        r'\bpost\s+(a\s+)?case(\s+study)?\b',
        r'\bcreate\s+(a\s+)?case(\s+study)?\b',
        r'\badd\s+(a\s+)?case(\s+study)?\b',
        r'\bnew\s+case(\s+study)?\b',
        r'\bshare\s+(a\s+)?case\b',
    ],
    'view_posts': [
        r'\b(show|view|see|display)\s+(the\s+)?(forum\s+)?posts\b',
        r'\b(show|view|see)\s+(the\s+)?discussions?\b',
        r'\bwhat\s+(are\s+)?(students|people)\s+(saying|discussing|posting)\b',
        r'\brecent\s+posts\b',
        r'\blatest\s+posts\b',
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

        # === FORUM RESPONSES ===
        if intent_value == 'post_case':
            return "Opening case study creation. What scenario would you like students to discuss?"

        if intent_value == 'view_posts':
            if isinstance(results, dict) and results.get("posts"):
                posts = results["posts"]
                if len(posts) > 0:
                    return f"There are {len(posts)} posts in the forum. The latest is about: {posts[0].get('content', '')[:50]}..."
            return "No posts yet in this session's forum."

    # Default fallback
    return "I can help you navigate pages, manage courses and sessions, create polls, generate reports, and more. What would you like to do?"


@router.post("/converse", response_model=ConverseResponse)
async def voice_converse(request: ConverseRequest, db: Session = Depends(get_db)):
    """
    Conversational voice endpoint that processes natural language
    and returns appropriate responses with actions.

    OPTIMIZED FLOW (fast regex checks before expensive LLM calls):
    1. Regex navigation check (instant)
    2. Regex action check (instant)
    3. LLM orchestrator (only for complex requests)
    4. Template-based summary (no LLM)
    """
    transcript = request.transcript.strip()

    if not transcript:
        return ConverseResponse(
            message=sanitize_speech("I didn't catch that. Could you say it again?"),
            suggestions=["Show my courses", "Start a session", "Open forum"]
        )

    # 1. Check for navigation intent first (fast regex - instant)
    nav_path = detect_navigation_intent(transcript)
    if nav_path:
        message = sanitize_speech(generate_conversational_response('navigate', nav_path))
        return ConverseResponse(
            message=message,
            action=ActionResponse(type='navigate', target=nav_path),
            suggestions=get_page_suggestions(nav_path)
        )

    # 2. Check for action intent via regex BEFORE expensive LLM call (fast - instant)
    action = detect_action_intent(transcript)
    if action:
        result = await execute_action(action, request.user_id, request.current_page, db)
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


def _resolve_course_id(db: Session, current_page: Optional[str]) -> Optional[int]:
    course_id, _ = _parse_ids_from_path(current_page)
    if course_id:
        return course_id
    course = db.query(Course).order_by(Course.created_at.desc()).first()
    return course.id if course else None


def _resolve_session_id(db: Session, current_page: Optional[str]) -> Optional[int]:
    _, session_id = _parse_ids_from_path(current_page)
    if session_id:
        return session_id
    session = (
        db.query(SessionModel)
        .filter(SessionModel.status == SessionStatus.live)
        .order_by(SessionModel.created_at.desc())
        .first()
    )
    if session:
        return session.id
    session = db.query(SessionModel).order_by(SessionModel.created_at.desc()).first()
    return session.id if session else None


def _execute_tool(db: Session, tool_name: str, args: Dict[str, Any]) -> Optional[Any]:
    tool_info = TOOL_REGISTRY.get(tool_name)
    if not tool_info:
        return None
    handler = tool_info["handler"]
    return invoke_tool_handler(handler, args, db=db)


async def execute_action(
    action: str,
    user_id: Optional[int],
    current_page: Optional[str],
    db: Session,
) -> Optional[Any]:
    """Execute an MCP tool and return results, including UI actions for frontend."""
    try:
        # === COURSE ACTIONS ===
        if action == 'list_courses':
            return _execute_tool(db, 'list_courses', {"skip": 0, "limit": 100})

        if action == 'create_course':
            # Return UI action to open create course modal/page
            return {
                "action": "create_course",
                "ui_actions": [
                    {"type": "ui.navigate", "payload": {"path": "/courses"}},
                    {"type": "ui.openModal", "payload": {"modal": "createCourse"}},
                ],
                "message": "Opening course creation. What would you like to name the course?",
            }

        if action == 'select_course':
            courses = _execute_tool(db, 'list_courses', {"skip": 0, "limit": 10})
            if courses and len(courses) > 0:
                first_course = courses[0]
                return {
                    "action": "select_course",
                    "course": first_course,
                    "ui_actions": [
                        {"type": "ui.navigate", "payload": {"path": f"/courses/{first_course['id']}"}},
                    ],
                }
            return {"error": "No courses found to select."}

        if action == 'view_course_details':
            course_id = _resolve_course_id(db, current_page)
            if course_id:
                return _execute_tool(db, 'get_course', {"course_id": course_id})
            return {"error": "No course selected. Please navigate to a course first."}

        # === SESSION ACTIONS ===
        if action == 'list_sessions':
            course_id = _resolve_course_id(db, current_page)
            if not course_id:
                return []
            return _execute_tool(db, 'list_sessions', {"course_id": course_id})

        if action == 'create_session':
            course_id = _resolve_course_id(db, current_page)
            return {
                "action": "create_session",
                "course_id": course_id,
                "ui_actions": [
                    {"type": "ui.navigate", "payload": {"path": "/sessions"}},
                    {"type": "ui.openModal", "payload": {"modal": "createSession", "courseId": course_id}},
                ],
                "message": "Opening session creation.",
            }

        if action == 'select_session':
            course_id = _resolve_course_id(db, current_page)
            if course_id:
                sessions = _execute_tool(db, 'list_sessions', {"course_id": course_id})
                if sessions and len(sessions) > 0:
                    first_session = sessions[0]
                    return {
                        "action": "select_session",
                        "session": first_session,
                        "ui_actions": [
                            {"type": "ui.navigate", "payload": {"path": f"/sessions/{first_session['id']}"}},
                        ],
                    }
            return {"error": "No sessions found to select."}

        if action == 'go_live':
            session_id = _resolve_session_id(db, current_page)
            if session_id:
                result = _execute_tool(db, 'update_session_status', {"session_id": session_id, "status": "live"})
                if result:
                    result["ui_actions"] = [
                        {"type": "ui.navigate", "payload": {"path": f"/console?session={session_id}"}},
                    ]
                return result
            return {"error": "No session found to go live."}

        if action == 'end_session':
            session_id = _resolve_session_id(db, current_page)
            if session_id:
                return _execute_tool(db, 'update_session_status', {"session_id": session_id, "status": "completed"})
            return {"error": "No active session found to end."}

        # === COPILOT ACTIONS ===
        if action == 'get_interventions':
            session_id = _resolve_session_id(db, current_page)
            if not session_id:
                return []
            return _execute_tool(db, 'get_copilot_suggestions', {"session_id": session_id})

        if action == 'start_copilot':
            session_id = _resolve_session_id(db, current_page)
            if not session_id:
                return None
            return _execute_tool(db, 'start_copilot', {"session_id": session_id})

        if action == 'stop_copilot':
            session_id = _resolve_session_id(db, current_page)
            if not session_id:
                return None
            return _execute_tool(db, 'stop_copilot', {"session_id": session_id})

        # === POLL ACTIONS ===
        if action == 'create_poll':
            session_id = _resolve_session_id(db, current_page)
            return {
                "action": "create_poll",
                "session_id": session_id,
                "ui_actions": [
                    {"type": "ui.openModal", "payload": {"modal": "createPoll", "sessionId": session_id}},
                ],
                "message": "Opening poll creation. What question would you like to ask?",
                "needs_input": ["question", "options"],
            }

        # === REPORT ACTIONS ===
        if action == 'generate_report':
            session_id = _resolve_session_id(db, current_page)
            if not session_id:
                return None
            result = _execute_tool(db, 'generate_report', {"session_id": session_id})
            if result:
                result["ui_actions"] = [
                    {"type": "ui.navigate", "payload": {"path": "/reports"}},
                ]
            return result

        # === ENROLLMENT ACTIONS ===
        if action == 'list_enrollments':
            course_id = _resolve_course_id(db, current_page)
            if not course_id:
                return []
            return _execute_tool(db, 'get_enrolled_students', {"course_id": course_id})

        if action == 'manage_enrollments':
            course_id = _resolve_course_id(db, current_page)
            return {
                "action": "manage_enrollments",
                "course_id": course_id,
                "ui_actions": [
                    {"type": "ui.navigate", "payload": {"path": f"/courses/{course_id}" if course_id else "/courses"}},
                    {"type": "ui.openModal", "payload": {"modal": "manageEnrollments", "courseId": course_id}},
                ],
                "message": "Opening enrollment management.",
            }

        # === FORUM ACTIONS ===
        if action == 'post_case':
            session_id = _resolve_session_id(db, current_page)
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
            session_id = _resolve_session_id(db, current_page)
            if session_id:
                posts = _execute_tool(db, 'get_session_posts', {"session_id": session_id})
                if posts:
                    posts_result = {"posts": posts}
                    posts_result["ui_actions"] = [{"type": "ui.navigate", "payload": {"path": "/forum"}}]
                    return posts_result
            return {
                "posts": [],
                "ui_actions": [{"type": "ui.navigate", "payload": {"path": "/forum"}}],
            }

        # For actions that need more info, return guidance
        return {"message": f"Action '{action}' recognized but needs more details."}

    except Exception as e:
        print(f"Action execution failed: {e}")
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
        'view_posts': ["Pin a post", "Label post", "Post case"],
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
