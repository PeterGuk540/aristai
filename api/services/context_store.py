"""Redis-backed store for per-user context."""

from __future__ import annotations

import json
from typing import Any, Dict, Optional

import redis

from api.core.config import get_settings


class ContextStore:
    """Store and retrieve user context for voice operations."""

    def __init__(self, redis_client: Optional[redis.Redis] = None, ttl_seconds: int = 3600):
        settings = get_settings()
        self._client = redis_client or redis.Redis.from_url(
            settings.redis_url, decode_responses=True
        )
        self._ttl_seconds = ttl_seconds

    def _key(self, user_id: Optional[int]) -> str:
        key_suffix = str(user_id) if user_id is not None else "anon"
        return f"mcp:context:{key_suffix}"

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
