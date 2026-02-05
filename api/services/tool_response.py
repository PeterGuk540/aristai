"""Helpers for standardized tool responses."""

from __future__ import annotations

from typing import Any, Dict, Optional


def _build_ui_actions(result: Dict[str, Any]) -> Optional[list[Dict[str, Any]]]:
    if result.get("action", "").startswith("navigate") or result.get("path"):
        path = result.get("path")
        if path:
            return [{"type": "ui.navigate", "payload": {"path": path}}]
    return None


def normalize_tool_result(result: Any, tool_name: str) -> Dict[str, Any]:
    if isinstance(result, dict) and {"ok", "type", "summary", "data"}.issubset(result.keys()):
        return result

    response: Dict[str, Any] = {"ok": True, "type": "result", "summary": "", "data": {}}

    if isinstance(result, dict):
        if result.get("requires_confirmation") or "action_id" in result:
            response["type"] = "plan"
            response["requires_confirmation"] = True
            response["action_id"] = result.get("action_id")
        if "error" in result:
            response["ok"] = False
            response["type"] = "error"
            response["summary"] = str(result.get("error"))
        elif "message" in result:
            response["summary"] = str(result.get("message"))
        elif "voice_response" in result:
            response["summary"] = str(result.get("voice_response"))
        else:
            response["summary"] = f"{tool_name} completed."
        response["data"] = result
        ui_actions = list(result.get("ui_actions") or [])
        derived_actions = _build_ui_actions(result)
        if derived_actions:
            for action in derived_actions:
                if action not in ui_actions:
                    ui_actions.append(action)
        if ui_actions:
            response["ui_actions"] = ui_actions
        return response

    response["summary"] = f"{tool_name} completed."
    response["data"] = {"result": result}
    return response
