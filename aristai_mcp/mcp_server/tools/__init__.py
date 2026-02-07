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
- content_generation: AI-powered content generation (syllabus, objectives, session plans)
"""

from mcp_server.tools import (
    courses,
    sessions,
    forum,
    polls,
    copilot,
    reports,
    enrollment,
    content_generation,
)

__all__ = [
    "courses",
    "sessions",
    "forum",
    "polls",
    "copilot",
    "reports",
    "enrollment",
    "content_generation",
]
