"""MCP tool execution endpoints for the voice assistant."""

import logging
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from api.core.database import get_db
from mcp_server.server import TOOL_REGISTRY

logger = logging.getLogger(__name__)

router = APIRouter()


class MCPExecuteRequest(BaseModel):
    tool: str = Field(..., min_length=1)
    arguments: Dict[str, Any] = Field(default_factory=dict)


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
    validation_error = _validate_tool_args(request.tool, args, tool_info.get("parameters", {}))
    if validation_error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=validation_error)

    try:
        logger.info("Executing MCP tool '%s'", request.tool)
        result = tool_info["handler"](db, **args)
        if isinstance(result, dict):
            return {"tool": request.tool, **result}
        return {"tool": request.tool, "result": result}
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("MCP tool execution failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to execute MCP tool",
        )
