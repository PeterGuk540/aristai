"""Voice Text Extraction Utilities - LLM-Based.

This module provides functions for extracting structured information
from voice transcripts using LLM-based understanding.

All extraction is done through the UnifiedVoiceExtractor which uses
a single LLM call to understand and extract:
1. Dictated content extraction
2. Dropdown/button/tab target extraction
3. Search query extraction
4. Student name extraction
5. Confirmation detection

NO REGEX PATTERNS OR HARD-CODED PHRASE DICTIONARIES ARE USED.
"""

import logging
import unicodedata
from typing import Any, Dict, List, Optional

from api.api.voice_llm_extraction import (
    get_unified_extractor,
    aggregate_all_ui_elements,
    UnifiedExtractionResult,
)

logger = logging.getLogger(__name__)


def normalize_spanish_text(text: str) -> str:
    """
    Normalize Spanish text by removing accents and diacritics.
    This allows voice transcripts (which often lack accents) to match patterns.
    E.g., "sesion" -> "sesion", "llevame" -> "llevame"

    Note: This is kept for preprocessing, not pattern matching.
    """
    if not text:
        return text
    # Normalize to decomposed form (NFD), then remove combining marks
    normalized = unicodedata.normalize('NFD', text)
    # Remove combining diacritical marks (accents)
    without_accents = ''.join(c for c in normalized if unicodedata.category(c) != 'Mn')
    return without_accents


def extract_dictated_content(transcript: str, action: str = "") -> Optional[str]:
    """
    Extract dictated content from transcript for form filling using LLM.

    Args:
        transcript: The voice transcript to extract from
        action: The action context (e.g., "create_course", "create_poll")

    Returns:
        The extracted content string, or None if not dictation
    """
    if not transcript or not transcript.strip():
        return None

    extractor = get_unified_extractor()
    result = extractor.extract(
        user_input=transcript,
        conversation_state="awaiting_field_input",
    )

    if result.dictation and result.dictation.has_content and result.dictation.content:
        return result.dictation.content

    # If the LLM didn't explicitly classify as dictation but there's no command detected,
    # and the intent is dictate, return the original text as content
    if result.intent_category == "dictate" and not result.dictation.is_command:
        return transcript.strip()

    return None


def extract_universal_dictation(transcript: str) -> Optional[Dict[str, str]]:
    """
    Universal dictation extraction using LLM - works for ANY input field.
    Extracts field name and value from natural speech patterns.

    Args:
        transcript: The voice transcript

    Returns:
        Dict with "field" and "value" keys, or None
    """
    if not transcript or not transcript.strip():
        return None

    extractor = get_unified_extractor()
    result = extractor.extract(
        user_input=transcript,
        conversation_state="awaiting_field_input",
    )

    if result.dictation:
        if result.dictation.is_command:
            # Return command info
            return None

        if result.dictation.has_content and result.dictation.content:
            return {
                "field": result.dictation.field_name or "focused-input",
                "value": result.dictation.content,
            }

    # If intent is dictate but no structured extraction, treat as content for focused input
    if result.intent_category == "dictate":
        return {"field": "focused-input", "value": transcript.strip()}

    return None


def extract_dropdown_hint(transcript: str) -> str:
    """
    Extract which dropdown the user is referring to using LLM.

    Args:
        transcript: The voice transcript

    Returns:
        The dropdown voice_id, or empty string for any dropdown
    """
    if not transcript or not transcript.strip():
        return ""

    extractor = get_unified_extractor()
    ui_context = aggregate_all_ui_elements()

    result = extractor.extract(
        user_input=transcript,
        all_dropdowns=ui_context.get("all_dropdowns", []),
    )

    if result.ui_target and result.ui_target.element_type == "dropdown":
        return result.ui_target.voice_id or ""

    return ""


def extract_button_info(transcript: str) -> Dict[str, str]:
    """
    Extract button target from transcript using LLM.

    Args:
        transcript: The voice transcript

    Returns:
        Dict with "target" (voice_id) and "label" keys, or empty dict
    """
    if not transcript or not transcript.strip():
        return {}

    extractor = get_unified_extractor()
    ui_context = aggregate_all_ui_elements()

    result = extractor.extract(
        user_input=transcript,
        all_buttons=ui_context.get("all_buttons", []),
    )

    if result.ui_target and result.ui_target.element_type == "button":
        voice_id = result.ui_target.voice_id
        if voice_id:
            return {
                "target": voice_id,
                "label": result.ui_target.element_name or voice_id,
            }

    return {}


def extract_search_query(transcript: str) -> Optional[str]:
    """
    Extract the intended search query using LLM.

    Args:
        transcript: The voice transcript

    Returns:
        The search query string, or None
    """
    if not transcript or not transcript.strip():
        return None

    extractor = get_unified_extractor()
    result = extractor.extract(user_input=transcript)

    if result.search_query:
        return result.search_query

    return None


def extract_student_name(transcript: str) -> Optional[str]:
    """
    Extract student name from transcript using LLM.

    Args:
        transcript: The voice transcript

    Returns:
        The extracted student name, or None
    """
    if not transcript or not transcript.strip():
        return None

    extractor = get_unified_extractor()
    result = extractor.extract(user_input=transcript)

    if result.student_name:
        return result.student_name

    return None


def extract_tab_info(transcript: str) -> Dict[str, str]:
    """
    Extract tab name from transcript using LLM.

    Args:
        transcript: The voice transcript

    Returns:
        Dict with "tabName" key containing the normalized tab name
    """
    if not transcript or not transcript.strip():
        return {"tabName": ""}

    extractor = get_unified_extractor()
    ui_context = aggregate_all_ui_elements()

    result = extractor.extract(
        user_input=transcript,
        all_tabs=ui_context.get("all_tabs", []),
    )

    if result.ui_target and result.ui_target.element_type == "tab":
        voice_id = result.ui_target.voice_id
        if voice_id:
            # Remove "tab-" prefix if present for backward compatibility
            tab_name = voice_id.replace("tab-", "") if voice_id.startswith("tab-") else voice_id
            return {"tabName": tab_name}

    # Fallback: return cleaned transcript as tab name
    return {"tabName": transcript.lower().strip()}


def extract_dropdown_selection(transcript: str) -> Dict[str, Any]:
    """
    Extract dropdown selection info from transcript using LLM.

    Args:
        transcript: The voice transcript

    Returns:
        Dict with "optionIndex" and/or "optionName" keys
    """
    if not transcript or not transcript.strip():
        return {}

    extractor = get_unified_extractor()
    result = extractor.extract(
        user_input=transcript,
        conversation_state="awaiting_dropdown_selection",
    )

    if result.selection and result.selection.selection_type != "none":
        response = {}

        if result.selection.ordinal_index is not None:
            response["optionIndex"] = result.selection.ordinal_index

        if result.selection.matched_name:
            response["optionName"] = result.selection.matched_name

        if response:
            return response

    # Fallback: return the cleaned transcript as option name
    return {"optionName": transcript.lower().strip()}


def is_confirmation(text: str) -> bool:
    """
    Check if the text is a confirmation response using LLM.

    Args:
        text: The text to check

    Returns:
        True if this is a positive confirmation (yes/sure/ok/etc.)
    """
    if not text or not text.strip():
        return False

    extractor = get_unified_extractor()
    result = extractor.extract(
        user_input=text,
        conversation_state="awaiting_confirmation",
    )

    if result.is_confirmation and result.confirmation_type == "yes":
        return True

    return False


def get_confirmation_type(text: str) -> Optional[str]:
    """
    Get the type of confirmation from text using LLM.

    Args:
        text: The text to analyze

    Returns:
        "yes", "no", "skip", "cancel", or None
    """
    if not text or not text.strip():
        return None

    extractor = get_unified_extractor()
    result = extractor.extract(
        user_input=text,
        conversation_state="awaiting_confirmation",
    )

    if result.is_confirmation:
        return result.confirmation_type

    return None


def extract_full_context(
    transcript: str,
    current_page: str = "",
    conversation_state: str = "idle",
    dropdown_options: Optional[List[Dict[str, str]]] = None,
    form_fields: Optional[List[str]] = None,
    active_course: Optional[str] = None,
    active_session: Optional[str] = None,
    language: str = "en",
) -> UnifiedExtractionResult:
    """
    Extract all relevant information from a voice transcript in one LLM call.

    This is the recommended function for new code - it returns all extraction
    results in a single structured object.

    Args:
        transcript: The voice transcript
        current_page: Current page path
        conversation_state: Current conversation state
        dropdown_options: Options if awaiting dropdown selection
        form_fields: Field names if in form filling state
        active_course: Name of active course
        active_session: Name of active session
        language: User's preferred language

    Returns:
        UnifiedExtractionResult with all extracted information
    """
    extractor = get_unified_extractor()
    ui_context = aggregate_all_ui_elements()

    return extractor.extract(
        user_input=transcript,
        current_page=current_page,
        conversation_state=conversation_state,
        all_tabs=ui_context.get("all_tabs", []),
        all_buttons=ui_context.get("all_buttons", []),
        all_dropdowns=ui_context.get("all_dropdowns", []),
        dropdown_options=dropdown_options,
        form_fields=form_fields,
        active_course=active_course,
        active_session=active_session,
        language=language,
    )
