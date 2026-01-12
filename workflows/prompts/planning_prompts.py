"""
Prompts for the Planning Workflow.

These prompts guide the LLM through the syllabus-to-session-plans pipeline.
"""

PARSE_SYLLABUS_PROMPT = """You are an expert curriculum designer. Analyze the following course syllabus and learning objectives.

COURSE TITLE: {course_title}

SYLLABUS:
{syllabus_text}

LEARNING OBJECTIVES:
{objectives}

Extract and return a structured analysis in JSON format:
{{
    "course_summary": "Brief 2-3 sentence summary of the course",
    "total_sessions": <number of sessions/classes to plan>,
    "main_topics": ["topic1", "topic2", ...],
    "key_concepts": ["concept1", "concept2", ...],
    "suggested_readings_themes": ["theme1", "theme2", ...],
    "objectives_breakdown": [
        {{"objective": "...", "related_topics": ["..."]}}
    ]
}}

Guidelines:
- Determine the number of sessions based on syllabus structure (look for weeks, modules, or logical divisions)
- If not explicitly stated, assume 10-12 sessions for a typical course
- Extract main topics that should be covered across all sessions
- Identify key concepts students must understand
- Map each objective to related topics

Return ONLY valid JSON, no additional text."""


PLAN_SESSION_PROMPT = """You are an expert instructional designer. Create a detailed plan for Session {session_number} of {total_sessions}.

COURSE: {course_title}
COURSE SUMMARY: {course_summary}

TOPICS TO COVER THIS SESSION:
{session_topics}

RELEVANT OBJECTIVES:
{relevant_objectives}

KEY CONCEPTS FROM SYLLABUS:
{key_concepts}

PREVIOUS SESSIONS COVERED:
{previous_sessions}

Create a session plan in JSON format:
{{
    "session_number": {session_number},
    "title": "Descriptive session title",
    "topics": ["specific topic 1", "specific topic 2"],
    "learning_goals": ["By end of session, students will..."],
    "readings": [
        {{"title": "Reading title", "type": "article|chapter|video", "description": "Brief description"}}
    ],
    "case_prompt": "A realistic case study or problem scenario for discussion (2-4 sentences)",
    "discussion_prompts": [
        "Open-ended question 1 to spark discussion",
        "Follow-up question to deepen analysis"
    ],
    "key_takeaways": ["Main point 1", "Main point 2"]
}}

Guidelines:
- Title should be specific and engaging
- Include 2-4 specific topics for this session
- Suggest 1-3 relevant readings (can be hypothetical but realistic)
- Case prompt should be practical and relate to real-world application
- Discussion prompts should encourage critical thinking
- Avoid overlap with previous sessions

Return ONLY valid JSON, no additional text."""


DESIGN_FLOW_PROMPT = """You are an expert facilitator designing the instructional flow for a class session.

SESSION PLAN:
{session_plan}

Design the class flow with timing and interaction checkpoints in JSON format:
{{
    "flow": [
        {{"phase": "intro", "duration_minutes": 5, "activity": "Welcome and session overview"}},
        {{"phase": "theory", "duration_minutes": 15, "activity": "Present key concepts: ..."}},
        {{"phase": "case", "duration_minutes": 10, "activity": "Introduce case study"}},
        {{"phase": "discussion", "duration_minutes": 20, "activity": "Facilitated discussion"}},
        {{"phase": "wrap-up", "duration_minutes": 5, "activity": "Summary and preview"}}
    ],
    "checkpoints": [
        {{
            "type": "poll",
            "timing": "after_theory",
            "question": "Quick comprehension check question",
            "options": ["Option A", "Option B", "Option C"]
        }},
        {{
            "type": "quick_write",
            "timing": "before_discussion",
            "prompt": "Brief reflection prompt"
        }}
    ],
    "total_duration_minutes": 55
}}

Guidelines:
- Standard session is 50-60 minutes
- Include at least one poll for engagement
- Place checkpoints at natural transition points
- Balance lecture and interaction time (aim for 40% interactive)

Return ONLY valid JSON, no additional text."""


CONSISTENCY_CHECK_PROMPT = """You are a curriculum quality assurance expert. Review these session plans for consistency and completeness.

COURSE TITLE: {course_title}

LEARNING OBJECTIVES:
{objectives}

SESSION PLANS:
{session_plans}

Analyze and return a quality report in JSON format:
{{
    "objectives_coverage": {{
        "fully_covered": ["objective 1", ...],
        "partially_covered": ["objective X", ...],
        "not_covered": ["objective Y", ...]
    }},
    "issues": [
        {{"session": 1, "issue": "Description of issue", "severity": "low|medium|high"}}
    ],
    "suggestions": [
        {{"session": 1, "suggestion": "Improvement suggestion"}}
    ],
    "overall_quality_score": <1-10>,
    "summary": "Brief overall assessment"
}}

Check for:
- All objectives are addressed across sessions
- No major topic gaps or excessive overlap
- Logical progression of difficulty
- Balanced workload across sessions
- Case studies are varied and relevant

Return ONLY valid JSON, no additional text."""
