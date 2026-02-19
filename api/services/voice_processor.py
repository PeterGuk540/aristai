"""
Unified Voice Processor - LLM-Based Voice Command Processing

This module provides the core voice processing logic using a pure LLM-based
approach with no hardcoded patterns or regex matching.

Flow:
1. Receive transcribed voice input + UI state context
2. LLM classifies intent and extracts parameters
3. Execute appropriate tool/action
4. Return structured response with UI action

All processing is done through LLM - no regex, no hardcoded phrase dictionaries.
"""

import json
import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from pydantic import BaseModel, Field

from api.services.voice_agent_tools import (
    execute_voice_tool,
    ToolResult,
    ToolResultStatus,
    VOICE_AGENT_TOOLS,
)
from workflows.llm_utils import (
    get_fast_voice_llm,
    invoke_llm_with_metrics,
    parse_json_response,
    LLMResponse,
)

logger = logging.getLogger(__name__)


# ============================================================================
# UI STATE MODELS (from frontend)
# ============================================================================

class TabState(BaseModel):
    """State of a tab element."""
    id: str = Field(..., description="voice-id of the tab")
    label: str = Field(..., description="Display label")
    active: bool = Field(False, description="Whether tab is currently active")


class ButtonState(BaseModel):
    """State of a button element."""
    id: str = Field(..., description="voice-id of the button")
    label: str = Field(..., description="Display label")


class InputState(BaseModel):
    """State of an input field."""
    id: str = Field(..., description="voice-id of the input")
    label: str = Field(..., description="Field label or placeholder")
    value: str = Field("", description="Current value")


class DropdownOptionState(BaseModel):
    """State of a dropdown option."""
    idx: int = Field(..., description="0-based index")
    label: str = Field(..., description="Option label")


class DropdownState(BaseModel):
    """State of a dropdown element."""
    id: str = Field(..., description="voice-id of the dropdown")
    label: str = Field(..., description="Dropdown label")
    selected: Optional[str] = Field(None, description="Currently selected option label")
    options: List[DropdownOptionState] = Field(default_factory=list)


class UiState(BaseModel):
    """Complete UI state from frontend."""
    route: str = Field(..., description="Current page route")
    activeTab: Optional[str] = Field(None, description="voice-id of active tab")
    tabs: List[TabState] = Field(default_factory=list)
    buttons: List[ButtonState] = Field(default_factory=list)
    inputs: List[InputState] = Field(default_factory=list)
    dropdowns: List[DropdownState] = Field(default_factory=list)
    modal: Optional[str] = Field(None, description="Title of open modal, if any")


# ============================================================================
# VOICE PROCESSOR RESPONSE
# ============================================================================

@dataclass
class VoiceProcessorResponse:
    """Response from voice processor."""
    success: bool
    spoken_response: str  # Text to speak to user
    ui_action: Optional[Dict[str, Any]] = None  # Action to dispatch to frontend
    tool_used: Optional[str] = None
    confidence: float = 0.0
    needs_confirmation: bool = False
    confirmation_context: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        result = {
            "success": self.success,
            "spoken_response": self.spoken_response,
            "confidence": self.confidence,
            "needs_confirmation": self.needs_confirmation,
        }
        if self.ui_action:
            result["ui_action"] = self.ui_action
        if self.tool_used:
            result["tool_used"] = self.tool_used
        if self.confirmation_context:
            result["confirmation_context"] = self.confirmation_context
        return result


# ============================================================================
# LLM PROMPT FOR VOICE UNDERSTANDING
# ============================================================================

VOICE_UNDERSTANDING_PROMPT = """You are the voice command processor for AristAI, an educational discussion platform.
Analyze the user's voice input and determine which tool to call.

## Available Tools
{tools_json}

## Current UI State
Route: {route}
Active Tab: {active_tab}

### Visible Tabs
{tabs_list}

### Available Buttons
{buttons_list}

### Form Inputs
{inputs_list}

### Dropdowns
{dropdowns_list}

### Modal
{modal_state}

## Conversation Context
State: {conversation_state}
Language: {language}
Active Course: {active_course}
Active Session: {active_session}

## User Input
"{user_input}"

## Instructions

1. Analyze what the user wants to do
2. Match their intent to one of the available tools
3. Extract the required parameters

### Important Rules:
- Match UI elements by SEMANTIC MEANING, not exact words
  - "polls tab" / "show polls" / "go to polls" → switch_tab(tab_voice_id="tab-polls")
  - "AI features" / "enhanced features" → switch_tab(tab_voice_id="tab-ai-features")
  - "create poll" / "new poll" / "make a poll" → click_button(button_voice_id="create-poll")

- Handle ordinals for dropdown selection:
  - "first" / "primero" / "one" → selection_index: 0
  - "second" / "segundo" / "two" → selection_index: 1
  - "third" / "tercero" / "three" → selection_index: 2
  - "last" / "último" → selection_index: -1

- If the user provides content to fill (like "the title is Introduction to AI"):
  - Use fill_input with the content extracted
  - If no specific field mentioned, use the first empty input

- Handle confirmations:
  - "yes" / "si" / "confirm" / "go ahead" → confirm_action(confirmed=true)
  - "no" / "cancel" / "stop" → confirm_action(confirmed=false)
  - "skip" / "next" / "omitir" → confirm_action(confirmed=false, skip=true)

## Response Format

Return ONLY valid JSON:
{{
    "tool_name": "name of tool to call",
    "parameters": {{ ... tool parameters ... }},
    "confidence": 0.0-1.0,
    "spoken_response": "Brief response to speak to user (in {language})"
}}

If you cannot understand the command, return:
{{
    "tool_name": null,
    "parameters": {{}},
    "confidence": 0.0,
    "spoken_response": "I didn't understand that. Could you try again?"
}}
"""


# ============================================================================
# VOICE PROCESSOR CLASS
# ============================================================================

class VoiceProcessor:
    """
    Process voice commands using pure LLM-based understanding.

    This class:
    1. Receives voice input and UI state
    2. Uses LLM to understand intent and extract parameters
    3. Executes the appropriate tool
    4. Returns structured response with UI action
    """

    def __init__(self):
        self._llm = None
        self._model_name = None

    def _ensure_llm(self) -> bool:
        """Ensure LLM is initialized."""
        if self._llm is None:
            self._llm, self._model_name = get_fast_voice_llm()
        return self._llm is not None

    def _format_tabs(self, tabs: List[TabState]) -> str:
        """Format tabs list for prompt."""
        if not tabs:
            return "No tabs available"
        lines = []
        for tab in tabs:
            status = " (ACTIVE)" if tab.active else ""
            lines.append(f"- {tab.id}: {tab.label}{status}")
        return "\n".join(lines)

    def _format_buttons(self, buttons: List[ButtonState]) -> str:
        """Format buttons list for prompt."""
        if not buttons:
            return "No buttons available"
        lines = [f"- {btn.id}: {btn.label}" for btn in buttons]
        return "\n".join(lines)

    def _format_inputs(self, inputs: List[InputState]) -> str:
        """Format inputs list for prompt."""
        if not inputs:
            return "No input fields"
        lines = []
        for inp in inputs:
            value_preview = f' = "{inp.value[:30]}..."' if inp.value else " (empty)"
            lines.append(f"- {inp.id}: {inp.label}{value_preview}")
        return "\n".join(lines)

    def _format_dropdowns(self, dropdowns: List[DropdownState]) -> str:
        """Format dropdowns list for prompt."""
        if not dropdowns:
            return "No dropdowns"
        lines = []
        for dd in dropdowns:
            selected = f" (selected: {dd.selected})" if dd.selected else ""
            options_preview = ", ".join([o.label for o in dd.options[:5]])
            if len(dd.options) > 5:
                options_preview += f"... ({len(dd.options)} total)"
            lines.append(f"- {dd.id}: {dd.label}{selected}")
            if dd.options:
                lines.append(f"  Options: {options_preview}")
        return "\n".join(lines)

    def _build_prompt(
        self,
        user_input: str,
        ui_state: UiState,
        conversation_state: str,
        language: str,
        active_course: Optional[str],
        active_session: Optional[str],
    ) -> str:
        """Build the LLM prompt with all context."""
        tools_json = json.dumps(VOICE_AGENT_TOOLS, indent=2)

        return VOICE_UNDERSTANDING_PROMPT.format(
            tools_json=tools_json,
            route=ui_state.route,
            active_tab=ui_state.activeTab or "None",
            tabs_list=self._format_tabs(ui_state.tabs),
            buttons_list=self._format_buttons(ui_state.buttons),
            inputs_list=self._format_inputs(ui_state.inputs),
            dropdowns_list=self._format_dropdowns(ui_state.dropdowns),
            modal_state=ui_state.modal or "No modal open",
            conversation_state=conversation_state,
            language=language,
            active_course=active_course or "None",
            active_session=active_session or "None",
            user_input=user_input,
        )

    def process(
        self,
        user_input: str,
        ui_state: Optional[UiState] = None,
        conversation_state: str = "idle",
        language: str = "en",
        active_course: Optional[str] = None,
        active_session: Optional[str] = None,
    ) -> VoiceProcessorResponse:
        """
        Process a voice command.

        Args:
            user_input: Transcribed voice input
            ui_state: Current UI state from frontend
            conversation_state: Current conversation state (idle, awaiting_confirmation, etc.)
            language: User's language preference (en/es)
            active_course: Name of active course
            active_session: Name of active session

        Returns:
            VoiceProcessorResponse with spoken response and UI action
        """
        if not user_input or not user_input.strip():
            return VoiceProcessorResponse(
                success=False,
                spoken_response="I didn't catch that." if language == "en" else "No te escuché.",
                confidence=0.0,
            )

        # Ensure LLM is available
        if not self._ensure_llm():
            return VoiceProcessorResponse(
                success=False,
                spoken_response="Voice processing is temporarily unavailable.",
                confidence=0.0,
            )

        # Default UI state if not provided
        if ui_state is None:
            ui_state = UiState(route="/dashboard")

        # Build and send prompt to LLM
        prompt = self._build_prompt(
            user_input=user_input,
            ui_state=ui_state,
            conversation_state=conversation_state,
            language=language,
            active_course=active_course,
            active_session=active_session,
        )

        try:
            llm_response = invoke_llm_with_metrics(self._llm, prompt, self._model_name)

            if not llm_response.success or not llm_response.content:
                logger.error(f"LLM call failed: {llm_response.metrics.error_message}")
                return VoiceProcessorResponse(
                    success=False,
                    spoken_response="I'm having trouble understanding. Please try again.",
                    confidence=0.0,
                )

            # Parse LLM response
            parsed = parse_json_response(llm_response.content)
            if not parsed:
                logger.error(f"Failed to parse LLM response: {llm_response.content[:200]}")
                return VoiceProcessorResponse(
                    success=False,
                    spoken_response="I didn't understand that command.",
                    confidence=0.0,
                )

            tool_name = parsed.get("tool_name")
            parameters = parsed.get("parameters", {})
            confidence = float(parsed.get("confidence", 0.0))
            spoken_response = parsed.get("spoken_response", "")

            # If no tool matched
            if not tool_name:
                return VoiceProcessorResponse(
                    success=False,
                    spoken_response=spoken_response or "I didn't understand that.",
                    confidence=confidence,
                )

            # Execute the tool
            tool_result = execute_voice_tool(tool_name, parameters)

            return VoiceProcessorResponse(
                success=tool_result.status == ToolResultStatus.SUCCESS,
                spoken_response=spoken_response or tool_result.message,
                ui_action=tool_result.ui_action,
                tool_used=tool_name,
                confidence=confidence,
            )

        except Exception as e:
            logger.exception(f"Error processing voice command: {e}")
            return VoiceProcessorResponse(
                success=False,
                spoken_response="Something went wrong. Please try again.",
                confidence=0.0,
            )


# ============================================================================
# SINGLETON ACCESSOR
# ============================================================================

_voice_processor: Optional[VoiceProcessor] = None


def get_voice_processor() -> VoiceProcessor:
    """Get the singleton voice processor instance."""
    global _voice_processor
    if _voice_processor is None:
        _voice_processor = VoiceProcessor()
    return _voice_processor
