"""
Voice API v2 - Pure LLM-Based Voice Processing

This module provides the v2 voice API endpoints using the new architecture:
1. Pure LLM-based intent classification (no regex)
2. Tool-based action execution
3. UI state grounding
4. Verification-ready responses

Endpoints:
- POST /voice/v2/process - Process a voice command
- POST /voice/v2/ui-state - Receive UI state from frontend
- GET /voice/v2/tools - Get available voice tools
"""

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from api.core.database import get_db
from api.services.voice_processor import (
    get_voice_processor,
    VoiceProcessorResponse,
    UiState,
    TabState,
    ButtonState,
    InputState,
    DropdownState,
    DropdownOptionState,
)
from api.services.voice_agent_tools import (
    get_voice_tools,
    execute_voice_tool,
    ToolResult,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/voice/v2", tags=["voice-v2"])


# ============================================================================
# REQUEST/RESPONSE MODELS
# ============================================================================

class ProcessVoiceRequest(BaseModel):
    """Request to process a voice command."""
    user_id: int = Field(..., description="User ID")
    transcript: str = Field(..., description="Transcribed voice input")
    language: str = Field("en", description="Language code (en/es)")

    # UI State
    ui_state: Optional[UiState] = Field(None, description="Current UI state from frontend")

    # Context
    conversation_state: str = Field("idle", description="Current conversation state")
    active_course_name: Optional[str] = Field(None, description="Name of active course")
    active_session_name: Optional[str] = Field(None, description="Name of active session")


class ProcessVoiceResponse(BaseModel):
    """Response from voice processing."""
    success: bool
    spoken_response: str
    ui_action: Optional[Dict[str, Any]] = None
    tool_used: Optional[str] = None
    confidence: float = 0.0
    needs_confirmation: bool = False
    confirmation_context: Optional[Dict[str, Any]] = None


class UiStateRequest(BaseModel):
    """Request to update UI state."""
    user_id: int
    ui_state: UiState


class ToolExecuteRequest(BaseModel):
    """Request to execute a specific tool."""
    user_id: int
    tool_name: str
    parameters: Dict[str, Any]


class ToolExecuteResponse(BaseModel):
    """Response from tool execution."""
    status: str
    message: str
    ui_action: Optional[Dict[str, Any]] = None
    data: Optional[Dict[str, Any]] = None


# ============================================================================
# UI STATE CACHE
# ============================================================================

# Simple in-memory cache for UI state per user
# In production, this should use Redis or similar
_ui_state_cache: Dict[int, UiState] = {}


def get_cached_ui_state(user_id: int) -> Optional[UiState]:
    """Get cached UI state for a user."""
    return _ui_state_cache.get(user_id)


def set_cached_ui_state(user_id: int, ui_state: UiState) -> None:
    """Cache UI state for a user."""
    _ui_state_cache[user_id] = ui_state


# ============================================================================
# ENDPOINTS
# ============================================================================

@router.post("/process", response_model=ProcessVoiceResponse)
async def process_voice_command(
    request: ProcessVoiceRequest,
    db: Session = Depends(get_db),
) -> ProcessVoiceResponse:
    """
    Process a voice command using pure LLM-based understanding.

    This endpoint:
    1. Receives the transcribed voice input and UI state
    2. Uses LLM to understand intent and extract parameters
    3. Executes the appropriate tool
    4. Returns the spoken response and UI action
    """
    logger.info(f"Processing voice command for user {request.user_id}: {request.transcript[:100]}")

    # Get UI state from request or cache
    ui_state = request.ui_state
    if ui_state is None:
        ui_state = get_cached_ui_state(request.user_id)

    # Process the voice command
    processor = get_voice_processor()
    result = processor.process(
        user_input=request.transcript,
        ui_state=ui_state,
        conversation_state=request.conversation_state,
        language=request.language,
        active_course=request.active_course_name,
        active_session=request.active_session_name,
    )

    return ProcessVoiceResponse(
        success=result.success,
        spoken_response=result.spoken_response,
        ui_action=result.ui_action,
        tool_used=result.tool_used,
        confidence=result.confidence,
        needs_confirmation=result.needs_confirmation,
        confirmation_context=result.confirmation_context,
    )


@router.post("/ui-state")
async def update_ui_state(request: UiStateRequest) -> Dict[str, str]:
    """
    Receive UI state from frontend.

    The frontend should call this endpoint periodically or on significant
    UI changes to keep the backend informed of the current UI state.
    This enables smarter voice command processing.
    """
    set_cached_ui_state(request.user_id, request.ui_state)
    logger.debug(f"Updated UI state for user {request.user_id}: {request.ui_state.route}")
    return {"status": "ok"}


@router.get("/ui-state/{user_id}")
async def get_ui_state(user_id: int) -> Optional[UiState]:
    """Get cached UI state for a user."""
    return get_cached_ui_state(user_id)


@router.post("/execute-tool", response_model=ToolExecuteResponse)
async def execute_tool(request: ToolExecuteRequest) -> ToolExecuteResponse:
    """
    Execute a specific voice tool directly.

    This endpoint allows the ElevenLabs Agent or other clients to
    execute tools without going through the full LLM processing.
    """
    logger.info(f"Executing tool {request.tool_name} for user {request.user_id}")

    result = execute_voice_tool(request.tool_name, request.parameters)

    return ToolExecuteResponse(
        status=result.status.value,
        message=result.message,
        ui_action=result.ui_action,
        data=result.data,
    )


@router.get("/tools")
async def list_tools() -> List[Dict[str, Any]]:
    """
    Get the list of available voice tools.

    This endpoint returns the tool definitions that can be registered
    with the ElevenLabs Agent or used by other voice systems.
    """
    return get_voice_tools()


# ============================================================================
# HEALTH CHECK
# ============================================================================

@router.get("/health")
async def health_check() -> Dict[str, str]:
    """Check if the voice v2 system is healthy."""
    processor = get_voice_processor()
    llm_available = processor._ensure_llm()

    if llm_available:
        return {"status": "healthy", "llm": "available"}
    else:
        return {"status": "degraded", "llm": "unavailable"}
