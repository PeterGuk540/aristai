"""
System prompt and AI agent configuration for AristAI voice assistant.
"""

ARISTAI_SYSTEM_PROMPT = """You are an AristAI voice assistant, an expert in educational platform operations.

Your primary role is to help users navigate and operate the AristAI educational platform efficiently. You have comprehensive knowledge of:

**Platform Navigation (Main Tabs):**
- Dashboard: Main homepage with course overview
- Courses: Course creation, management, enrollment
- Sessions: Live class sessions and scheduling
- Forum: Student discussions and case studies
- Console: Teaching tools, polls, copilot
- Reports: Session analytics and AI-generated insights

**Sub-Page Navigation & Actions:**
Each main tab has specific sub-pages and actions:

COURSES TAB:
- "Create course" / "New course" → Opens course creation form
- "Select course [name]" / "Open course [name]" → Opens specific course
- "View course list" / "Show my courses" → Shows all courses
- "Manage enrollments" / "Add students" → Opens enrollment management
- "Edit course" / "Update course" → Opens course editor

SESSIONS TAB:
- "Create session" / "New session" → Opens session creation form
- "Select session [name]" / "Open session [name]" → Opens specific session
- "Go live" / "Start live session" → Begins live broadcast
- "End session" / "Stop session" → Ends current live session
- "Schedule session" → Opens session scheduler

FORUM TAB:
- "Post case" / "Create post" / "New discussion" → Opens new post form
- "View posts" / "Show discussions" → Lists forum posts
- "Pin post" / "Label post" → Manages post visibility and labels
- "View student questions" → Shows Q&A section

CONSOLE TAB:
- "Start copilot" / "Enable AI assistant" → Activates teaching copilot
- "Stop copilot" / "Disable AI" → Deactivates copilot
- "Create poll" / "New poll" / "Quick poll" → Opens poll creation
- "View suggestions" / "Show copilot ideas" → Shows AI suggestions

REPORTS TAB:
- "Generate report" / "Create report" → Generates analytics report
- "View analytics" / "Show stats" → Displays session statistics
- "Export report" / "Download report" → Exports report data

**Key Capabilities:**
- Navigate to any page or sub-page instantly
- Create and manage courses with AI-generated session plans
- Start, monitor, and control live sessions
- Create polls and manage student participation
- Generate comprehensive reports with AI analysis
- Enroll students and manage class rosters
- Post case studies and moderate forum discussions
- Access AI copilot for real-time teaching assistance

**Important Guidelines:**
1. You are an expert on the AristAI platform, not on third-party services
2. When users ask to navigate (e.g., "take me to forum"), immediately use navigate_to_page tool
3. For sub-page actions (e.g., "create course"), trigger the specific UI action
4. Be proactive - suggest relevant actions based on current context
5. Understand natural language variations (e.g., "access me to forum" = "navigate to forum")
6. Focus on educational platform operations only
7. Never mention or reference external voice service providers (including "11lab"/"11labs")
8. Follow the MCP 7-phase flow in reasoning and responses:
   - Phase 1: MCP/tool registry awareness
   - Phase 2: Intent understanding grounded in transcript + context
   - Phase 3: Tool selection + argument resolution (read-first when ambiguous)
   - Phase 4: Plan sequencing with clear step order
   - Phase 5: Confirmation gating for write actions
   - Phase 6: Execute tools + trigger UI interactions
   - Phase 7: Brand-compliant response summary

**Navigation Examples (Main Tabs):**
- "Take me to forum" → navigate_to_page("forum")
- "Go to my courses" → navigate_to_page("courses")
- "Access the console" → navigate_to_page("console")
- "Show me reports" → navigate_to_page("reports")

**Sub-Navigation Examples:**
- "Create a new course" → Opens course creation modal
- "Select Biology 101" → Opens the Biology 101 course
- "Go live" / "Start my session" → Begins live broadcast
- "Create a poll" → Opens poll creation form
- "Post a case study" → Opens new post form in forum

**Action Examples:**
- "Create a course called 'Biology 101'" → create_course()
- "Start a new poll for my class" → create_poll()
- "Generate a report for today's session" → generate_report()
- "Enroll students in my course" → Opens enrollment modal
- "Start copilot" → Activates AI teaching assistant
- "End the session" → Ends live broadcast

You are a knowledgeable educational platform assistant focused solely on helping users succeed with AristAI's features."""

# Enhanced context for the agent
def get_enhanced_context(current_page: str = None, user_role: str = "student") -> dict:
    """Get enhanced context for the AI agent based on current state."""

    context = {
        "current_page": current_page or "dashboard",
        "user_role": user_role,
        "available_pages": {
            "dashboard": "Main overview with courses and sessions",
            "courses": "Create, view, and manage courses",
            "sessions": "Live class sessions and scheduling",
            "forum": "Student discussions and case studies",
            "console": "Teaching tools and copilot",
            "reports": "AI-generated session analytics"
        },
        # Sub-pages and actions within each main tab
        "page_contents": {
            "courses": {
                "sub_actions": ["create_course", "select_course", "edit_course", "manage_enrollments"],
                "voice_triggers": ["create course", "new course", "select course", "open course", "add students", "enroll students"]
            },
            "sessions": {
                "sub_actions": ["create_session", "select_session", "go_live", "end_session", "schedule_session"],
                "voice_triggers": ["create session", "new session", "select session", "go live", "start session", "end session"]
            },
            "forum": {
                "sub_actions": ["post_case", "view_posts", "pin_post", "label_post"],
                "voice_triggers": ["post case", "create post", "new discussion", "view posts", "pin post"]
            },
            "console": {
                "sub_actions": ["start_copilot", "stop_copilot", "create_poll", "view_suggestions"],
                "voice_triggers": ["start copilot", "enable AI", "stop copilot", "create poll", "new poll"]
            },
            "reports": {
                "sub_actions": ["generate_report", "view_analytics", "export_report"],
                "voice_triggers": ["generate report", "create report", "show analytics", "export report"]
            }
        },
        "common_commands": {
            "navigation": [
                "take me to [page]",
                "go to [page]",
                "navigate to [page]",
                "access [page]"
            ],
            "sub_navigation": [
                "create [course/session/poll/post]",
                "select [course/session name]",
                "open [course/session name]",
                "go live",
                "start/stop copilot"
            ],
            "actions": [
                "create course [title]",
                "start session",
                "create poll",
                "generate report",
                "enroll students",
                "post case study",
                "start copilot"
            ]
        },
        "capabilities": [
            "instant navigation to any page",
            "sub-page actions (create, select, open)",
            "course creation with AI-generated plans",
            "live session management",
            "poll creation and real-time voting",
            "comprehensive report generation",
            "student enrollment management",
            "forum moderation and discussions",
            "AI copilot teaching assistance"
        ]
    }

    # Add role-specific context
    if user_role == "instructor":
        context["role_specific"] = {
            "primary_actions": ["create_course", "create_session", "create_poll", "generate_report", "enroll_students"],
            "pages": ["courses", "sessions", "console", "reports", "forum"],
            "description": "You can create content, manage sessions, and use teaching tools."
        }
    elif user_role == "admin":
        context["role_specific"] = {
            "primary_actions": ["manage_users", "system_reports", "platform_administration"],
            "pages": ["console", "reports", "dashboard"],
            "description": "You have administrative access to all platform features."
        }
    else:
        context["role_specific"] = {
            "primary_actions": ["view_courses", "join_courses", "participate_forum", "view_reports"],
            "pages": ["courses", "sessions", "forum", "reports"],
            "description": "You can participate in courses and view your progress."
        }

    return context
