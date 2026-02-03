"""
Conversational Voice Endpoint for AristAI

This module provides a conversational AI interface that:
1. Understands natural language queries
2. Determines intent (navigate, execute action, provide info)
3. Returns conversational responses with context
4. Executes MCP tools when appropriate

Add this router to your main API router.
"""

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional, List, Any, Dict
import json
import re
from datetime import datetime

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


# Navigation intent patterns
NAVIGATION_PATTERNS = {
    r'\b(go to|open|show|navigate to|take me to)\s+(the\s+)?(courses?|course list|my courses)\b': '/courses',
    r'\b(go to|open|show|navigate to|take me to)\s+(the\s+)?(sessions?|session list)\b': '/sessions',
    r'\b(go to|open|show|navigate to|take me to)\s+(the\s+)?(forum|discussion|discussions)\b': '/forum',
    r'\b(go to|open|show|navigate to|take me to)\s+(the\s+)?(console|instructor console)\b': '/console',
    r'\b(go to|open|show|navigate to|take me to)\s+(the\s+)?(reports?|report page)\b': '/reports',
    r'\b(go to|open|show|navigate to|take me to)\s+(the\s+)?(dashboard|home)\b': '/dashboard',
}

# Action intent patterns (these will trigger MCP tool execution)
ACTION_PATTERNS = {
    'list_courses': [
        r'\b(list|show|get|what are)\s+(all\s+)?(my\s+)?courses\b',
        r'\bmy courses\b',
        r'\bcourse list\b',
    ],
    'list_sessions': [
        r'\b(list|show|get|what are)\s+(the\s+)?(live\s+)?sessions\b',
        r'\blive sessions\b',
        r'\bactive sessions\b',
    ],
    'start_copilot': [
        r'\bstart\s+(the\s+)?copilot\b',
        r'\bactivate\s+(the\s+)?copilot\b',
        r'\bturn on\s+(the\s+)?copilot\b',
    ],
    'stop_copilot': [
        r'\bstop\s+(the\s+)?copilot\b',
        r'\bdeactivate\s+(the\s+)?copilot\b',
        r'\bturn off\s+(the\s+)?copilot\b',
    ],
    'create_poll': [
        r'\bcreate\s+(a\s+)?poll\b',
        r'\bmake\s+(a\s+)?poll\b',
        r'\bstart\s+(a\s+)?poll\b',
    ],
    'generate_report': [
        r'\bgenerate\s+(a\s+)?report\b',
        r'\bcreate\s+(a\s+)?report\b',
        r'\bmake\s+(a\s+)?report\b',
    ],
    'get_interventions': [
        r'\b(show|get|what are)\s+(the\s+)?(copilot\s+)?suggestions\b',
        r'\binterventions\b',
        r'\bconfusion points\b',
    ],
    'list_enrollments': [
        r'\b(list|show|who are)\s+(the\s+)?(enrolled\s+)?students\b',
        r'\benrollment\s+(list|status)\b',
        r'\bhow many students\b',
    ],
}


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


def generate_conversational_response(
    intent_type: str,
    intent_value: str,
    results: Optional[Any] = None,
    context: Optional[List[str]] = None,
    current_page: Optional[str] = None,
) -> str:
    """Generate a natural conversational response"""
    
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
        if intent_value == 'list_courses' and results:
            if isinstance(results, list) and len(results) > 0:
                course_names = [c.get('title', 'Untitled') for c in results[:5]]
                if len(results) == 1:
                    return f"You have one course: {course_names[0]}. Would you like me to open it?"
                elif len(results) <= 3:
                    return f"You have {len(results)} courses: {', '.join(course_names)}. Which one would you like to work with?"
                else:
                    return f"You have {len(results)} courses, including {', '.join(course_names[:3])}, and {len(results) - 3} more. Would you like to see them all, or work with a specific one?"
            else:
                return "You don't have any courses yet. Would you like me to help you create one?"
        
        if intent_value == 'list_sessions' and results:
            if isinstance(results, list) and len(results) > 0:
                live = [s for s in results if s.get('status') == 'live']
                if live:
                    return f"There {'is' if len(live) == 1 else 'are'} {len(live)} live session{'s' if len(live) > 1 else ''} right now: {', '.join(s.get('title', 'Untitled') for s in live[:3])}. Would you like to join one?"
                else:
                    return f"No live sessions at the moment. You have {len(results)} sessions total. Would you like to start one?"
            else:
                return "No sessions found. Would you like to create a new session?"
        
        if intent_value == 'start_copilot':
            return "I've started the AI copilot. It will now monitor the discussion and provide suggestions every 90 seconds. I'll let you know when there are new insights."
        
        if intent_value == 'stop_copilot':
            return "Copilot has been stopped. You can restart it anytime by asking me."
        
        if intent_value == 'create_poll':
            return "I can help you create a poll. What question would you like to ask? Or, if you'd prefer, I can suggest some questions based on the current discussion."
        
        if intent_value == 'generate_report':
            return "I'm generating the session report now. This may take a moment as I analyze all the discussion posts. I'll let you know when it's ready."
        
        if intent_value == 'get_interventions' and results:
            if isinstance(results, list) and len(results) > 0:
                latest = results[0]
                suggestion = latest.get('suggestion_json', {})
                summary = suggestion.get('rolling_summary', '')
                confusion = suggestion.get('confusion_points', [])
                
                response = f"Here's the latest from the copilot: {summary}" if summary else "I have some suggestions from the copilot."
                
                if confusion:
                    response += f" I detected {len(confusion)} potential confusion point{'s' if len(confusion) > 1 else ''}: {confusion[0].get('issue', 'Unknown')}."
                    if len(confusion) > 1:
                        response += f" There are {len(confusion) - 1} more. Would you like details?"
                
                return response
            else:
                return "No suggestions yet from the copilot. It analyzes the discussion every 90 seconds when active."
        
        if intent_value == 'list_enrollments' and results:
            if isinstance(results, list):
                return f"There are {len(results)} students enrolled. Would you like me to list them or show participation stats?"
            return "I couldn't retrieve the enrollment information."
    
    # Default fallback
    return "I'm not sure how to help with that. You can ask me to navigate to a page, list your courses, start a session, create a poll, or get copilot suggestions."


@router.post("/converse", response_model=ConverseResponse)
async def voice_converse(request: ConverseRequest):
    """
    Conversational voice endpoint that processes natural language
    and returns appropriate responses with actions.
    """
    transcript = request.transcript.strip()
    
    if not transcript:
        return ConverseResponse(
            message="I didn't catch that. Could you say it again?",
            suggestions=["Show my courses", "Start a session", "Open forum"]
        )
    
    # Check for navigation intent first
    nav_path = detect_navigation_intent(transcript)
    if nav_path:
        return ConverseResponse(
            message=generate_conversational_response('navigate', nav_path),
            action=ActionResponse(type='navigate', target=nav_path),
            suggestions=get_page_suggestions(nav_path)
        )
    
    # Check for action intent
    action = detect_action_intent(transcript)
    if action:
        # Execute the action and get results
        results = await execute_action(action, request.user_id, request.current_page)
        
        return ConverseResponse(
            message=generate_conversational_response(
                'execute', 
                action, 
                results=results,
                context=request.context,
                current_page=request.current_page
            ),
            action=ActionResponse(type='execute', executed=True),
            results=results,
            suggestions=get_action_suggestions(action)
        )
    
    # No clear intent - try to be helpful
    return ConverseResponse(
        message=generate_fallback_response(transcript, request.context),
        action=ActionResponse(type='info'),
        suggestions=["Show my courses", "Go to forum", "Start copilot", "Create a poll"]
    )


async def execute_action(action: str, user_id: Optional[int], current_page: Optional[str]) -> Optional[Any]:
    """Execute an MCP tool and return results"""
    # This would integrate with your MCP server
    # For now, returning mock data - replace with actual MCP calls
    
    try:
        if action == 'list_courses':
            # Call your actual API
            # courses = await mcp_server.call_tool('list_courses', {})
            # return courses
            return []  # Replace with actual implementation
        
        if action == 'list_sessions':
            return []  # Replace with actual implementation
        
        if action == 'get_interventions':
            return []  # Replace with actual implementation
        
        if action == 'list_enrollments':
            return []  # Replace with actual implementation
        
        # For actions that don't return data
        return None
        
    except Exception as e:
        print(f"Action execution failed: {e}")
        return None


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
        'list_courses': ["Open a course", "Create new course", "View sessions"],
        'list_sessions': ["Start a session", "Go to forum", "View details"],
        'start_copilot': ["View suggestions", "Create a poll", "Post case"],
        'stop_copilot': ["Generate report", "View interventions", "Go to forum"],
        'get_interventions': ["Create suggested poll", "Post to forum", "View details"],
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
