"""UI action streaming endpoints."""

from __future__ import annotations

import asyncio
import json
import time
from typing import Any, AsyncGenerator, Dict, Optional

from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from api.services.ui_action_broker import UiActionBroker

router = APIRouter()
broker = UiActionBroker()


class UiActionPublishRequest(BaseModel):
    user_id: Optional[int] = None
    type: str = Field(..., min_length=1)
    payload: Dict[str, Any] = Field(default_factory=dict)
    correlation_id: Optional[str] = None


def _require_token(request: Request) -> None:
    auth_header = request.headers.get("Authorization")
    token_param = request.query_params.get("token")
    if not auth_header and not token_param:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization token required",
        )


def _format_sse(data: Dict[str, Any]) -> str:
    return f"data: {json.dumps(data)}\n\n"


async def _event_stream(user_id: Optional[int]) -> AsyncGenerator[str, None]:
    last_heartbeat = time.time()
    heartbeat_interval = 15
    async for message in broker.listen(user_id):
        message.setdefault("created_at", time.time())
        yield _format_sse(message)
        now = time.time()
        if now - last_heartbeat > heartbeat_interval:
            yield _format_sse({"type": "heartbeat", "created_at": now})
            last_heartbeat = now


@router.get("/stream")
async def stream_ui_actions(request: Request, user_id: Optional[int] = None):
    """Stream UI actions to the browser via SSE."""
    _require_token(request)

    async def generator():
        try:
            async for event in _event_stream(user_id):
                yield event
                await asyncio.sleep(0)
        except asyncio.CancelledError:
            return

    return StreamingResponse(generator(), media_type="text/event-stream")


@router.post("/publish")
async def publish_ui_action(request: Request, payload: UiActionPublishRequest):
    """Publish a UI action to a user channel."""
    _require_token(request)
    message = {
        "type": payload.type,
        "payload": payload.payload,
        "correlation_id": payload.correlation_id,
        "created_at": time.time(),
    }
    await broker.publish(payload.user_id, message)
    return {"success": True}
