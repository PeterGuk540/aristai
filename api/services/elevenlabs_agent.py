import logging
from dataclasses import dataclass

import httpx

from api.core.config import get_settings

logger = logging.getLogger(__name__)


@dataclass
class ElevenLabsAgentError(Exception):
    message: str
    status_code: int

    def __str__(self) -> str:
        return self.message


async def get_signed_url() -> str:
    settings = get_settings()

    if not settings.elevenlabs_api_key:
        raise ElevenLabsAgentError(
            "ELEVENLABS_API_KEY is required to request a signed URL.",
            status_code=500,
        )

    if not settings.elevenlabs_agent_id:
        raise ElevenLabsAgentError(
            "ELEVENLABS_AGENT_ID is required to request a signed URL.",
            status_code=500,
        )

    url = "https://api.elevenlabs.io/v1/convai/conversations/get_signed_url"
    headers = {"xi-api-key": settings.elevenlabs_api_key}
    params = {"agent_id": settings.elevenlabs_agent_id}

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.post(url, headers=headers, params=params)
    except httpx.HTTPError as exc:
        logger.exception("Failed to reach ElevenLabs signed URL endpoint")
        raise ElevenLabsAgentError(
            f"Failed to reach ElevenLabs signed URL endpoint: {exc}",
            status_code=502,
        ) from exc

    if response.status_code >= 400:
        raise ElevenLabsAgentError(
            f"ElevenLabs signed URL error {response.status_code}: {response.text}",
            status_code=502,
        )

    try:
        payload = response.json()
    except ValueError as exc:
        raise ElevenLabsAgentError(
            f"Invalid JSON response from ElevenLabs: {response.text}",
            status_code=502,
        ) from exc

    signed_url = payload.get("signed_url") or payload.get("url")
    if not signed_url:
        raise ElevenLabsAgentError(
            f"Signed URL missing in ElevenLabs response: {payload}",
            status_code=502,
        )

    return signed_url
