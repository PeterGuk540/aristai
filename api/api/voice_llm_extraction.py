"""LLM-Based Voice Extraction Module.

This module provides unified LLM-based extraction for all voice commands,
replacing all regex patterns and hard-coded phrase dictionaries.

Every voice command goes through a single LLM call that extracts:
- Intent classification
- UI target identification (tabs, buttons, dropdowns)
- Dropdown selection (ordinals, names, indices)
- Form dictation content
- Confirmation detection
- Search queries
- Student names
"""

import json
import logging
from dataclasses import asdict
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field

from workflows.llm_utils import (
    get_fast_voice_llm,
    invoke_llm_with_metrics,
    parse_json_response,
    LLMResponse,
)

logger = logging.getLogger(__name__)


# ============================================================================
# PYDANTIC MODELS FOR STRUCTURED EXTRACTION OUTPUT
# ============================================================================

class ExtractedUITarget(BaseModel):
    """Extraction result for UI element targeting."""
    element_type: Literal["tab", "button", "dropdown", "input", "none"] = "none"
    element_name: Optional[str] = Field(None, description="Matched element name")
    voice_id: Optional[str] = Field(None, description="data-voice-id of the element")
    confidence: float = Field(0.0, ge=0.0, le=1.0)


class ExtractedSelection(BaseModel):
    """Extraction result for dropdown/list selection."""
    selection_type: Literal["ordinal", "name", "numeric", "partial", "none"] = "none"
    ordinal_index: Optional[int] = Field(
        None,
        description="0-based index. first=0, second=1, last=-1"
    )
    matched_name: Optional[str] = Field(None, description="Text that matched an option")
    confidence: float = Field(0.0, ge=0.0, le=1.0)


class ExtractedDictation(BaseModel):
    """Extraction result for form field dictation."""
    has_content: bool = False
    field_name: Optional[str] = Field(None, description="Inferred field name if pattern like 'the title is X'")
    content: Optional[str] = Field(None, description="The actual dictated content")
    is_command: bool = Field(False, description="True if this is a command like cancel/skip/help")
    command_type: Optional[str] = Field(None, description="cancel, skip, help, navigate, or null")


class UnifiedExtractionResult(BaseModel):
    """Comprehensive extraction result from single LLM call."""

    # Core intent classification
    intent_category: str = Field(
        "unclear",
        description="navigate, ui_action, query, create, control, confirm, dictate, unclear"
    )
    intent_action: str = Field("", description="Specific action within category")
    confidence: float = Field(0.0, ge=0.0, le=1.0)

    # UI interaction
    ui_target: Optional[ExtractedUITarget] = None

    # Dropdown selection
    selection: Optional[ExtractedSelection] = None

    # Form dictation
    dictation: Optional[ExtractedDictation] = None

    # Confirmation detection
    is_confirmation: bool = False
    confirmation_type: Optional[str] = Field(
        None,
        description="yes, no, skip, cancel, or null"
    )

    # Search query extraction
    search_query: Optional[str] = None

    # Student name extraction
    student_name: Optional[str] = None

    # Navigation target
    target_page: Optional[str] = None

    # Clarification
    needs_clarification: bool = False
    clarification_reason: Optional[str] = None

    # Original input preserved
    original_text: str = ""


# ============================================================================
# UNIFIED VOICE UNDERSTANDING PROMPT
# ============================================================================

UNIFIED_VOICE_UNDERSTANDING_PROMPT = '''You are the voice understanding system for AristAI, an educational discussion platform.
Your task is to analyze the user's voice command and extract ALL relevant information in a single pass.

## Full UI Context (All Pages)

### Available Tabs (across all pages):
{all_tabs_json}

### Available Buttons (across all pages):
{all_buttons_json}

### Available Dropdowns:
{all_dropdowns_json}

## Current State
- Current Page: {current_page}
- Conversation State: {conversation_state}
- Active Course: {active_course}
- Active Session: {active_session}
- Language: {language}

## Dropdown Options (if awaiting selection)
{dropdown_options_json}

## Form Fields (if in form filling context)
{form_fields_json}

## User Input
"{user_input}"

## Instructions

Analyze the user input and extract ALL of the following:

### 1. Intent Classification
Categories:
- `navigate` - User wants to go to a different page (/courses, /sessions, /forum, /console, /reports, /dashboard, /introduction, /profile)
- `ui_action` - User wants to interact with UI (switch tab, click button, select dropdown, fill input)
- `query` - User is asking for information
- `create` - User wants to create something (course, session, poll, post)
- `control` - User wants to control a feature (start/stop copilot, go live, end session)
- `confirm` - User is responding yes/no to a question
- `dictate` - User is providing content for a form field
- `unclear` - Cannot determine intent

### 2. Confirmation Detection (CRITICAL)
Detect confirmations in BOTH English and Spanish:
- YES: yes, yeah, yep, yup, sure, okay, ok, confirm, go ahead, do it, proceed, absolutely, right, correct, affirmative, si, sí, claro, dale, vale, confirmar, hazlo, adelante, por favor, correcto, exacto, de acuerdo
- NO: no, nope, nah, cancel, stop, abort, quit, never mind, don't, negative, cancelar, parar, detener, no quiero
- SKIP: skip, next, pass, later, not now, omitir, siguiente, saltar, después, luego

If the input is a confirmation, set:
- `is_confirmation: true`
- `confirmation_type: "yes" | "no" | "skip" | "cancel"`
- `intent_category: "confirm"`
- `confidence: 0.95`

### 3. UI Target Matching
Match user intent to available UI elements by SEMANTIC MEANING, not exact words:
- "polls tab", "go to polls", "show me the polls" → tab: "polls", voice_id: "tab-polls"
- "AI features", "aifeatures", "enhanced features", "AI tab" → tab: "ai-features", voice_id: "tab-ai-features"
- "AI insights", "participation insights" → tab: "ai-insights", voice_id: "tab-ai-insights"
- "create poll", "new poll", "make a poll" → button: "create-poll"
- "start copilot", "turn on copilot", "enable AI assistant" → button: "start-copilot"
- "go live", "start session", "begin class" → button: "go-live"

Always return the voice_id that matches the element in the provided lists.

### 4. Dropdown Selection (if options provided)
When dropdown_options are provided, match the user's selection:

**Ordinals (0-based index):**
- first, primero, uno, 1st, one → ordinal_index: 0
- second, segundo, dos, 2nd, two → ordinal_index: 1
- third, tercero, tres, 3rd, three → ordinal_index: 2
- fourth, cuarto, 4th, four → ordinal_index: 3
- fifth, quinto, 5th, five → ordinal_index: 4
- last, último, ultimo → ordinal_index: -1

**Name matching:**
- Find the closest match in the options list
- "select Statistics 101" → match option containing "Statistics 101"

### 5. Dictation Extraction (if in form context)
When conversation_state indicates form filling:
- Distinguish content from meta-conversation:
  - "let me think" / "hmm" / "wait" = META (not content)
  - Actual values = CONTENT
- Extract field-value patterns:
  - "the title is Introduction to AI" → field: "title", content: "Introduction to AI"
  - "set description to Weekly discussion" → field: "description", content: "Weekly discussion"
- Detect embedded commands:
  - "cancel" / "skip this" / "go back" / "help" → is_command: true

### 6. Navigation Detection
For navigation intents, extract the target page:
- "go to courses", "take me to courses" → target_page: "/courses"
- "open sessions" → target_page: "/sessions"
- "show forum" → target_page: "/forum"
- "instructor console" → target_page: "/console"
- "view reports" → target_page: "/reports"

### 7. Search Query Extraction
- "search for statistics", "find machine learning" → search_query: "statistics" / "machine learning"
- "buscar física" → search_query: "física"

### 8. Student Name Extraction
- "select John Smith", "enroll Maria Garcia" → student_name: "John Smith" / "Maria Garcia"

## Response Format

Return ONLY valid JSON in this exact structure:

{{
    "intent_category": "navigate|ui_action|query|create|control|confirm|dictate|unclear",
    "intent_action": "specific_action_name",
    "confidence": 0.0-1.0,

    "ui_target": {{
        "element_type": "tab|button|dropdown|input|none",
        "element_name": "matched element name or null",
        "voice_id": "data-voice-id or null",
        "confidence": 0.0-1.0
    }},

    "selection": {{
        "selection_type": "ordinal|name|numeric|partial|none",
        "ordinal_index": "0-based index, -1 for last, or null",
        "matched_name": "matched option text or null",
        "confidence": 0.0-1.0
    }},

    "dictation": {{
        "has_content": true|false,
        "field_name": "inferred field name or null",
        "content": "dictated content or null",
        "is_command": true|false,
        "command_type": "cancel|skip|help|navigate|null"
    }},

    "is_confirmation": true|false,
    "confirmation_type": "yes|no|skip|cancel|null",

    "search_query": "extracted search text or null",
    "student_name": "extracted student name or null",
    "target_page": "/courses|/sessions|/forum|/console|/reports|/dashboard|null",

    "needs_clarification": true|false,
    "clarification_reason": "reason for clarification or null"
}}

IMPORTANT: Return ONLY the JSON object, no explanation or markdown formatting.
'''


# ============================================================================
# UNIFIED VOICE EXTRACTOR CLASS
# ============================================================================

class UnifiedVoiceExtractor:
    """
    Single LLM-based extraction for all voice understanding needs.

    This class replaces all regex-based extraction functions with a unified
    LLM call that handles:
    - Intent classification
    - Confirmation detection
    - UI target matching (tabs, buttons, dropdowns)
    - Dropdown selection (ordinals, names)
    - Form dictation extraction
    - Search query extraction
    - Student name extraction
    """

    def __init__(self):
        self._llm = None
        self._model_name = None

    def _ensure_llm(self) -> bool:
        """Ensure LLM is initialized. Returns True if available."""
        if self._llm is None:
            self._llm, self._model_name = get_fast_voice_llm()
        return self._llm is not None

    def _build_prompt(
        self,
        user_input: str,
        current_page: str,
        conversation_state: str,
        all_tabs: List[Dict[str, str]],
        all_buttons: List[Dict[str, str]],
        all_dropdowns: List[str],
        dropdown_options: Optional[List[Dict[str, str]]],
        form_fields: Optional[List[str]],
        active_course: Optional[str],
        active_session: Optional[str],
        language: str,
    ) -> str:
        """Build the unified understanding prompt with all context."""

        # Format UI elements as compact JSON
        all_tabs_json = json.dumps(all_tabs, indent=2) if all_tabs else "[]"
        all_buttons_json = json.dumps(all_buttons, indent=2) if all_buttons else "[]"
        all_dropdowns_json = json.dumps(all_dropdowns, indent=2) if all_dropdowns else "[]"

        # Format dropdown options
        if dropdown_options:
            dropdown_options_json = json.dumps(
                [{"index": i, "label": opt.get("label", ""), "value": opt.get("value", "")}
                 for i, opt in enumerate(dropdown_options)],
                indent=2
            )
        else:
            dropdown_options_json = "null (not awaiting dropdown selection)"

        # Format form fields
        form_fields_json = json.dumps(form_fields, indent=2) if form_fields else "null (not in form context)"

        return UNIFIED_VOICE_UNDERSTANDING_PROMPT.format(
            all_tabs_json=all_tabs_json,
            all_buttons_json=all_buttons_json,
            all_dropdowns_json=all_dropdowns_json,
            current_page=current_page or "unknown",
            conversation_state=conversation_state or "idle",
            active_course=active_course or "none",
            active_session=active_session or "none",
            language=language or "en",
            dropdown_options_json=dropdown_options_json,
            form_fields_json=form_fields_json,
            user_input=user_input,
        )

    def _parse_response(self, response_content: str, original_text: str) -> UnifiedExtractionResult:
        """Parse LLM response into structured result."""
        parsed = parse_json_response(response_content)

        if not parsed:
            logger.warning(f"Failed to parse LLM response: {response_content[:200]}")
            return self._fallback_result(original_text)

        try:
            # Build UI target
            ui_target = None
            if parsed.get("ui_target"):
                ui_data = parsed["ui_target"]
                ui_target = ExtractedUITarget(
                    element_type=ui_data.get("element_type", "none"),
                    element_name=ui_data.get("element_name"),
                    voice_id=ui_data.get("voice_id"),
                    confidence=float(ui_data.get("confidence", 0.0)),
                )

            # Build selection
            selection = None
            if parsed.get("selection"):
                sel_data = parsed["selection"]
                selection = ExtractedSelection(
                    selection_type=sel_data.get("selection_type", "none"),
                    ordinal_index=sel_data.get("ordinal_index"),
                    matched_name=sel_data.get("matched_name"),
                    confidence=float(sel_data.get("confidence", 0.0)),
                )

            # Build dictation
            dictation = None
            if parsed.get("dictation"):
                dict_data = parsed["dictation"]
                dictation = ExtractedDictation(
                    has_content=dict_data.get("has_content", False),
                    field_name=dict_data.get("field_name"),
                    content=dict_data.get("content"),
                    is_command=dict_data.get("is_command", False),
                    command_type=dict_data.get("command_type"),
                )

            return UnifiedExtractionResult(
                intent_category=parsed.get("intent_category", "unclear"),
                intent_action=parsed.get("intent_action", ""),
                confidence=float(parsed.get("confidence", 0.0)),
                ui_target=ui_target,
                selection=selection,
                dictation=dictation,
                is_confirmation=parsed.get("is_confirmation", False),
                confirmation_type=parsed.get("confirmation_type"),
                search_query=parsed.get("search_query"),
                student_name=parsed.get("student_name"),
                target_page=parsed.get("target_page"),
                needs_clarification=parsed.get("needs_clarification", False),
                clarification_reason=parsed.get("clarification_reason"),
                original_text=original_text,
            )

        except Exception as e:
            logger.exception(f"Error parsing extraction result: {e}")
            return self._fallback_result(original_text)

    def _fallback_result(self, original_text: str) -> UnifiedExtractionResult:
        """Return a safe fallback result when extraction fails."""
        return UnifiedExtractionResult(
            intent_category="unclear",
            intent_action="",
            confidence=0.0,
            needs_clarification=True,
            clarification_reason="Could not understand the command. Please try rephrasing.",
            original_text=original_text,
        )

    def extract(
        self,
        user_input: str,
        current_page: str = "",
        conversation_state: str = "idle",
        all_tabs: Optional[List[Dict[str, str]]] = None,
        all_buttons: Optional[List[Dict[str, str]]] = None,
        all_dropdowns: Optional[List[str]] = None,
        dropdown_options: Optional[List[Dict[str, str]]] = None,
        form_fields: Optional[List[str]] = None,
        active_course: Optional[str] = None,
        active_session: Optional[str] = None,
        language: str = "en",
    ) -> UnifiedExtractionResult:
        """
        Extract all relevant information from voice input using LLM.

        Args:
            user_input: The transcribed voice command
            current_page: Current page path (e.g., "/courses")
            conversation_state: Current conversation state (e.g., "idle", "awaiting_confirmation")
            all_tabs: List of all available tabs [{name, voice_id}, ...]
            all_buttons: List of all available buttons [{name, voice_id}, ...]
            all_dropdowns: List of all dropdown voice_ids
            dropdown_options: Options for current dropdown if in selection state
            form_fields: Current form field names if in form filling state
            active_course: Name of the currently selected course
            active_session: Name of the currently selected session
            language: User's preferred language ("en" or "es")

        Returns:
            UnifiedExtractionResult with all extracted information
        """
        if not user_input or not user_input.strip():
            return UnifiedExtractionResult(
                intent_category="unclear",
                confidence=0.0,
                needs_clarification=True,
                clarification_reason="No input received.",
                original_text=user_input or "",
            )

        if not self._ensure_llm():
            logger.error("No LLM available for voice extraction")
            return self._fallback_result(user_input)

        # Build the prompt with full context
        prompt = self._build_prompt(
            user_input=user_input.strip(),
            current_page=current_page,
            conversation_state=conversation_state,
            all_tabs=all_tabs or [],
            all_buttons=all_buttons or [],
            all_dropdowns=all_dropdowns or [],
            dropdown_options=dropdown_options,
            form_fields=form_fields,
            active_course=active_course,
            active_session=active_session,
            language=language,
        )

        # Single LLM call
        response: LLMResponse = invoke_llm_with_metrics(self._llm, prompt, self._model_name)

        if not response.success or not response.content:
            logger.warning(f"LLM extraction failed: {response.metrics.error_message}")
            return self._fallback_result(user_input)

        logger.debug(
            f"Voice extraction completed in {response.metrics.execution_time_seconds}s, "
            f"tokens: {response.metrics.total_tokens}, "
            f"cost: ${response.metrics.estimated_cost_usd:.6f}"
        )

        return self._parse_response(response.content, user_input)


# ============================================================================
# SINGLETON ACCESSOR
# ============================================================================

_extractor: Optional[UnifiedVoiceExtractor] = None


def get_unified_extractor() -> UnifiedVoiceExtractor:
    """Get or create the singleton UnifiedVoiceExtractor instance."""
    global _extractor
    if _extractor is None:
        _extractor = UnifiedVoiceExtractor()
    return _extractor


# ============================================================================
# UI CONTEXT AGGREGATION
# ============================================================================

def aggregate_all_ui_elements() -> Dict[str, Any]:
    """
    Aggregate all UI elements from PAGE_STRUCTURES for LLM context.

    Returns a dict with:
    - all_tabs: List of {name, voice_id, page} for all tabs across all pages
    - all_buttons: List of {name, voice_id, page} for all buttons across all pages
    - all_dropdowns: List of voice_ids for all dropdowns
    """
    from api.services.voice_conversation_state import PAGE_STRUCTURES

    all_tabs = []
    all_buttons = []
    all_dropdowns = []

    for path, page_structure in PAGE_STRUCTURES.items():
        # Aggregate tabs
        for tab in page_structure.tabs:
            all_tabs.append({
                "name": tab.name,
                "voice_id": tab.voice_id,
                "page": path,
            })

        # Aggregate buttons
        for button in page_structure.buttons:
            all_buttons.append({
                "name": button.name,
                "voice_id": button.voice_id,
                "page": path,
            })

        # Aggregate dropdowns
        for dropdown in page_structure.dropdowns:
            if dropdown.voice_id not in all_dropdowns:
                all_dropdowns.append(dropdown.voice_id)

    return {
        "all_tabs": all_tabs,
        "all_buttons": all_buttons,
        "all_dropdowns": all_dropdowns,
    }


# ============================================================================
# CONVENIENCE WRAPPER FUNCTIONS
# ============================================================================
# These maintain API compatibility while using the unified extractor internally

def extract_confirmation_llm(user_input: str, language: str = "en") -> Optional[str]:
    """
    Extract confirmation type using LLM.

    Returns: "yes", "no", "skip", "cancel", or None
    """
    extractor = get_unified_extractor()
    result = extractor.extract(
        user_input=user_input,
        conversation_state="awaiting_confirmation",
        language=language,
    )

    if result.is_confirmation:
        return result.confirmation_type
    return None


def extract_dropdown_selection_llm(
    user_input: str,
    options: List[Dict[str, str]],
    language: str = "en",
) -> Optional[int]:
    """
    Extract dropdown selection using LLM.

    Args:
        user_input: User's voice command
        options: List of {label, value} for dropdown options
        language: User's language

    Returns: 0-based index of selected option, or None
    """
    extractor = get_unified_extractor()
    result = extractor.extract(
        user_input=user_input,
        conversation_state="awaiting_dropdown_selection",
        dropdown_options=options,
        language=language,
    )

    if result.selection and result.selection.selection_type != "none":
        idx = result.selection.ordinal_index
        if idx is not None:
            # Handle "last" (-1)
            if idx == -1:
                return len(options) - 1
            return idx

    return None


def extract_tab_llm(
    user_input: str,
    available_tabs: List[Dict[str, str]],
    language: str = "en",
) -> Optional[str]:
    """
    Extract tab name/voice_id using LLM.

    Returns: voice_id of matched tab, or None
    """
    extractor = get_unified_extractor()
    result = extractor.extract(
        user_input=user_input,
        all_tabs=available_tabs,
        language=language,
    )

    if result.ui_target and result.ui_target.element_type == "tab":
        return result.ui_target.voice_id
    return None


def extract_button_llm(
    user_input: str,
    available_buttons: List[Dict[str, str]],
    language: str = "en",
) -> Optional[str]:
    """
    Extract button voice_id using LLM.

    Returns: voice_id of matched button, or None
    """
    extractor = get_unified_extractor()
    result = extractor.extract(
        user_input=user_input,
        all_buttons=available_buttons,
        language=language,
    )

    if result.ui_target and result.ui_target.element_type == "button":
        return result.ui_target.voice_id
    return None


def extract_dictation_llm(
    user_input: str,
    form_fields: Optional[List[str]] = None,
    language: str = "en",
) -> Optional[Dict[str, Any]]:
    """
    Extract dictated content using LLM.

    Returns: {field_name, content, is_command, command_type} or None
    """
    extractor = get_unified_extractor()
    result = extractor.extract(
        user_input=user_input,
        conversation_state="awaiting_field_input",
        form_fields=form_fields,
        language=language,
    )

    if result.dictation and result.dictation.has_content:
        return {
            "field_name": result.dictation.field_name,
            "content": result.dictation.content,
            "is_command": result.dictation.is_command,
            "command_type": result.dictation.command_type,
        }

    if result.dictation and result.dictation.is_command:
        return {
            "field_name": None,
            "content": None,
            "is_command": True,
            "command_type": result.dictation.command_type,
        }

    return None
