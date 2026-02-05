"""In-memory broker for UI actions dispatched to connected clients."""

from __future__ import annotations

import asyncio
from collections import defaultdict
from typing import Any, AsyncGenerator, Dict, Optional


class UiActionBroker:
    def __init__(self) -> None:
        self._queues: Dict[str, asyncio.Queue] = defaultdict(asyncio.Queue)
        self._lock = asyncio.Lock()

    def _key(self, user_id: Optional[int]) -> str:
        return str(user_id) if user_id is not None else "anon"

    async def subscribe(self, user_id: Optional[int]) -> asyncio.Queue:
        key = self._key(user_id)
        async with self._lock:
            return self._queues[key]

    async def publish(self, user_id: Optional[int], payload: Dict[str, Any]) -> None:
        queue = await self.subscribe(user_id)
        await queue.put(payload)

    async def listen(self, user_id: Optional[int]) -> AsyncGenerator[Dict[str, Any], None]:
        queue = await self.subscribe(user_id)
        while True:
            message = await queue.get()
            yield message
