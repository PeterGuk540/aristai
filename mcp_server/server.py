"""
AristAI MCP Server Implementation.

This module implements a Model Context Protocol (MCP) server that exposes
all AristAI classroom forum operations as tools. It enables voice assistants
and other MCP clients to perform any forum action without clicks or keyboard input.

Usage:
    # Run as standalone server (stdio transport for Claude Desktop)
    python -m mcp_server.server

    # Run as HTTP server (SSE transport for web clients)
    python -m mcp_server.server --transport sse --port 8080

Features:
    - 30+ tools covering all forum operations
    - Read tools execute immediately
    - Write tools require confirmation (handled by client)
    - Full observability and audit logging
    - Graceful error handling with helpful messages
"""

import asyncio
import inspect
import logging
import os
import sys
from typing import Any, Dict, List, Optional

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import (
    Tool,
    TextContent,
    CallToolResult,
    ListToolsResult,
)

from api.core.database import SessionLocal
from api.services.action_preview import build_action_preview
from api.services.action_store import ActionStore
from api.services.tool_response import normalize_tool_result

# Import all tool modules
from mcp_server.tools import (
    courses,
    sessions,
    forum,
    polls,
    reports,
    copilot,
    enrollment,
    navigation,
    resolve,
    voice,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize MCP Server
server = Server("aristai-mcp-server")
ACTION_TOOL_NAMES = {"plan_action", "execute_action", "cancel_action"}
action_store = ActionStore()


# ============ Tool Registry ============

# Comprehensive tool registry with all forum operations
TOOL_REGISTRY: Dict[str, Dict[str, Any]] = {}


def _handler_requires_db(handler: callable) -> bool:
    try:
        signature = inspect.signature(handler)
    except (TypeError, ValueError):
        return False
    return "db" in signature.parameters


def _invoke_tool_handler_in_thread(handler: callable, arguments: Dict[str, Any]) -> Any:
    if _handler_requires_db(handler):
        db = SessionLocal()
        try:
            return handler(db=db, **arguments)
        finally:
            db.close()
    return handler(**arguments)


def _invoke_tool_handler_with_db(
    handler: callable, arguments: Dict[str, Any], db: Any
) -> Any:
    if _handler_requires_db(handler):
        return handler(db=db, **arguments)
    return handler(**arguments)


def _plan_action_in_thread(tool_name: str, args: Dict[str, Any], user_id: Optional[int]) -> Dict[str, Any]:
    db = SessionLocal()
    try:
        return plan_action(db=db, tool_name=tool_name, args=args, user_id=user_id)
    finally:
        db.close()


def register_tool(
    name: str,
    description: str,
    parameters: Dict[str, Any],
    handler: callable,
    mode: str = "read",
    category: str = "general",
):
    """Register a tool in the registry."""
    TOOL_REGISTRY[name] = {
        "name": name,
        "description": description,
        "parameters": parameters,
        "handler": handler,
        "mode": mode,  # "read" or "write"
        "category": category,
    }


def plan_action(
    db: Any,
    tool_name: str,
    args: Dict[str, Any],
    user_id: Optional[int] = None,
    **kwargs: Any,
) -> Dict[str, Any]:
    tool_info = TOOL_REGISTRY.get(tool_name)
    if not tool_info:
        return {"success": False, "error": f"Unknown tool '{tool_name}'"}
    if tool_info.get("mode") != "write":
        return {"success": False, "error": f"Tool '{tool_name}' is not a write action"}
    preview = build_action_preview(tool_name, args, db=db)
    action = action_store.create_action(
        user_id=user_id,
        tool_name=tool_name,
        args=args,
        preview=preview,
    )
    return {
        "success": True,
        "action_id": action.action_id,
        "requires_confirmation": True,
        "preview": preview,
        "message": "Action planned. Please confirm to execute.",
    }


def execute_action(
    db: Any,
    action_id: str,
    user_id: Optional[int] = None,
    **kwargs: Any,
) -> Dict[str, Any]:
    action = action_store.get_action(action_id)
    if not action:
        return {"success": False, "error": "Action not found or expired"}
    ownership_error = ActionStore.ensure_owner(action, user_id)
    if ownership_error:
        return {"success": False, "error": ownership_error}
    if action.status != "planned":
        return {"success": False, "error": f"Action is {action.status} and cannot be executed"}
    tool_info = TOOL_REGISTRY.get(action.tool_name)
    if not tool_info:
        action_store.update_action(action.action_id, status="failed", result={"error": "Unknown tool"})
        return {"success": False, "error": "Unknown tool"}
    result = _invoke_tool_handler_with_db(tool_info["handler"], action.args, db=db)
    action_store.update_action(
        action.action_id,
        status="executed",
        result={"result": result},
    )
    return {"success": True, "action_id": action.action_id, "result": result}


def cancel_action(
    db: Any,
    action_id: str,
    user_id: Optional[int] = None,
    **kwargs: Any,
) -> Dict[str, Any]:
    action = action_store.get_action(action_id)
    if not action:
        return {"success": False, "error": "Action not found or expired"}
    ownership_error = ActionStore.ensure_owner(action, user_id)
    if ownership_error:
        return {"success": False, "error": ownership_error}
    action_store.update_action(action.action_id, status="cancelled")
    return {"success": True, "action_id": action.action_id, "status": "cancelled"}


def build_tool_registry():
    """Build the complete tool registry from all modules."""
    
    # ============ COURSE TOOLS ============
    
    register_tool(
        name="list_courses",
        description="List all available courses. Use this to see what courses exist in the system.",
        parameters={
            "type": "object",
            "properties": {
                "skip": {"type": "integer", "description": "Number of courses to skip (for pagination)", "default": 0},
                "limit": {"type": "integer", "description": "Maximum courses to return", "default": 100},
            },
            "required": [],
        },
        handler=courses.list_courses,
        mode="read",
        category="courses",
    )
    
    register_tool(
        name="get_course",
        description="Get detailed information about a specific course including syllabus and objectives.",
        parameters={
            "type": "object",
            "properties": {
                "course_id": {"type": "integer", "description": "The course ID"},
            },
            "required": ["course_id"],
        },
        handler=courses.get_course,
        mode="read",
        category="courses",
    )
    
    register_tool(
        name="create_course",
        description="Create a new course with title, syllabus, and learning objectives.",
        parameters={
            "type": "object",
            "properties": {
                "title": {"type": "string", "description": "Course title"},
                "syllabus_text": {"type": "string", "description": "Full syllabus text"},
                "objectives": {"type": "array", "items": {"type": "string"}, "description": "List of learning objectives"},
            },
            "required": ["title"],
        },
        handler=courses.create_course,
        mode="write",
        category="courses",
    )
    
    register_tool(
        name="generate_session_plans",
        description="Generate AI-powered session plans from a course syllabus. This queues an async task.",
        parameters={
            "type": "object",
            "properties": {
                "course_id": {"type": "integer", "description": "The course ID to generate plans for"},
            },
            "required": ["course_id"],
        },
        handler=courses.generate_session_plans,
        mode="write",
        category="courses",
    )
    
    # ============ SESSION TOOLS ============
    
    register_tool(
        name="list_sessions",
        description="List all sessions for a course. Shows session titles, status, and IDs.",
        parameters={
            "type": "object",
            "properties": {
                "course_id": {"type": "integer", "description": "The course ID"},
                "status": {"type": "string", "description": "Filter by status: draft, scheduled, live, completed"},
            },
            "required": ["course_id"],
        },
        handler=sessions.list_sessions,
        mode="read",
        category="sessions",
    )
    
    register_tool(
        name="get_session",
        description="Get detailed information about a session including its plan, topics, and current status.",
        parameters={
            "type": "object",
            "properties": {
                "session_id": {"type": "integer", "description": "The session ID"},
            },
            "required": ["session_id"],
        },
        handler=sessions.get_session,
        mode="read",
        category="sessions",
    )
    
    register_tool(
        name="get_session_plan",
        description="Get the AI-generated session plan with topics, goals, case study, and discussion prompts.",
        parameters={
            "type": "object",
            "properties": {
                "session_id": {"type": "integer", "description": "The session ID"},
            },
            "required": ["session_id"],
        },
        handler=sessions.get_session_plan,
        mode="read",
        category="sessions",
    )
    
    register_tool(
        name="create_session",
        description="Create a new session in a course.",
        parameters={
            "type": "object",
            "properties": {
                "course_id": {"type": "integer", "description": "The course ID"},
                "title": {"type": "string", "description": "Session title"},
            },
            "required": ["course_id", "title"],
        },
        handler=sessions.create_session,
        mode="write",
        category="sessions",
    )
    
    register_tool(
        name="update_session_status",
        description="Update session status. Valid transitions: draft->scheduled->live->completed.",
        parameters={
            "type": "object",
            "properties": {
                "session_id": {"type": "integer", "description": "The session ID"},
                "status": {"type": "string", "enum": ["draft", "scheduled", "live", "completed"], "description": "New status"},
            },
            "required": ["session_id", "status"],
        },
        handler=sessions.update_session_status,
        mode="write",
        category="sessions",
    )
    
    register_tool(
        name="go_live",
        description="Shortcut to set a session status to 'live'. Use this to start a class session.",
        parameters={
            "type": "object",
            "properties": {
                "session_id": {"type": "integer", "description": "The session ID"},
            },
            "required": ["session_id"],
        },
        handler=sessions.go_live,
        mode="write",
        category="sessions",
    )
    
    register_tool(
        name="end_session",
        description="Shortcut to set a session status to 'completed'. Use this to end a class session.",
        parameters={
            "type": "object",
            "properties": {
                "session_id": {"type": "integer", "description": "The session ID"},
            },
            "required": ["session_id"],
        },
        handler=sessions.end_session,
        mode="write",
        category="sessions",
    )
    
    # ============ FORUM TOOLS (Cases, Posts, Moderation) ============
    
    register_tool(
        name="get_session_cases",
        description="Get the case studies/discussion prompts posted for a session.",
        parameters={
            "type": "object",
            "properties": {
                "session_id": {"type": "integer", "description": "The session ID"},
            },
            "required": ["session_id"],
        },
        handler=forum.get_session_cases,
        mode="read",
        category="forum",
    )
    
    register_tool(
        name="post_case",
        description="Post a new case study or discussion prompt for students to respond to.",
        parameters={
            "type": "object",
            "properties": {
                "session_id": {"type": "integer", "description": "The session ID"},
                "prompt": {"type": "string", "description": "The case study or discussion prompt text"},
            },
            "required": ["session_id", "prompt"],
        },
        handler=forum.post_case,
        mode="write",
        category="forum",
    )
    
    register_tool(
        name="get_session_posts",
        description="Get all posts in a session's discussion thread. Returns posts with author info and labels.",
        parameters={
            "type": "object",
            "properties": {
                "session_id": {"type": "integer", "description": "The session ID"},
                "include_content": {"type": "boolean", "description": "Include full post content (default true)", "default": True},
            },
            "required": ["session_id"],
        },
        handler=forum.get_session_posts,
        mode="read",
        category="forum",
    )
    
    register_tool(
        name="get_latest_posts",
        description="Get the most recent posts in a session. Useful for checking what's new.",
        parameters={
            "type": "object",
            "properties": {
                "session_id": {"type": "integer", "description": "The session ID"},
                "count": {"type": "integer", "description": "Number of recent posts to get", "default": 5},
            },
            "required": ["session_id"],
        },
        handler=forum.get_latest_posts,
        mode="read",
        category="forum",
    )
    
    register_tool(
        name="get_pinned_posts",
        description="Get all pinned posts in a session. These are important posts marked by the instructor.",
        parameters={
            "type": "object",
            "properties": {
                "session_id": {"type": "integer", "description": "The session ID"},
            },
            "required": ["session_id"],
        },
        handler=forum.get_pinned_posts,
        mode="read",
        category="forum",
    )
    
    register_tool(
        name="get_post",
        description="Get details of a specific post including its content, author, and any replies.",
        parameters={
            "type": "object",
            "properties": {
                "post_id": {"type": "integer", "description": "The post ID"},
            },
            "required": ["post_id"],
        },
        handler=forum.get_post,
        mode="read",
        category="forum",
    )
    
    register_tool(
        name="search_posts",
        description="Search for posts containing specific keywords in a session.",
        parameters={
            "type": "object",
            "properties": {
                "session_id": {"type": "integer", "description": "The session ID"},
                "query": {"type": "string", "description": "Search query"},
            },
            "required": ["session_id", "query"],
        },
        handler=forum.search_posts,
        mode="read",
        category="forum",
    )
    
    register_tool(
        name="create_post",
        description="Create a new post in a session's discussion.",
        parameters={
            "type": "object",
            "properties": {
                "session_id": {"type": "integer", "description": "The session ID"},
                "user_id": {"type": "integer", "description": "The user ID of the author"},
                "content": {"type": "string", "description": "The post content"},
            },
            "required": ["session_id", "user_id", "content"],
        },
        handler=forum.create_post,
        mode="write",
        category="forum",
    )
    
    register_tool(
        name="reply_to_post",
        description="Reply to an existing post in the discussion.",
        parameters={
            "type": "object",
            "properties": {
                "session_id": {"type": "integer", "description": "The session ID"},
                "parent_post_id": {"type": "integer", "description": "The post ID to reply to"},
                "user_id": {"type": "integer", "description": "The user ID of the author"},
                "content": {"type": "string", "description": "The reply content"},
            },
            "required": ["session_id", "parent_post_id", "user_id", "content"],
        },
        handler=forum.reply_to_post,
        mode="write",
        category="forum",
    )
    
    register_tool(
        name="pin_post",
        description="Pin or unpin a post. Pinned posts appear at the top of the discussion.",
        parameters={
            "type": "object",
            "properties": {
                "post_id": {"type": "integer", "description": "The post ID"},
                "pinned": {"type": "boolean", "description": "True to pin, False to unpin"},
            },
            "required": ["post_id", "pinned"],
        },
        handler=forum.pin_post,
        mode="write",
        category="forum",
    )
    
    register_tool(
        name="label_post",
        description="Add labels to a post. Labels: high-quality, needs-clarification, insightful, misconception, question.",
        parameters={
            "type": "object",
            "properties": {
                "post_id": {"type": "integer", "description": "The post ID"},
                "labels": {"type": "array", "items": {"type": "string"}, "description": "List of labels to set"},
            },
            "required": ["post_id", "labels"],
        },
        handler=forum.label_post,
        mode="write",
        category="forum",
    )
    
    register_tool(
        name="mark_high_quality",
        description="Shortcut to mark a post as high-quality.",
        parameters={
            "type": "object",
            "properties": {
                "post_id": {"type": "integer", "description": "The post ID"},
            },
            "required": ["post_id"],
        },
        handler=forum.mark_high_quality,
        mode="write",
        category="forum",
    )
    
    register_tool(
        name="mark_needs_clarification",
        description="Shortcut to mark a post as needing clarification.",
        parameters={
            "type": "object",
            "properties": {
                "post_id": {"type": "integer", "description": "The post ID"},
            },
            "required": ["post_id"],
        },
        handler=forum.mark_needs_clarification,
        mode="write",
        category="forum",
    )
    
    # ============ POLL TOOLS ============
    
    register_tool(
        name="get_session_polls",
        description="Get all polls for a session.",
        parameters={
            "type": "object",
            "properties": {
                "session_id": {"type": "integer", "description": "The session ID"},
            },
            "required": ["session_id"],
        },
        handler=polls.get_session_polls,
        mode="read",
        category="polls",
    )
    
    register_tool(
        name="get_poll_results",
        description="Get the results of a specific poll including vote counts and percentages.",
        parameters={
            "type": "object",
            "properties": {
                "poll_id": {"type": "integer", "description": "The poll ID"},
            },
            "required": ["poll_id"],
        },
        handler=polls.get_poll_results,
        mode="read",
        category="polls",
    )
    
    register_tool(
        name="create_poll",
        description="Create a new poll in a session.",
        parameters={
            "type": "object",
            "properties": {
                "session_id": {"type": "integer", "description": "The session ID"},
                "question": {"type": "string", "description": "The poll question"},
                "options": {"type": "array", "items": {"type": "string"}, "description": "List of answer options"},
            },
            "required": ["session_id", "question", "options"],
        },
        handler=polls.create_poll,
        mode="write",
        category="polls",
    )
    
    register_tool(
        name="vote_on_poll",
        description="Cast a vote on a poll.",
        parameters={
            "type": "object",
            "properties": {
                "poll_id": {"type": "integer", "description": "The poll ID"},
                "user_id": {"type": "integer", "description": "The user ID voting"},
                "option_index": {"type": "integer", "description": "The index of the option to vote for (0-based)"},
            },
            "required": ["poll_id", "user_id", "option_index"],
        },
        handler=polls.vote_on_poll,
        mode="write",
        category="polls",
    )
    
    # ============ COPILOT TOOLS ============
    
    register_tool(
        name="get_copilot_status",
        description="Check if the AI copilot is currently running for a session.",
        parameters={
            "type": "object",
            "properties": {
                "session_id": {"type": "integer", "description": "The session ID"},
            },
            "required": ["session_id"],
        },
        handler=copilot.get_copilot_status,
        mode="read",
        category="copilot",
    )
    
    register_tool(
        name="get_copilot_suggestions",
        description="Get the latest AI copilot suggestions for the instructor.",
        parameters={
            "type": "object",
            "properties": {
                "session_id": {"type": "integer", "description": "The session ID"},
                "count": {"type": "integer", "description": "Number of recent suggestions", "default": 3},
            },
            "required": ["session_id"],
        },
        handler=copilot.get_copilot_suggestions,
        mode="read",
        category="copilot",
    )
    
    register_tool(
        name="start_copilot",
        description="Start the AI copilot for a session. It will analyze discussion and provide suggestions.",
        parameters={
            "type": "object",
            "properties": {
                "session_id": {"type": "integer", "description": "The session ID"},
            },
            "required": ["session_id"],
        },
        handler=copilot.start_copilot,
        mode="write",
        category="copilot",
    )
    
    register_tool(
        name="stop_copilot",
        description="Stop the AI copilot for a session.",
        parameters={
            "type": "object",
            "properties": {
                "session_id": {"type": "integer", "description": "The session ID"},
            },
            "required": ["session_id"],
        },
        handler=copilot.stop_copilot,
        mode="write",
        category="copilot",
    )
    
    # ============ REPORT TOOLS ============
    
    register_tool(
        name="get_report",
        description="Get the feedback report for a session. Includes themes, objectives alignment, misconceptions, and scores.",
        parameters={
            "type": "object",
            "properties": {
                "session_id": {"type": "integer", "description": "The session ID"},
            },
            "required": ["session_id"],
        },
        handler=reports.get_report,
        mode="read",
        category="reports",
    )
    
    register_tool(
        name="get_report_summary",
        description="Get a concise summary of the session report suitable for voice output.",
        parameters={
            "type": "object",
            "properties": {
                "session_id": {"type": "integer", "description": "The session ID"},
            },
            "required": ["session_id"],
        },
        handler=reports.get_report_summary,
        mode="read",
        category="reports",
    )
    
    register_tool(
        name="get_participation_stats",
        description="Get participation statistics: who participated, who didn't, participation rate.",
        parameters={
            "type": "object",
            "properties": {
                "session_id": {"type": "integer", "description": "The session ID"},
            },
            "required": ["session_id"],
        },
        handler=reports.get_participation_stats,
        mode="read",
        category="reports",
    )
    
    register_tool(
        name="get_student_scores",
        description="Get answer scores for students in a session.",
        parameters={
            "type": "object",
            "properties": {
                "session_id": {"type": "integer", "description": "The session ID"},
            },
            "required": ["session_id"],
        },
        handler=reports.get_student_scores,
        mode="read",
        category="reports",
    )
    
    register_tool(
        name="generate_report",
        description="Generate a new feedback report for a session. This queues an async task.",
        parameters={
            "type": "object",
            "properties": {
                "session_id": {"type": "integer", "description": "The session ID"},
            },
            "required": ["session_id"],
        },
        handler=reports.generate_report,
        mode="write",
        category="reports",
    )
    
    # ============ ENROLLMENT TOOLS ============
    
    register_tool(
        name="get_enrolled_students",
        description="Get list of students enrolled in a course.",
        parameters={
            "type": "object",
            "properties": {
                "course_id": {"type": "integer", "description": "The course ID"},
            },
            "required": ["course_id"],
        },
        handler=enrollment.get_enrolled_students,
        mode="read",
        category="enrollment",
    )
    
    register_tool(
        name="enroll_student",
        description="Enroll a student in a course.",
        parameters={
            "type": "object",
            "properties": {
                "user_id": {"type": "integer", "description": "The user ID to enroll"},
                "course_id": {"type": "integer", "description": "The course ID"},
            },
            "required": ["user_id", "course_id"],
        },
        handler=enrollment.enroll_student,
        mode="write",
        category="enrollment",
    )
    
    register_tool(
        name="get_users",
        description="Get list of users, optionally filtered by role.",
        parameters={
            "type": "object",
            "properties": {
                "role": {"type": "string", "enum": ["instructor", "student"], "description": "Filter by role"},
            },
            "required": [],
        },
        handler=enrollment.get_users,
        mode="read",
        category="enrollment",
    )
    
    # ============ NAVIGATION TOOLS ============
    
    register_tool(
        name="navigate_to_page",
        description="Navigate to a specific page in the AristAI interface. Use this when user asks to go to a page like forum, courses, dashboard, etc.",
        parameters={
            "type": "object",
            "properties": {
                "page": {
                    "type": "string",
                    "description": "The page to navigate to (courses, sessions, forum, reports, console, dashboard, home, settings)",
                    "enum": ["courses", "sessions", "forum", "reports", "console", "dashboard", "home", "settings"]
                },
            },
            "required": ["page"],
        },
        handler=navigation.navigate_to_page,
        mode="read",
        category="navigation",
    )
    
    register_tool(
        name="get_available_pages",
        description="Get list of all available pages for navigation.",
        parameters={
            "type": "object",
            "properties": {},
            "required": [],
        },
        handler=navigation.get_available_pages,
        mode="read",
        category="navigation",
    )
    
    register_tool(
        name="get_current_context",
        description="Get current page context and available actions.",
        parameters={
            "type": "object",
            "properties": {
                "context": {
                    "type": "object",
                    "description": "Current context object from the application",
                    "properties": {
                        "current_page": {"type": "string", "description": "Current page name"},
                        "user_role": {"type": "string", "description": "Current user role"}
                    }
                },
            },
            "required": [],
        },
        handler=navigation.get_current_context,
        mode="read",
        category="navigation",
    )
    
    register_tool(
        name="get_help_for_page",
        description="Get help information for a specific page.",
        parameters={
            "type": "object",
            "properties": {
                "page": {
                    "type": "string",
                    "description": "The page to get help for (courses, sessions, forum, reports, console, dashboard)",
                    "enum": ["courses", "sessions", "forum", "reports", "console", "dashboard"]
                },
            },
            "required": ["page"],
        },
        handler=navigation.get_help_for_page,
        mode="read",
        category="navigation",
    )

    # ============ ACTION TOOLS ============

    register_tool(
        name="plan_action",
        description="Plan a write action and return a preview plus action_id for confirmation.",
        parameters={
            "type": "object",
            "properties": {
                "tool_name": {"type": "string"},
                "args": {"type": "object"},
                "user_id": {"type": "integer"},
            },
            "required": ["tool_name", "args"],
        },
        handler=plan_action,
        mode="write",
        category="actions",
    )

    register_tool(
        name="execute_action",
        description="Execute a previously planned action by action_id.",
        parameters={
            "type": "object",
            "properties": {
                "action_id": {"type": "string"},
                "user_id": {"type": "integer"},
            },
            "required": ["action_id"],
        },
        handler=execute_action,
        mode="write",
        category="actions",
    )

    register_tool(
        name="cancel_action",
        description="Cancel a previously planned action by action_id.",
        parameters={
            "type": "object",
            "properties": {
                "action_id": {"type": "string"},
                "user_id": {"type": "integer"},
            },
            "required": ["action_id"],
        },
        handler=cancel_action,
        mode="write",
        category="actions",
    )

    # ============ RESOLVE/CONTEXT TOOLS ============

    register_tool(
        name="resolve_course",
        description="Resolve a course query to candidate course IDs.",
        parameters={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Course title or code query"},
                "limit": {"type": "integer", "description": "Maximum candidates to return"},
            },
            "required": ["query"],
        },
        handler=resolve.resolve_course,
        mode="read",
        category="context",
    )

    register_tool(
        name="resolve_session",
        description="Resolve a session query to candidate session IDs.",
        parameters={
            "type": "object",
            "properties": {
                "course_id": {"type": "integer", "description": "Course ID"},
                "query": {"type": "string", "description": "Session query (latest|today|live|title)"},
                "limit": {"type": "integer", "description": "Maximum candidates to return"},
            },
            "required": ["course_id"],
        },
        handler=resolve.resolve_session,
        mode="read",
        category="context",
    )

    register_tool(
        name="resolve_user",
        description="Resolve a user by email or name.",
        parameters={
            "type": "object",
            "properties": {
                "email_or_name": {"type": "string", "description": "Email or name query"},
                "limit": {"type": "integer", "description": "Maximum candidates to return"},
            },
            "required": ["email_or_name"],
        },
        handler=resolve.resolve_user,
        mode="read",
        category="context",
    )

    register_tool(
        name="get_current_context",
        description="Get active course/session context for the user.",
        parameters={
            "type": "object",
            "properties": {
                "user_id": {"type": "integer", "description": "User ID for context lookup"},
            },
            "required": [],
        },
        handler=resolve.get_current_context,
        mode="read",
        category="context",
    )

    register_tool(
        name="set_active_course",
        description="Set the active course for the user context.",
        parameters={
            "type": "object",
            "properties": {
                "course_id": {"type": "integer", "description": "Course ID"},
                "user_id": {"type": "integer", "description": "User ID for context"},
            },
            "required": ["course_id"],
        },
        handler=resolve.set_active_course,
        mode="write",
        category="context",
    )

    register_tool(
        name="set_active_session",
        description="Set the active session for the user context.",
        parameters={
            "type": "object",
            "properties": {
                "session_id": {"type": "integer", "description": "Session ID"},
                "user_id": {"type": "integer", "description": "User ID for context"},
            },
            "required": ["session_id"],
        },
        handler=resolve.set_active_session,
        mode="write",
        category="context",
    )

    # ============ VOICE MACROS ============

    register_tool(
        name="voice_open_page",
        description="Open a page with optional course/session resolution.",
        parameters={
            "type": "object",
            "properties": {
                "target": {"type": "string", "description": "Target page or entity"},
                "course_query": {"type": "string"},
                "session_query": {"type": "string"},
                "auto_open": {"type": "boolean"},
            },
            "required": ["target"],
        },
        handler=voice.voice_open_page,
        mode="read",
        category="voice",
    )

    register_tool(
        name="voice_create_poll",
        description="Resolve context and plan a poll creation action.",
        parameters={
            "type": "object",
            "properties": {
                "course_query": {"type": "string"},
                "session_query": {"type": "string"},
                "question": {"type": "string"},
                "options": {"type": "array"},
                "auto_open": {"type": "boolean"},
                "user_id": {"type": "integer"},
            },
            "required": ["course_query"],
        },
        handler=voice.voice_create_poll,
        mode="read",
        category="voice",
    )

    register_tool(
        name="voice_generate_report",
        description="Resolve context and plan a report generation action.",
        parameters={
            "type": "object",
            "properties": {
                "course_query": {"type": "string"},
                "session_query": {"type": "string"},
                "auto_open": {"type": "boolean"},
                "user_id": {"type": "integer"},
            },
            "required": ["course_query"],
        },
        handler=voice.voice_generate_report,
        mode="read",
        category="voice",
    )

    register_tool(
        name="voice_enroll_students",
        description="Resolve students and plan a bulk enrollment action.",
        parameters={
            "type": "object",
            "properties": {
                "course_query": {"type": "string"},
                "emails": {"type": "array"},
                "csv_text": {"type": "string"},
                "csv_url": {"type": "string"},
                "role": {"type": "string"},
                "auto_open": {"type": "boolean"},
                "user_id": {"type": "integer"},
            },
            "required": ["course_query"],
        },
        handler=voice.voice_enroll_students,
        mode="read",
        category="voice",
    )

    register_tool(
        name="bulk_enroll_students",
        description="Bulk enroll students by user IDs in a course.",
        parameters={
            "type": "object",
            "properties": {
                "course_id": {"type": "integer"},
                "user_ids": {"type": "array"},
            },
            "required": ["course_id", "user_ids"],
        },
        handler=enrollment.bulk_enroll_students,
        mode="write",
        category="enrollment",
    )


# Build the registry on module load
build_tool_registry()


# ============ MCP Server Handlers ============

@server.list_tools()
async def list_tools() -> ListToolsResult:
    """Return list of all available tools."""
    tools = []
    for name, tool_info in TOOL_REGISTRY.items():
        tools.append(
            Tool(
                name=name,
                description=f"[{tool_info['mode'].upper()}] {tool_info['description']}",
                inputSchema=tool_info["parameters"],
            )
        )
    return ListToolsResult(tools=tools)


@server.call_tool()
async def call_tool(name: str, arguments: Dict[str, Any]) -> CallToolResult:
    """Execute a tool and return the result."""
    if name not in TOOL_REGISTRY:
        return CallToolResult(
            content=[TextContent(type="text", text=f"Error: Unknown tool '{name}'")],
            isError=True,
        )
    
    tool_info = TOOL_REGISTRY[name]
    handler = tool_info["handler"]
    
    try:
        if tool_info["mode"] == "write" and name not in ACTION_TOOL_NAMES:
            result = await asyncio.to_thread(_plan_action_in_thread, name, arguments, None)
        else:
            result = await asyncio.to_thread(_invoke_tool_handler_in_thread, handler, arguments)
            
        normalized = normalize_tool_result(result, name)
        if not normalized.get("ok", True):
            return CallToolResult(
                content=[TextContent(type="text", text=f"Error: {normalized.get('summary')}")],
                isError=True,
            )
        
        import json
        result_text = json.dumps(normalized, indent=2, default=str)
        return CallToolResult(
            content=[TextContent(type="text", text=result_text)],
            isError=False,
        )
                
    except Exception as e:
        logger.exception(f"Tool execution failed: {name}")
        return CallToolResult(
            content=[TextContent(type="text", text=f"Error executing {name}: {str(e)}")],
            isError=True,
        )


# ============ Server Entry Point ============

async def main():
    """Run the MCP server."""
    logger.info("Starting AristAI MCP Server...")
    logger.info(f"Registered {len(TOOL_REGISTRY)} tools")
    
    # Log tools by category
    categories = {}
    for name, info in TOOL_REGISTRY.items():
        cat = info["category"]
        if cat not in categories:
            categories[cat] = []
        categories[cat].append(name)
    
    for cat, tools in categories.items():
        logger.info(f"  {cat}: {len(tools)} tools")
    
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())
