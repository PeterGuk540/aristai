"""Utilities for executing MCP tool handlers safely."""

import inspect
from typing import Any, Callable, Dict, Optional

from sqlalchemy.orm import Session


def _handler_requires_db(handler: Callable[..., Any]) -> bool:
    try:
        signature = inspect.signature(handler)
    except (TypeError, ValueError):
        return False
    return "db" in signature.parameters


def invoke_tool_handler(
    handler: Callable[..., Any],
    args: Dict[str, Any],
    db: Optional[Session] = None,
) -> Any:
    """Invoke a tool handler with optional database session injection."""
    if _handler_requires_db(handler):
        if db is None:
            raise RuntimeError("Database session required for tool handler.")
        return handler(db=db, **args)
    return handler(**args)
