"""
Golden Set Sample Data for AristAI Evaluation

Contains sample inputs and expected output structures for:
1. Session Planning workflow
2. Live Copilot workflow
3. Report Generation workflow

These samples represent realistic classroom scenarios for evaluation.
"""

from datetime import datetime
from typing import Dict, Any, List

# ============ Session Planning Golden Sets ============

SESSION_PLANNING_SAMPLES = [
    {
        "id": "planning_001",
        "name": "Ethics Case Discussion",
        "input": {
            "course": {
                "name": "Business Ethics 101",
                "objectives_json": [
                    "Understand ethical frameworks",
                    "Apply ethics to business decisions",
                    "Analyze stakeholder perspectives"
                ]
            },
            "session_title": "Week 3: Corporate Social Responsibility",
            "instructor_notes": "Focus on environmental responsibility and shareholder vs stakeholder theory."
        },
        "expected_structure": {
            "required_keys": ["topics", "goals", "discussion_prompts", "case"],
            "topics_min_count": 2,
            "goals_min_count": 2,
            "discussion_prompts_min_count": 2,
        },
        "quality_criteria": {
            "topics_should_mention": ["CSR", "responsibility", "stakeholder"],
            "should_include_case": True,
        }
    },
    {
        "id": "planning_002",
        "name": "Healthcare Decision Making",
        "input": {
            "course": {
                "name": "Medical Ethics",
                "objectives_json": [
                    "Apply ethical principles to patient care",
                    "Navigate informed consent",
                    "Balance autonomy and beneficence"
                ]
            },
            "session_title": "End-of-Life Care Decisions",
            "instructor_notes": "Discuss autonomy vs family wishes. Include advance directives."
        },
        "expected_structure": {
            "required_keys": ["topics", "goals", "discussion_prompts"],
            "topics_min_count": 2,
            "goals_min_count": 2,
            "discussion_prompts_min_count": 2,
        },
        "quality_criteria": {
            "topics_should_mention": ["autonomy", "end-of-life", "consent"],
            "should_include_case": True,
        }
    },
    {
        "id": "planning_003",
        "name": "Technology and Privacy",
        "input": {
            "course": {
                "name": "Information Systems Ethics",
                "objectives_json": [
                    "Evaluate data privacy frameworks",
                    "Assess AI bias and fairness",
                    "Understand digital rights"
                ]
            },
            "session_title": "AI in Hiring: Bias and Fairness",
            "instructor_notes": "Amazon resume screening case. GDPR implications."
        },
        "expected_structure": {
            "required_keys": ["topics", "goals", "discussion_prompts"],
            "topics_min_count": 2,
            "goals_min_count": 2,
            "discussion_prompts_min_count": 1,
        },
        "quality_criteria": {
            "topics_should_mention": ["bias", "AI", "fairness"],
            "should_include_case": True,
        }
    },
]


# ============ Live Copilot Golden Sets ============

COPILOT_SAMPLES = [
    {
        "id": "copilot_001",
        "name": "Active Discussion with Confusion",
        "input": {
            "session_title": "Business Ethics: Stakeholder Theory",
            "session_plan": {
                "topics": ["Stakeholder theory", "Shareholder primacy", "Corporate responsibility"],
                "goals": ["Compare stakeholder vs shareholder models", "Apply to real cases"]
            },
            "posts": [
                {"post_id": 1, "user_id": 101, "author_role": "student", "content": "I think shareholders should always come first since they own the company.", "timestamp": "10:05:00"},
                {"post_id": 2, "user_id": 102, "author_role": "student", "content": "But what about employees? They're stakeholders too.", "timestamp": "10:06:00"},
                {"post_id": 3, "user_id": 103, "author_role": "student", "content": "Isn't stakeholder theory the same as CSR?", "timestamp": "10:07:00"},
                {"post_id": 4, "user_id": 104, "author_role": "student", "content": "I'm confused about the difference between stakeholders and shareholders.", "timestamp": "10:08:00"},
                {"post_id": 5, "user_id": 101, "author_role": "student", "content": "Milton Friedman said profit is the only responsibility.", "timestamp": "10:09:00"},
                {"post_id": 6, "user_id": 105, "author_role": "student", "content": "What about environmental responsibility? That's not profitable.", "timestamp": "10:10:00"},
            ]
        },
        "expected_structure": {
            "required_keys": ["rolling_summary", "confusion_points", "instructor_prompts", "reengagement_activity"],
            "confusion_points_min_count": 1,
            "instructor_prompts_min_count": 2,
        },
        "quality_criteria": {
            "should_identify_confusion": ["stakeholder vs shareholder", "CSR"],
            "should_cite_evidence": True,
        }
    },
    {
        "id": "copilot_002",
        "name": "Low Engagement Discussion",
        "input": {
            "session_title": "Medical Ethics: Informed Consent",
            "session_plan": {
                "topics": ["Informed consent", "Patient autonomy", "Capacity assessment"],
                "goals": ["Define informed consent elements", "Discuss capacity challenges"]
            },
            "posts": [
                {"post_id": 10, "user_id": 201, "author_role": "student", "content": "Informed consent means the patient agrees to treatment.", "timestamp": "14:05:00"},
                {"post_id": 11, "user_id": 202, "author_role": "student", "content": "Yes, they have to sign a form.", "timestamp": "14:08:00"},
            ]
        },
        "expected_structure": {
            "required_keys": ["rolling_summary", "instructor_prompts", "reengagement_activity"],
            "instructor_prompts_min_count": 2,
            "should_suggest_activity": True,
        },
        "quality_criteria": {
            "should_address_low_engagement": True,
            "should_suggest_deeper_questions": True,
        }
    },
    {
        "id": "copilot_003",
        "name": "Productive Discussion - Minimal Intervention",
        "input": {
            "session_title": "AI Ethics: Algorithmic Bias",
            "session_plan": {
                "topics": ["Algorithmic bias", "Fairness metrics", "Accountability"],
                "goals": ["Identify sources of bias", "Evaluate mitigation strategies"]
            },
            "posts": [
                {"post_id": 20, "user_id": 301, "author_role": "student", "content": "Training data bias is a major source of algorithmic unfairness.", "timestamp": "09:05:00"},
                {"post_id": 21, "user_id": 302, "author_role": "student", "content": "Right, like COMPAS - the recidivism prediction tool that was biased against Black defendants.", "timestamp": "09:06:00"},
                {"post_id": 22, "user_id": 303, "author_role": "student", "content": "But how do we define fairness? There are different metrics that can conflict.", "timestamp": "09:07:00"},
                {"post_id": 23, "user_id": 304, "author_role": "student", "content": "Equal opportunity vs demographic parity - they can't both be satisfied.", "timestamp": "09:08:00"},
                {"post_id": 24, "user_id": 301, "author_role": "student", "content": "Building on what Sarah said, we need to decide what trade-offs are acceptable.", "timestamp": "09:09:00"},
                {"post_id": 25, "user_id": 305, "author_role": "student", "content": "I think accountability is key - someone needs to be responsible when algorithms cause harm.", "timestamp": "09:10:00"},
            ]
        },
        "expected_structure": {
            "required_keys": ["rolling_summary", "instructor_prompts", "overall_assessment"],
            "should_indicate_high_engagement": True,
        },
        "quality_criteria": {
            "should_recognize_quality_discussion": True,
            "should_suggest_minimal_intervention": True,
        }
    },
]


# ============ Report Generation Golden Sets ============

REPORT_SAMPLES = [
    {
        "id": "report_001",
        "name": "Complete Session with Polls",
        "input": {
            "session": {
                "title": "Business Ethics Week 3",
                "plan_json": {
                    "topics": ["Stakeholder theory", "CSR"],
                    "goals": ["Compare stakeholder models"]
                }
            },
            "course_objectives": [
                "Understand ethical frameworks",
                "Apply ethics to business decisions"
            ],
            "posts": [
                {"post_id": 1, "content": "Shareholders should come first.", "author_role": "student", "labels_json": []},
                {"post_id": 2, "content": "What about other stakeholders?", "author_role": "student", "labels_json": []},
                {"post_id": 3, "content": "Good question! Think about employees, customers, community.", "author_role": "instructor", "labels_json": []},
                {"post_id": 4, "content": "I see - stakeholder theory considers everyone affected.", "author_role": "student", "labels_json": ["insight"]},
                {"post_id": 5, "content": "But how do we balance competing interests?", "author_role": "student", "labels_json": []},
            ],
            "polls": [
                {
                    "question": "Which model do you prefer?",
                    "options": ["Shareholder primacy", "Stakeholder theory", "Hybrid approach"],
                    "vote_counts": [5, 12, 8],
                    "total_votes": 25
                }
            ],
            "interventions_count": 2
        },
        "expected_structure": {
            "required_keys": ["themes", "objectives_alignment", "poll_results"],
            "themes_min_count": 1,
            "should_include_poll_analysis": True,
        },
        "quality_criteria": {
            "should_align_to_objectives": True,
            "should_cite_evidence": True,
            "should_interpret_polls": True,
        }
    },
    {
        "id": "report_002",
        "name": "Session with Misconceptions",
        "input": {
            "session": {
                "title": "Medical Ethics: Autonomy",
                "plan_json": {
                    "topics": ["Patient autonomy", "Informed consent"],
                    "goals": ["Understand autonomy limits"]
                }
            },
            "course_objectives": [
                "Apply ethical principles to patient care",
                "Navigate informed consent"
            ],
            "posts": [
                {"post_id": 10, "content": "Patients can refuse any treatment, right?", "author_role": "student", "labels_json": []},
                {"post_id": 11, "content": "Yes, autonomy is absolute.", "author_role": "student", "labels_json": ["misconception"]},
                {"post_id": 12, "content": "Actually, there are limits - for example, patients can't demand treatments that aren't medically indicated.", "author_role": "instructor", "labels_json": []},
                {"post_id": 13, "content": "Oh, so autonomy is about refusal, not demands?", "author_role": "student", "labels_json": ["insight"]},
            ],
            "polls": [],
            "interventions_count": 1
        },
        "expected_structure": {
            "required_keys": ["themes", "misconceptions", "objectives_alignment"],
            "should_identify_misconception": True,
        },
        "quality_criteria": {
            "should_highlight_misconception": ["autonomy", "absolute"],
            "should_show_correction": True,
        }
    },
]


# ============ Helper Functions ============

def get_all_samples() -> Dict[str, List[Dict[str, Any]]]:
    """Return all golden set samples organized by workflow type."""
    return {
        "session_planning": SESSION_PLANNING_SAMPLES,
        "copilot": COPILOT_SAMPLES,
        "report": REPORT_SAMPLES,
    }


def get_sample_by_id(sample_id: str) -> Dict[str, Any]:
    """Find a specific sample by ID across all workflow types."""
    all_samples = get_all_samples()
    for workflow_type, samples in all_samples.items():
        for sample in samples:
            if sample["id"] == sample_id:
                return {"workflow_type": workflow_type, **sample}
    return None
