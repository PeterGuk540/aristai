"""Preview builders for planned write actions."""

from typing import Any, Dict, Optional

from sqlalchemy.orm import Session


def build_action_preview(
    tool_name: str,
    args: Dict[str, Any],
    db: Optional[Session] = None,
) -> Dict[str, Any]:
    """Return a structured preview describing the intended write action."""
    if tool_name == "create_course":
        return {"tool_name": tool_name, "affected": {"courses": 1}, "args": args}
    if tool_name == "create_session":
        return {
            "tool_name": tool_name,
            "affected": {"sessions": 1},
            "course_id": args.get("course_id"),
            "args": args,
        }
    if tool_name == "update_session_status":
        return {
            "tool_name": tool_name,
            "affected": {"sessions": 1},
            "session_id": args.get("session_id"),
            "new_status": args.get("status"),
            "args": args,
        }
    if tool_name == "generate_session_plan":
        return {
            "tool_name": tool_name,
            "affected": {"session_plans": "async"},
            "course_id": args.get("course_id"),
            "args": args,
        }
    if tool_name == "post_case":
        return {
            "tool_name": tool_name,
            "affected": {"cases": 1},
            "session_id": args.get("session_id"),
            "args": args,
        }
    if tool_name == "create_poll":
        return {
            "tool_name": tool_name,
            "affected": {"polls": 1},
            "session_id": args.get("session_id"),
            "args": args,
        }
    if tool_name == "navigate_to_page":
        return {
            "tool_name": tool_name,
            "affected": {"navigation": 1},
            "page": args.get("page"),
            "args": args,
        }
    return {"tool_name": tool_name, "affected": {"items": 1}, "args": args}
