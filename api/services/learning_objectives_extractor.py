"""
Learning Objectives Extractor Service.

Automatically extracts learning objectives from syllabus text using LLM.
"""
import logging
from typing import List, Optional
import sys
import os

# Add workflows directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from workflows.llm_utils import (
    get_llm_with_tracking,
    invoke_llm_with_retry,
    parse_json_response,
    LLMResponse,
)

logger = logging.getLogger(__name__)


EXTRACTION_PROMPT = """You are an expert educational curriculum designer. Analyze the following syllabus text and extract the key learning objectives.

Learning objectives should be:
1. Specific and measurable (using action verbs like: analyze, evaluate, create, apply, demonstrate, etc.)
2. Student-centered (what students will be able to do, not what the instructor will teach)
3. Achievable within the course timeframe
4. Relevant to the course content and real-world application

Extract 5-10 clear learning objectives from the syllabus. If the syllabus doesn't explicitly list objectives, infer them from the course description, topics, and assessments.

SYLLABUS TEXT:
{syllabus_text}

Respond with a JSON object in exactly this format:
{{
    "objectives": [
        "By the end of this course, students will be able to...",
        "Students will demonstrate the ability to...",
        ...
    ],
    "confidence": "high" | "medium" | "low",
    "notes": "Brief explanation if objectives were inferred rather than explicit"
}}

Return ONLY the JSON object, no additional text."""


def extract_learning_objectives(syllabus_text: str) -> dict:
    """
    Extract learning objectives from syllabus text using LLM.

    Args:
        syllabus_text: The syllabus content to analyze

    Returns:
        Dictionary with:
        - objectives: List of extracted learning objectives
        - confidence: "high", "medium", or "low"
        - notes: Any notes about the extraction
        - success: Boolean indicating if extraction succeeded
        - error: Error message if extraction failed
    """
    if not syllabus_text or len(syllabus_text.strip()) < 50:
        return {
            "objectives": [],
            "confidence": "low",
            "notes": "Syllabus text is too short to extract meaningful objectives",
            "success": False,
            "error": "Syllabus text must be at least 50 characters"
        }

    # Truncate very long syllabi to avoid token limits
    max_chars = 15000
    if len(syllabus_text) > max_chars:
        syllabus_text = syllabus_text[:max_chars] + "\n\n[... text truncated for length ...]"
        logger.info(f"Truncated syllabus from {len(syllabus_text)} to {max_chars} characters")

    # Get LLM
    llm, model_name = get_llm_with_tracking()

    if not llm:
        logger.warning("No LLM API key available, using fallback extraction")
        return _fallback_extraction(syllabus_text)

    # Create prompt
    prompt = EXTRACTION_PROMPT.format(syllabus_text=syllabus_text)

    # Invoke LLM with retry
    response: LLMResponse = invoke_llm_with_retry(llm, prompt, model_name, max_retries=2)

    if not response.success:
        logger.error(f"LLM extraction failed: {response.metrics.error_message}")
        return _fallback_extraction(syllabus_text)

    # Parse JSON response
    parsed = parse_json_response(response.content)

    if not parsed or "objectives" not in parsed:
        logger.warning("Failed to parse LLM response, using fallback")
        return _fallback_extraction(syllabus_text)

    objectives = parsed.get("objectives", [])

    # Validate and clean objectives
    cleaned_objectives = []
    for obj in objectives:
        if isinstance(obj, str) and len(obj.strip()) > 10:
            cleaned_objectives.append(obj.strip())

    if not cleaned_objectives:
        logger.warning("No valid objectives extracted, using fallback")
        return _fallback_extraction(syllabus_text)

    return {
        "objectives": cleaned_objectives,
        "confidence": parsed.get("confidence", "medium"),
        "notes": parsed.get("notes", ""),
        "success": True,
        "error": None,
        "tokens_used": response.metrics.total_tokens,
        "model": model_name,
    }


def _fallback_extraction(syllabus_text: str) -> dict:
    """
    Fallback extraction when LLM is unavailable.
    Uses simple heuristics to identify potential objectives.
    """
    objectives = []

    # Look for common objective patterns
    patterns = [
        "students will be able to",
        "students will learn",
        "students will understand",
        "students will demonstrate",
        "by the end of this course",
        "course objectives",
        "learning objectives",
        "learning outcomes",
        "upon completion",
        "after completing",
    ]

    lines = syllabus_text.lower().split('\n')

    for i, line in enumerate(lines):
        line_lower = line.lower().strip()

        # Check if line contains objective patterns
        for pattern in patterns:
            if pattern in line_lower:
                # Get this line and potentially the next few lines
                objective_text = line.strip()

                # Clean up the objective
                if len(objective_text) > 20:
                    # Capitalize first letter
                    objective_text = objective_text[0].upper() + objective_text[1:]
                    objectives.append(objective_text)
                    break

        # Also look for bullet points or numbered lists after "objectives" header
        if any(header in line_lower for header in ["objective", "outcome", "goal"]):
            # Check next 10 lines for bullet points
            for j in range(i + 1, min(i + 11, len(lines))):
                next_line = lines[j].strip()
                if next_line and (next_line.startswith('-') or
                                   next_line.startswith('•') or
                                   (len(next_line) > 2 and next_line[0].isdigit() and next_line[1] in '.)')):
                    # Remove bullet/number prefix
                    clean_line = next_line.lstrip('-•0123456789.) ').strip()
                    if len(clean_line) > 20:
                        clean_line = clean_line[0].upper() + clean_line[1:]
                        if clean_line not in objectives:
                            objectives.append(clean_line)

    # Deduplicate while preserving order
    seen = set()
    unique_objectives = []
    for obj in objectives:
        obj_lower = obj.lower()
        if obj_lower not in seen:
            seen.add(obj_lower)
            unique_objectives.append(obj)

    # Limit to 10 objectives
    unique_objectives = unique_objectives[:10]

    return {
        "objectives": unique_objectives,
        "confidence": "low" if not unique_objectives else "medium",
        "notes": "Extracted using pattern matching (no LLM available)" if unique_objectives else "No objectives found - please add manually",
        "success": len(unique_objectives) > 0,
        "error": None if unique_objectives else "Could not extract objectives from syllabus",
        "tokens_used": 0,
        "model": "fallback",
    }
