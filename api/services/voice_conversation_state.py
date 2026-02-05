"""Voice conversation state management with page structure registry.

This module enables the voice controller to:
1. Know the structure of each page (forms, fields, dropdowns, tabs)
2. Track conversation state (idle, awaiting input, awaiting confirmation)
3. Guide users through form filling conversationally
4. Remember context within a session
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Any, Dict, List, Optional, Union

import redis

from api.core.config import get_settings


class ConversationState(str, Enum):
    """States for the voice conversation flow."""
    IDLE = "idle"  # Ready for new command
    AWAITING_FIELD_INPUT = "awaiting_field_input"  # Waiting for user to provide field value
    AWAITING_DROPDOWN_SELECTION = "awaiting_dropdown_selection"  # Waiting for dropdown choice
    AWAITING_CONFIRMATION = "awaiting_confirmation"  # Waiting for yes/no on destructive action
    PROCESSING = "processing"  # Backend is processing
    ERROR_RETRY = "error_retry"  # Retrying after error


@dataclass
class FormField:
    """Definition of a form field."""
    name: str  # Human-readable name (e.g., "Course Title")
    voice_id: str  # data-voice-id attribute
    field_type: str  # "input", "textarea", "select", "checkbox"
    required: bool = True
    prompt: str = ""  # Question to ask user (e.g., "What would you like the course title to be?")
    validation_hint: str = ""  # Help text for validation errors


@dataclass
class DropdownOption:
    """A selectable option in a dropdown."""
    label: str
    value: str


@dataclass
class Dropdown:
    """Definition of a dropdown/select element."""
    name: str  # Human-readable name
    voice_id: str  # data-voice-id attribute
    prompt: str  # Question when presenting options
    dynamic: bool = True  # True if options come from API, False if static


@dataclass
class Tab:
    """Definition of a tab."""
    name: str  # Human-readable name
    voice_id: str  # data-voice-id attribute
    description: str = ""  # What this tab does


@dataclass
class ActionButton:
    """Definition of an action button."""
    name: str
    voice_id: str
    description: str
    destructive: bool = False  # Requires confirmation if True
    confirmation_prompt: str = ""  # Question to ask before executing


@dataclass
class PageStructure:
    """Complete structure of a page's interactive elements."""
    path: str  # URL path
    name: str  # Human-readable page name
    description: str  # What this page does
    tabs: List[Tab] = field(default_factory=list)
    forms: Dict[str, List[FormField]] = field(default_factory=dict)  # form_name -> fields
    dropdowns: List[Dropdown] = field(default_factory=list)
    buttons: List[ActionButton] = field(default_factory=list)


# === PAGE STRUCTURE REGISTRY ===

PAGE_STRUCTURES: Dict[str, PageStructure] = {
    # --- COURSES PAGE ---
    "/courses": PageStructure(
        path="/courses",
        name="Courses",
        description="Manage your courses - view enrolled courses, create new courses, or join existing ones",
        tabs=[
            Tab(name="My Courses", voice_id="tab-courses", description="View your enrolled or created courses"),
            Tab(name="Create Course", voice_id="tab-create", description="Create a new course as an instructor"),
            Tab(name="Enrollment", voice_id="tab-enrollment", description="Manage student enrollment in your courses"),
            Tab(name="Join Course", voice_id="tab-join", description="Join an existing course using an access code"),
            Tab(name="Instructor Courses", voice_id="tab-instructor", description="View courses you teach"),
        ],
        forms={
            "create_course": [
                FormField(
                    name="Course Title",
                    voice_id="course-title",
                    field_type="input",
                    required=True,
                    prompt="What would you like to name this course?",
                    validation_hint="Course title should be descriptive, like 'Introduction to Psychology'"
                ),
                FormField(
                    name="Syllabus",
                    voice_id="syllabus",
                    field_type="textarea",
                    required=False,
                    prompt="Would you like to add a syllabus? You can describe the course content and schedule.",
                    validation_hint="You can skip this for now and add it later"
                ),
                FormField(
                    name="Learning Objectives",
                    voice_id="learning-objectives",
                    field_type="textarea",
                    required=False,
                    prompt="What are the learning objectives for this course?",
                    validation_hint="List what students will learn, like 'Understand basic concepts of...'"
                ),
            ],
            "join_course": [
                FormField(
                    name="Access Code",
                    voice_id="input-access-code",
                    field_type="input",
                    required=True,
                    prompt="What is the course access code?",
                    validation_hint="The access code is usually provided by your instructor"
                ),
            ],
        },
        dropdowns=[
            Dropdown(
                name="Course Selection",
                voice_id="select-course",
                prompt="Which course would you like to select?",
                dynamic=True
            ),
        ],
        buttons=[
            ActionButton(
                name="Create Course",
                voice_id="create-course",
                description="Create the new course",
                destructive=False
            ),
            ActionButton(
                name="Join Course",
                voice_id="join-course",
                description="Join the course with the access code",
                destructive=False
            ),
            ActionButton(
                name="Enroll Student",
                voice_id="enroll-student",
                description="Enroll the selected student",
                destructive=False
            ),
        ],
    ),

    # --- SESSIONS PAGE ---
    "/sessions": PageStructure(
        path="/sessions",
        name="Sessions",
        description="View and manage class sessions",
        tabs=[
            Tab(name="Upcoming", voice_id="tab-upcoming", description="View upcoming sessions"),
            Tab(name="Past", voice_id="tab-past", description="View past sessions"),
            Tab(name="Create", voice_id="tab-create", description="Create a new session"),
        ],
        forms={
            "create_session": [
                FormField(
                    name="Session Title",
                    voice_id="input-session-title",
                    field_type="input",
                    required=True,
                    prompt="What would you like to call this session?",
                ),
                FormField(
                    name="Date",
                    voice_id="input-session-date",
                    field_type="input",
                    required=True,
                    prompt="When should this session be scheduled?",
                ),
                FormField(
                    name="Description",
                    voice_id="textarea-session-description",
                    field_type="textarea",
                    required=False,
                    prompt="Would you like to add a description for this session?",
                ),
            ],
        },
        dropdowns=[
            Dropdown(
                name="Course",
                voice_id="select-course",
                prompt="Which course is this session for?",
                dynamic=True
            ),
        ],
        buttons=[
            ActionButton(
                name="Create Session",
                voice_id="create-session",
                description="Create the new session",
                destructive=False
            ),
            ActionButton(
                name="Go Live",
                voice_id="go-live",
                description="Start the live session",
                destructive=False
            ),
            ActionButton(
                name="Complete Session",
                voice_id="complete-session",
                description="Mark the session as complete",
                destructive=True,
                confirmation_prompt="Are you sure you want to end this session?"
            ),
        ],
    ),

    # --- FORUM PAGE ---
    "/forum": PageStructure(
        path="/forum",
        name="Forum",
        description="View and participate in course discussions",
        tabs=[
            Tab(name="Cases", voice_id="tab-cases", description="View case studies and scenarios"),
            Tab(name="Discussion", voice_id="tab-discussion", description="General discussion posts"),
        ],
        forms={
            "create_post": [
                FormField(
                    name="Post Content",
                    voice_id="textarea-post-content",
                    field_type="textarea",
                    required=True,
                    prompt="What would you like to post?",
                ),
            ],
        },
        dropdowns=[
            Dropdown(
                name="Course",
                voice_id="select-course",
                prompt="Which course's forum would you like to view?",
                dynamic=True
            ),
            Dropdown(
                name="Session",
                voice_id="select-session",
                prompt="Which session would you like to filter by?",
                dynamic=True
            ),
        ],
        buttons=[
            ActionButton(
                name="Submit Post",
                voice_id="submit-post",
                description="Post your message to the forum",
                destructive=False
            ),
        ],
    ),

    # --- CONSOLE PAGE ---
    "/console": PageStructure(
        path="/console",
        name="Console",
        description="Instructor control panel for managing live sessions",
        tabs=[
            Tab(name="Copilot", voice_id="tab-copilot", description="AI teaching assistant for live sessions"),
            Tab(name="Polls", voice_id="tab-polls", description="Create and manage live polls"),
            Tab(name="Cases", voice_id="tab-cases", description="Present case studies to students"),
            Tab(name="Requests", voice_id="tab-requests", description="View student questions and requests"),
            Tab(name="Roster", voice_id="tab-roster", description="View class roster and attendance"),
        ],
        forms={
            "create_poll": [
                FormField(
                    name="Question",
                    voice_id="poll-question",
                    field_type="input",
                    required=True,
                    prompt="What question would you like to ask in the poll?",
                ),
                FormField(
                    name="Option 1",
                    voice_id="poll-option-1",
                    field_type="input",
                    required=True,
                    prompt="What is the first answer option?",
                ),
                FormField(
                    name="Option 2",
                    voice_id="poll-option-2",
                    field_type="input",
                    required=True,
                    prompt="What is the second answer option?",
                ),
                FormField(
                    name="Option 3",
                    voice_id="poll-option-3",
                    field_type="input",
                    required=False,
                    prompt="Would you like to add a third option?",
                ),
                FormField(
                    name="Option 4",
                    voice_id="poll-option-4",
                    field_type="input",
                    required=False,
                    prompt="Would you like to add a fourth option?",
                ),
            ],
            "post_case": [
                FormField(
                    name="Case Prompt",
                    voice_id="case-prompt",
                    field_type="textarea",
                    required=True,
                    prompt="What case scenario would you like to present to students?",
                ),
            ],
        },
        dropdowns=[
            Dropdown(
                name="Course",
                voice_id="select-course",
                prompt="Which course would you like to manage?",
                dynamic=True
            ),
            Dropdown(
                name="Session",
                voice_id="select-session",
                prompt="Which session would you like to control?",
                dynamic=True
            ),
        ],
        buttons=[
            ActionButton(
                name="Start Copilot",
                voice_id="start-copilot",
                description="Start the AI teaching assistant",
                destructive=False
            ),
            ActionButton(
                name="Stop Copilot",
                voice_id="stop-copilot",
                description="Stop the AI teaching assistant",
                destructive=True,
                confirmation_prompt="Are you sure you want to stop the copilot? This will end the AI assistance for this session."
            ),
            ActionButton(
                name="Create Poll",
                voice_id="create-poll",
                description="Launch the poll for students",
                destructive=False
            ),
            ActionButton(
                name="End Poll",
                voice_id="end-poll",
                description="Close the current poll",
                destructive=True,
                confirmation_prompt="Are you sure you want to end this poll? Students will no longer be able to respond."
            ),
            ActionButton(
                name="Post Case",
                voice_id="post-case",
                description="Post the case study for students",
                destructive=False
            ),
        ],
    ),

    # --- REPORTS PAGE ---
    "/reports": PageStructure(
        path="/reports",
        name="Reports",
        description="View analytics and reports for your courses",
        tabs=[
            Tab(name="Overview", voice_id="tab-overview", description="Summary of course activity"),
            Tab(name="Engagement", voice_id="tab-engagement", description="Student engagement metrics"),
            Tab(name="Performance", voice_id="tab-performance", description="Student performance data"),
        ],
        forms={},
        dropdowns=[
            Dropdown(
                name="Course",
                voice_id="select-course",
                prompt="Which course would you like to see reports for?",
                dynamic=True
            ),
            Dropdown(
                name="Date Range",
                voice_id="select-date-range",
                prompt="What time period would you like to view?",
                dynamic=False
            ),
        ],
        buttons=[
            ActionButton(
                name="Export Report",
                voice_id="btn-export-report",
                description="Download the report as a file",
                destructive=False
            ),
        ],
    ),

    # --- DASHBOARD PAGE ---
    "/dashboard": PageStructure(
        path="/dashboard",
        name="Dashboard",
        description="Your main dashboard with overview of courses and activities",
        tabs=[],
        forms={},
        dropdowns=[],
        buttons=[],
    ),
}


@dataclass
class ConversationContext:
    """Current conversation context and state."""
    state: ConversationState = ConversationState.IDLE
    current_page: str = "/dashboard"

    # Form filling state
    active_form: Optional[str] = None  # Name of form being filled
    current_field_index: int = 0  # Which field we're asking about
    collected_values: Dict[str, str] = field(default_factory=dict)  # field_voice_id -> value

    # Dropdown state
    active_dropdown: Optional[str] = None  # voice_id of dropdown being interacted with
    dropdown_options: List[DropdownOption] = field(default_factory=list)  # Loaded options

    # Confirmation state
    pending_action: Optional[str] = None  # Action waiting for confirmation
    pending_action_data: Dict[str, Any] = field(default_factory=dict)

    # Retry state
    retry_count: int = 0
    last_error: Optional[str] = None

    # Memory
    active_course_id: Optional[int] = None
    active_course_name: Optional[str] = None
    active_session_id: Optional[int] = None
    active_session_name: Optional[str] = None

    # Timestamps
    last_interaction: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        data = asdict(self)
        data["state"] = self.state.value
        data["dropdown_options"] = [asdict(opt) for opt in self.dropdown_options]
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ConversationContext":
        """Create from dictionary."""
        if "state" in data:
            data["state"] = ConversationState(data["state"])
        if "dropdown_options" in data:
            data["dropdown_options"] = [
                DropdownOption(**opt) for opt in data["dropdown_options"]
            ]
        return cls(**data)


class VoiceConversationManager:
    """Manages voice conversation state and page structure awareness."""

    MAX_RETRIES = 3

    def __init__(self, redis_client: Optional[redis.Redis] = None, ttl_seconds: int = 3600):
        settings = get_settings()
        self._client = redis_client or redis.Redis.from_url(
            settings.redis_url, decode_responses=True
        )
        self._ttl_seconds = ttl_seconds

    def _key(self, user_id: Optional[int]) -> str:
        key_suffix = str(user_id) if user_id is not None else "anon"
        return f"voice:conversation:{key_suffix}"

    # === Context Management ===

    def get_context(self, user_id: Optional[int]) -> ConversationContext:
        """Get current conversation context for user."""
        data = self._client.get(self._key(user_id))
        if not data:
            return ConversationContext()
        try:
            return ConversationContext.from_dict(json.loads(data))
        except (json.JSONDecodeError, TypeError):
            return ConversationContext()

    def save_context(self, user_id: Optional[int], context: ConversationContext) -> None:
        """Save conversation context."""
        context.last_interaction = time.time()
        self._client.set(
            self._key(user_id),
            json.dumps(context.to_dict()),
            ex=self._ttl_seconds
        )

    def clear_context(self, user_id: Optional[int]) -> None:
        """Clear conversation context (e.g., on logout)."""
        self._client.delete(self._key(user_id))

    # === Page Structure ===

    def get_page_structure(self, path: str) -> Optional[PageStructure]:
        """Get the structure for a page."""
        # Handle paths with dynamic segments (e.g., /courses/123)
        base_path = "/" + path.strip("/").split("/")[0] if path else "/dashboard"
        return PAGE_STRUCTURES.get(base_path)

    def get_page_description(self, path: str) -> str:
        """Get human-readable description of current page."""
        structure = self.get_page_structure(path)
        if not structure:
            return f"You are on {path}"

        parts = [f"You are on the {structure.name} page. {structure.description}"]

        if structure.tabs:
            tab_names = [t.name for t in structure.tabs]
            parts.append(f"Available tabs: {', '.join(tab_names)}")

        if structure.dropdowns:
            dropdown_names = [d.name for d in structure.dropdowns]
            parts.append(f"You can select: {', '.join(dropdown_names)}")

        return " ".join(parts)

    # === Form Filling Flow ===

    def start_form_filling(
        self,
        user_id: Optional[int],
        form_name: str,
        page_path: str
    ) -> Optional[str]:
        """Start filling a form. Returns the first question or None if form not found."""
        structure = self.get_page_structure(page_path)
        if not structure or form_name not in structure.forms:
            return None

        fields = structure.forms[form_name]
        if not fields:
            return None

        context = self.get_context(user_id)
        context.state = ConversationState.AWAITING_FIELD_INPUT
        context.active_form = form_name
        context.current_field_index = 0
        context.collected_values = {}
        context.current_page = page_path
        self.save_context(user_id, context)

        first_field = fields[0]
        return first_field.prompt

    def get_current_field(self, user_id: Optional[int]) -> Optional[FormField]:
        """Get the current field being asked about."""
        context = self.get_context(user_id)
        if context.state != ConversationState.AWAITING_FIELD_INPUT:
            return None
        if not context.active_form:
            return None

        structure = self.get_page_structure(context.current_page)
        if not structure or context.active_form not in structure.forms:
            return None

        fields = structure.forms[context.active_form]
        if context.current_field_index >= len(fields):
            return None

        return fields[context.current_field_index]

    def record_field_value(
        self,
        user_id: Optional[int],
        value: str
    ) -> Dict[str, Any]:
        """Record user's answer for current field.

        Returns:
            {
                "done": bool,  # True if form complete
                "next_prompt": str | None,  # Next question or None
                "field_to_fill": FormField | None,  # Field to fill with value
                "all_values": Dict[str, str]  # All collected values
            }
        """
        context = self.get_context(user_id)
        current_field = self.get_current_field(user_id)

        if not current_field:
            return {"done": True, "next_prompt": None, "field_to_fill": None, "all_values": {}}

        # Record the value
        context.collected_values[current_field.voice_id] = value

        # Move to next field
        context.current_field_index += 1

        structure = self.get_page_structure(context.current_page)
        if not structure or context.active_form not in structure.forms:
            context.state = ConversationState.IDLE
            self.save_context(user_id, context)
            return {
                "done": True,
                "next_prompt": None,
                "field_to_fill": current_field,
                "all_values": context.collected_values
            }

        fields = structure.forms[context.active_form]

        # Check if there are more fields
        if context.current_field_index >= len(fields):
            # Form complete
            context.state = ConversationState.IDLE
            context.active_form = None
            self.save_context(user_id, context)
            return {
                "done": True,
                "next_prompt": "I've filled in all the fields. Would you like me to submit the form?",
                "field_to_fill": current_field,
                "all_values": context.collected_values
            }

        # Get next field
        next_field = fields[context.current_field_index]
        self.save_context(user_id, context)

        return {
            "done": False,
            "next_prompt": next_field.prompt,
            "field_to_fill": current_field,
            "all_values": context.collected_values
        }

    def skip_current_field(self, user_id: Optional[int]) -> Dict[str, Any]:
        """Skip the current optional field."""
        current_field = self.get_current_field(user_id)
        if current_field and current_field.required:
            return {
                "skipped": False,
                "message": f"Sorry, {current_field.name} is required. {current_field.prompt}"
            }

        # Move to next field without recording value
        context = self.get_context(user_id)
        context.current_field_index += 1
        self.save_context(user_id, context)

        next_field = self.get_current_field(user_id)
        if next_field:
            return {"skipped": True, "message": next_field.prompt}
        else:
            context.state = ConversationState.IDLE
            self.save_context(user_id, context)
            return {
                "skipped": True,
                "message": "I've filled in all the required fields. Would you like me to submit the form?"
            }

    # === Dropdown Flow ===

    def start_dropdown_selection(
        self,
        user_id: Optional[int],
        dropdown_voice_id: str,
        options: List[DropdownOption],
        page_path: str
    ) -> str:
        """Start dropdown selection flow. Returns the prompt with options."""
        context = self.get_context(user_id)

        # Find dropdown definition
        structure = self.get_page_structure(page_path)
        dropdown = None
        if structure:
            for d in structure.dropdowns:
                if d.voice_id == dropdown_voice_id:
                    dropdown = d
                    break

        context.state = ConversationState.AWAITING_DROPDOWN_SELECTION
        context.active_dropdown = dropdown_voice_id
        context.dropdown_options = options
        context.current_page = page_path
        self.save_context(user_id, context)

        # Build the prompt
        if not options:
            return "There are no options available in this dropdown."

        prompt_parts = [dropdown.prompt if dropdown else "Please select an option:"]
        prompt_parts.append("Your options are:")
        for i, opt in enumerate(options, 1):
            prompt_parts.append(f"{i}. {opt.label}")
        prompt_parts.append("Which would you like to select?")

        return " ".join(prompt_parts)

    def select_dropdown_option(
        self,
        user_id: Optional[int],
        selection: Union[int, str]
    ) -> Dict[str, Any]:
        """Process user's dropdown selection.

        Args:
            selection: Either index (1-based) or partial label match

        Returns:
            {
                "success": bool,
                "selected": DropdownOption | None,
                "message": str,
                "voice_id": str  # dropdown voice_id for UI action
            }
        """
        context = self.get_context(user_id)

        if context.state != ConversationState.AWAITING_DROPDOWN_SELECTION:
            return {
                "success": False,
                "selected": None,
                "message": "I'm not currently waiting for a dropdown selection.",
                "voice_id": None
            }

        options = context.dropdown_options
        selected = None

        # Try to match by index
        if isinstance(selection, int) or (isinstance(selection, str) and selection.isdigit()):
            idx = int(selection) - 1
            if 0 <= idx < len(options):
                selected = options[idx]

        # Try to match by label
        if not selected and isinstance(selection, str):
            selection_lower = selection.lower()
            for opt in options:
                if selection_lower in opt.label.lower():
                    selected = opt
                    break

        if not selected:
            # Offer options again
            option_list = ", ".join([f"{i}. {opt.label}" for i, opt in enumerate(options, 1)])
            return {
                "success": False,
                "selected": None,
                "message": f"I couldn't find that option. Please choose from: {option_list}",
                "voice_id": context.active_dropdown
            }

        # Success - reset state
        voice_id = context.active_dropdown
        context.state = ConversationState.IDLE
        context.active_dropdown = None
        context.dropdown_options = []
        self.save_context(user_id, context)

        return {
            "success": True,
            "selected": selected,
            "message": f"Selected {selected.label}.",
            "voice_id": voice_id
        }

    # === Confirmation Flow ===

    def request_confirmation(
        self,
        user_id: Optional[int],
        action: str,
        action_data: Dict[str, Any],
        page_path: str
    ) -> str:
        """Request confirmation for a destructive action."""
        context = self.get_context(user_id)

        # Find the button definition for custom confirmation prompt
        structure = self.get_page_structure(page_path)
        confirmation_prompt = f"Are you sure you want to {action}?"

        if structure:
            for btn in structure.buttons:
                if btn.voice_id == action_data.get("voice_id") and btn.confirmation_prompt:
                    confirmation_prompt = btn.confirmation_prompt
                    break

        context.state = ConversationState.AWAITING_CONFIRMATION
        context.pending_action = action
        context.pending_action_data = action_data
        context.current_page = page_path
        self.save_context(user_id, context)

        return confirmation_prompt + " Say yes to confirm or no to cancel."

    def process_confirmation(
        self,
        user_id: Optional[int],
        confirmed: bool
    ) -> Dict[str, Any]:
        """Process user's confirmation response.

        Returns:
            {
                "confirmed": bool,
                "action": str | None,
                "action_data": Dict | None,
                "message": str
            }
        """
        context = self.get_context(user_id)

        if context.state != ConversationState.AWAITING_CONFIRMATION:
            return {
                "confirmed": False,
                "action": None,
                "action_data": None,
                "message": "I'm not waiting for a confirmation."
            }

        action = context.pending_action
        action_data = context.pending_action_data

        # Reset state
        context.state = ConversationState.IDLE
        context.pending_action = None
        context.pending_action_data = {}
        self.save_context(user_id, context)

        if confirmed:
            return {
                "confirmed": True,
                "action": action,
                "action_data": action_data,
                "message": f"Confirmed. Executing {action}."
            }
        else:
            return {
                "confirmed": False,
                "action": None,
                "action_data": None,
                "message": "Cancelled. Is there anything else I can help you with?"
            }

    # === Retry Logic ===

    def record_error(self, user_id: Optional[int], error: str) -> Dict[str, Any]:
        """Record an error and determine if we should retry.

        Returns:
            {
                "should_retry": bool,
                "retry_count": int,
                "message": str
            }
        """
        context = self.get_context(user_id)
        context.retry_count += 1
        context.last_error = error

        if context.retry_count < self.MAX_RETRIES:
            context.state = ConversationState.ERROR_RETRY
            self.save_context(user_id, context)
            return {
                "should_retry": True,
                "retry_count": context.retry_count,
                "message": f"That didn't work. Let me try again. Attempt {context.retry_count + 1} of {self.MAX_RETRIES}."
            }
        else:
            # Max retries reached
            context.state = ConversationState.IDLE
            context.retry_count = 0
            self.save_context(user_id, context)
            return {
                "should_retry": False,
                "retry_count": self.MAX_RETRIES,
                "message": f"I'm sorry, I wasn't able to complete that action after {self.MAX_RETRIES} attempts. The error was: {error}. Would you like to try something else?"
            }

    def reset_retry_count(self, user_id: Optional[int]) -> None:
        """Reset retry count after successful action."""
        context = self.get_context(user_id)
        context.retry_count = 0
        context.last_error = None
        self.save_context(user_id, context)

    # === Memory Management ===

    def update_active_course(
        self,
        user_id: Optional[int],
        course_id: Optional[int],
        course_name: Optional[str] = None
    ) -> None:
        """Update the active course in memory."""
        context = self.get_context(user_id)
        context.active_course_id = course_id
        context.active_course_name = course_name
        # Clear session when course changes
        if course_id != context.active_course_id:
            context.active_session_id = None
            context.active_session_name = None
        self.save_context(user_id, context)

    def update_active_session(
        self,
        user_id: Optional[int],
        session_id: Optional[int],
        session_name: Optional[str] = None
    ) -> None:
        """Update the active session in memory."""
        context = self.get_context(user_id)
        context.active_session_id = session_id
        context.active_session_name = session_name
        self.save_context(user_id, context)

    def update_current_page(self, user_id: Optional[int], page_path: str) -> None:
        """Update the current page."""
        context = self.get_context(user_id)
        context.current_page = page_path
        self.save_context(user_id, context)

    def get_context_summary(self, user_id: Optional[int]) -> str:
        """Get human-readable context summary for the agent."""
        context = self.get_context(user_id)
        parts = []

        # Page
        structure = self.get_page_structure(context.current_page)
        if structure:
            parts.append(f"Page: {structure.name}")
        else:
            parts.append(f"Page: {context.current_page}")

        # Active course
        if context.active_course_name:
            parts.append(f"Course: {context.active_course_name}")
        elif context.active_course_id:
            parts.append(f"Course ID: {context.active_course_id}")

        # Active session
        if context.active_session_name:
            parts.append(f"Session: {context.active_session_name}")
        elif context.active_session_id:
            parts.append(f"Session ID: {context.active_session_id}")

        # State
        if context.state != ConversationState.IDLE:
            state_descriptions = {
                ConversationState.AWAITING_FIELD_INPUT: "Filling form",
                ConversationState.AWAITING_DROPDOWN_SELECTION: "Selecting from dropdown",
                ConversationState.AWAITING_CONFIRMATION: "Waiting for confirmation",
                ConversationState.PROCESSING: "Processing",
                ConversationState.ERROR_RETRY: "Retrying after error",
            }
            parts.append(f"State: {state_descriptions.get(context.state, context.state.value)}")

        return " | ".join(parts) if parts else "No active context"
