"""
Standard TTS endpoint for AristAI voice components.
"""
import logging
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response

from api.services.tts import synthesize

logger = logging.getLogger(__name__)
router = APIRouter()

@router.post("/synthesize")
async def voice_synthesize(request):
    """Standard TTS endpoint for frontend voice components."""
    try:
        data = await request.json()
        text = data.get("text", "")
        if not text:
            raise HTTPException(status_code=400, detail="Text is required")
        
        result = synthesize(text)
        
        return Response(
            content=result.audio_bytes,
            media_type=result.content_type,
            headers={"Cache-Control": "no-cache"}
        )
    except Exception as e:
        logger.exception(f"TTS synthesis failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))