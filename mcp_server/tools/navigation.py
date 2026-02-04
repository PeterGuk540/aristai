"""
Navigation and UI control MCP tools.

Tools for navigating the AristAI interface and controlling UI elements.
"""

import logging
from typing import Any, Dict

logger = logging.getLogger(__name__)


def navigate_to_page(page: str) -> Dict[str, Any]:
    """
    Navigate to a specific page in the AristAI interface.
    
    Args:
        page: The page to navigate to (courses, sessions, forum, reports, console, dashboard)
    
    Returns:
        Navigation result with path and confirmation
    """
    page_map = {
        'courses': '/courses',
        'course': '/courses', 
        'sessions': '/sessions',
        'session': '/sessions',
        'forum': '/forum',
        'reports': '/reports',
        'report': '/reports',
        'console': '/console',
        'dashboard': '/dashboard',
        'home': '/dashboard',
        'settings': '/console'
    }
    
    page_lower = page.lower().strip()
    
    # Direct matches
    if page_lower in page_map:
        path = page_map[page_lower]
        return {
            "success": True,
            "action": "navigate",
            "path": path,
            "page": page_lower,
            "message": f"Navigating to {page_lower} page...",
            "voice_response": f"I'll take you to the {page_lower} page now."
        }
    
    # Partial matches
    for key, path in page_map.items():
        if key in page_lower:
            return {
                "success": True,
                "action": "navigate", 
                "path": path,
                "page": key,
                "message": f"Navigating to {key} page...",
                "voice_response": f"I'll take you to the {key} page now."
            }
    
    return {
        "success": False,
        "error": f"Unknown page '{page}'. Available pages: courses, sessions, forum, reports, console, dashboard",
        "voice_response": f"Sorry, I don't know how to navigate to {page}. Available pages are courses, sessions, forum, reports, console, and dashboard."
    }


def get_available_pages() -> Dict[str, Any]:
    """
    Get list of available pages for navigation.
    
    Returns:
        List of all available pages with descriptions
    """
    pages = {
        "courses": "View and manage your courses",
        "sessions": "Access class sessions and meetings", 
        "forum": "Join discussions and view posts",
        "reports": "Generate and view session reports",
        "console": "Access teaching tools and copilot",
        "dashboard": "Main homepage and overview"
    }
    
    return {
        "success": True,
        "pages": pages,
        "message": f"There are {len(pages)} available pages: {', '.join(pages.keys())}",
        "voice_response": f"You can navigate to any of these pages: {', '.join(pages.keys())}. Just say 'take me to' followed by the page name."
    }


def get_current_context(context: Dict[str, Any]) -> Dict[str, Any]:
    """
    Get current page context and available actions.
    
    Args:
        context: Current context from the application
    
    Returns:
        Context information and available actions
    """
    current_page = context.get('current_page', 'dashboard')
    user_role = context.get('user_role', 'student')
    
    actions = []
    if current_page == 'dashboard':
        actions = [
            "View courses",
            "Check sessions", 
            "Go to forum",
            "Generate reports",
            "Open console"
        ]
    elif current_page == 'courses':
        actions = [
            "Create new course",
            "View course details",
            "Manage enrollment",
            "Generate session plans"
        ]
    elif current_page == 'forum':
        actions = [
            "View discussions",
            "Post case study", 
            "Reply to posts",
            "Pin important posts"
        ]
    elif current_page == 'console':
        actions = [
            "Start AI copilot",
            "Create polls",
            "Upload roster",
            "Manage sessions"
        ]
    elif current_page == 'reports':
        actions = [
            "Generate report",
            "View existing reports",
            "Analyze participation",
            "Export data"
        ]
    
    return {
        "success": True,
        "current_page": current_page,
        "user_role": user_role,
        "available_actions": actions,
        "message": f"You are on the {current_page} page. Available actions: {', '.join(actions[:3])}",
        "voice_response": f"You're currently on the {current_page} page. You can {', '.join(actions[:3])}."
    }


def get_help_for_page(page: str) -> Dict[str, Any]:
    """
    Get help information for a specific page.
    
    Args:
        page: The page to get help for
    
    Returns:
        Help information and voice response
    """
    help_content = {
        "dashboard": "Your main homepage shows course overview, upcoming sessions, and quick access to all features.",
        "courses": "Here you can view all your courses, create new ones, manage enrollment, and generate AI session plans.",
        "sessions": "View and manage class sessions. Start live sessions, monitor discussions, and control session states.",
        "forum": "Participate in discussions, post case studies, reply to students, and moderate conversations.",
        "console": "Access teaching tools including AI copilot, poll creation, roster management, and session controls.",
        "reports": "Generate AI-powered reports, analyze student participation, and export session summaries."
    }
    
    page_lower = page.lower().strip()
    
    if page_lower in help_content:
        content = help_content[page_lower]
        return {
            "success": True,
            "page": page_lower,
            "help": content,
            "message": f"Help for {page_lower}: {content}",
            "voice_response": f"The {page_lower} page is where you can {content}"
        }
    
    return {
        "success": False,
        "error": f"No help available for page '{page}'",
        "voice_response": f"Sorry, I don't have help information for the {page} page."
    }