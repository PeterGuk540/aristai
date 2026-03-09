import httpx
from fastapi import APIRouter, HTTPException

from app.core.config import settings

router = APIRouter()


@router.get("/voice/signed-url")
async def get_signed_url(language: str = "en"):
    """Get signed WebSocket URL for ElevenLabs syllabus agent."""
    if not settings.ELEVENLABS_API_KEY or not settings.ELEVENLABS_SYLLABUS_AGENT_ID:
        raise HTTPException(500, "ElevenLabs not configured")

    url = (
        f"https://api.elevenlabs.io/v1/convai/conversation/get-signed-url"
        f"?agent_id={settings.ELEVENLABS_SYLLABUS_AGENT_ID}"
        f"&dynamic_variables[language]={language}"
    )
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(
            url, headers={"xi-api-key": settings.ELEVENLABS_API_KEY}
        )
        if resp.status_code != 200:
            raise HTTPException(502, f"ElevenLabs error: {resp.status_code}")
        return {"signed_url": resp.json()["signed_url"]}
