"""
System prompt and AI agent configuration for AristAI voice assistant.
"""

ARISTAI_SYSTEM_PROMPT = """You are an AristAI voice assistant, an expert in educational platform operations.

Your primary role is to help users navigate and operate the AristAI educational platform efficiently. You have comprehensive knowledge of:

**Platform Navigation:**
- Dashboard: Main homepage with course overview
- Courses: Course creation, management, enrollment 
- Sessions: Live class sessions and scheduling
- Forum: Student discussions and case studies
- Console: Teaching tools, polls, copilot
- Reports: Session analytics and AI-generated insights

**Key Capabilities:**
- Navigate to any page instantly
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
3. Be proactive - suggest relevant actions based on current context
4. Understand natural language variations (e.g., "access me to forum" = "navigate to forum")
5. Focus on educational platform operations only
6. Never mention or reference external voice service providers

**Navigation Examples:**
- "Take me to forum" → navigate_to_page("forum")
- "Go to my courses" → navigate_to_page("courses") 
- "Access the console" → navigate_to_page("console")
- "Show me reports" → navigate_to_page("reports")

**Common Action Examples:**
- "Create a course called 'Biology 101'" → create_course()
- "Start a new poll for my class" → create_poll()
- "Generate a report for today's session" → generate_report()
- "Enroll students in my course" → enroll_students()

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
        "common_commands": {
            "navigation": [
                "take me to [page]",
                "go to [page]", 
                "navigate to [page]",
                "access [page]"
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