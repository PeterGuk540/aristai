"""
Prompts for the Report Workflow.

These prompts guide the LLM through generating post-discussion feedback reports.
All prompts require explicit post_id citations to prevent hallucination.
"""

CLUSTER_POSTS_PROMPT = """You are an expert discussion analyst. Analyze the following discussion posts and identify thematic clusters.

SESSION TITLE: {session_title}
SESSION TOPICS: {session_topics}

DISCUSSION POSTS:
{posts_formatted}

Identify 3-5 thematic clusters in the discussion. For each cluster, cite the specific post IDs that belong to it.

Return JSON format:
{{
    "clusters": [
        {{
            "theme": "Theme name",
            "description": "Brief description of what this cluster covers",
            "post_ids": [1, 2, 5],
            "key_points": ["Point raised in this cluster"]
        }}
    ],
    "unclustered_posts": [3, 7],
    "discussion_quality": "high|medium|low",
    "participation_summary": {{
        "total_posts": <number>,
        "student_posts": <number>,
        "instructor_posts": <number>
    }}
}}

Guidelines:
- Every post_id you cite MUST exist in the posts provided above
- If a post doesn't fit any cluster, include it in unclustered_posts
- Do not invent or hallucinate post IDs
- Base themes only on actual post content

Return ONLY valid JSON, no additional text."""


ALIGN_OBJECTIVES_PROMPT = """You are a curriculum alignment expert. Map the discussion themes to the course learning objectives.

LEARNING OBJECTIVES:
{objectives}

DISCUSSION CLUSTERS:
{clusters_json}

POSTS CONTENT (for reference):
{posts_formatted}

Analyze how the discussion aligns with learning objectives.

Return JSON format:
{{
    "objective_alignment": [
        {{
            "objective": "The learning objective text",
            "coverage": "fully|partially|not_covered",
            "evidence_post_ids": [1, 2],
            "explanation": "How this objective was addressed (or why not)"
        }}
    ],
    "strong_contributions": [
        {{
            "post_id": 5,
            "reason": "Why this contribution was valuable",
            "related_objectives": ["Objective 1"]
        }}
    ],
    "gaps": ["Topics that should have been discussed but weren't"]
}}

Guidelines:
- Only cite post_ids that exist in the provided posts
- If an objective has no supporting posts, say "insufficient evidence from discussion"
- Strong contributions must have specific, verifiable reasons tied to post content

Return ONLY valid JSON, no additional text."""


MISCONCEPTIONS_PROMPT = """You are an expert educator identifying misconceptions. Analyze the discussion for incorrect or incomplete understanding.

SESSION TOPICS: {session_topics}

SYLLABUS/COURSE MATERIAL:
{syllabus_text}

COURSE RESOURCES:
{resources_text}

DISCUSSION POSTS:
{posts_formatted}

Identify misconceptions in student posts and provide corrections grounded in the course materials.

Return JSON format:
{{
    "misconceptions": [
        {{
            "post_id": 3,
            "misconception": "What the student got wrong or incomplete",
            "quote": "Relevant quote from the post",
            "correction": "The correct understanding",
            "source": "Where in syllabus/resources this is addressed (or 'general knowledge' if basic)"
        }}
    ],
    "common_confusion_points": [
        "Topics where multiple students showed confusion"
    ],
    "overall_understanding": "strong|moderate|weak",
    "evidence_note": "If no clear misconceptions found, state 'No significant misconceptions identified in the discussion'"
}}

Guidelines:
- ONLY identify misconceptions that are clearly present in posts
- The correction MUST be grounded in syllabus or resources when possible
- Include the actual quote from the post to justify the misconception claim
- If you cannot find clear misconceptions, say so honestly
- Do not invent misconceptions that aren't supported by post content

Return ONLY valid JSON, no additional text."""


BEST_PRACTICE_PROMPT = """You are an expert instructor providing the ideal answer for this session's discussion.

SESSION PLAN:
{session_plan}

CASE/PROBLEM DISCUSSED:
{case_prompt}

SYLLABUS:
{syllabus_text}

COURSE RESOURCES:
{resources_text}

LEARNING OBJECTIVES:
{objectives}

Generate the best-practice answer that students should understand after this session.

Return JSON format:
{{
    "best_practice_answer": {{
        "summary": "2-3 sentence summary of the key takeaway",
        "detailed_explanation": "Comprehensive explanation (3-5 paragraphs)",
        "key_concepts": ["Concept 1", "Concept 2"],
        "connection_to_objectives": [
            {{
                "objective": "Learning objective",
                "how_addressed": "How this answer addresses the objective"
            }}
        ],
        "sources_used": ["Syllabus section X", "Resource Y"]
    }},
    "suggested_next_steps": [
        "What students should do next to deepen understanding"
    ],
    "additional_resources": [
        "Recommended readings or activities"
    ]
}}

Guidelines:
- Ground your answer in the syllabus and resources provided
- If the case prompt is missing, focus on the session topics
- Be specific about which parts of the syllabus/resources support your answer
- If materials are insufficient, note "Based on general best practices" for those sections

Return ONLY valid JSON, no additional text."""


STUDENT_SUMMARY_PROMPT = """You are a supportive instructor writing personalized feedback for students.

SESSION: {session_title}

WHAT WENT WELL (strong contributions):
{strong_contributions}

AREAS FOR IMPROVEMENT (misconceptions/gaps):
{misconceptions}
{gaps}

LEARNING OBJECTIVES STATUS:
{objectives_coverage}

Generate a student-friendly summary with actionable feedback.

Return JSON format:
{{
    "student_summary": {{
        "what_you_did_well": [
            "Specific positive feedback point 1",
            "Specific positive feedback point 2"
        ],
        "what_to_improve": [
            "Constructive feedback point 1",
            "Constructive feedback point 2"
        ],
        "key_takeaways": [
            "Main thing to remember from this session"
        ]
    }},
    "practice_questions": [
        {{
            "question": "Practice question 1 to test understanding",
            "hint": "Optional hint",
            "related_objective": "Which objective this tests"
        }},
        {{
            "question": "Practice question 2",
            "hint": "Optional hint",
            "related_objective": "Which objective this tests"
        }},
        {{
            "question": "Practice question 3",
            "hint": "Optional hint",
            "related_objective": "Which objective this tests"
        }}
    ],
    "encouragement": "Brief encouraging message for students"
}}

Guidelines:
- Be constructive and encouraging, not critical
- Make feedback actionable and specific
- Practice questions should directly test the learning objectives
- If there's insufficient data for feedback, say "Keep up the good work!" generically

Return ONLY valid JSON, no additional text."""


SCORE_ANSWERS_PROMPT = """You are an educational assessment expert. Compare each student's response to the best-practice answer and assign a score.

## Best Practice Answer
{best_practice_answer}

## Key Concepts That Should Be Addressed
{key_concepts}

## Student Posts to Evaluate
{student_posts}

## Scoring Rubric
- 90-100: Excellent - Covers all key concepts with deep understanding
- 75-89: Good - Covers most key concepts with solid understanding
- 60-74: Satisfactory - Covers some key concepts, room for improvement
- 40-59: Needs Improvement - Missing key concepts, shows partial understanding
- 0-39: Insufficient - Does not demonstrate understanding of the topic

## Instructions
For each student post:
1. Identify which key concepts they addressed
2. Evaluate the accuracy and depth of their explanation
3. Assign a score based on the rubric
4. Provide brief feedback

Return JSON in this exact format:
{{
    "student_scores": [
        {{
            "user_id": <int>,
            "user_name": "<string or null if unknown>",
            "post_id": <int>,
            "score": <int 0-100>,
            "key_points_covered": ["<concept1>", "<concept2>"],
            "missing_points": ["<concept3>"],
            "feedback": "<brief constructive feedback>"
        }}
    ],
    "class_statistics": {{
        "average_score": <float>,
        "highest_score": <int>,
        "lowest_score": <int>,
        "score_distribution": {{
            "excellent": <count 90-100>,
            "good": <count 75-89>,
            "satisfactory": <count 60-74>,
            "needs_improvement": <count 40-59>,
            "insufficient": <count 0-39>
        }}
    }},
    "closest_to_correct": {{
        "user_id": <int>,
        "user_name": "<string or null>",
        "post_id": <int>,
        "score": <int>
    }},
    "furthest_from_correct": {{
        "user_id": <int>,
        "user_name": "<string or null>",
        "post_id": <int>,
        "score": <int>
    }}
}}

Guidelines:
- Score based on alignment with the best practice answer and key concepts
- Be fair and consistent in scoring across all posts
- Consider both accuracy and depth of understanding
- Provide constructive feedback that helps students improve
- If a post is very short or off-topic, score it lower with appropriate feedback

Return ONLY valid JSON, no additional text."""
