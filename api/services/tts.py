"""
TTS (Text-to-Speech) service abstraction.

Provider selected via VOICE_TTS_PROVIDER env var:
  - "stub": returns empty bytes (for dev/testing)
  - "elevenlabs": uses ElevenLabs API via httpx
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

    voice_id = "21m00Tcm4TlvDq8ikWAM"  # Rachel default voice

    resp = httpx.post(
        f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}",
        headers={
            "xi-api-key": settings.elevenlabs_api_key,
            "Content-Type": "application/json",
        },
        json={"text": text, "model_id": "eleven_monolingual_v1"},
        timeout=30.0,
    )
    resp.raise_for_status()
    return TTSResult(audio_bytes=resp.content, content_type="audio/mpeg")
