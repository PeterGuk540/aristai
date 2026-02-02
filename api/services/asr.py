"""
ASR (Automatic Speech Recognition) service abstraction.

Provider selected via VOICE_ASR_PROVIDER env var:
  - "stub": returns a fixed transcript (for dev/testing)
  - "whisper": uses OpenAI Whisper API via httpx
"""
import logging
from typing import Optional

from api.core.config import get_settings

logger = logging.getLogger(__name__)


class ASRResult:
    def __init__(
        self,
        transcript: str,
        language: Optional[str] = None,
        duration_seconds: Optional[float] = None,
    ):
        self.transcript = transcript
        self.language = language
        self.duration_seconds = duration_seconds


def transcribe(audio_bytes: bytes, content_type: str = "audio/webm") -> ASRResult:
    """Transcribe audio bytes to text using the configured provider."""
    settings = get_settings()
    provider = settings.voice_asr_provider

    if provider == "whisper":
        return _transcribe_whisper(audio_bytes, content_type, settings)
    else:
        return _transcribe_stub(audio_bytes)


def _transcribe_stub(audio_bytes: bytes) -> ASRResult:
    """Stub ASR: returns a fixed transcript for testing."""
    logger.info(f"ASR stub: received {len(audio_bytes)} bytes")
    return ASRResult(
        transcript="[stub] Show me all courses and their sessions.",
        language="en",
        duration_seconds=3.0,
    )


def _transcribe_whisper(audio_bytes: bytes, content_type: str, settings) -> ASRResult:
    """Real ASR via OpenAI Whisper API."""
    import httpx
    import io

    if not settings.openai_api_key:
        raise ValueError("OPENAI_API_KEY required for Whisper ASR provider")

    ext = "webm" if "webm" in content_type else "wav"
    resp = httpx.post(
        "https://api.openai.com/v1/audio/transcriptions",
        headers={"Authorization": f"Bearer {settings.openai_api_key}"},
        files={"file": (f"audio.{ext}", io.BytesIO(audio_bytes), content_type)},
        data={"model": "whisper-1", "response_format": "verbose_json"},
        timeout=30.0,
    )
    resp.raise_for_status()
    data = resp.json()
    return ASRResult(
        transcript=data["text"],
        language=data.get("language"),
        duration_seconds=data.get("duration"),
    )
