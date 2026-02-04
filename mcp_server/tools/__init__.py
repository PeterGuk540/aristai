"""
AristAI MCP Tools Package.

This package contains all tool implementations organized by domain:
- courses: Course management (list, create, generate plans)
- sessions: Session management (list, create, status control)
- forum: Posts, cases, and moderation
- polls: Poll creation and voting
- copilot: Live AI copilot control
- reports: Report generation and viewing
- enrollment: Student enrollment management
"""

from mcp_server.tools import (
    courses,
    sessions,
    forum,
    polls,
    copilot,
    reports,
    enrollment,
    navigation,
)

__all__ = [
    "courses",
    "sessions",
    "forum",
    "polls",
    "copilot",
    "reports",
    "enrollment",
    "navigation",
]
