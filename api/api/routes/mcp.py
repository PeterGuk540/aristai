"""MCP tool execution endpoints for the voice assistant."""

import logging
import traceback
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from api.api.mcp_executor import invoke_tool_handler
from api.core.database import get_db
from api.services.action_preview import build_action_preview
from api.services.action_store import ActionStore
from api.services.tool_response import normalize_tool_result
from mcp_server.server import TOOL_REGISTRY

logger = logging.getLogger(__name__)

router = APIRouter()
action_store = ActionStore()
ACTION_TOOL_NAMES = {"plan_action", "execute_action", "cancel_action"}


class MCPExecuteRequest(BaseModel):
    tool: str = Field(..., min_length=1)
    arguments: Dict[str, Any] = Field(default_factory=dict)
    user_id: Optional[int] = None


def _validate_tool_args(tool_name: str, args: Dict[str, Any], schema: Dict[str, Any]) -> Optional[str]:
    required = schema.get("required", [])
    properties = schema.get("properties", {})

    for field in required:
        if field not in args:
            return f"Missing required field '{field}' for tool '{tool_name}'"

    for field, value in args.items():
        expected = properties.get(field, {}).get("type")
        if not expected:
            continue
        if expected == "integer" and not isinstance(value, int):
            return f"Field '{field}' must be integer"
        if expected == "string" and not isinstance(value, str):
            return f"Field '{field}' must be string"
        if expected == "array" and not isinstance(value, list):
            return f"Field '{field}' must be array"
        if expected == "boolean" and not isinstance(value, bool):
            return f"Field '{field}' must be boolean"
    return None


@router.post("/execute")
async def execute_tool(request: MCPExecuteRequest, db: Session = Depends(get_db)):
    """Execute a registered MCP tool by name."""
    tool_info = TOOL_REGISTRY.get(request.tool)
    if not tool_info:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Tool '{request.tool}' not found",
        )

    args = request.arguments or {}
    if tool_info.get("mode") == "write" and request.user_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="user_id is required for write tools",
        )

    if request.user_id is not None:
        for identity_field in ("user_id", "created_by", "uploaded_by", "triggered_by"):
            if identity_field in args and args[identity_field] is not None and args[identity_field] != request.user_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Argument '{identity_field}' must match request user_id",
                )

    validation_error = _validate_tool_args(request.tool, args, tool_info.get("parameters", {}))
    if validation_error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=validation_error)

    try:
        logger.info("Executing MCP tool '%s'", request.tool)
        if tool_info.get("mode") == "write" and request.tool not in ACTION_TOOL_NAMES:
            preview = build_action_preview(request.tool, args, db=db)
            action = action_store.create_action(
                user_id=request.user_id,
                tool_name=request.tool,
                args=args,
                preview=preview,
            )
            planned = {
                "tool": request.tool,
                "success": True,
                "action_id": action.action_id,
                "requires_confirmation": True,
                "preview": preview,
                "message": "Action planned. Please confirm to execute.",
            }
            return {"tool": request.tool, **normalize_tool_result(planned, request.tool)}
        result = invoke_tool_handler(tool_info["handler"], args, db=db)
        return {"tool": request.tool, **normalize_tool_result(result, request.tool)}
    except HTTPException:
        raise
    except Exception as exc:
        traceback.print_exc()
        logger.exception("MCP tool execution failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        )
