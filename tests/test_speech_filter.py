from api.services.speech_filter import DEFAULT_FALLBACK, sanitize_speech_text


def test_rewrite_vendor_dashboard():
    result = sanitize_speech_text(
        "Open ElevenLabs dashboard",
        denylist=["ElevenLabs"],
        allowlist=[],
    )
    assert result == "open the settings page"


def test_rewrite_vendor_mentions():
    result = sanitize_speech_text(
        "Use OpenAI and Google for this task.",
        denylist=["OpenAI", "Google"],
        allowlist=[],
    )
    assert "OpenAI" not in result
    assert "Google" not in result


def test_fallback_on_remaining_banned_terms():
    result = sanitize_speech_text(
        "Visit Amazon website",
        denylist=["Amazon"],
        allowlist=[],
    )
    assert result in {DEFAULT_FALLBACK, "open the documentation"}
