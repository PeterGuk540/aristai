"""
Voice Controller v2 API Tests

Tests the pure LLM-based voice processing pipeline:
1. UI state handling
2. Tool execution
3. Action generation

Run with: pytest tests/test_voice_v2.py -v
"""

import pytest
from unittest.mock import patch, MagicMock
from pydantic import BaseModel
from typing import List, Optional, Dict, Any


# Import the modules we're testing
from api.services.voice_processor import (
    VoiceProcessor,
    UiState,
    TabState,
    ButtonState,
    InputState,
    DropdownState,
    DropdownOptionState,
    VoiceProcessorResponse,
)
from api.services.voice_agent_tools import (
    execute_voice_tool,
    ToolResult,
    ToolResultStatus,
    VOICE_AGENT_TOOLS,
    handle_switch_tab,
    handle_click_button,
    handle_fill_input,
    handle_select_dropdown_option,
    handle_navigate_to_page,
)


# ============================================================================
# TOOL EXECUTION TESTS
# ============================================================================

class TestVoiceAgentTools:
    """Test individual tool handlers."""

    def test_navigate_to_valid_page(self):
        """Test navigation to valid pages."""
        result = handle_navigate_to_page("courses")
        assert result.status == ToolResultStatus.SUCCESS
        assert result.ui_action["type"] == "ui.navigate"
        assert result.ui_action["payload"]["path"] == "/courses"

    def test_navigate_to_invalid_page(self):
        """Test navigation to invalid page returns error."""
        result = handle_navigate_to_page("invalid-page")
        assert result.status == ToolResultStatus.FAILURE
        assert "Unknown page" in result.message

    def test_switch_tab(self):
        """Test tab switching."""
        result = handle_switch_tab("tab-ai-features", "AI Features")
        assert result.status == ToolResultStatus.SUCCESS
        assert result.ui_action["type"] == "ui.switchTab"
        assert result.ui_action["payload"]["voiceId"] == "tab-ai-features"

    def test_click_button(self):
        """Test button click."""
        result = handle_click_button("create-course", "Create Course")
        assert result.status == ToolResultStatus.SUCCESS
        assert result.ui_action["type"] == "ui.clickButton"
        assert result.ui_action["payload"]["voiceId"] == "create-course"

    def test_fill_input(self):
        """Test input filling."""
        result = handle_fill_input("course-title", "Introduction to AI", False)
        assert result.status == ToolResultStatus.SUCCESS
        assert result.ui_action["type"] == "ui.fillInput"
        assert result.ui_action["payload"]["content"] == "Introduction to AI"
        assert result.ui_action["payload"]["append"] == False

    def test_fill_input_append(self):
        """Test input append mode."""
        result = handle_fill_input("post-content", " additional text", True)
        assert result.status == ToolResultStatus.SUCCESS
        assert result.ui_action["payload"]["append"] == True

    def test_select_dropdown_by_index(self):
        """Test dropdown selection by index."""
        result = handle_select_dropdown_option("select-course", selection_index=0)
        assert result.status == ToolResultStatus.SUCCESS
        assert result.ui_action["type"] == "ui.selectDropdown"
        assert result.ui_action["payload"]["selectionIndex"] == 0

    def test_select_dropdown_by_text(self):
        """Test dropdown selection by text."""
        result = handle_select_dropdown_option(
            "select-course", selection_text="Statistics 101"
        )
        assert result.status == ToolResultStatus.SUCCESS
        assert result.ui_action["payload"]["optionName"] == "Statistics 101"

    def test_select_dropdown_missing_params(self):
        """Test dropdown selection fails without index or text."""
        result = handle_select_dropdown_option("select-course")
        assert result.status == ToolResultStatus.FAILURE
        assert "Must provide" in result.message


class TestToolDispatcher:
    """Test the tool dispatcher."""

    def test_dispatch_navigate(self):
        result = execute_voice_tool("navigate_to_page", {"page": "sessions"})
        assert result.status == ToolResultStatus.SUCCESS

    def test_dispatch_switch_tab(self):
        result = execute_voice_tool(
            "switch_tab",
            {"tab_voice_id": "tab-create", "tab_label": "Create"},
        )
        assert result.status == ToolResultStatus.SUCCESS

    def test_dispatch_click_button(self):
        result = execute_voice_tool(
            "click_button",
            {"button_voice_id": "go-live", "button_label": "Go Live"},
        )
        assert result.status == ToolResultStatus.SUCCESS

    def test_dispatch_unknown_tool(self):
        result = execute_voice_tool("unknown_tool", {})
        assert result.status == ToolResultStatus.FAILURE
        assert "Unknown tool" in result.message


# ============================================================================
# UI STATE TESTS
# ============================================================================

class TestUiState:
    """Test UI state models."""

    def test_ui_state_creation(self):
        """Test creating a valid UI state."""
        state = UiState(
            route="/sessions",
            activeTab="tab-sessions",
            tabs=[
                TabState(id="tab-sessions", label="Sessions", active=True),
                TabState(id="tab-create", label="Create", active=False),
            ],
            buttons=[
                ButtonState(id="create-session", label="Create Session"),
            ],
            inputs=[
                InputState(id="session-title", label="Title", value=""),
            ],
            dropdowns=[
                DropdownState(
                    id="select-course",
                    label="Course",
                    selected="Statistics 101",
                    options=[
                        DropdownOptionState(idx=0, label="Statistics 101"),
                        DropdownOptionState(idx=1, label="Machine Learning"),
                    ],
                ),
            ],
        )
        assert state.route == "/sessions"
        assert state.activeTab == "tab-sessions"
        assert len(state.tabs) == 2
        assert len(state.dropdowns[0].options) == 2

    def test_minimal_ui_state(self):
        """Test creating minimal UI state."""
        state = UiState(route="/dashboard")
        assert state.route == "/dashboard"
        assert state.activeTab is None
        assert state.tabs == []


# ============================================================================
# TOOL DEFINITIONS TESTS
# ============================================================================

class TestToolDefinitions:
    """Test that tool definitions are properly formatted."""

    def test_all_tools_have_required_fields(self):
        """Verify all tools have name, description, parameters."""
        for tool in VOICE_AGENT_TOOLS:
            assert "name" in tool, f"Tool missing 'name'"
            assert "description" in tool, f"Tool {tool.get('name')} missing 'description'"
            assert "parameters" in tool, f"Tool {tool.get('name')} missing 'parameters'"

    def test_tool_parameters_are_valid_json_schema(self):
        """Verify tool parameters follow JSON Schema format."""
        for tool in VOICE_AGENT_TOOLS:
            params = tool["parameters"]
            assert params.get("type") == "object"
            assert "properties" in params
            if "required" in params:
                assert isinstance(params["required"], list)

    def test_required_tools_exist(self):
        """Verify essential tools are defined."""
        tool_names = [t["name"] for t in VOICE_AGENT_TOOLS]
        required_tools = [
            "navigate_to_page",
            "switch_tab",
            "click_button",
            "fill_input",
            "select_dropdown_option",
            "expand_dropdown",
            "get_ui_state",
            "submit_form",
            "scroll",
            "confirm_action",
        ]
        for required in required_tools:
            assert required in tool_names, f"Missing required tool: {required}"


# ============================================================================
# VOICE PROCESSOR TESTS
# ============================================================================

class TestVoiceProcessor:
    """Test the voice processor."""

    def test_empty_input_returns_error(self):
        """Test that empty input is handled gracefully."""
        processor = VoiceProcessor()
        result = processor.process(user_input="", language="en")
        assert result.success == False
        assert "didn't catch" in result.spoken_response.lower()

    def test_whitespace_input_returns_error(self):
        """Test that whitespace-only input is handled."""
        processor = VoiceProcessor()
        result = processor.process(user_input="   ", language="en")
        assert result.success == False

    @patch("api.services.voice_processor.get_fast_voice_llm")
    def test_llm_unavailable_returns_error(self, mock_get_llm):
        """Test handling when LLM is unavailable."""
        mock_get_llm.return_value = (None, None)
        processor = VoiceProcessor()
        result = processor.process(user_input="go to courses")
        assert result.success == False
        assert "unavailable" in result.spoken_response.lower()


# ============================================================================
# FAILURE TRACE TESTS (Real-world failures)
# ============================================================================

class TestFailureTraces:
    """
    Tests based on real failure traces:
    transcript → inferred intent → planned actions → execution results → UI state deltas
    """

    def test_failure_trace_1_hyphenated_tab_names(self):
        """
        Failure: Tab switch fails due to hyphenated name normalization

        Trace:
        - Transcript: "switch to AI features tab"
        - LLM output: {"tab_voice_id": "aifeatures"}
        - Expected DOM: data-voice-id="tab-ai-features"
        - Result: Tab not found

        Fix: Tool should use exact voice-id from UI state, not normalized name
        """
        # The tool should accept the voice-id as-is
        result = handle_switch_tab("tab-ai-features", "AI Features")
        assert result.status == ToolResultStatus.SUCCESS
        assert result.ui_action["payload"]["voiceId"] == "tab-ai-features"

    def test_failure_trace_2_ordinal_selection_off_by_one(self):
        """
        Failure: "Select the first course" selects the second course

        Trace:
        - Transcript: "select the first course"
        - LLM output: {"selection_index": 1}  # Should be 0
        - Result: Wrong course selected

        Fix: LLM prompt should clarify 0-indexed selection
        """
        # First = index 0
        result = handle_select_dropdown_option("select-course", selection_index=0)
        assert result.ui_action["payload"]["selectionIndex"] == 0

        # Last = index -1
        result = handle_select_dropdown_option("select-course", selection_index=-1)
        assert result.ui_action["payload"]["selectionIndex"] == -1

    def test_failure_trace_3_form_content_not_saved(self):
        """
        Failure: Form content filled but not persisted to React state

        Trace:
        - Transcript: "set title to Introduction to AI"
        - DOM input.value changes
        - React state not updated (no events dispatched)
        - Form submission uses stale empty value

        Fix: Use React-compatible value setter in executor
        """
        result = handle_fill_input("course-title", "Introduction to AI", False)
        assert result.status == ToolResultStatus.SUCCESS
        # The UI action should trigger proper React events in frontend
        assert result.ui_action["payload"]["content"] == "Introduction to AI"


# ============================================================================
# INTEGRATION-STYLE TESTS
# ============================================================================

class TestEndToEndFlow:
    """Test complete voice command flows."""

    def test_create_course_flow(self):
        """Test the voice flow for creating a course."""
        # Step 1: Navigate to courses
        nav_result = execute_voice_tool("navigate_to_page", {"page": "courses"})
        assert nav_result.status == ToolResultStatus.SUCCESS
        assert nav_result.ui_action["payload"]["path"] == "/courses"

        # Step 2: Switch to create tab
        tab_result = execute_voice_tool(
            "switch_tab", {"tab_voice_id": "tab-create", "tab_label": "Create"}
        )
        assert tab_result.status == ToolResultStatus.SUCCESS

        # Step 3: Fill course title
        fill_result = execute_voice_tool(
            "fill_input",
            {"field_voice_id": "course-title", "content": "Statistics 101"},
        )
        assert fill_result.status == ToolResultStatus.SUCCESS

        # Step 4: Click create button
        click_result = execute_voice_tool(
            "click_button", {"button_voice_id": "create-course"}
        )
        assert click_result.status == ToolResultStatus.SUCCESS

    def test_dropdown_selection_flow(self):
        """Test selecting from a dropdown."""
        # First, expand dropdown
        expand_result = execute_voice_tool(
            "expand_dropdown", {"dropdown_voice_id": "select-course"}
        )
        assert expand_result.status == ToolResultStatus.SUCCESS

        # Then select option
        select_result = execute_voice_tool(
            "select_dropdown_option",
            {"dropdown_voice_id": "select-course", "selection_index": 0},
        )
        assert select_result.status == ToolResultStatus.SUCCESS
