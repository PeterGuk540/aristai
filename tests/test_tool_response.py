from api.services.tool_response import normalize_tool_result


def test_normalize_success_with_navigation():
    result = {
        "success": True,
        "action": "navigate_and_execute",
        "path": "/courses",
        "message": "Navigating",
    }
    normalized = normalize_tool_result(result, "navigate_to_page")
    assert normalized["ok"] is True
    assert normalized["type"] == "result"
    assert normalized["ui_actions"][0]["type"] == "ui.navigate"


def test_normalize_error():
    normalized = normalize_tool_result({"error": "Nope"}, "create_course")
    assert normalized["ok"] is False
    assert normalized["type"] == "error"
    assert normalized["summary"] == "Nope"
