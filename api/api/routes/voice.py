"""
Voice Assistant API routes.

Endpoints for ElevenLabs Agent:
    GET  /api/voice/agent/signed-url - Get signed WebSocket URL for ElevenLabs Agent
    GET  /api/voice/agent/test        - Test endpoint

Legacy TTS endpoints removed - using ElevenLabs Agent realtime conversation
"""
import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Request, status
import httpx

from api.core.config import get_settings
from api.services.elevenlabs_agent import get_signed_url

logger = logging.getLogger(__name__)

# Legacy exports removed - ElevenLabs Agents integration uses new endpoints
router = APIRouter()


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
