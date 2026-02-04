"""
TTS (Text-to-Speech) service abstraction.

Provider selected via VOICE_TTS_PROVIDER env var:
  - "stub": returns empty bytes (for dev/testing)
  - "elevenlabs": uses ElevenLabs REST TTS API via httpx
  - "elevenlabs_realtime": uses ElevenLabs realtime websocket streaming API
  - "elevenlabs_agent": uses ElevenLabs Conversational Agent API (fastest, integrated ASR+LLM+TTS)
"""
import logging
from api.core.config import get_settings

logger = logging.getLogger(__name__)


class TTSResult:
    def __init__(self, audio_bytes: bytes, content_type: str = "audio/mpeg"):
        self.audio_bytes = audio_bytes
        self.content_type = content_type


def synthesize(text: str) -> TTSResult:
    """Synthesize text to speech using the configured provider."""
    settings = get_settings()
    provider = settings.voice_tts_provider

    if provider == "elevenlabs_agent":
        return _synthesize_elevenlabs_agent(text, settings)
    if provider == "elevenlabs_realtime":
        return _synthesize_elevenlabs_realtime(text, settings)
    if provider == "elevenlabs":
        return _synthesize_elevenlabs(text, settings)
    else:
        return _synthesize_stub(text)


def _synthesize_stub(text: str) -> TTSResult:
    """Stub TTS: returns empty audio bytes for testing."""
    logger.info(f"TTS stub: synthesizing {len(text)} chars")
    return TTSResult(audio_bytes=b"", content_type="audio/mpeg")


def _synthesize_elevenlabs(text: str, settings) -> TTSResult:
    """Real TTS via ElevenLabs API."""
    import httpx

    if not settings.elevenlabs_api_key:
        raise ValueError("ELEVENLABS_API_KEY required for ElevenLabs TTS provider")

    voice_id = settings.elevenlabs_voice_id

    resp = httpx.post(
        f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}",
        headers={
            "xi-api-key": settings.elevenlabs_api_key,
            "Content-Type": "application/json",
        },
        json={"text": text, "model_id": settings.elevenlabs_model_id},
        timeout=30.0,
    )
    if resp.status_code >= 400:
        raise ValueError(
            f"ElevenLabs Agent API error {resp.status_code}: {resp.text}"
        )
    return TTSResult(audio_bytes=resp.content, content_type="audio/mpeg")


def _synthesize_elevenlabs_agent(text: str, settings) -> TTSResult:
    """
    DEPRECATED: ElevenLabs Agent simulate-conversation is NOT for production.
    
    For production, use the official SDK with signed URLs:
    - Backend: GET /api/voice/agent/signed-url  
    - Frontend: Conversation.startSession({ signedUrl })
    
    This function should never be called in production deployment.
    """
    logger.error("❌ PRODUCTION ERROR: Legacy simulate-conversation called")
    logger.error("❌ Use signed URL + official SDK instead")
    raise ValueError(
        "Legacy TTS/simulate-conversation is deprecated for production. "
        "Use ElevenLabs Agents with signed URLs and official SDK."
    )


def _synthesize_elevenlabs_realtime(text: str, settings) -> TTSResult:
    """Realtime TTS via ElevenLabs websocket streaming API."""
    import base64
    import json
    from websockets.sync.client import connect

    if not settings.elevenlabs_api_key:
        raise ValueError("ELEVENLABS_API_KEY required for ElevenLabs TTS provider")

    voice_id = settings.elevenlabs_voice_id
    model_id = settings.elevenlabs_model_id
    ws_url = (
        "wss://api.elevenlabs.io/v1/text-to-speech/"
        f"{voice_id}/stream-input?model_id={model_id}"
    )

    audio_chunks = []
    with connect(ws_url, extra_headers={"xi-api-key": settings.elevenlabs_api_key}) as ws:
        ws.send(json.dumps({"text": text}))
        ws.send(json.dumps({"text": "", "flush": True}))

        while True:
            message = ws.recv()
            data = json.loads(message)
            audio_b64 = data.get("audio")
            if audio_b64:
                audio_chunks.append(base64.b64decode(audio_b64))
            if data.get("isFinal") or data.get("event") == "end":
                break

    return TTSResult(audio_bytes=b"".join(audio_chunks), content_type="audio/mpeg")
