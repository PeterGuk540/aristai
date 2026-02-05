"""
Voice Assistant API routes.

Endpoints for ElevenLabs Agent:
    GET  /api/voice/agent/signed-url - Get signed WebSocket URL for ElevenLabs Agent
    GET  /api/voice/agent/test        - Test endpoint

Legacy TTS endpoints removed - using ElevenLabs Agent realtime conversation
"""
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
import httpx
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from api.api.routes.ui_actions import broker
from api.api.voice_converse_router import ConverseRequest, voice_converse
from api.core.database import get_db
from api.services.elevenlabs_agent import get_signed_url
from api.services.tool_response import normalize_tool_result

logger = logging.getLogger(__name__)

# Legacy exports removed - ElevenLabs Agents integration uses new endpoints
router = APIRouter()

class DelegateRequest(BaseModel):
    transcript: str = Field(..., min_length=1)
    current_page: Optional[str] = None
    user_id: Optional[int] = None
    context: Optional[list[str]] = None


def require_auth(request: Request) -> bool:
    """
    Simple authentication check.
    TODO: Validate Cognito JWT properly later.
    For now, just check for Authorization header presence.
    """
    auth_header = request.headers.get("Authorization")
    if not auth_header:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization header required",
        )
    # TODO: Add proper JWT validation when Cognito is integrated
    # TODO: Implement full Cognito JWT verification for production
    return True

# Legacy TTS endpoint removed - use ElevenLabs Agents realtime conversation instead
# @router.post("/synthesize", response_model=None)
# async def voice_synthesize(request: Request):
#     """LEGACY: Standard TTS endpoint - DEPRECATED"""
#     # This endpoint is removed for production deployment
#     # Use GET /api/voice/agent/signed-url + official SDK instead


# Legacy voice endpoints (transcribe, plan, execute) removed
# Using ElevenLabs Agent realtime conversation instead


# Legacy TTS endpoint removed - use ElevenLabs Agents realtime conversation instead
# @router.post("/synthesize")
# async def voice_synthesize(request: Request):
#     """Standard TTS endpoint for frontend voice components."""
#     try:
#         logger.info("=== VOICE SYNTHESIS REQUEST ===")
#         data = await request.json()
#         text = data.get("text", "")
#         logger.info(f"Text to synthesize: {text}")
#         
#         if not text:
#             logger.warning("Empty text received")
#             raise HTTPException(status_code=400, detail="Text is required")
#         
#         logger.info("Calling TTS service...")
#         result = tts.synthesize(text)
#         logger.info(f"TTS success: {len(result.audio_bytes)} bytes, type: {result.content_type}")
#         
#         return Response(
#             content=result.audio_bytes,
#             media_type=result.content_type,
#             headers={"Cache-Control": "no-cache"}
#         )
#     except Exception as e:
#         logger.error(f"TTS synthesis failed: {type(e).__name__}: {str(e)}")
#         import traceback
#         logger.error(f"Full traceback: {traceback.format_exc()}")
#         raise HTTPException(status_code=500, detail=f"Voice synthesis error: {str(e)}")


# Legacy audit endpoint removed - no longer needed with ElevenLabs Agent


@router.get("/agent/test")
async def test_route():
    """Test route to verify router is working."""
    return {"message": "Router is working", "status": "ok"}

@router.get("/agent/signed-url", status_code=status.HTTP_200_OK)
async def get_agent_signed_url(request: Request):
    """
    Get a signed WebSocket URL for ElevenLabs Agent conversation.
    
    The browser will connect directly to ElevenLabs using this URL.
    The API key and agent ID are kept server-side.
    """
    import time
    import uuid
    request_id = str(uuid.uuid4())[:8]
    start_time = time.time()
    
    logger.info(f"[{request_id}] GET /api/voice/agent/signed-url - Processing request")
    
    # Simple authentication check
    require_auth(request)
    logger.info(f"[{request_id}] Authentication passed")
    
    try:
        signed_url = await get_signed_url()
        processing_time = time.time() - start_time
        logger.info(f"[{request_id}] Signed URL generated successfully - processing_time: {processing_time:.2f}s")
        return {"signed_url": signed_url}
    except ValueError as e:
        processing_time = time.time() - start_time
        logger.error(f"[{request_id}] Configuration error - processing_time: {processing_time:.2f}s - error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )
    except httpx.HTTPStatusError as e:
        processing_time = time.time() - start_time
        logger.error(f"[{request_id}] ElevenLabs API error - processing_time: {processing_time:.2f}s - status: {e.response.status_code}")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Upstream service error: {e.response.text}"
        )
    except Exception as e:
        processing_time = time.time() - start_time
        logger.error(f"[{request_id}] Unexpected error - processing_time: {processing_time:.2f}s - error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )


@router.post("/agent/delegate", status_code=status.HTTP_200_OK)
async def delegate_to_mcp(request: Request, db: Session = Depends(get_db)):
    """
    Delegate ElevenLabs agent tool calls to the MCP voice orchestrator.

    The ElevenLabs agent should define a single tool (delegate_to_mcp) that
    forwards transcript/current_page here. We execute MCP logic and return the
    response for the agent to speak, while streaming any UI actions to clients.
    """
    payload = await request.json()
    parameters = payload.get("parameters") or payload.get("arguments") or payload
    data = DelegateRequest(**parameters)

    response = await voice_converse(
        ConverseRequest(
            transcript=data.transcript,
            context=data.context,
            user_id=data.user_id,
            current_page=data.current_page,
        ),
        db=db,
    )

    ui_actions: list[dict] = []
    if response.action and response.action.type == "navigate" and response.action.target:
        ui_actions.append({"type": "ui.navigate", "payload": {"path": response.action.target}})

    if response.results:
        for item in response.results:
            if not isinstance(item, dict):
                continue
            normalized = normalize_tool_result(item, item.get("tool", "mcp"))
            ui_actions.extend(normalized.get("ui_actions") or [])

    for action in ui_actions:
        await broker.publish(data.user_id, action)

    return {
        "result": response.message,
        "message": response.message,
        "voice_response": response.message,
        "ui_actions": ui_actions,
        "results": response.results,
        "suggestions": response.suggestions,
    }
