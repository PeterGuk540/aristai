"""
Voice Page Registry - Ground Truth for Application Structure

This module provides the SINGLE SOURCE OF TRUTH for:
1. What pages exist in the application
2. What tabs exist on each page
3. What actions/features are available on each page+tab
4. What workflows require multi-step navigation

The LLM uses this registry to:
- Verify that a tab exists on the current page before switching
- Determine navigation prerequisites (must go to /sessions before switching to ai-features)
- Execute complete workflows as atomic operations

NO REGEX OR KEYWORD MATCHING - This is structured data for the LLM to reason about.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set
from enum import Enum


# ============================================================================
# PAGE STRUCTURE DEFINITIONS
# ============================================================================

@dataclass
class TabDefinition:
    """Definition of a tab on a page."""
    voice_id: str  # The data-voice-id attribute (e.g., "tab-sessions")
    label: str  # Display label (e.g., "Sessions")
    description: str  # What this tab is for
    features: List[str] = field(default_factory=list)  # What can be done here
    requires_instructor: bool = False  # Only visible to instructors


@dataclass
class PageDefinition:
    """Definition of a page in the application."""
    route: str  # URL path (e.g., "/courses")
    name: str  # Human-readable name
    description: str  # What this page is for
    tabs: List[TabDefinition] = field(default_factory=list)
    default_tab: Optional[str] = None  # Default tab voice_id


# ============================================================================
# APPLICATION PAGE REGISTRY
# ============================================================================

PAGE_REGISTRY: Dict[str, PageDefinition] = {
    "/courses": PageDefinition(
        route="/courses",
        name="Courses",
        description="Course management - create courses, manage enrollments, view AI insights",
        default_tab="tab-courses",
        tabs=[
            TabDefinition(
                voice_id="tab-courses",
                label="Courses",
                description="View and select courses",
                features=["view courses", "select course", "see course details"]
            ),
            TabDefinition(
                voice_id="tab-create",
                label="Create",
                description="Create a new course with syllabus",
                features=["create course", "add syllabus", "set learning objectives"],
                requires_instructor=True
            ),
            TabDefinition(
                voice_id="tab-join",
                label="Join",
                description="Join a course with join code (students only)",
                features=["join course", "enter join code"]
            ),
            TabDefinition(
                voice_id="tab-advanced",
                label="Advanced",
                description="ENROLLMENT MANAGEMENT - add/remove students, manage instructor access",
                features=["enroll students", "manage enrollment", "add students", "remove students",
                         "bulk upload students", "manage instructor access"],
                requires_instructor=True
            ),
            TabDefinition(
                voice_id="tab-ai-insights",
                label="AI Insights",
                description="AI-powered participation insights and objective coverage for courses",
                features=["participation insights", "objective coverage", "course analytics"],
                requires_instructor=True
            ),
        ]
    ),

    "/sessions": PageDefinition(
        route="/sessions",
        name="Sessions",
        description="Session management - create sessions, manage status, upload materials, AI features",
        default_tab="tab-sessions",
        tabs=[
            TabDefinition(
                voice_id="tab-sessions",
                label="Sessions",
                description="View and select sessions",
                features=["view sessions", "select session", "see session details"]
            ),
            TabDefinition(
                voice_id="tab-materials",
                label="Materials",
                description="Upload and manage course materials",
                features=["upload materials", "manage files", "add PDFs"]
            ),
            TabDefinition(
                voice_id="tab-create",
                label="Create",
                description="Create a new session",
                features=["create session", "new session"],
                requires_instructor=True
            ),
            TabDefinition(
                voice_id="tab-manage",
                label="Manage",
                description="Change session status (draft/scheduled/live/completed)",
                features=["start session", "go live", "end session", "complete session",
                         "schedule session", "manage status"],
                requires_instructor=True
            ),
            TabDefinition(
                voice_id="tab-insights",
                label="Insights",
                description="View session engagement and analytics",
                features=["session insights", "engagement analytics", "participation metrics"],
                requires_instructor=True
            ),
            TabDefinition(
                voice_id="tab-ai-features",
                label="AI Features",
                description="AI-enhanced features: live summary, question bank, peer review",
                features=["live summary", "generate summary", "question bank", "generate questions",
                         "peer review", "AI features", "enhanced features"],
                requires_instructor=True
            ),
        ]
    ),

    "/console": PageDefinition(
        route="/console",
        name="Console",
        description="Live instructor console - monitor and interact with a LIVE session in real-time",
        default_tab="tab-copilot",
        tabs=[
            TabDefinition(
                voice_id="tab-copilot",
                label="Copilot",
                description="AI copilot suggestions and interventions",
                features=["start copilot", "stop copilot", "AI suggestions", "interventions"]
            ),
            TabDefinition(
                voice_id="tab-polls",
                label="Polls",
                description="Create and monitor live polls",
                features=["create poll", "launch poll", "view poll results", "close poll"]
            ),
            TabDefinition(
                voice_id="tab-cases",
                label="Cases",
                description="Post case studies for discussion",
                features=["post case", "case study", "discussion prompt"]
            ),
            TabDefinition(
                voice_id="tab-tools",
                label="Tools",
                description="Instructor tools: timer, breakout groups, heatmap, facilitation",
                features=["timer", "breakout groups", "engagement heatmap", "facilitation suggestions"]
            ),
            TabDefinition(
                voice_id="tab-requests",
                label="Requests",
                description="View instructor access requests",
                features=["access requests", "approve request"]
            ),
            TabDefinition(
                voice_id="tab-roster",
                label="Roster",
                description="Upload student roster",
                features=["upload roster", "student list", "CSV upload"]
            ),
        ]
    ),

    "/forum": PageDefinition(
        route="/forum",
        name="Forum",
        description="Discussion forum - view and participate in session discussions",
        default_tab="tab-discussion",
        tabs=[
            TabDefinition(
                voice_id="tab-discussion",
                label="Discussion",
                description="View posts and replies",
                features=["view posts", "read discussion", "reply to post", "pin post"]
            ),
            TabDefinition(
                voice_id="tab-cases",
                label="Cases",
                description="View case studies",
                features=["view cases", "case studies"]
            ),
        ]
    ),

    "/reports": PageDefinition(
        route="/reports",
        name="Reports",
        description="Analytics and reports - view session reports and course analytics",
        default_tab="tab-summary",
        tabs=[
            TabDefinition(
                voice_id="tab-summary",
                label="Summary",
                description="Report overview",
                features=["view summary", "session summary", "report overview"]
            ),
            TabDefinition(
                voice_id="tab-participation",
                label="Participation",
                description="Participation metrics",
                features=["participation metrics", "who participated", "engagement"]
            ),
            TabDefinition(
                voice_id="tab-scoring",
                label="Scoring",
                description="Student scores",
                features=["student scores", "grades", "scoring"]
            ),
            TabDefinition(
                voice_id="tab-analytics",
                label="Analytics",
                description="Course-level analytics",
                features=["course analytics", "trends", "session comparisons"]
            ),
        ]
    ),

    "/integrations": PageDefinition(
        route="/integrations",
        name="Integrations",
        description="LMS integrations - connect to Canvas, UPP, import courses",
        tabs=[
            TabDefinition(
                voice_id="tab-canvas",
                label="Canvas",
                description="Canvas LMS integration",
                features=["connect canvas", "import from canvas", "push to canvas"]
            ),
            TabDefinition(
                voice_id="tab-upp",
                label="UPP",
                description="UPP system integration",
                features=["connect UPP", "import from UPP"]
            ),
        ]
    ),

    "/dashboard": PageDefinition(
        route="/dashboard",
        name="Dashboard",
        description="Main dashboard - overview of courses and sessions",
        tabs=[]
    ),

    "/profile": PageDefinition(
        route="/profile",
        name="Profile",
        description="User profile settings",
        tabs=[]
    ),

    "/platform-guide": PageDefinition(
        route="/platform-guide",
        name="Platform Guide",
        description="Introduction to the platform",
        tabs=[]
    ),
}


# ============================================================================
# WORKFLOW DEFINITIONS
# ============================================================================

@dataclass
class WorkflowStep:
    """A single step in a workflow."""
    action: str  # "navigate", "switch_tab", "click_button", "fill_input", "select_dropdown"
    target: str  # voice_id or route
    description: str
    wait_for_load: bool = False  # Wait for page/UI to stabilize


@dataclass
class WorkflowDefinition:
    """A multi-step workflow that accomplishes a task."""
    name: str
    description: str
    triggers: List[str]  # Natural language phrases that trigger this workflow
    steps: List[WorkflowStep]
    required_context: List[str] = field(default_factory=list)  # e.g., ["course_selected"]


WORKFLOW_REGISTRY: Dict[str, WorkflowDefinition] = {
    "enroll_students": WorkflowDefinition(
        name="enroll_students",
        description="Navigate to enrollment management to add/remove students",
        triggers=[
            "enroll students", "add students", "manage enrollment",
            "bulk upload students", "student enrollment", "enrollar estudiantes"
        ],
        steps=[
            WorkflowStep("navigate", "/courses", "Go to courses page", wait_for_load=True),
            WorkflowStep("switch_tab", "tab-advanced", "Switch to advanced tab for enrollment"),
        ]
    ),

    "view_ai_features": WorkflowDefinition(
        name="view_ai_features",
        description="Navigate to AI features tab on sessions page",
        triggers=[
            "AI features", "enhanced features", "live summary", "question bank",
            "peer review", "funciones de IA", "caracteristicas de IA"
        ],
        steps=[
            WorkflowStep("navigate", "/sessions", "Go to sessions page", wait_for_load=True),
            WorkflowStep("switch_tab", "tab-ai-features", "Switch to AI features tab"),
        ]
    ),

    "create_poll": WorkflowDefinition(
        name="create_poll",
        description="Navigate to console and create a poll",
        triggers=[
            "create poll", "new poll", "launch poll", "crear encuesta"
        ],
        steps=[
            WorkflowStep("navigate", "/console", "Go to console page", wait_for_load=True),
            WorkflowStep("switch_tab", "tab-polls", "Switch to polls tab"),
            WorkflowStep("click_button", "create-poll", "Click create poll button"),
        ]
    ),

    "start_session": WorkflowDefinition(
        name="start_session",
        description="Navigate to session management and go live",
        triggers=[
            "start session", "go live", "begin class", "iniciar sesion", "comenzar clase"
        ],
        steps=[
            WorkflowStep("navigate", "/sessions", "Go to sessions page", wait_for_load=True),
            WorkflowStep("switch_tab", "tab-manage", "Switch to manage tab"),
            WorkflowStep("click_button", "go-live", "Click go live button"),
        ],
        required_context=["session_selected"]
    ),

    "create_course": WorkflowDefinition(
        name="create_course",
        description="Navigate to course creation",
        triggers=[
            "create course", "new course", "crear curso", "nuevo curso"
        ],
        steps=[
            WorkflowStep("navigate", "/courses", "Go to courses page", wait_for_load=True),
            WorkflowStep("switch_tab", "tab-create", "Switch to create tab"),
        ]
    ),

    "view_participation": WorkflowDefinition(
        name="view_participation",
        description="View participation insights for a course",
        triggers=[
            "participation insights", "who participated", "engagement",
            "participation metrics", "ver participacion"
        ],
        steps=[
            WorkflowStep("navigate", "/courses", "Go to courses page", wait_for_load=True),
            WorkflowStep("switch_tab", "tab-ai-insights", "Switch to AI insights tab"),
        ]
    ),

    "upload_materials": WorkflowDefinition(
        name="upload_materials",
        description="Upload course materials for a session",
        triggers=[
            "upload materials", "add materials", "upload PDF", "subir materiales"
        ],
        steps=[
            WorkflowStep("navigate", "/sessions", "Go to sessions page", wait_for_load=True),
            WorkflowStep("switch_tab", "tab-materials", "Switch to materials tab"),
        ]
    ),
}


# ============================================================================
# REGISTRY QUERY FUNCTIONS
# ============================================================================

def get_page(route: str) -> Optional[PageDefinition]:
    """Get page definition by route."""
    # Handle routes with IDs (e.g., /courses/123)
    base_route = "/" + route.strip("/").split("/")[0] if route else None
    if base_route:
        return PAGE_REGISTRY.get(base_route) or PAGE_REGISTRY.get(route)
    return PAGE_REGISTRY.get(route)


def get_tabs_for_page(route: str) -> List[TabDefinition]:
    """Get all tabs available on a page."""
    page = get_page(route)
    return page.tabs if page else []


def get_tab_voice_ids_for_page(route: str) -> List[str]:
    """Get list of tab voice_ids for a page."""
    return [tab.voice_id for tab in get_tabs_for_page(route)]


def is_tab_on_page(tab_voice_id: str, route: str) -> bool:
    """Check if a tab exists on a specific page."""
    return tab_voice_id in get_tab_voice_ids_for_page(route)


def find_tab_page(tab_voice_id: str) -> Optional[str]:
    """Find which page a tab belongs to."""
    for route, page in PAGE_REGISTRY.items():
        for tab in page.tabs:
            if tab.voice_id == tab_voice_id:
                return route
    return None


def find_feature_location(feature: str) -> Optional[tuple]:
    """Find which page and tab a feature is on.

    Returns: (route, tab_voice_id) or None
    """
    feature_lower = feature.lower()
    for route, page in PAGE_REGISTRY.items():
        for tab in page.tabs:
            for tab_feature in tab.features:
                if feature_lower in tab_feature.lower() or tab_feature.lower() in feature_lower:
                    return (route, tab.voice_id)
    return None


def get_workflow(intent: str) -> Optional[WorkflowDefinition]:
    """Find a workflow that matches the user's intent."""
    intent_lower = intent.lower()
    for workflow in WORKFLOW_REGISTRY.values():
        for trigger in workflow.triggers:
            if trigger.lower() in intent_lower or intent_lower in trigger.lower():
                return workflow
    return None


def get_navigation_steps(current_route: str, target_tab: str) -> List[WorkflowStep]:
    """Get the steps needed to navigate to a target tab from current location.

    Returns list of steps: may include navigation if tab is on different page.
    """
    steps = []

    # Find which page the target tab is on
    target_page = find_tab_page(target_tab)

    if target_page is None:
        return []  # Tab not found in registry

    # Check if we need to navigate to a different page
    current_base = "/" + current_route.strip("/").split("/")[0] if current_route else ""

    if current_base != target_page:
        # Need to navigate first
        steps.append(WorkflowStep(
            action="navigate",
            target=target_page,
            description=f"Navigate to {PAGE_REGISTRY[target_page].name}",
            wait_for_load=True
        ))

    # Then switch to the tab
    steps.append(WorkflowStep(
        action="switch_tab",
        target=target_tab,
        description=f"Switch to tab"
    ))

    return steps


# ============================================================================
# CONTEXT GENERATION FOR LLM
# ============================================================================

def generate_page_context_for_llm(current_route: str) -> str:
    """Generate a structured context string for the LLM about the current page."""
    page = get_page(current_route)

    if not page:
        return f"Current page: {current_route} (unknown page)"

    lines = [
        f"Current page: {page.name} ({page.route})",
        f"Description: {page.description}",
        "",
        "Available tabs on THIS page:"
    ]

    for tab in page.tabs:
        features_str = ", ".join(tab.features[:3])
        if len(tab.features) > 3:
            features_str += "..."
        lines.append(f"  - {tab.voice_id}: {tab.label} - {tab.description}")
        lines.append(f"    Features: {features_str}")

    if not page.tabs:
        lines.append("  (No tabs on this page)")

    return "\n".join(lines)


def generate_full_topology_for_llm() -> str:
    """Generate a complete page topology for the LLM prompt."""
    lines = ["=== APPLICATION PAGE TOPOLOGY ===", ""]

    for route, page in PAGE_REGISTRY.items():
        lines.append(f"## {page.name} ({route})")
        lines.append(f"{page.description}")

        if page.tabs:
            lines.append("Tabs:")
            for tab in page.tabs:
                lines.append(f"  - {tab.voice_id}: {tab.label}")
                lines.append(f"    → {tab.description}")
        else:
            lines.append("(No tabs)")

        lines.append("")

    lines.append("=== IMPORTANT RULES ===")
    lines.append("1. ENROLLMENT is under /courses → tab-advanced (NOT create tab)")
    lines.append("2. AI FEATURES is under /sessions → tab-ai-features")
    lines.append("3. POLLS are under /console → tab-polls")
    lines.append("4. If target tab is on DIFFERENT page, NAVIGATE FIRST then SWITCH TAB")

    return "\n".join(lines)
