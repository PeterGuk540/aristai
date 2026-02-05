import pytest
from fastapi.testclient import TestClient

from api.main import app
from api.api.voice_converse_router import ConverseResponse, ActionResponse
from api.core import database
import api.api.routes.voice as voice_routes


def test_delegate_to_mcp_routes_transcript(monkeypatch):
    captured = {}
    fake_db = object()

    async def fake_voice_converse(request, db):
        captured["request"] = request
        captured["db"] = db
        return ConverseResponse(
            message="Delegated response",
            action=ActionResponse(type="navigate", target="/courses"),
            results=[],
            suggestions=["next step"],
        )

    def override_get_db():
        yield fake_db

    monkeypatch.setattr(voice_routes, "voice_converse", fake_voice_converse)
    app.dependency_overrides[database.get_db] = override_get_db

    client = TestClient(app)
    response = client.post(
        "/api/voice/agent/delegate",
        json={
            "parameters": {
                "transcript": "show my courses",
                "current_page": "/dashboard",
                "user_id": 123,
                "context": ["User: hello"],
            }
        },
    )

    app.dependency_overrides.clear()

    assert response.status_code == 200
    payload = response.json()
    assert payload["message"] == "Delegated response"
    assert payload["ui_actions"] == [{"type": "ui.navigate", "payload": {"path": "/courses"}}]

    assert captured["db"] is fake_db
    assert captured["request"].transcript == "show my courses"
    assert captured["request"].current_page == "/dashboard"
    assert captured["request"].user_id == 123
    assert captured["request"].context == ["User: hello"]
