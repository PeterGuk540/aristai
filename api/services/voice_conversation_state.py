"""Voice conversation state management with page structure registry.

This module enables the voice controller to:
1. Know the structure of each page (forms, fields, dropdowns, tabs)
2. Track conversation state (idle, awaiting input, awaiting confirmation)
3. Guide users through form filling conversationally
4. Remember context within a session
"""

from __future__ import annotations

import json
import re
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
    # Forum posting states
    AWAITING_POST_OFFER_RESPONSE = "awaiting_post_offer_response"  # Asked "Would you like to post?"
    AWAITING_POST_DICTATION = "awaiting_post_dictation"  # User is dictating post content
    AWAITING_POST_SUBMIT_CONFIRMATION = "awaiting_post_submit_confirmation"  # Asked "Should I post it?"
    # Poll creation states
    AWAITING_POLL_OFFER_RESPONSE = "awaiting_poll_offer_response"  # Asked "Would you like to create a poll?"
    AWAITING_POLL_QUESTION = "awaiting_poll_question"  # Waiting for poll question
    AWAITING_POLL_OPTION = "awaiting_poll_option"  # Waiting for a poll option
    AWAITING_POLL_MORE_OPTIONS = "awaiting_poll_more_options"  # Asked "Do you need more options?"
    AWAITING_POLL_CONFIRM = "awaiting_poll_confirm"  # Asked "Should I create the poll?"
    # Case posting states
    AWAITING_CASE_OFFER_RESPONSE = "awaiting_case_offer_response"  # Asked "Would you like to post a case?"
    AWAITING_CASE_PROMPT = "awaiting_case_prompt"  # Waiting for case prompt dictation
    AWAITING_CASE_CONFIRM = "awaiting_case_confirm"  # Asked "Should I post the case?"
    # AI content generation states
    AWAITING_SYLLABUS_GENERATION_CONFIRM = "awaiting_syllabus_generation_confirm"  # Asked "Generate syllabus?"
    AWAITING_SYLLABUS_REVIEW = "awaiting_syllabus_review"  # Reviewing generated syllabus
    AWAITING_OBJECTIVES_GENERATION_CONFIRM = "awaiting_objectives_generation_confirm"  # Asked "Generate objectives?"
    AWAITING_OBJECTIVES_REVIEW = "awaiting_objectives_review"  # Reviewing generated objectives
    AWAITING_SESSION_PLAN_GENERATION_CONFIRM = "awaiting_session_plan_generation_confirm"  # Asked "Generate session plan?"
    AWAITING_SESSION_PLAN_REVIEW = "awaiting_session_plan_review"  # Reviewing generated session plan


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
            Tab(name="AI Insights", voice_id="tab-ai-insights", description="View AI-powered participation insights and learning objective coverage"),
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
                    prompt="Would you like me to generate a syllabus for this course? Say 'generate' for AI assistance, or dictate the syllabus yourself. You can also say 'skip'.",
                    validation_hint="You can skip this for now and add it later"
                ),
                FormField(
                    name="Learning Objectives",
                    voice_id="learning-objectives",
                    field_type="textarea",
                    required=False,
                    prompt="Would you like me to generate learning objectives? Say 'generate' for AI assistance, or dictate them yourself. You can also say 'skip'.",
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
            Tab(name="Materials", voice_id="tab-materials", description="View and manage course materials and files"),
            Tab(name="Insights", voice_id="tab-insights", description="View session analytics, engagement data, and AI summaries"),
            Tab(name="Manage", voice_id="tab-manage", description="Manage session status - go live, end, or schedule sessions"),
            Tab(name="AI Features", voice_id="tab-ai-features", description="Access enhanced AI features like pre-class prep and discussion summaries"),
        ],
        forms={
            "create_session": [
                FormField(
                    name="Session Title",
                    voice_id="input-session-title",
                    field_type="input",
                    required=True,
                    prompt="What would you like to call this session? This will also be the topic for AI-generated content.",
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
                    prompt="Would you like me to generate a session plan with discussion prompts and a case study? Say 'generate' for AI assistance, or dictate a description yourself.",
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
            ActionButton(
                name="Edit Session",
                voice_id="edit-session",
                description="Edit the selected session's title and details",
                destructive=False
            ),
            ActionButton(
                name="Delete Session",
                voice_id="delete-session",
                description="Delete the selected session",
                destructive=True,
                confirmation_prompt="Are you sure you want to delete this session? This action cannot be undone."
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
            Tab(name="Tools", voice_id="tab-tools", description="Instructor tools including timers and breakout groups"),
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
            "create_breakout_groups": [
                FormField(
                    name="Number of Groups",
                    voice_id="num-breakout-groups",
                    field_type="input",
                    required=True,
                    prompt="How many breakout groups would you like to create?",
                    validation_hint="Choose between 2 and 10 groups."
                ),
            ],
            "start_timer": [
                FormField(
                    name="Duration in Minutes",
                    voice_id="timer-duration-minutes",
                    field_type="input",
                    required=True,
                    prompt="How many minutes should the timer run?",
                    validation_hint="Use a value from 1 to 60 minutes."
                ),
                FormField(
                    name="Timer Label",
                    voice_id="timer-label",
                    field_type="input",
                    required=False,
                    prompt="What label should I use for this timer? You can say skip to keep the default.",
                    validation_hint="For example: Group discussion or Q and A."
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
            ActionButton(
                name="Create Breakout Groups",
                voice_id="create-breakout-groups",
                description="Create breakout groups for the current session",
                destructive=False
            ),
            ActionButton(
                name="Start Session Timer",
                voice_id="start-session-timer",
                description="Start a countdown timer for the current session",
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
            Tab(name="Summary", voice_id="tab-summary", description="Summary of course activity and reports"),
            Tab(name="Participation", voice_id="tab-participation", description="Student participation metrics"),
            Tab(name="Scoring", voice_id="tab-scoring", description="Student scores and grades"),
            Tab(name="Analytics", voice_id="tab-analytics", description="Advanced data analytics"),
            Tab(name="My Performance", voice_id="tab-my-performance", description="View your personal performance and progress"),
            Tab(name="Best Practice", voice_id="tab-best-practice", description="View best practice answers and examples"),
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

# === FORM TO SUBMIT BUTTON MAPPING ===
# Maps form names to their submit button voice_ids
FORM_SUBMIT_BUTTONS: Dict[str, str] = {
    "create_course": "create-course-with-plans",  # Create course AND generate plans
    "create_session": "create-session",
    "create_poll": "create-poll",
    "create_case": "post-case",
    "create_post": "submit-post",
    "create_breakout_groups": "create-breakout-groups",
    "start_timer": "start-session-timer",
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

    # Forum posting state
    post_dictation_content: str = ""  # Accumulated content during dictation
    post_offer_declined: bool = False  # Track if user declined the post offer

    # Poll creation state
    poll_question: str = ""  # The poll question
    poll_options: List[str] = field(default_factory=list)  # Poll options
    poll_current_option_index: int = 1  # Current option being filled (1-based)
    poll_offer_declined: bool = False  # Track if user declined the poll offer

    # Case posting state
    case_prompt_content: str = ""  # The case study prompt content
    case_offer_declined: bool = False  # Track if user declined the case offer

    # AI content generation state
    generated_syllabus: str = ""  # AI-generated syllabus pending review
    generated_objectives: List[str] = field(default_factory=list)  # AI-generated objectives pending review
    generated_session_plan: Dict[str, Any] = field(default_factory=dict)  # AI-generated session plan pending review
    course_name_for_generation: str = ""  # Course name used for content generation

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

    def cancel_form(self, user_id: Optional[int]) -> None:
        """Cancel form-filling state and reset to IDLE."""
        context = self.get_context(user_id)
        context.state = ConversationState.IDLE
        context.form_context = None
        context.pending_action = None
        context.pending_action_data = None
        context.retry_count = 0
        self.save_context(user_id, context)

    # === Phase 2.5: Pending Action for Cross-Page Navigation ===

    def set_pending_action(
        self,
        user_id: Optional[int],
        action: str,
        parameters: Optional[Dict[str, Any]] = None,
        transcript: Optional[str] = None,
    ) -> None:
        """
        Store a pending action to execute after navigation completes.

        This is used when a user issues a command from a different page
        (e.g., "create course" from /forum). The system navigates first,
        then executes the action on the target page.
        """
        context = self.get_context(user_id)
        context.pending_action = action
        context.pending_action_data = {
            "parameters": parameters or {},
            "transcript": transcript or "",
            "timestamp": time.time(),
        }
        self.save_context(user_id, context)

    def get_pending_action(self, user_id: Optional[int]) -> Optional[Dict[str, Any]]:
        """
        Get and clear any pending action for the user.

        Returns:
            Dict with 'action', 'parameters', 'transcript' keys, or None.
        """
        context = self.get_context(user_id)
        if not context.pending_action:
            return None

        result = {
            "action": context.pending_action,
            "parameters": context.pending_action_data.get("parameters", {}),
            "transcript": context.pending_action_data.get("transcript", ""),
        }

        # Clear the pending action
        context.pending_action = None
        context.pending_action_data = {}
        self.save_context(user_id, context)

        return result

    def has_pending_action(self, user_id: Optional[int]) -> bool:
        """Check if user has a pending action without clearing it."""
        context = self.get_context(user_id)
        return context.pending_action is not None

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

    @staticmethod
    def _sanitize_transcription(value: str) -> str:
        """Remove trailing punctuation from transcribed text.

        ElevenLabs often adds periods at the end of transcriptions,
        which can cause issues with course titles and other form fields.
        """
        if not value:
            return value
        # Strip whitespace first
        value = value.strip()
        # Remove trailing punctuation (period, comma, exclamation, question mark)
        while value and value[-1] in '.!?,;:':
            value = value[:-1].strip()
        return value

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

        # Sanitize the value - remove trailing punctuation from transcription
        clean_value = self._sanitize_transcription(value)

        # Record the value
        context.collected_values[current_field.voice_id] = clean_value

        # Move to next field
        context.current_field_index += 1

        structure = self.get_page_structure(context.current_page)
        if not structure or context.active_form not in structure.forms:
            form_name = context.active_form
            submit_button = FORM_SUBMIT_BUTTONS.get(form_name) if form_name else None
            context.state = ConversationState.IDLE
            context.active_form = None
            self.save_context(user_id, context)
            return {
                "done": True,
                "next_prompt": None,
                "field_to_fill": current_field,
                "all_values": context.collected_values,
                "submit_button": submit_button,
                "form_name": form_name,
            }

        fields = structure.forms[context.active_form]
        form_name = context.active_form  # Save before potential reset

        # Check if there are more fields
        if context.current_field_index >= len(fields):
            # Form complete - get the submit button for this form
            submit_button = FORM_SUBMIT_BUTTONS.get(form_name)

            # Set up for confirmation (don't reset to IDLE yet)
            context.state = ConversationState.AWAITING_CONFIRMATION
            context.pending_action = "ui_click_button"
            context.pending_action_data = {
                "voice_id": submit_button,
                "form_name": form_name,
            }
            self.save_context(user_id, context)

            # Debug logging
            print(f"📝 FORM COMPLETE: Setting up confirmation for button '{submit_button}', form '{form_name}'")
            print(f"📝 State: {context.state}, pending_action: {context.pending_action}")

            return {
                "done": True,
                "next_prompt": "I've filled in all the fields. Would you like me to submit the form?",
                "field_to_fill": current_field,
                "all_values": context.collected_values,
                "submit_button": submit_button,
                "form_name": form_name,
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
        selection_str = str(selection).lower().strip()

        # Remove common filler words from selection
        filler_words = ['the', 'a', 'an', 'please', 'select', 'choose', 'pick', 'use', 'course', 'session', 'option', 'number', 'one', 'called']
        selection_clean = selection_str
        for word in filler_words:
            selection_clean = re.sub(rf'\b{word}\b', '', selection_clean)
        selection_clean = ' '.join(selection_clean.split())  # Clean up whitespace

        # Ordinal mapping (first, second, etc.)
        ordinals = {
            'first': 1, 'second': 2, 'third': 3, 'fourth': 4, 'fifth': 5,
            'sixth': 6, 'seventh': 7, 'eighth': 8, 'ninth': 9, 'tenth': 10,
            'last': len(options),
            '1st': 1, '2nd': 2, '3rd': 3, '4th': 4, '5th': 5,
            '6th': 6, '7th': 7, '8th': 8, '9th': 9, '10th': 10,
        }

        # Word-to-number mapping (one, two, three, etc.)
        number_words = {
            'one': 1, 'two': 2, 'three': 3, 'four': 4, 'five': 5,
            'six': 6, 'seven': 7, 'eight': 8, 'nine': 9, 'ten': 10,
            'eleven': 11, 'twelve': 12, 'thirteen': 13, 'fourteen': 14, 'fifteen': 15,
        }

        # Try to match by ordinal (first, second, etc.)
        for ordinal, idx in ordinals.items():
            if ordinal in selection_str:
                if 0 < idx <= len(options):
                    selected = options[idx - 1]
                    break

        # Try to match by number word (one, two, three, six, etc.)
        if not selected:
            for word, num in number_words.items():
                if word in selection_str:
                    if 0 < num <= len(options):
                        selected = options[num - 1]
                        break

        # Try to match by numeric index (1, 2, 3...)
        if not selected:
            numbers = re.findall(r'\b(\d+)\b', selection_str)
            if numbers:
                idx = int(numbers[0]) - 1
                if 0 <= idx < len(options):
                    selected = options[idx]

        # Try to match by exact label
        if not selected:
            for opt in options:
                if selection_clean == opt.label.lower():
                    selected = opt
                    break

        # Try to match by partial label (selection in label OR label in selection)
        if not selected:
            for opt in options:
                opt_lower = opt.label.lower()
                if selection_clean in opt_lower or opt_lower in selection_clean:
                    selected = opt
                    break

        # Try to match by ID in value
        if not selected:
            for opt in options:
                if selection_clean == opt.value or selection_clean in opt.value:
                    selected = opt
                    break

        # Try to match by any significant word overlap
        if not selected:
            selection_words = set(selection_clean.split())
            best_match = None
            best_score = 0
            for opt in options:
                opt_words = set(opt.label.lower().split())
                overlap = len(selection_words & opt_words)
                if overlap > best_score:
                    best_score = overlap
                    best_match = opt
            if best_score > 0:
                selected = best_match

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

    def cancel_dropdown_selection(self, user_id: Optional[int]) -> Dict[str, Any]:
        """Cancel an active dropdown selection and reset state to IDLE."""
        context = self.get_context(user_id)

        if context.state != ConversationState.AWAITING_DROPDOWN_SELECTION:
            return {
                "cancelled": False,
                "message": "No active selection to cancel.",
                "voice_id": None
            }

        voice_id = context.active_dropdown
        context.state = ConversationState.IDLE
        context.active_dropdown = None
        context.dropdown_options = []
        self.save_context(user_id, context)

        return {
            "cancelled": True,
            "message": "Selection cancelled. What would you like to do next?",
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
                ConversationState.AWAITING_POST_OFFER_RESPONSE: "Waiting for post offer response",
                ConversationState.AWAITING_POST_DICTATION: "Dictating forum post",
                ConversationState.AWAITING_POST_SUBMIT_CONFIRMATION: "Confirming post submission",
                ConversationState.AWAITING_POLL_OFFER_RESPONSE: "Waiting for poll offer response",
                ConversationState.AWAITING_POLL_QUESTION: "Waiting for poll question",
                ConversationState.AWAITING_POLL_OPTION: "Waiting for poll option",
                ConversationState.AWAITING_POLL_MORE_OPTIONS: "Asked about more poll options",
                ConversationState.AWAITING_POLL_CONFIRM: "Confirming poll creation",
            }
            parts.append(f"State: {state_descriptions.get(context.state, context.state.value)}")

        return " | ".join(parts) if parts else "No active context"

    # === Forum Posting Flow ===

    def offer_forum_post(self, user_id: Optional[int]) -> Optional[str]:
        """Offer to help user post to discussion. Returns prompt or None if already declined."""
        context = self.get_context(user_id)

        # Don't offer if user already declined this session
        if context.post_offer_declined:
            return None

        context.state = ConversationState.AWAITING_POST_OFFER_RESPONSE
        self.save_context(user_id, context)

        return "Would you like to post something to the discussion?"

    def handle_post_offer_response(self, user_id: Optional[int], accepted: bool) -> Dict[str, Any]:
        """Handle user's response to the post offer.

        Returns:
            {
                "accepted": bool,
                "message": str,
                "start_dictation": bool
            }
        """
        context = self.get_context(user_id)

        if accepted:
            # User wants to post - start dictation mode
            context.state = ConversationState.AWAITING_POST_DICTATION
            context.post_dictation_content = ""
            self.save_context(user_id, context)
            return {
                "accepted": True,
                "message": "Go ahead, I'm listening. Tell me what you'd like to post. Say 'I'm done' or 'finished' when you're ready.",
                "start_dictation": True
            }
        else:
            # User declined - mark as declined so we don't ask again
            context.state = ConversationState.IDLE
            context.post_offer_declined = True
            self.save_context(user_id, context)
            return {
                "accepted": False,
                "message": "No problem. Let me know if you need anything else.",
                "start_dictation": False
            }

    def append_post_content(self, user_id: Optional[int], content: str) -> Dict[str, Any]:
        """Append dictated content to the post.

        Returns:
            {
                "content": str,  # Full accumulated content
                "message": str   # Acknowledgment
            }
        """
        context = self.get_context(user_id)

        # Clean trailing punctuation from transcription
        clean_content = self._sanitize_transcription(content)

        # Append with proper spacing
        if context.post_dictation_content:
            context.post_dictation_content += " " + clean_content
        else:
            context.post_dictation_content = clean_content

        self.save_context(user_id, context)

        return {
            "content": context.post_dictation_content,
            "message": "Got it. Continue, or say 'I'm done' when finished."
        }

    def finish_post_dictation(self, user_id: Optional[int]) -> Dict[str, Any]:
        """User indicated they're done dictating. Ask for confirmation.

        Returns:
            {
                "content": str,   # The full post content
                "message": str,   # Confirmation prompt
                "has_content": bool
            }
        """
        context = self.get_context(user_id)
        content = context.post_dictation_content.strip()

        if not content:
            # No content was dictated
            context.state = ConversationState.IDLE
            self.save_context(user_id, context)
            return {
                "content": "",
                "message": "It seems like you didn't dictate anything. Would you like to try again?",
                "has_content": False
            }

        # Move to confirmation state
        context.state = ConversationState.AWAITING_POST_SUBMIT_CONFIRMATION
        self.save_context(user_id, context)

        # Truncate for speech if too long
        preview = content[:100] + "..." if len(content) > 100 else content

        return {
            "content": content,
            "message": f"Your post says: '{preview}'. Should I post it now?",
            "has_content": True
        }

    def handle_post_submit_response(self, user_id: Optional[int], confirmed: bool) -> Dict[str, Any]:
        """Handle user's response to post submission confirmation.

        Returns:
            {
                "confirmed": bool,
                "content": str,      # Post content (for submitting)
                "message": str,
                "clear_form": bool   # True if we should clear the textarea
            }
        """
        context = self.get_context(user_id)
        content = context.post_dictation_content

        # Reset state
        context.state = ConversationState.IDLE
        context.post_dictation_content = ""
        self.save_context(user_id, context)

        if confirmed:
            return {
                "confirmed": True,
                "content": content,
                "message": "Posting now!",
                "clear_form": False
            }
        else:
            return {
                "confirmed": False,
                "content": "",
                "message": "Okay, I've cancelled the post. The form has been cleared.",
                "clear_form": True
            }

    def reset_post_offer(self, user_id: Optional[int]) -> None:
        """Reset the post offer declined flag (e.g., when leaving forum page)."""
        context = self.get_context(user_id)
        context.post_offer_declined = False
        context.post_dictation_content = ""
        if context.state in [
            ConversationState.AWAITING_POST_OFFER_RESPONSE,
            ConversationState.AWAITING_POST_DICTATION,
            ConversationState.AWAITING_POST_SUBMIT_CONFIRMATION
        ]:
            context.state = ConversationState.IDLE
        self.save_context(user_id, context)

    def is_in_post_dictation(self, user_id: Optional[int]) -> bool:
        """Check if user is currently dictating a post."""
        context = self.get_context(user_id)
        return context.state == ConversationState.AWAITING_POST_DICTATION

    def get_post_dictation_content(self, user_id: Optional[int]) -> str:
        """Get the current accumulated post content."""
        context = self.get_context(user_id)
        return context.post_dictation_content

    # === Poll Creation Flow ===

    def offer_poll_creation(self, user_id: Optional[int]) -> Optional[str]:
        """Offer to help user create a poll. Returns prompt or None if already declined."""
        context = self.get_context(user_id)

        # Don't offer if user already declined this session
        if context.poll_offer_declined:
            return None

        context.state = ConversationState.AWAITING_POLL_OFFER_RESPONSE
        self.save_context(user_id, context)

        return "Would you like to create a poll?"

    def handle_poll_offer_response(self, user_id: Optional[int], accepted: bool) -> Dict[str, Any]:
        """Handle user's response to the poll offer.

        Returns:
            {
                "accepted": bool,
                "message": str,
                "start_poll_creation": bool
            }
        """
        context = self.get_context(user_id)

        if accepted:
            # User wants to create poll - ask for the question
            context.state = ConversationState.AWAITING_POLL_QUESTION
            context.poll_question = ""
            context.poll_options = []
            context.poll_current_option_index = 1
            self.save_context(user_id, context)
            return {
                "accepted": True,
                "message": "Great! What question would you like to ask in the poll?",
                "start_poll_creation": True
            }
        else:
            # User declined - mark as declined so we don't ask again
            context.state = ConversationState.IDLE
            context.poll_offer_declined = True
            self.save_context(user_id, context)
            return {
                "accepted": False,
                "message": "No problem. Let me know if you need anything else.",
                "start_poll_creation": False
            }

    def set_poll_question(self, user_id: Optional[int], question: str) -> Dict[str, Any]:
        """Set the poll question and ask for the first option.

        Returns:
            {
                "question": str,
                "message": str,
                "ui_actions": List[Dict]  # Actions to perform on UI
            }
        """
        context = self.get_context(user_id)

        # Clean the question
        clean_question = self._sanitize_transcription(question)
        context.poll_question = clean_question
        context.state = ConversationState.AWAITING_POLL_OPTION
        context.poll_current_option_index = 1
        self.save_context(user_id, context)

        return {
            "question": clean_question,
            "message": "Got it. What is the first answer option?",
            "ui_actions": [
                {
                    "action": "fillInput",
                    "voiceId": "poll-question",
                    "value": clean_question
                }
            ]
        }

    def add_poll_option(self, user_id: Optional[int], option: str) -> Dict[str, Any]:
        """Add a poll option and ask for the next one or if done.

        Returns:
            {
                "option": str,
                "option_index": int,
                "message": str,
                "ui_actions": List[Dict],
                "ask_for_more": bool  # True if we need to ask about more options
            }
        """
        context = self.get_context(user_id)

        # Clean the option
        clean_option = self._sanitize_transcription(option)
        context.poll_options.append(clean_option)

        current_index = context.poll_current_option_index
        voice_id = f"poll-option-{current_index}"

        # Move to next option
        context.poll_current_option_index += 1
        next_index = context.poll_current_option_index

        # We need at least 2 options before asking "do you want more?"
        if len(context.poll_options) < 2:
            self.save_context(user_id, context)
            return {
                "option": clean_option,
                "option_index": current_index,
                "message": f"Got it. What is option {next_index}?",
                "ui_actions": [
                    {
                        "action": "fillInput",
                        "voiceId": voice_id,
                        "value": clean_option
                    }
                ],
                "ask_for_more": False
            }
        else:
            # We have 2+ options, ask if they want more
            context.state = ConversationState.AWAITING_POLL_MORE_OPTIONS
            self.save_context(user_id, context)
            return {
                "option": clean_option,
                "option_index": current_index,
                "message": f"Got it. Would you like to add another option?",
                "ui_actions": [
                    {
                        "action": "fillInput",
                        "voiceId": voice_id,
                        "value": clean_option
                    }
                ],
                "ask_for_more": True
            }

    def handle_more_options_response(self, user_id: Optional[int], wants_more: bool) -> Dict[str, Any]:
        """Handle user's response to "do you want more options?"

        Returns:
            {
                "wants_more": bool,
                "message": str,
                "ui_actions": List[Dict],  # Click "Add Option" if wants_more
                "ready_to_confirm": bool
            }
        """
        context = self.get_context(user_id)
        next_index = context.poll_current_option_index

        if wants_more:
            # User wants more options - click "Add Option" and wait for input
            context.state = ConversationState.AWAITING_POLL_OPTION
            self.save_context(user_id, context)
            return {
                "wants_more": True,
                "message": f"What is option {next_index}?",
                "ui_actions": [
                    {
                        "action": "clickButton",
                        "voiceId": "add-poll-option"  # The "Add Option" button
                    }
                ],
                "ready_to_confirm": False
            }
        else:
            # User is done - ask for confirmation
            context.state = ConversationState.AWAITING_POLL_CONFIRM
            self.save_context(user_id, context)

            # Build a summary
            num_options = len(context.poll_options)
            return {
                "wants_more": False,
                "message": f"You have a poll with {num_options} options. Should I create it now?",
                "ui_actions": [],
                "ready_to_confirm": True
            }

    def handle_poll_confirm(self, user_id: Optional[int], confirmed: bool) -> Dict[str, Any]:
        """Handle user's confirmation to create the poll.

        Returns:
            {
                "confirmed": bool,
                "message": str,
                "ui_actions": List[Dict],
                "poll_data": Dict  # The poll question and options
            }
        """
        context = self.get_context(user_id)

        poll_data = {
            "question": context.poll_question,
            "options": context.poll_options.copy()
        }

        if confirmed:
            # Create the poll
            message = "Creating your poll now!"
            ui_actions = [
                {
                    "action": "clickButton",
                    "voiceId": "create-poll"
                }
            ]
        else:
            message = "Okay, I've cancelled the poll creation."
            ui_actions = []

        # Reset poll state
        context.state = ConversationState.IDLE
        context.poll_question = ""
        context.poll_options = []
        context.poll_current_option_index = 1
        self.save_context(user_id, context)

        return {
            "confirmed": confirmed,
            "message": message,
            "ui_actions": ui_actions,
            "poll_data": poll_data
        }

    def reset_poll_offer(self, user_id: Optional[int]) -> None:
        """Reset the poll offer declined flag (e.g., when leaving console page)."""
        context = self.get_context(user_id)
        context.poll_offer_declined = False
        context.poll_question = ""
        context.poll_options = []
        context.poll_current_option_index = 1
        if context.state in [
            ConversationState.AWAITING_POLL_OFFER_RESPONSE,
            ConversationState.AWAITING_POLL_QUESTION,
            ConversationState.AWAITING_POLL_OPTION,
            ConversationState.AWAITING_POLL_MORE_OPTIONS,
            ConversationState.AWAITING_POLL_CONFIRM
        ]:
            context.state = ConversationState.IDLE
        self.save_context(user_id, context)

    def is_in_poll_creation(self, user_id: Optional[int]) -> bool:
        """Check if user is currently creating a poll."""
        context = self.get_context(user_id)
        return context.state in [
            ConversationState.AWAITING_POLL_QUESTION,
            ConversationState.AWAITING_POLL_OPTION,
            ConversationState.AWAITING_POLL_MORE_OPTIONS,
            ConversationState.AWAITING_POLL_CONFIRM
        ]

    def get_poll_creation_data(self, user_id: Optional[int]) -> Dict[str, Any]:
        """Get the current poll creation data."""
        context = self.get_context(user_id)
        return {
            "question": context.poll_question,
            "options": context.poll_options.copy(),
            "current_option_index": context.poll_current_option_index
        }

    # === Case Posting Flow ===

    def offer_case_posting(self, user_id: Optional[int]) -> Optional[str]:
        """Offer to help user post a case study. Returns prompt or None if already declined."""
        context = self.get_context(user_id)

        # Don't offer if user already declined this session
        if context.case_offer_declined:
            return None

        context.state = ConversationState.AWAITING_CASE_OFFER_RESPONSE
        self.save_context(user_id, context)

        return "Would you like to post a case study?"

    def handle_case_offer_response(self, user_id: Optional[int], accepted: bool) -> Dict[str, Any]:
        """Handle user's response to the case offer.

        Returns:
            {
                "accepted": bool,
                "message": str,
                "start_case_creation": bool
            }
        """
        context = self.get_context(user_id)

        if accepted:
            # User wants to post a case - ask for the content
            context.state = ConversationState.AWAITING_CASE_PROMPT
            context.case_prompt_content = ""
            self.save_context(user_id, context)
            return {
                "accepted": True,
                "message": "Great! What case scenario would you like to present to students? You can dictate it now, and say 'done' or 'that's it' when you're finished.",
                "start_case_creation": True
            }
        else:
            # User declined - mark as declined so we don't ask again
            context.state = ConversationState.IDLE
            context.case_offer_declined = True
            self.save_context(user_id, context)
            return {
                "accepted": False,
                "message": "No problem. Let me know if you need anything else.",
                "start_case_creation": False
            }

    def append_case_content(self, user_id: Optional[int], content: str) -> Dict[str, Any]:
        """Append content to the case prompt during dictation.

        Returns:
            {
                "content": str,  # The appended content
                "total_content": str,  # Full accumulated content
                "message": str,
                "ui_actions": List[Dict]
            }
        """
        context = self.get_context(user_id)

        # Clean and append the content
        clean_content = self._sanitize_transcription(content)

        if context.case_prompt_content:
            context.case_prompt_content += " " + clean_content
        else:
            context.case_prompt_content = clean_content

        self.save_context(user_id, context)

        return {
            "content": clean_content,
            "total_content": context.case_prompt_content,
            "message": "Got it. Continue dictating, or say 'done' when you're finished.",
            "ui_actions": [
                {
                    "action": "fillInput",
                    "voiceId": "case-prompt",
                    "value": context.case_prompt_content
                }
            ]
        }

    def finish_case_dictation(self, user_id: Optional[int]) -> Dict[str, Any]:
        """Finish dictation and ask for confirmation.

        Returns:
            {
                "content": str,
                "message": str,
                "ui_actions": List[Dict],
                "ready_to_confirm": bool
            }
        """
        context = self.get_context(user_id)

        if not context.case_prompt_content.strip():
            return {
                "content": "",
                "message": "It seems you haven't dictated any content yet. What case would you like to post?",
                "ui_actions": [],
                "ready_to_confirm": False
            }

        context.state = ConversationState.AWAITING_CASE_CONFIRM
        self.save_context(user_id, context)

        # Create a preview (first 100 chars)
        preview = context.case_prompt_content[:100]
        if len(context.case_prompt_content) > 100:
            preview += "..."

        return {
            "content": context.case_prompt_content,
            "message": f"Your case study says: \"{preview}\". Should I post it now?",
            "ui_actions": [],
            "ready_to_confirm": True
        }

    def handle_case_confirm(self, user_id: Optional[int], confirmed: bool) -> Dict[str, Any]:
        """Handle user's confirmation to post the case.

        Returns:
            {
                "confirmed": bool,
                "message": str,
                "ui_actions": List[Dict],
                "case_content": str
            }
        """
        context = self.get_context(user_id)

        case_content = context.case_prompt_content

        if confirmed:
            # Post the case
            message = "Posting your case study now!"
            ui_actions = [
                {
                    "action": "clickButton",
                    "voiceId": "post-case"
                }
            ]
        else:
            message = "Okay, I've cancelled the case posting. The content is still in the form if you want to edit it."
            ui_actions = []

        # Reset case state
        context.state = ConversationState.IDLE
        if not confirmed:
            # Only clear the content if cancelled
            context.case_prompt_content = ""
        self.save_context(user_id, context)

        return {
            "confirmed": confirmed,
            "message": message,
            "ui_actions": ui_actions,
            "case_content": case_content
        }

    def reset_case_offer(self, user_id: Optional[int]) -> None:
        """Reset the case offer declined flag (e.g., when leaving console page)."""
        context = self.get_context(user_id)
        context.case_offer_declined = False
        context.case_prompt_content = ""
        if context.state in [
            ConversationState.AWAITING_CASE_OFFER_RESPONSE,
            ConversationState.AWAITING_CASE_PROMPT,
            ConversationState.AWAITING_CASE_CONFIRM
        ]:
            context.state = ConversationState.IDLE
        self.save_context(user_id, context)

    def is_in_case_creation(self, user_id: Optional[int]) -> bool:
        """Check if user is currently creating a case."""
        context = self.get_context(user_id)
        return context.state in [
            ConversationState.AWAITING_CASE_PROMPT,
            ConversationState.AWAITING_CASE_CONFIRM
        ]

    def get_case_creation_data(self, user_id: Optional[int]) -> Dict[str, Any]:
        """Get the current case creation data."""
        context = self.get_context(user_id)
        return {
            "content": context.case_prompt_content
        }
