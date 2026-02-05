"""Redis-backed store for planned write actions."""

from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass
from typing import Any, Dict, Optional

import redis

from api.core.config import get_settings


@dataclass
class ActionRecord:
    action_id: str
    user_id: Optional[int]
    tool_name: str
    args: Dict[str, Any]
    preview: Dict[str, Any]
    created_at: float
    expires_at: float
    status: str
    result: Optional[Dict[str, Any]] = None


class ActionStore:
    """Store and manage planned actions."""

    def __init__(self, redis_client: Optional[redis.Redis] = None, ttl_seconds: int = 600):
        settings = get_settings()
        self._client = redis_client or redis.Redis.from_url(
            settings.redis_url, decode_responses=True
        )
        self._ttl_seconds = ttl_seconds

    def _key(self, action_id: str) -> str:
        return f"mcp:action:{action_id}"

    def create_action(
        self,
        user_id: Optional[int],
        tool_name: str,
        args: Dict[str, Any],
        preview: Dict[str, Any],
    ) -> ActionRecord:
        action_id = uuid.uuid4().hex
        now = time.time()
        expires_at = now + self._ttl_seconds
        record = ActionRecord(
            action_id=action_id,
            user_id=user_id,
            tool_name=tool_name,
            args=args,
            preview=preview,
            created_at=now,
            expires_at=expires_at,
            status="planned",
        )
        self._client.set(self._key(action_id), json.dumps(record.__dict__), ex=self._ttl_seconds)
        return record

    def get_action(self, action_id: str) -> Optional[ActionRecord]:
        data = self._client.get(self._key(action_id))
        if not data:
            return None
        payload = json.loads(data)
        return ActionRecord(**payload)

    def update_action(self, action_id: str, **updates: Any) -> Optional[ActionRecord]:
        record = self.get_action(action_id)
        if not record:
            return None
        for key, value in updates.items():
            setattr(record, key, value)
        ttl = self._client.ttl(self._key(action_id))
        ttl = ttl if ttl and ttl > 0 else self._ttl_seconds
        self._client.set(self._key(action_id), json.dumps(record.__dict__), ex=ttl)
        return record

    def delete_action(self, action_id: str) -> None:
        self._client.delete(self._key(action_id))

    @staticmethod
    def ensure_owner(action: ActionRecord, user_id: Optional[int]) -> Optional[str]:
        if action.user_id is None and user_id is None:
            return None
        if action.user_id != user_id:
            return "Action does not belong to the current user."
        return None
