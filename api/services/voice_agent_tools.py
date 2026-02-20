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

# Import LLM utilities for content generation
from workflows.llm_utils import (
    get_fast_voice_llm,
    invoke_llm_with_metrics,
    LLMResponse,
)

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
    # =========================================================================
    # AI CONTENT GENERATION TOOLS - Generate and fill form fields
    # =========================================================================
    {
        "name": "generate_syllabus",
        "description": """Generate a syllabus for a course using AI and fill the syllabus form field.

Use this when the user asks you to generate, create, or write a syllabus for them.
The generated syllabus will automatically be filled into the syllabus text area.

Examples of when to use this tool:
- "Generate a syllabus for this course"
- "Create a syllabus for Machine Learning"
- "Write me a syllabus"
- "Can you make a syllabus for me?"
- "Help me with the syllabus"

IMPORTANT: Use this BEFORE clicking create/submit buttons when user wants AI-generated syllabus.""",
        "parameters": {
            "type": "object",
            "properties": {
                "course_name": {
                    "type": "string",
                    "description": "Name of the course to generate syllabus for"
                },
                "course_description": {
                    "type": "string",
                    "description": "Optional description or context about the course"
                }
            },
            "required": ["course_name"]
        }
    },
    {
        "name": "generate_objectives",
        "description": """Generate learning objectives for a course using AI and fill the objectives form field.

Use this when the user asks you to generate or create learning objectives.
The generated objectives will automatically be filled into the learning objectives text area.

Examples of when to use this tool:
- "Generate learning objectives"
- "Create objectives for this course"
- "What should the learning objectives be?"
- "Help me with the objectives"

IMPORTANT: Use this BEFORE clicking create/submit buttons when user wants AI-generated objectives.""",
        "parameters": {
            "type": "object",
            "properties": {
                "course_name": {
                    "type": "string",
                    "description": "Name of the course"
                },
                "syllabus": {
                    "type": "string",
                    "description": "Course syllabus to base objectives on (if available)"
                }
            },
            "required": ["course_name"]
        }
    },
    {
        "name": "generate_session_plan",
        "description": """Generate a session plan/description for a class session using AI and fill the session description field.

Use this when the user asks you to generate or create a session plan.
The generated plan will automatically be filled into the session description text area.

Examples of when to use this tool:
- "Generate a session plan"
- "Create a plan for this session"
- "Write a session description"
- "Help me plan this session"

IMPORTANT: Use this BEFORE clicking create/submit buttons when user wants AI-generated session plan.""",
        "parameters": {
            "type": "object",
            "properties": {
                "session_title": {
                    "type": "string",
                    "description": "Title or topic of the session"
                },
                "course_name": {
                    "type": "string",
                    "description": "Name of the course this session belongs to"
                },
                "duration_minutes": {
                    "type": "integer",
                    "description": "Duration of the session in minutes",
                    "default": 60
                }
            },
            "required": ["session_title"]
        }
    },
    # =========================================================================
    # SESSION MANAGEMENT TOOLS
    # =========================================================================
    {
        "name": "go_live",
        "description": """Start a live session. Use this when the user wants to begin a live class session.

Examples: "go live", "start the session", "begin the live session", "make session live", "start class".""",
        "parameters": {
            "type": "object",
            "properties": {
                "session_id": {
                    "type": "integer",
                    "description": "ID of the session to start (optional, uses current if not specified)"
                }
            },
            "required": []
        }
    },
    {
        "name": "end_session",
        "description": """End a live session. Use this when the user wants to finish/complete the current live session.

Examples: "end session", "stop the session", "finish class", "complete the session", "end class".""",
        "parameters": {
            "type": "object",
            "properties": {
                "session_id": {
                    "type": "integer",
                    "description": "ID of the session to end (optional, uses current if not specified)"
                }
            },
            "required": []
        }
    },
    {
        "name": "start_timer",
        "description": """Start a countdown timer for session pacing. Use for timed activities, discussions, or breaks.

Examples: "start a 5 minute timer", "set timer for 10 minutes", "start countdown", "time this activity".""",
        "parameters": {
            "type": "object",
            "properties": {
                "minutes": {
                    "type": "integer",
                    "description": "Duration in minutes",
                    "default": 5
                },
                "label": {
                    "type": "string",
                    "description": "Label for the timer (e.g., 'Discussion', 'Break')"
                }
            },
            "required": []
        }
    },
    {
        "name": "pause_timer",
        "description": """Pause the running timer. Use when user wants to temporarily stop the countdown.

Examples: "pause timer", "stop the clock", "hold the timer", "pause countdown".""",
        "parameters": {"type": "object", "properties": {}, "required": []}
    },
    {
        "name": "resume_timer",
        "description": """Resume a paused timer. Use when user wants to continue a paused countdown.

Examples: "resume timer", "continue timer", "unpause", "start timer again".""",
        "parameters": {"type": "object", "properties": {}, "required": []}
    },
    {
        "name": "stop_timer",
        "description": """Stop and reset the timer. Use when user wants to cancel the current timer.

Examples: "stop timer", "cancel timer", "clear timer", "reset countdown".""",
        "parameters": {"type": "object", "properties": {}, "required": []}
    },
    {
        "name": "get_timer_status",
        "description": """Check current timer status. Use when user asks about remaining time.

Examples: "how much time left", "timer status", "check the timer", "time remaining".""",
        "parameters": {"type": "object", "properties": {}, "required": []}
    },
    # =========================================================================
    # BREAKOUT GROUPS TOOLS
    # =========================================================================
    {
        "name": "create_breakout_groups",
        "description": """Create AI-powered breakout groups for collaborative activities.

Supports different grouping strategies:
- random: Random assignment
- debate: Opposing viewpoints for debates
- mixed: Balance high/low participation
- jigsaw: Topic-based expert groups

Examples: "create breakout groups", "split students into groups", "make 4 groups", "create debate groups".""",
        "parameters": {
            "type": "object",
            "properties": {
                "num_groups": {
                    "type": "integer",
                    "description": "Number of groups to create",
                    "default": 4
                },
                "strategy": {
                    "type": "string",
                    "enum": ["random", "debate", "mixed", "jigsaw"],
                    "description": "Grouping strategy",
                    "default": "random"
                },
                "topic": {
                    "type": "string",
                    "description": "Topic for the group activity"
                }
            },
            "required": []
        }
    },
    {
        "name": "get_breakout_groups",
        "description": """View current breakout groups and their members.

Examples: "show breakout groups", "who is in which group", "view groups", "list the groups".""",
        "parameters": {"type": "object", "properties": {}, "required": []}
    },
    {
        "name": "dissolve_breakout_groups",
        "description": """End breakout session and bring everyone back together.

Examples: "dissolve groups", "end breakout", "bring everyone back", "close breakout groups".""",
        "parameters": {"type": "object", "properties": {}, "required": []}
    },
    # =========================================================================
    # AI COPILOT TOOLS
    # =========================================================================
    {
        "name": "start_copilot",
        "description": """Start the AI copilot for live teaching assistance. Provides real-time suggestions during class.

Examples: "start copilot", "turn on AI assistant", "enable copilot", "start AI help".""",
        "parameters": {"type": "object", "properties": {}, "required": []}
    },
    {
        "name": "stop_copilot",
        "description": """Stop the AI copilot.

Examples: "stop copilot", "turn off AI assistant", "disable copilot", "stop AI help".""",
        "parameters": {"type": "object", "properties": {}, "required": []}
    },
    {
        "name": "get_copilot_suggestions",
        "description": """Get current AI copilot suggestions for teaching.

Examples: "what does copilot suggest", "show suggestions", "AI recommendations", "copilot advice".""",
        "parameters": {"type": "object", "properties": {}, "required": []}
    },
    {
        "name": "get_facilitation_suggestions",
        "description": """Get AI-powered facilitation suggestions based on current discussion.

Examples: "facilitation suggestions", "how should I facilitate", "teaching suggestions", "what should I do next".""",
        "parameters": {"type": "object", "properties": {}, "required": []}
    },
    # =========================================================================
    # STUDENT MONITORING TOOLS
    # =========================================================================
    {
        "name": "get_engagement_heatmap",
        "description": """Show visual engagement heatmap of student participation.

Examples: "show engagement heatmap", "participation heatmap", "who is participating", "engagement visualization".""",
        "parameters": {"type": "object", "properties": {}, "required": []}
    },
    {
        "name": "get_disengaged_students",
        "description": """Identify students who are disengaged or at-risk.

Examples: "who is disengaged", "at-risk students", "who needs attention", "inactive students".""",
        "parameters": {"type": "object", "properties": {}, "required": []}
    },
    {
        "name": "who_needs_help",
        "description": """Identify students who may be struggling and need help.

Examples: "who needs help", "struggling students", "students having difficulty", "who should I help".""",
        "parameters": {"type": "object", "properties": {}, "required": []}
    },
    {
        "name": "student_lookup",
        "description": """Look up information about a specific student.

Examples: "look up John Smith", "find student Maria", "student info for...", "tell me about student...".""",
        "parameters": {
            "type": "object",
            "properties": {
                "student_name": {
                    "type": "string",
                    "description": "Name or partial name of the student to look up"
                }
            },
            "required": ["student_name"]
        }
    },
    {
        "name": "get_class_status",
        "description": """Get overall class engagement and participation status.

Examples: "class status", "how is the class doing", "participation levels", "engagement overview".""",
        "parameters": {"type": "object", "properties": {}, "required": []}
    },
    {
        "name": "get_participation_stats",
        "description": """Get detailed participation statistics for the session.

Examples: "participation stats", "engagement statistics", "how many participated", "participation breakdown".""",
        "parameters": {"type": "object", "properties": {}, "required": []}
    },
    {
        "name": "suggest_next_student",
        "description": """AI suggests which student to call on next for balanced participation.

Examples: "who should I call on", "suggest next student", "who hasn't spoken", "next participant".""",
        "parameters": {"type": "object", "properties": {}, "required": []}
    },
    {
        "name": "get_student_progress",
        "description": """Get progress tracking for a specific student or all students.

Examples: "student progress", "how is John doing", "track progress", "student performance".""",
        "parameters": {
            "type": "object",
            "properties": {
                "student_name": {
                    "type": "string",
                    "description": "Optional: specific student name"
                }
            },
            "required": []
        }
    },
    # =========================================================================
    # DISCUSSION & CONTENT TOOLS
    # =========================================================================
    {
        "name": "summarize_discussion",
        "description": """Generate AI summary of the current discussion thread.

Examples: "summarize discussion", "summary of posts", "what has been discussed", "recap the discussion".""",
        "parameters": {
            "type": "object",
            "properties": {
                "include_key_points": {
                    "type": "boolean",
                    "description": "Include key points in summary",
                    "default": True
                }
            },
            "required": []
        }
    },
    {
        "name": "get_misconceptions",
        "description": """Identify student misconceptions from discussion posts.

Examples: "any misconceptions", "what are students getting wrong", "identify misunderstandings", "check for errors".""",
        "parameters": {"type": "object", "properties": {}, "required": []}
    },
    {
        "name": "get_student_questions",
        "description": """Get unanswered questions from students.

Examples: "student questions", "unanswered questions", "what are students asking", "pending questions".""",
        "parameters": {"type": "object", "properties": {}, "required": []}
    },
    {
        "name": "get_poll_suggestions",
        "description": """Get AI-suggested poll questions based on current discussion.

Examples: "suggest a poll", "poll ideas", "what poll should I create", "recommend poll questions".""",
        "parameters": {"type": "object", "properties": {}, "required": []}
    },
    {
        "name": "read_posts",
        "description": """Read recent discussion posts aloud.

Examples: "read posts", "what did students post", "read the discussion", "show me posts".""",
        "parameters": {
            "type": "object",
            "properties": {
                "count": {
                    "type": "integer",
                    "description": "Number of posts to read",
                    "default": 5
                }
            },
            "required": []
        }
    },
    # =========================================================================
    # AI TEACHING ASSISTANT TOOLS
    # =========================================================================
    {
        "name": "generate_ai_draft",
        "description": """Generate an AI draft response to a student question.

Examples: "draft a response", "AI answer this", "generate response for...", "help me respond".""",
        "parameters": {
            "type": "object",
            "properties": {
                "question": {
                    "type": "string",
                    "description": "The student question to respond to"
                },
                "context": {
                    "type": "string",
                    "description": "Additional context for the response"
                }
            },
            "required": ["question"]
        }
    },
    {
        "name": "get_ai_drafts",
        "description": """Get pending AI-generated response drafts awaiting review.

Examples: "show AI drafts", "pending responses", "drafts to review", "AI responses queue".""",
        "parameters": {"type": "object", "properties": {}, "required": []}
    },
    {
        "name": "approve_ai_draft",
        "description": """Approve an AI-generated draft for posting.

Examples: "approve draft", "post the response", "accept AI response", "publish draft".""",
        "parameters": {
            "type": "object",
            "properties": {
                "draft_id": {
                    "type": "integer",
                    "description": "ID of the draft to approve"
                }
            },
            "required": []
        }
    },
    {
        "name": "reject_ai_draft",
        "description": """Reject an AI-generated draft.

Examples: "reject draft", "discard response", "don't post that", "delete draft".""",
        "parameters": {
            "type": "object",
            "properties": {
                "draft_id": {
                    "type": "integer",
                    "description": "ID of the draft to reject"
                }
            },
            "required": []
        }
    },
    # =========================================================================
    # SESSION TEMPLATES & SUMMARIES
    # =========================================================================
    {
        "name": "save_template",
        "description": """Save current session as a reusable template.

Examples: "save as template", "create template", "save this session template", "make reusable".""",
        "parameters": {
            "type": "object",
            "properties": {
                "template_name": {
                    "type": "string",
                    "description": "Name for the template"
                }
            },
            "required": []
        }
    },
    {
        "name": "clone_session",
        "description": """Clone/duplicate a session for reuse.

Examples: "clone session", "duplicate session", "copy this session", "create copy".""",
        "parameters": {
            "type": "object",
            "properties": {
                "new_title": {
                    "type": "string",
                    "description": "Title for the cloned session"
                }
            },
            "required": []
        }
    },
    {
        "name": "get_session_summary",
        "description": """Generate a post-session summary.

Examples: "session summary", "summarize the session", "post-class summary", "what happened in class".""",
        "parameters": {"type": "object", "properties": {}, "required": []}
    },
    {
        "name": "send_session_summary",
        "description": """Send session summary to students via email or Canvas.

Examples: "send summary to students", "email the summary", "share session recap", "distribute summary".""",
        "parameters": {
            "type": "object",
            "properties": {
                "method": {
                    "type": "string",
                    "enum": ["email", "canvas", "in_app"],
                    "description": "Delivery method",
                    "default": "in_app"
                }
            },
            "required": []
        }
    },
    # =========================================================================
    # ANALYTICS & COMPARISON TOOLS
    # =========================================================================
    {
        "name": "compare_sessions",
        "description": """Compare engagement/participation across multiple sessions.

Examples: "compare sessions", "session comparison", "how does this compare", "compare to last week".""",
        "parameters": {
            "type": "object",
            "properties": {
                "session_ids": {
                    "type": "array",
                    "items": {"type": "integer"},
                    "description": "IDs of sessions to compare"
                }
            },
            "required": []
        }
    },
    {
        "name": "get_course_analytics",
        "description": """Get overall course analytics and trends.

Examples: "course analytics", "course statistics", "how is the course going", "course trends".""",
        "parameters": {"type": "object", "properties": {}, "required": []}
    },
    # =========================================================================
    # LMS INTEGRATION TOOLS
    # =========================================================================
    {
        "name": "push_to_canvas",
        "description": """Push AI-generated session summary to Canvas LMS as announcement or assignment.

Examples: "push summary to Canvas", "send summary to Canvas", "push to Canvas", "create Canvas announcement".""",
        "parameters": {
            "type": "object",
            "properties": {
                "push_type": {
                    "type": "string",
                    "enum": ["announcement", "assignment"],
                    "description": "Type of Canvas content to create",
                    "default": "announcement"
                }
            },
            "required": []
        }
    },
    {
        "name": "notify_canvas_status",
        "description": """Notify students on Canvas about session status change (draft, scheduled, live, completed).

Examples: "notify Canvas about status", "send status notification to Canvas", "tell students on Canvas the session is live".""",
        "parameters": {"type": "object", "properties": {}, "required": []}
    },
    {
        "name": "edit_session",
        "description": """Open the edit modal for the currently selected session.

Examples: "edit session", "edit this session", "modify session", "change session details", "update session".""",
        "parameters": {"type": "object", "properties": {}, "required": []}
    },
    {
        "name": "delete_session",
        "description": """Delete the currently selected session (with confirmation).

Examples: "delete session", "remove session", "delete this session".""",
        "parameters": {"type": "object", "properties": {}, "required": []}
    },
    {
        "name": "generate_questions",
        "description": """Generate AI quiz questions from session content for the question bank.

Examples: "generate questions", "create quiz questions", "build question bank", "generate quiz from discussion".""",
        "parameters": {
            "type": "object",
            "properties": {
                "count": {
                    "type": "integer",
                    "description": "Number of questions to generate",
                    "default": 5
                }
            },
            "required": []
        }
    },
    {
        "name": "create_peer_reviews",
        "description": """Match students for peer review assignments.

Examples: "create peer reviews", "match students for review", "set up peer review", "assign peer reviews".""",
        "parameters": {
            "type": "object",
            "properties": {
                "reviews_per_submission": {
                    "type": "integer",
                    "description": "Number of reviewers per submission",
                    "default": 2
                }
            },
            "required": []
        }
    },
    {
        "name": "generate_live_summary",
        "description": """Generate an AI summary of the current live discussion.

Examples: "generate summary", "summarize discussion", "create live summary", "what are students discussing".""",
        "parameters": {"type": "object", "properties": {}, "required": []}
    },
    # =========================================================================
    # UTILITY TOOLS
    # =========================================================================
    {
        "name": "undo_action",
        "description": """Undo the last action performed.

Examples: "undo", "undo that", "go back", "revert", "cancel last action".""",
        "parameters": {"type": "object", "properties": {}, "required": []}
    },
    {
        "name": "toggle_theme",
        "description": """Toggle between light and dark theme.

Examples: "toggle theme", "dark mode", "light mode", "switch theme", "change appearance".""",
        "parameters": {
            "type": "object",
            "properties": {
                "theme": {
                    "type": "string",
                    "enum": ["light", "dark", "toggle"],
                    "description": "Theme to switch to",
                    "default": "toggle"
                }
            },
            "required": []
        }
    },
    {
        "name": "get_help",
        "description": """Get help about voice commands or the current page.

Examples: "help", "what can I do", "voice commands", "how do I...", "show help".""",
        "parameters": {
            "type": "object",
            "properties": {
                "topic": {
                    "type": "string",
                    "description": "Specific topic to get help about"
                }
            },
            "required": []
        }
    },
    {
        "name": "sign_out",
        "description": """Sign out of the application.

Examples: "sign out", "log out", "logout", "exit", "sign me out".""",
        "parameters": {"type": "object", "properties": {}, "required": []}
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
# AI CONTENT GENERATION HANDLERS
# ============================================================================

def handle_generate_syllabus(
    course_name: str,
    course_description: Optional[str] = None
) -> ToolResult:
    """Generate a syllabus for a course using LLM and fill the form field."""
    try:
        llm, model_name = get_fast_voice_llm()
        if not llm:
            return ToolResult(
                status=ToolResultStatus.FAILURE,
                message="AI generation is temporarily unavailable."
            )

        # Build generation prompt
        context = f"Course: {course_name}"
        if course_description:
            context += f"\nDescription: {course_description}"

        prompt = f"""Generate a comprehensive syllabus for the following course.
The syllabus should include:
- Course overview and description
- Learning outcomes
- Weekly topics/modules (8-12 weeks)
- Assessment methods
- Required materials/textbooks

{context}

Generate a well-structured syllabus in plain text format (no markdown headers, just clear sections).
Keep it concise but comprehensive (300-500 words)."""

        response = invoke_llm_with_metrics(llm, prompt, model_name)

        if not response.success or not response.content:
            return ToolResult(
                status=ToolResultStatus.FAILURE,
                message="Failed to generate syllabus. Please try again."
            )

        syllabus = response.content.strip()

        return ToolResult(
            status=ToolResultStatus.SUCCESS,
            message=f"Generated syllabus for {course_name}",
            data={"syllabus": syllabus},
            ui_action={
                "type": "ui.fillInput",
                "payload": {
                    "target": "syllabus",
                    "value": syllabus
                }
            }
        )

    except Exception as e:
        logger.exception(f"Error generating syllabus: {e}")
        return ToolResult(
            status=ToolResultStatus.FAILURE,
            message=f"Error generating syllabus: {str(e)}"
        )


def handle_generate_objectives(
    course_name: str,
    syllabus: Optional[str] = None
) -> ToolResult:
    """Generate learning objectives for a course using LLM and fill the form field."""
    try:
        llm, model_name = get_fast_voice_llm()
        if not llm:
            return ToolResult(
                status=ToolResultStatus.FAILURE,
                message="AI generation is temporarily unavailable."
            )

        # Build generation prompt
        context = f"Course: {course_name}"
        if syllabus:
            context += f"\nSyllabus: {syllabus[:1000]}..."  # Truncate if too long

        prompt = f"""Generate 5-7 clear learning objectives for the following course.
Each objective should:
- Start with an action verb (Understand, Analyze, Apply, Create, Evaluate, etc.)
- Be specific and measurable
- Be achievable within the course duration

{context}

Format: One objective per line, numbered 1-7. No bullet points or dashes.
Keep each objective concise (1-2 sentences max)."""

        response = invoke_llm_with_metrics(llm, prompt, model_name)

        if not response.success or not response.content:
            return ToolResult(
                status=ToolResultStatus.FAILURE,
                message="Failed to generate objectives. Please try again."
            )

        objectives = response.content.strip()

        return ToolResult(
            status=ToolResultStatus.SUCCESS,
            message=f"Generated learning objectives for {course_name}",
            data={"objectives": objectives},
            ui_action={
                "type": "ui.fillInput",
                "payload": {
                    "target": "learning-objectives",
                    "value": objectives
                }
            }
        )

    except Exception as e:
        logger.exception(f"Error generating objectives: {e}")
        return ToolResult(
            status=ToolResultStatus.FAILURE,
            message=f"Error generating objectives: {str(e)}"
        )


def handle_generate_session_plan(
    session_title: str,
    course_name: Optional[str] = None,
    duration_minutes: int = 60
) -> ToolResult:
    """Generate a session plan/description using LLM and fill the form field."""
    try:
        llm, model_name = get_fast_voice_llm()
        if not llm:
            return ToolResult(
                status=ToolResultStatus.FAILURE,
                message="AI generation is temporarily unavailable."
            )

        # Build generation prompt
        context = f"Session Topic: {session_title}\nDuration: {duration_minutes} minutes"
        if course_name:
            context += f"\nCourse: {course_name}"

        prompt = f"""Generate a detailed session plan for the following class session.
The plan should include:
- Session overview (2-3 sentences)
- Key learning goals for this session
- Outline of activities with approximate timing
- Discussion questions to engage students
- Key takeaways

{context}

Format as a clear, readable plan in plain text (no markdown).
Keep it practical and actionable (200-400 words)."""

        response = invoke_llm_with_metrics(llm, prompt, model_name)

        if not response.success or not response.content:
            return ToolResult(
                status=ToolResultStatus.FAILURE,
                message="Failed to generate session plan. Please try again."
            )

        session_plan = response.content.strip()

        return ToolResult(
            status=ToolResultStatus.SUCCESS,
            message=f"Generated session plan for {session_title}",
            data={"session_plan": session_plan},
            ui_action={
                "type": "ui.fillInput",
                "payload": {
                    "target": "textarea-session-description",
                    "value": session_plan
                }
            }
        )

    except Exception as e:
        logger.exception(f"Error generating session plan: {e}")
        return ToolResult(
            status=ToolResultStatus.FAILURE,
            message=f"Error generating session plan: {str(e)}"
        )


# ============================================================================
# SESSION MANAGEMENT HANDLERS
# ============================================================================

def handle_go_live(session_id: Optional[int] = None) -> ToolResult:
    """Start a live session."""
    return ToolResult(
        status=ToolResultStatus.SUCCESS,
        message="Starting live session",
        ui_action={
            "type": "ui.clickButton",
            "payload": {"target": "go-live", "voiceId": "go-live"}
        }
    )


def handle_end_session(session_id: Optional[int] = None) -> ToolResult:
    """End the current live session."""
    return ToolResult(
        status=ToolResultStatus.SUCCESS,
        message="Ending session",
        ui_action={
            "type": "ui.clickButton",
            "payload": {"target": "end-session", "voiceId": "end-session"}
        }
    )


def handle_start_timer(minutes: int = 5, label: Optional[str] = None) -> ToolResult:
    """Start a countdown timer."""
    timer_label = label or f"{minutes} minute timer"
    return ToolResult(
        status=ToolResultStatus.SUCCESS,
        message=f"Starting {timer_label}",
        data={"minutes": minutes, "label": timer_label},
        ui_action={
            "type": "ui.startTimer",
            "payload": {"minutes": minutes, "label": timer_label}
        }
    )


def handle_pause_timer() -> ToolResult:
    """Pause the running timer."""
    return ToolResult(
        status=ToolResultStatus.SUCCESS,
        message="Timer paused",
        ui_action={"type": "ui.pauseTimer", "payload": {}}
    )


def handle_resume_timer() -> ToolResult:
    """Resume a paused timer."""
    return ToolResult(
        status=ToolResultStatus.SUCCESS,
        message="Timer resumed",
        ui_action={"type": "ui.resumeTimer", "payload": {}}
    )


def handle_stop_timer() -> ToolResult:
    """Stop and reset the timer."""
    return ToolResult(
        status=ToolResultStatus.SUCCESS,
        message="Timer stopped",
        ui_action={"type": "ui.stopTimer", "payload": {}}
    )


def handle_get_timer_status() -> ToolResult:
    """Get current timer status."""
    return ToolResult(
        status=ToolResultStatus.SUCCESS,
        message="Checking timer status",
        ui_action={"type": "ui.getTimerStatus", "payload": {}}
    )


# ============================================================================
# BREAKOUT GROUPS HANDLERS
# ============================================================================

def handle_create_breakout_groups(
    num_groups: int = 4,
    strategy: str = "random",
    topic: Optional[str] = None
) -> ToolResult:
    """Create AI-powered breakout groups."""
    return ToolResult(
        status=ToolResultStatus.SUCCESS,
        message=f"Creating {num_groups} breakout groups using {strategy} strategy",
        data={"num_groups": num_groups, "strategy": strategy, "topic": topic},
        ui_action={
            "type": "ui.createBreakoutGroups",
            "payload": {"numGroups": num_groups, "strategy": strategy, "topic": topic}
        }
    )


def handle_get_breakout_groups() -> ToolResult:
    """View current breakout groups."""
    return ToolResult(
        status=ToolResultStatus.SUCCESS,
        message="Showing breakout groups",
        ui_action={"type": "ui.showBreakoutGroups", "payload": {}}
    )


def handle_dissolve_breakout_groups() -> ToolResult:
    """Dissolve breakout groups."""
    return ToolResult(
        status=ToolResultStatus.SUCCESS,
        message="Dissolving breakout groups",
        ui_action={"type": "ui.dissolveBreakoutGroups", "payload": {}}
    )


# ============================================================================
# AI COPILOT HANDLERS
# ============================================================================

def handle_start_copilot() -> ToolResult:
    """Start the AI copilot."""
    return ToolResult(
        status=ToolResultStatus.SUCCESS,
        message="Starting AI copilot",
        ui_action={
            "type": "ui.clickButton",
            "payload": {"target": "start-copilot", "voiceId": "start-copilot"}
        }
    )


def handle_stop_copilot() -> ToolResult:
    """Stop the AI copilot."""
    return ToolResult(
        status=ToolResultStatus.SUCCESS,
        message="Stopping AI copilot",
        ui_action={
            "type": "ui.clickButton",
            "payload": {"target": "stop-copilot", "voiceId": "stop-copilot"}
        }
    )


def handle_get_copilot_suggestions() -> ToolResult:
    """Get copilot suggestions."""
    return ToolResult(
        status=ToolResultStatus.SUCCESS,
        message="Fetching copilot suggestions",
        ui_action={"type": "ui.getCopilotSuggestions", "payload": {}}
    )


def handle_get_facilitation_suggestions() -> ToolResult:
    """Get facilitation suggestions using LLM."""
    try:
        llm, model_name = get_fast_voice_llm()
        if not llm:
            return ToolResult(
                status=ToolResultStatus.FAILURE,
                message="AI suggestions temporarily unavailable"
            )

        prompt = """As a teaching assistant, provide 3-5 brief facilitation suggestions for a live class discussion.
Focus on:
- Engaging quiet students
- Deepening the discussion
- Addressing potential confusion
- Transitioning between topics

Keep each suggestion to 1-2 sentences. Be practical and actionable."""

        response = invoke_llm_with_metrics(llm, prompt, model_name)

        if response.success and response.content:
            return ToolResult(
                status=ToolResultStatus.SUCCESS,
                message="Here are some facilitation suggestions",
                data={"suggestions": response.content.strip()}
            )

        return ToolResult(
            status=ToolResultStatus.FAILURE,
            message="Could not generate suggestions"
        )
    except Exception as e:
        logger.exception(f"Error getting facilitation suggestions: {e}")
        return ToolResult(
            status=ToolResultStatus.FAILURE,
            message="Error getting suggestions"
        )


# ============================================================================
# STUDENT MONITORING HANDLERS
# ============================================================================

def handle_get_engagement_heatmap() -> ToolResult:
    """Show engagement heatmap."""
    return ToolResult(
        status=ToolResultStatus.SUCCESS,
        message="Showing engagement heatmap",
        ui_action={"type": "ui.showEngagementHeatmap", "payload": {}}
    )


def handle_get_disengaged_students() -> ToolResult:
    """Identify disengaged students."""
    return ToolResult(
        status=ToolResultStatus.SUCCESS,
        message="Identifying disengaged students",
        ui_action={"type": "ui.getDisengagedStudents", "payload": {}}
    )


def handle_who_needs_help() -> ToolResult:
    """Identify students who need help."""
    return ToolResult(
        status=ToolResultStatus.SUCCESS,
        message="Finding students who need help",
        ui_action={"type": "ui.getStudentsNeedingHelp", "payload": {}}
    )


def handle_student_lookup(student_name: str) -> ToolResult:
    """Look up a specific student."""
    return ToolResult(
        status=ToolResultStatus.SUCCESS,
        message=f"Looking up student: {student_name}",
        data={"student_name": student_name},
        ui_action={
            "type": "ui.studentLookup",
            "payload": {"studentName": student_name}
        }
    )


def handle_get_class_status() -> ToolResult:
    """Get overall class status."""
    return ToolResult(
        status=ToolResultStatus.SUCCESS,
        message="Getting class status",
        ui_action={"type": "ui.getClassStatus", "payload": {}}
    )


def handle_get_participation_stats() -> ToolResult:
    """Get participation statistics."""
    return ToolResult(
        status=ToolResultStatus.SUCCESS,
        message="Getting participation statistics",
        ui_action={"type": "ui.getParticipationStats", "payload": {}}
    )


def handle_suggest_next_student() -> ToolResult:
    """Suggest next student to call on."""
    return ToolResult(
        status=ToolResultStatus.SUCCESS,
        message="Suggesting next student",
        ui_action={"type": "ui.suggestNextStudent", "payload": {}}
    )


def handle_get_student_progress(student_name: Optional[str] = None) -> ToolResult:
    """Get student progress."""
    return ToolResult(
        status=ToolResultStatus.SUCCESS,
        message=f"Getting progress for {student_name or 'all students'}",
        data={"student_name": student_name},
        ui_action={
            "type": "ui.getStudentProgress",
            "payload": {"studentName": student_name}
        }
    )


# ============================================================================
# DISCUSSION & CONTENT HANDLERS
# ============================================================================

def handle_summarize_discussion(include_key_points: bool = True) -> ToolResult:
    """Summarize the current discussion using LLM."""
    return ToolResult(
        status=ToolResultStatus.SUCCESS,
        message="Generating discussion summary",
        ui_action={
            "type": "ui.summarizeDiscussion",
            "payload": {"includeKeyPoints": include_key_points}
        }
    )


def handle_get_misconceptions() -> ToolResult:
    """Identify misconceptions in discussion."""
    return ToolResult(
        status=ToolResultStatus.SUCCESS,
        message="Analyzing for misconceptions",
        ui_action={"type": "ui.getMisconceptions", "payload": {}}
    )


def handle_get_student_questions() -> ToolResult:
    """Get unanswered student questions."""
    return ToolResult(
        status=ToolResultStatus.SUCCESS,
        message="Getting student questions",
        ui_action={"type": "ui.getStudentQuestions", "payload": {}}
    )


def handle_get_poll_suggestions() -> ToolResult:
    """Get AI-suggested poll questions."""
    try:
        llm, model_name = get_fast_voice_llm()
        if not llm:
            return ToolResult(
                status=ToolResultStatus.FAILURE,
                message="Poll suggestions temporarily unavailable"
            )

        prompt = """Suggest 3 engaging poll questions for a live class discussion.
Each poll should:
- Have a clear question
- Have 3-4 answer options
- Be relevant to educational discussions
- Encourage participation

Format as numbered list with question and options."""

        response = invoke_llm_with_metrics(llm, prompt, model_name)

        if response.success and response.content:
            return ToolResult(
                status=ToolResultStatus.SUCCESS,
                message="Here are some poll suggestions",
                data={"suggestions": response.content.strip()}
            )

        return ToolResult(
            status=ToolResultStatus.FAILURE,
            message="Could not generate poll suggestions"
        )
    except Exception as e:
        logger.exception(f"Error getting poll suggestions: {e}")
        return ToolResult(
            status=ToolResultStatus.FAILURE,
            message="Error getting poll suggestions"
        )


def handle_read_posts(count: int = 5) -> ToolResult:
    """Read recent discussion posts."""
    return ToolResult(
        status=ToolResultStatus.SUCCESS,
        message=f"Reading the last {count} posts",
        data={"count": count},
        ui_action={
            "type": "ui.readPosts",
            "payload": {"count": count}
        }
    )


# ============================================================================
# AI TEACHING ASSISTANT HANDLERS
# ============================================================================

def handle_generate_ai_draft(question: str, context: Optional[str] = None) -> ToolResult:
    """Generate AI response draft."""
    try:
        llm, model_name = get_fast_voice_llm()
        if not llm:
            return ToolResult(
                status=ToolResultStatus.FAILURE,
                message="AI draft generation temporarily unavailable"
            )

        ctx = f"\nContext: {context}" if context else ""
        prompt = f"""Generate a helpful instructor response to this student question.
Be clear, educational, and encouraging.

Question: {question}{ctx}

Provide a thoughtful response (2-3 paragraphs max)."""

        response = invoke_llm_with_metrics(llm, prompt, model_name)

        if response.success and response.content:
            return ToolResult(
                status=ToolResultStatus.SUCCESS,
                message="AI draft generated",
                data={"draft": response.content.strip(), "question": question}
            )

        return ToolResult(
            status=ToolResultStatus.FAILURE,
            message="Could not generate draft"
        )
    except Exception as e:
        logger.exception(f"Error generating AI draft: {e}")
        return ToolResult(
            status=ToolResultStatus.FAILURE,
            message="Error generating draft"
        )


def handle_get_ai_drafts() -> ToolResult:
    """Get pending AI drafts."""
    return ToolResult(
        status=ToolResultStatus.SUCCESS,
        message="Getting pending AI drafts",
        ui_action={"type": "ui.getAIDrafts", "payload": {}}
    )


def handle_approve_ai_draft(draft_id: Optional[int] = None) -> ToolResult:
    """Approve an AI draft."""
    return ToolResult(
        status=ToolResultStatus.SUCCESS,
        message="Approving AI draft",
        data={"draft_id": draft_id},
        ui_action={
            "type": "ui.approveAIDraft",
            "payload": {"draftId": draft_id}
        }
    )


def handle_reject_ai_draft(draft_id: Optional[int] = None) -> ToolResult:
    """Reject an AI draft."""
    return ToolResult(
        status=ToolResultStatus.SUCCESS,
        message="Rejecting AI draft",
        data={"draft_id": draft_id},
        ui_action={
            "type": "ui.rejectAIDraft",
            "payload": {"draftId": draft_id}
        }
    )


# ============================================================================
# SESSION TEMPLATES & SUMMARIES HANDLERS
# ============================================================================

def handle_save_template(template_name: Optional[str] = None) -> ToolResult:
    """Save session as template."""
    return ToolResult(
        status=ToolResultStatus.SUCCESS,
        message=f"Saving session as template{': ' + template_name if template_name else ''}",
        data={"template_name": template_name},
        ui_action={
            "type": "ui.saveTemplate",
            "payload": {"templateName": template_name}
        }
    )


def handle_clone_session(new_title: Optional[str] = None) -> ToolResult:
    """Clone the current session."""
    return ToolResult(
        status=ToolResultStatus.SUCCESS,
        message=f"Cloning session{': ' + new_title if new_title else ''}",
        data={"new_title": new_title},
        ui_action={
            "type": "ui.cloneSession",
            "payload": {"newTitle": new_title}
        }
    )


def handle_get_session_summary() -> ToolResult:
    """Generate session summary."""
    return ToolResult(
        status=ToolResultStatus.SUCCESS,
        message="Generating session summary",
        ui_action={"type": "ui.getSessionSummary", "payload": {}}
    )


def handle_send_session_summary(method: str = "in_app") -> ToolResult:
    """Send session summary to students."""
    return ToolResult(
        status=ToolResultStatus.SUCCESS,
        message=f"Sending session summary via {method}",
        data={"method": method},
        ui_action={
            "type": "ui.sendSessionSummary",
            "payload": {"method": method}
        }
    )


# ============================================================================
# ANALYTICS HANDLERS
# ============================================================================

def handle_compare_sessions(session_ids: Optional[List[int]] = None) -> ToolResult:
    """Compare multiple sessions."""
    return ToolResult(
        status=ToolResultStatus.SUCCESS,
        message="Comparing sessions",
        data={"session_ids": session_ids},
        ui_action={
            "type": "ui.compareSessions",
            "payload": {"sessionIds": session_ids}
        }
    )


def handle_get_course_analytics() -> ToolResult:
    """Get course analytics."""
    return ToolResult(
        status=ToolResultStatus.SUCCESS,
        message="Getting course analytics",
        ui_action={"type": "ui.getCourseAnalytics", "payload": {}}
    )


# ============================================================================
# LMS INTEGRATION HANDLERS
# ============================================================================

def handle_push_to_canvas(push_type: str = "announcement") -> ToolResult:
    """Push AI summary to Canvas LMS."""
    # First select the push type, then click the push button
    return ToolResult(
        status=ToolResultStatus.SUCCESS,
        message=f"Pushing session summary to Canvas as {push_type}",
        data={"push_type": push_type},
        ui_action={
            "type": "ui.clickButton",
            "payload": {"voiceId": "push-to-canvas"}
        }
    )


def handle_notify_canvas_status() -> ToolResult:
    """Notify Canvas about session status change."""
    return ToolResult(
        status=ToolResultStatus.SUCCESS,
        message="Sending session status notification to Canvas",
        ui_action={
            "type": "ui.clickButton",
            "payload": {"voiceId": "notify-canvas-status"}
        }
    )


def handle_edit_session() -> ToolResult:
    """Open edit session modal."""
    return ToolResult(
        status=ToolResultStatus.SUCCESS,
        message="Opening session editor",
        ui_action={
            "type": "ui.clickButton",
            "payload": {"voiceId": "edit-session"}
        }
    )


def handle_delete_session() -> ToolResult:
    """Delete the selected session."""
    return ToolResult(
        status=ToolResultStatus.SUCCESS,
        message="Opening delete confirmation. Say 'confirm' to delete or 'cancel' to abort.",
        ui_action={
            "type": "ui.clickButton",
            "payload": {"voiceId": "delete-session"}
        }
    )


def handle_generate_questions(count: int = 5) -> ToolResult:
    """Generate quiz questions from session content."""
    return ToolResult(
        status=ToolResultStatus.SUCCESS,
        message=f"Generating {count} quiz questions from the session content",
        data={"count": count},
        ui_action={
            "type": "ui.clickButton",
            "payload": {"voiceId": "generate-questions"}
        }
    )


def handle_create_peer_reviews(reviews_per_submission: int = 2) -> ToolResult:
    """Match students for peer review."""
    return ToolResult(
        status=ToolResultStatus.SUCCESS,
        message=f"Matching students for peer review ({reviews_per_submission} reviewers per submission)",
        data={"reviews_per_submission": reviews_per_submission},
        ui_action={
            "type": "ui.clickButton",
            "payload": {"voiceId": "match-peer-reviews"}
        }
    )


def handle_generate_live_summary() -> ToolResult:
    """Generate live discussion summary."""
    return ToolResult(
        status=ToolResultStatus.SUCCESS,
        message="Generating live discussion summary",
        ui_action={
            "type": "ui.clickButton",
            "payload": {"voiceId": "generate-live-summary"}
        }
    )


# ============================================================================
# UTILITY HANDLERS
# ============================================================================

def handle_undo_action() -> ToolResult:
    """Undo the last action."""
    return ToolResult(
        status=ToolResultStatus.SUCCESS,
        message="Undoing last action",
        ui_action={"type": "ui.undo", "payload": {}}
    )


def handle_toggle_theme(theme: str = "toggle") -> ToolResult:
    """Toggle or set theme."""
    return ToolResult(
        status=ToolResultStatus.SUCCESS,
        message=f"{'Toggling' if theme == 'toggle' else 'Switching to ' + theme} theme",
        ui_action={
            "type": "ui.toggleTheme",
            "payload": {"theme": theme}
        }
    )


def handle_get_help(topic: Optional[str] = None) -> ToolResult:
    """Get help information."""
    help_text = """Available voice commands:
- Navigation: "go to courses", "open sessions", "switch to forum"
- Session: "go live", "end session", "start 5 minute timer"
- Groups: "create breakout groups", "dissolve groups"
- Copilot: "start copilot", "show suggestions"
- Students: "who needs help", "show engagement heatmap"
- Content: "generate syllabus", "summarize discussion"
- Polls: "suggest a poll", "create poll"

Say the name of what you want to do!"""

    return ToolResult(
        status=ToolResultStatus.SUCCESS,
        message=help_text,
        data={"topic": topic, "help": help_text}
    )


def handle_sign_out() -> ToolResult:
    """Sign out of the application."""
    return ToolResult(
        status=ToolResultStatus.SUCCESS,
        message="Signing out",
        ui_action={
            "type": "ui.clickButton",
            "payload": {"target": "sign-out", "voiceId": "sign-out"}
        }
    )


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

        # AI Content Generation tools
        elif tool_name == "generate_syllabus":
            return handle_generate_syllabus(
                parameters.get("course_name", "this course"),
                parameters.get("course_description")
            )

        elif tool_name == "generate_objectives":
            return handle_generate_objectives(
                parameters.get("course_name", "this course"),
                parameters.get("syllabus")
            )

        elif tool_name == "generate_session_plan":
            return handle_generate_session_plan(
                parameters.get("session_title", "this session"),
                parameters.get("course_name"),
                parameters.get("duration_minutes", 60)
            )

        # Session Management tools
        elif tool_name == "go_live":
            return handle_go_live(parameters.get("session_id"))

        elif tool_name == "end_session":
            return handle_end_session(parameters.get("session_id"))

        elif tool_name == "start_timer":
            return handle_start_timer(
                parameters.get("minutes", 5),
                parameters.get("label")
            )

        elif tool_name == "pause_timer":
            return handle_pause_timer()

        elif tool_name == "resume_timer":
            return handle_resume_timer()

        elif tool_name == "stop_timer":
            return handle_stop_timer()

        elif tool_name == "get_timer_status":
            return handle_get_timer_status()

        # Breakout Groups tools
        elif tool_name == "create_breakout_groups":
            return handle_create_breakout_groups(
                parameters.get("num_groups", 4),
                parameters.get("strategy", "random"),
                parameters.get("topic")
            )

        elif tool_name == "get_breakout_groups":
            return handle_get_breakout_groups()

        elif tool_name == "dissolve_breakout_groups":
            return handle_dissolve_breakout_groups()

        # AI Copilot tools
        elif tool_name == "start_copilot":
            return handle_start_copilot()

        elif tool_name == "stop_copilot":
            return handle_stop_copilot()

        elif tool_name == "get_copilot_suggestions":
            return handle_get_copilot_suggestions()

        elif tool_name == "get_facilitation_suggestions":
            return handle_get_facilitation_suggestions()

        # Student Monitoring tools
        elif tool_name == "get_engagement_heatmap":
            return handle_get_engagement_heatmap()

        elif tool_name == "get_disengaged_students":
            return handle_get_disengaged_students()

        elif tool_name == "who_needs_help":
            return handle_who_needs_help()

        elif tool_name == "student_lookup":
            return handle_student_lookup(parameters.get("student_name", ""))

        elif tool_name == "get_class_status":
            return handle_get_class_status()

        elif tool_name == "get_participation_stats":
            return handle_get_participation_stats()

        elif tool_name == "suggest_next_student":
            return handle_suggest_next_student()

        elif tool_name == "get_student_progress":
            return handle_get_student_progress(parameters.get("student_name"))

        # Discussion & Content tools
        elif tool_name == "summarize_discussion":
            return handle_summarize_discussion(parameters.get("include_key_points", True))

        elif tool_name == "get_misconceptions":
            return handle_get_misconceptions()

        elif tool_name == "get_student_questions":
            return handle_get_student_questions()

        elif tool_name == "get_poll_suggestions":
            return handle_get_poll_suggestions()

        elif tool_name == "read_posts":
            return handle_read_posts(parameters.get("count", 5))

        # AI Teaching Assistant tools
        elif tool_name == "generate_ai_draft":
            return handle_generate_ai_draft(
                parameters.get("question", ""),
                parameters.get("context")
            )

        elif tool_name == "get_ai_drafts":
            return handle_get_ai_drafts()

        elif tool_name == "approve_ai_draft":
            return handle_approve_ai_draft(parameters.get("draft_id"))

        elif tool_name == "reject_ai_draft":
            return handle_reject_ai_draft(parameters.get("draft_id"))

        # Session Templates & Summaries tools
        elif tool_name == "save_template":
            return handle_save_template(parameters.get("template_name"))

        elif tool_name == "clone_session":
            return handle_clone_session(parameters.get("new_title"))

        elif tool_name == "get_session_summary":
            return handle_get_session_summary()

        elif tool_name == "send_session_summary":
            return handle_send_session_summary(parameters.get("method", "in_app"))

        # Analytics tools
        elif tool_name == "compare_sessions":
            return handle_compare_sessions(parameters.get("session_ids"))

        elif tool_name == "get_course_analytics":
            return handle_get_course_analytics()

        # LMS Integration tools
        elif tool_name == "push_to_canvas":
            return handle_push_to_canvas(parameters.get("push_type", "announcement"))

        elif tool_name == "notify_canvas_status":
            return handle_notify_canvas_status()

        # Session management tools
        elif tool_name == "edit_session":
            return handle_edit_session()

        elif tool_name == "delete_session":
            return handle_delete_session()

        # Enhanced AI feature tools
        elif tool_name == "generate_questions":
            return handle_generate_questions(parameters.get("count", 5))

        elif tool_name == "create_peer_reviews":
            return handle_create_peer_reviews(parameters.get("reviews_per_submission", 2))

        elif tool_name == "generate_live_summary":
            return handle_generate_live_summary()

        # Utility tools
        elif tool_name == "undo_action":
            return handle_undo_action()

        elif tool_name == "toggle_theme":
            return handle_toggle_theme(parameters.get("theme", "toggle"))

        elif tool_name == "get_help":
            return handle_get_help(parameters.get("topic"))

        elif tool_name == "sign_out":
            return handle_sign_out()

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
