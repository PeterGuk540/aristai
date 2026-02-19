"""
Voice Agent Tools - Tool definitions for ElevenLabs Conversational AI Agent.

This module defines the tools that the ElevenLabs Agent can call during voice
conversations. These tools enable the agent to:
1. Navigate between pages
2. Switch tabs
3. Click buttons
4. Fill form fields
5. Select dropdown options
6. Query the current UI state

All tools return structured responses that the agent can use to provide
voice feedback to the user.
"""

import json
import logging
from dataclasses import dataclass, asdict
from enum import Enum
from typing import Any, Dict, List, Literal, Optional, Union

from pydantic import BaseModel, Field

# Import page registry for workflow and topology knowledge
from api.services.voice_page_registry import (
    get_page,
    get_tabs_for_page,
    is_tab_on_page,
    find_tab_page,
    find_feature_location,
    get_workflow,
    get_navigation_steps,
    PAGE_REGISTRY,
    WORKFLOW_REGISTRY,
)

logger = logging.getLogger(__name__)


# ============================================================================
# TOOL RESPONSE TYPES
# ============================================================================

class ToolResultStatus(str, Enum):
    """Status of a tool execution."""
    SUCCESS = "success"
    FAILURE = "failure"
    PENDING = "pending"  # Action dispatched, verification pending


@dataclass
class ToolResult:
    """Result from a tool execution."""
    status: ToolResultStatus
    message: str
    data: Optional[Dict[str, Any]] = None
    ui_action: Optional[Dict[str, Any]] = None  # Action to dispatch to frontend

    def to_dict(self) -> Dict[str, Any]:
        result = {
            "status": self.status.value,
            "message": self.message,
        }
        if self.data:
            result["data"] = self.data
        if self.ui_action:
            result["ui_action"] = self.ui_action
        return result


# ============================================================================
# TOOL DEFINITIONS FOR ELEVENLABS AGENT
# ============================================================================

# These are the tool definitions that should be registered with the ElevenLabs
# Agent. They follow the ElevenLabs tool schema format.

VOICE_AGENT_TOOLS = [
    {
        "name": "navigate_to_page",
        "description": "Navigate to a different page in the application. Use this when the user wants to go to a specific page like courses, sessions, forum, console, or reports.",
        "parameters": {
            "type": "object",
            "properties": {
                "page": {
                    "type": "string",
                    "enum": ["courses", "sessions", "forum", "console", "reports", "dashboard", "integrations", "introduction", "profile"],
                    "description": "The page to navigate to"
                }
            },
            "required": ["page"]
        }
    },
    {
        "name": "switch_tab",
        "description": "Switch to a different tab on the current page. The tab is identified by its voice-id attribute (e.g., 'tab-courses', 'tab-create', 'tab-ai-features').",
        "parameters": {
            "type": "object",
            "properties": {
                "tab_voice_id": {
                    "type": "string",
                    "description": "The voice-id of the tab (e.g., 'tab-courses', 'tab-create', 'tab-polls', 'tab-ai-features')"
                },
                "tab_label": {
                    "type": "string",
                    "description": "Human-readable tab name for confirmation (e.g., 'Courses', 'Create', 'AI Features')"
                }
            },
            "required": ["tab_voice_id"]
        }
    },
    {
        "name": "click_button",
        "description": "Click a button on the page. The button is identified by its voice-id attribute.",
        "parameters": {
            "type": "object",
            "properties": {
                "button_voice_id": {
                    "type": "string",
                    "description": "The voice-id of the button (e.g., 'create-course', 'go-live', 'start-copilot')"
                },
                "button_label": {
                    "type": "string",
                    "description": "Human-readable button name for confirmation"
                }
            },
            "required": ["button_voice_id"]
        }
    },
    {
        "name": "fill_input",
        "description": "Fill a form input field with content. Use this for text inputs, textareas, or any form field.",
        "parameters": {
            "type": "object",
            "properties": {
                "field_voice_id": {
                    "type": "string",
                    "description": "The voice-id of the input field (e.g., 'course-title', 'poll-question', 'new-post')"
                },
                "content": {
                    "type": "string",
                    "description": "The content to fill in the field"
                },
                "append": {
                    "type": "boolean",
                    "description": "If true, append to existing content instead of replacing",
                    "default": False
                }
            },
            "required": ["field_voice_id", "content"]
        }
    },
    {
        "name": "select_dropdown_option",
        "description": "Select an option from a dropdown. Can select by index (0-based, -1 for last) or by option text.",
        "parameters": {
            "type": "object",
            "properties": {
                "dropdown_voice_id": {
                    "type": "string",
                    "description": "The voice-id of the dropdown (e.g., 'select-course', 'select-session')"
                },
                "selection_index": {
                    "type": "integer",
                    "description": "0-based index of option to select. Use -1 for last option."
                },
                "selection_text": {
                    "type": "string",
                    "description": "Text of the option to select (partial match supported)"
                }
            },
            "required": ["dropdown_voice_id"]
        }
    },
    {
        "name": "expand_dropdown",
        "description": "Expand a dropdown to show its options. Use this when the user wants to see available options before selecting.",
        "parameters": {
            "type": "object",
            "properties": {
                "dropdown_voice_id": {
                    "type": "string",
                    "description": "The voice-id of the dropdown to expand"
                }
            },
            "required": ["dropdown_voice_id"]
        }
    },
    {
        "name": "get_ui_state",
        "description": "Get the current state of the UI including visible tabs, buttons, form fields, and dropdown options. Use this to understand what actions are available.",
        "parameters": {
            "type": "object",
            "properties": {},
            "required": []
        }
    },
    {
        "name": "submit_form",
        "description": "Submit the current form by clicking the submit button.",
        "parameters": {
            "type": "object",
            "properties": {
                "submit_button_voice_id": {
                    "type": "string",
                    "description": "Optional voice-id of specific submit button to click"
                }
            },
            "required": []
        }
    },
    {
        "name": "scroll",
        "description": "Scroll the page in a direction.",
        "parameters": {
            "type": "object",
            "properties": {
                "direction": {
                    "type": "string",
                    "enum": ["up", "down", "top", "bottom"],
                    "description": "Direction to scroll"
                },
                "target_voice_id": {
                    "type": "string",
                    "description": "Optional voice-id of element to scroll to"
                }
            },
            "required": ["direction"]
        }
    },
    {
        "name": "confirm_action",
        "description": "Confirm or cancel a pending action. Use when the user responds yes/no to a confirmation prompt.",
        "parameters": {
            "type": "object",
            "properties": {
                "confirmed": {
                    "type": "boolean",
                    "description": "True if user confirmed, False if cancelled"
                },
                "skip": {
                    "type": "boolean",
                    "description": "True if user wants to skip this step",
                    "default": False
                }
            },
            "required": ["confirmed"]
        }
    },
    # =========================================================================
    # COMPOSITE TOOLS - Multi-step workflows as atomic operations
    # =========================================================================
    {
        "name": "execute_workflow",
        "description": """Execute a predefined multi-step workflow. Use this for common tasks that require multiple steps.

Available workflows:
- enroll_students: Navigate to /courses → advanced tab (for adding students)
- view_ai_features: Navigate to /sessions → ai-features tab
- create_poll: Navigate to /console → polls tab → create poll
- start_session: Navigate to /sessions → manage tab → go live
- create_course: Navigate to /courses → create tab
- view_participation: Navigate to /courses → ai-insights tab
- upload_materials: Navigate to /sessions → materials tab

IMPORTANT: Use this tool when user wants to do one of these tasks, regardless of which page they're currently on.""",
        "parameters": {
            "type": "object",
            "properties": {
                "workflow_name": {
                    "type": "string",
                    "enum": ["enroll_students", "view_ai_features", "create_poll",
                            "start_session", "create_course", "view_participation", "upload_materials"],
                    "description": "Name of the workflow to execute"
                }
            },
            "required": ["workflow_name"]
        }
    },
    {
        "name": "navigate_and_switch_tab",
        "description": """Navigate to a page AND switch to a specific tab in one operation.

Use this when you need to go to a tab that may be on a different page.
This tool automatically handles the navigation if needed.

IMPORTANT: Always use this instead of separate navigate + switch_tab calls.""",
        "parameters": {
            "type": "object",
            "properties": {
                "target_tab": {
                    "type": "string",
                    "description": "The voice-id of the target tab (e.g., 'tab-advanced', 'tab-ai-features')"
                },
                "current_route": {
                    "type": "string",
                    "description": "The current page route (e.g., '/courses', '/sessions')"
                }
            },
            "required": ["target_tab", "current_route"]
        }
    },
    {
        "name": "smart_switch_tab",
        "description": """Intelligently switch to a tab, navigating to the correct page first if necessary.

This tool knows the application structure:
- tab-advanced is on /courses (for enrollment)
- tab-ai-features is on /sessions (for AI features)
- tab-polls is on /console (for polls)
- etc.

Use this instead of switch_tab when you're not sure if the tab exists on the current page.""",
        "parameters": {
            "type": "object",
            "properties": {
                "tab_voice_id": {
                    "type": "string",
                    "description": "The voice-id of the tab to switch to"
                },
                "current_route": {
                    "type": "string",
                    "description": "Current page route for context"
                }
            },
            "required": ["tab_voice_id"]
        }
    },
]


# ============================================================================
# TOOL HANDLERS
# ============================================================================

def handle_navigate_to_page(page: str) -> ToolResult:
    """Handle navigation to a page."""
    route_map = {
        "courses": "/courses",
        "sessions": "/sessions",
        "forum": "/forum",
        "console": "/console",
        "reports": "/reports",
        "dashboard": "/dashboard",
        "integrations": "/integrations",
        "introduction": "/platform-guide",
        "profile": "/profile",
    }

    route = route_map.get(page.lower())
    if not route:
        return ToolResult(
            status=ToolResultStatus.FAILURE,
            message=f"Unknown page: {page}. Available pages: {', '.join(route_map.keys())}"
        )

    return ToolResult(
        status=ToolResultStatus.SUCCESS,
        message=f"Navigating to {page}",
        ui_action={
            "type": "ui.navigate",
            "payload": {"path": route}
        }
    )


def handle_switch_tab(tab_voice_id: str, tab_label: Optional[str] = None) -> ToolResult:
    """Handle tab switching."""
    return ToolResult(
        status=ToolResultStatus.SUCCESS,
        message=f"Switching to {tab_label or tab_voice_id} tab",
        ui_action={
            "type": "ui.switchTab",
            "payload": {
                "voiceId": tab_voice_id,
                "tabName": tab_voice_id,
            }
        }
    )


def handle_click_button(button_voice_id: str, button_label: Optional[str] = None) -> ToolResult:
    """Handle button click."""
    return ToolResult(
        status=ToolResultStatus.SUCCESS,
        message=f"Clicking {button_label or button_voice_id}",
        ui_action={
            "type": "ui.clickButton",
            "payload": {
                "voiceId": button_voice_id,
                "target": button_voice_id,
            }
        }
    )


def handle_fill_input(
    field_voice_id: str,
    content: str,
    append: bool = False
) -> ToolResult:
    """Handle filling an input field."""
    return ToolResult(
        status=ToolResultStatus.SUCCESS,
        message=f"{'Appending to' if append else 'Filling'} {field_voice_id}",
        ui_action={
            "type": "ui.fillInput",
            "payload": {
                "voiceId": field_voice_id,
                "target": field_voice_id,
                "value": content,
                "content": content,
                "append": append,
            }
        }
    )


def handle_select_dropdown_option(
    dropdown_voice_id: str,
    selection_index: Optional[int] = None,
    selection_text: Optional[str] = None
) -> ToolResult:
    """Handle dropdown selection."""
    payload: Dict[str, Any] = {
        "voiceId": dropdown_voice_id,
        "target": dropdown_voice_id,
    }

    if selection_index is not None:
        payload["selectionIndex"] = selection_index
        payload["optionIndex"] = selection_index
        message = f"Selecting option {selection_index + 1 if selection_index >= 0 else 'last'}"
    elif selection_text:
        payload["optionName"] = selection_text
        message = f"Selecting {selection_text}"
    else:
        return ToolResult(
            status=ToolResultStatus.FAILURE,
            message="Must provide either selection_index or selection_text"
        )

    return ToolResult(
        status=ToolResultStatus.SUCCESS,
        message=message,
        ui_action={
            "type": "ui.selectDropdown",
            "payload": payload
        }
    )


def handle_expand_dropdown(dropdown_voice_id: str) -> ToolResult:
    """Handle dropdown expansion."""
    return ToolResult(
        status=ToolResultStatus.SUCCESS,
        message=f"Expanding dropdown",
        ui_action={
            "type": "ui.expandDropdown",
            "payload": {
                "voiceId": dropdown_voice_id,
                "target": dropdown_voice_id,
            }
        }
    )


def handle_get_ui_state() -> ToolResult:
    """Request current UI state from frontend."""
    return ToolResult(
        status=ToolResultStatus.PENDING,
        message="Requesting UI state",
        ui_action={
            "type": "ui.getUiState",
            "payload": {}
        }
    )


def handle_submit_form(submit_button_voice_id: Optional[str] = None) -> ToolResult:
    """Handle form submission."""
    payload: Dict[str, Any] = {}
    if submit_button_voice_id:
        payload["submitButtonVoiceId"] = submit_button_voice_id

    return ToolResult(
        status=ToolResultStatus.SUCCESS,
        message="Submitting form",
        ui_action={
            "type": "ui.submitForm",
            "payload": payload
        }
    )


def handle_scroll(
    direction: str,
    target_voice_id: Optional[str] = None
) -> ToolResult:
    """Handle scrolling."""
    return ToolResult(
        status=ToolResultStatus.SUCCESS,
        message=f"Scrolling {direction}",
        ui_action={
            "type": "ui.scroll",
            "payload": {
                "direction": direction,
                "targetVoiceId": target_voice_id,
            }
        }
    )


def handle_confirm_action(confirmed: bool, skip: bool = False) -> ToolResult:
    """Handle confirmation response."""
    if skip:
        return ToolResult(
            status=ToolResultStatus.SUCCESS,
            message="Skipping this step",
            data={"confirmation_type": "skip"}
        )
    elif confirmed:
        return ToolResult(
            status=ToolResultStatus.SUCCESS,
            message="Action confirmed",
            data={"confirmation_type": "yes"}
        )
    else:
        return ToolResult(
            status=ToolResultStatus.SUCCESS,
            message="Action cancelled",
            data={"confirmation_type": "no"}
        )


# ============================================================================
# COMPOSITE TOOL HANDLERS
# ============================================================================

def handle_execute_workflow(workflow_name: str) -> ToolResult:
    """Execute a predefined multi-step workflow.

    This handler:
    1. Looks up the workflow in the registry
    2. Returns a compound UI action that executes all steps in sequence
    """
    workflow = WORKFLOW_REGISTRY.get(workflow_name)

    if not workflow:
        available = ", ".join(WORKFLOW_REGISTRY.keys())
        return ToolResult(
            status=ToolResultStatus.FAILURE,
            message=f"Unknown workflow: {workflow_name}. Available: {available}"
        )

    # Build compound action with all steps
    ui_actions = []
    for step in workflow.steps:
        if step.action == "navigate":
            ui_actions.append({
                "type": "ui.navigate",
                "payload": {"path": step.target},
                "waitForLoad": step.wait_for_load
            })
        elif step.action == "switch_tab":
            ui_actions.append({
                "type": "ui.switchTab",
                "payload": {"voiceId": step.target, "tabName": step.target}
            })
        elif step.action == "click_button":
            ui_actions.append({
                "type": "ui.clickButton",
                "payload": {"voiceId": step.target}
            })

    # Return compound action
    return ToolResult(
        status=ToolResultStatus.SUCCESS,
        message=workflow.description,
        ui_action={
            "type": "ui.workflow",
            "payload": {
                "workflow": workflow_name,
                "steps": ui_actions,
                "description": workflow.description
            }
        }
    )


def handle_navigate_and_switch_tab(target_tab: str, current_route: str) -> ToolResult:
    """Navigate to a page and switch to a tab in one operation.

    Uses the page registry to determine if navigation is needed.
    """
    # Get the steps needed (may include navigation)
    steps = get_navigation_steps(current_route, target_tab)

    if not steps:
        return ToolResult(
            status=ToolResultStatus.FAILURE,
            message=f"Tab '{target_tab}' not found in application"
        )

    # Build compound action
    ui_actions = []
    descriptions = []

    for step in steps:
        if step.action == "navigate":
            page = get_page(step.target)
            page_name = page.name if page else step.target
            ui_actions.append({
                "type": "ui.navigate",
                "payload": {"path": step.target},
                "waitForLoad": step.wait_for_load
            })
            descriptions.append(f"Navigating to {page_name}")
        elif step.action == "switch_tab":
            ui_actions.append({
                "type": "ui.switchTab",
                "payload": {"voiceId": step.target, "tabName": step.target}
            })
            descriptions.append(f"Switching to {step.target}")

    return ToolResult(
        status=ToolResultStatus.SUCCESS,
        message=". ".join(descriptions),
        ui_action={
            "type": "ui.workflow",
            "payload": {
                "workflow": "navigate_and_switch_tab",
                "steps": ui_actions
            }
        }
    )


def handle_smart_switch_tab(tab_voice_id: str, current_route: Optional[str] = None) -> ToolResult:
    """Intelligently switch to a tab, navigating first if necessary.

    This tool knows the application topology and will:
    1. Check if the tab exists on the current page
    2. If not, find which page has the tab
    3. Navigate to that page first
    4. Then switch to the tab
    """
    # Find which page has this tab
    target_page = find_tab_page(tab_voice_id)

    if not target_page:
        return ToolResult(
            status=ToolResultStatus.FAILURE,
            message=f"Tab '{tab_voice_id}' not found in any page"
        )

    # Check if we need to navigate
    if current_route:
        current_base = "/" + current_route.strip("/").split("/")[0]
        needs_navigation = current_base != target_page
    else:
        needs_navigation = True  # Assume we might need to navigate

    if needs_navigation:
        # Use navigate_and_switch_tab
        return handle_navigate_and_switch_tab(tab_voice_id, current_route or "/")
    else:
        # Just switch tab
        return handle_switch_tab(tab_voice_id)


# ============================================================================
# TOOL DISPATCHER
# ============================================================================

def execute_voice_tool(tool_name: str, parameters: Dict[str, Any]) -> ToolResult:
    """
    Execute a voice agent tool.

    Args:
        tool_name: Name of the tool to execute
        parameters: Parameters for the tool

    Returns:
        ToolResult with status, message, and optional UI action
    """
    logger.info(f"Executing voice tool: {tool_name} with params: {parameters}")

    try:
        if tool_name == "navigate_to_page":
            return handle_navigate_to_page(parameters.get("page", ""))

        elif tool_name == "switch_tab":
            return handle_switch_tab(
                parameters.get("tab_voice_id", ""),
                parameters.get("tab_label")
            )

        elif tool_name == "click_button":
            return handle_click_button(
                parameters.get("button_voice_id", ""),
                parameters.get("button_label")
            )

        elif tool_name == "fill_input":
            return handle_fill_input(
                parameters.get("field_voice_id", ""),
                parameters.get("content", ""),
                parameters.get("append", False)
            )

        elif tool_name == "select_dropdown_option":
            return handle_select_dropdown_option(
                parameters.get("dropdown_voice_id", ""),
                parameters.get("selection_index"),
                parameters.get("selection_text")
            )

        elif tool_name == "expand_dropdown":
            return handle_expand_dropdown(
                parameters.get("dropdown_voice_id", "")
            )

        elif tool_name == "get_ui_state":
            return handle_get_ui_state()

        elif tool_name == "submit_form":
            return handle_submit_form(
                parameters.get("submit_button_voice_id")
            )

        elif tool_name == "scroll":
            return handle_scroll(
                parameters.get("direction", "down"),
                parameters.get("target_voice_id")
            )

        elif tool_name == "confirm_action":
            return handle_confirm_action(
                parameters.get("confirmed", False),
                parameters.get("skip", False)
            )

        # Composite tools
        elif tool_name == "execute_workflow":
            return handle_execute_workflow(
                parameters.get("workflow_name", "")
            )

        elif tool_name == "navigate_and_switch_tab":
            return handle_navigate_and_switch_tab(
                parameters.get("target_tab", ""),
                parameters.get("current_route", "/")
            )

        elif tool_name == "smart_switch_tab":
            return handle_smart_switch_tab(
                parameters.get("tab_voice_id", ""),
                parameters.get("current_route")
            )

        else:
            return ToolResult(
                status=ToolResultStatus.FAILURE,
                message=f"Unknown tool: {tool_name}"
            )

    except Exception as e:
        logger.exception(f"Error executing voice tool {tool_name}: {e}")
        return ToolResult(
            status=ToolResultStatus.FAILURE,
            message=f"Error executing {tool_name}: {str(e)}"
        )


# ============================================================================
# EXPORT TOOLS FOR ELEVENLABS REGISTRATION
# ============================================================================

def get_voice_tools_json() -> str:
    """Get voice tools as JSON for ElevenLabs Agent registration."""
    return json.dumps(VOICE_AGENT_TOOLS, indent=2)


def get_voice_tools() -> List[Dict[str, Any]]:
    """Get voice tools as list of dictionaries."""
    return VOICE_AGENT_TOOLS
