"""Redis-backed store for per-user context."""

from __future__ import annotations

import json
import time
from typing import Any, Dict, List, Optional

import redis

from api.core.config import get_settings


class ContextStore:
    """Store and retrieve user context for voice operations.

    Tracks:
    - Active course/session IDs
    - Last action for undo capability
    - Action history for context
    - Current page for context-aware responses
    """

    MAX_ACTION_HISTORY = 10  # Keep last 10 actions for undo

    def __init__(self, redis_client: Optional[redis.Redis] = None, ttl_seconds: int = 3600):
        settings = get_settings()
        self._client = redis_client or redis.Redis.from_url(
            settings.redis_url, decode_responses=True
        )
        self._ttl_seconds = ttl_seconds

    def _key(self, user_id: Optional[int]) -> str:
        key_suffix = str(user_id) if user_id is not None else "anon"
        return f"mcp:context:{key_suffix}"

    def _action_history_key(self, user_id: Optional[int]) -> str:
        key_suffix = str(user_id) if user_id is not None else "anon"
        return f"mcp:action_history:{key_suffix}"

    def get_context(self, user_id: Optional[int]) -> Dict[str, Any]:
        data = self._client.get(self._key(user_id))
        if not data:
            return {}
        return json.loads(data)

    def set_context(self, user_id: Optional[int], context: Dict[str, Any]) -> Dict[str, Any]:
        self._client.set(self._key(user_id), json.dumps(context), ex=self._ttl_seconds)
        return context

    def update_context(self, user_id: Optional[int], **updates: Any) -> Dict[str, Any]:
        context = self.get_context(user_id)
        context.update({k: v for k, v in updates.items() if v is not None})
        return self.set_context(user_id, context)

    def clear_context(self, user_id: Optional[int]) -> Dict[str, Any]:
        """Clear user context."""
        self._client.delete(self._key(user_id))
        return {}

    # === Action History for Undo ===

    def record_action(
        self,
        user_id: Optional[int],
        action_type: str,
        action_data: Dict[str, Any],
        undo_data: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Record an action for potential undo.

        Args:
            user_id: User ID
            action_type: Type of action (e.g., 'create_poll', 'enroll_student')
            action_data: Data about what was done
            undo_data: Data needed to reverse the action (optional)

        Returns:
            The recorded action entry
        """
        action_entry = {
            "action_type": action_type,
            "action_data": action_data,
            "undo_data": undo_data,
            "timestamp": time.time(),
            "undone": False,
        }

        # Get current history
        history = self.get_action_history(user_id)

        # Add new action at the beginning
        history.insert(0, action_entry)

        # Trim to max size
        history = history[:self.MAX_ACTION_HISTORY]

        # Save
        self._client.set(
            self._action_history_key(user_id),
            json.dumps(history),
            ex=self._ttl_seconds
        )

        # Also update context with last action
        self.update_context(
            user_id,
            last_action_type=action_type,
            last_action_time=action_entry["timestamp"],
        )

        return action_entry

    def get_action_history(self, user_id: Optional[int], limit: int = 5) -> List[Dict[str, Any]]:
        """Get recent action history."""
        data = self._client.get(self._action_history_key(user_id))
        if not data:
            return []
        history = json.loads(data)
        return history[:limit]

    def get_last_undoable_action(self, user_id: Optional[int]) -> Optional[Dict[str, Any]]:
        """Get the most recent action that can be undone."""
        history = self.get_action_history(user_id)
        for action in history:
            if not action.get("undone") and action.get("undo_data"):
                return action
        return None

    def mark_action_undone(self, user_id: Optional[int], timestamp: float) -> bool:
        """Mark an action as undone."""
        history = self.get_action_history(user_id, limit=self.MAX_ACTION_HISTORY)
        for action in history:
            if action.get("timestamp") == timestamp:
                action["undone"] = True
                self._client.set(
                    self._action_history_key(user_id),
                    json.dumps(history),
                    ex=self._ttl_seconds
                )
                return True
        return False

    # === Context-Aware Helpers ===

    def get_active_course_id(self, user_id: Optional[int]) -> Optional[int]:
        """Get the active course ID for a user."""
        context = self.get_context(user_id)
        return context.get("active_course_id")

    def get_active_session_id(self, user_id: Optional[int]) -> Optional[int]:
        """Get the active session ID for a user."""
        context = self.get_context(user_id)
        return context.get("active_session_id")

    def set_current_page(self, user_id: Optional[int], page: str) -> Dict[str, Any]:
        """Set the current page for context-aware responses."""
        return self.update_context(user_id, current_page=page)

    def get_context_summary(self, user_id: Optional[int]) -> str:
        """Get a human-readable context summary."""
        context = self.get_context(user_id)
        parts = []

        if context.get("active_course_id"):
            parts.append(f"Course: #{context['active_course_id']}")
        if context.get("active_session_id"):
            parts.append(f"Session: #{context['active_session_id']}")
        if context.get("current_page"):
            parts.append(f"Page: {context['current_page']}")

        if not parts:
            return "No active context"
        return ", ".join(parts)
