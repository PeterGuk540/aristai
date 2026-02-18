"""Voice Text Extraction Utilities.

This module provides functions for extracting structured information
from voice transcripts, including:
1. Dictated content extraction
2. Dropdown/button/tab target extraction
3. Search query extraction
4. Student name extraction
"""

import re
import unicodedata
from typing import Any, Dict, List, Optional


def normalize_spanish_text(text: str) -> str:
    """
    Normalize Spanish text by removing accents and diacritics.
    This allows voice transcripts (which often lack accents) to match patterns.
    E.g., "sesión" -> "sesion", "llévame" -> "llevame"
    """
    if not text:
        return text
    # Normalize to decomposed form (NFD), then remove combining marks
    normalized = unicodedata.normalize('NFD', text)
    # Remove combining diacritical marks (accents)
    without_accents = ''.join(c for c in normalized if unicodedata.category(c) != 'Mn')
    return without_accents


def extract_dictated_content(transcript: str, action: str) -> Optional[str]:
    """Extract dictated content from transcript for form filling."""
    text = transcript.strip()

    # Remove common prefixes that indicate dictation
    prefixes_to_remove = [
        r'^(?:the\s+)?(?:course\s+)?(?:title\s+)?(?:is\s+)?(?:called\s+)?',
        r'^(?:the\s+)?(?:session\s+)?(?:title\s+)?(?:is\s+)?(?:called\s+)?',
        r'^(?:name|title|call)\s+(?:it|the\s+\w+)\s+',
        r'^(?:it\'?s?\s+called\s+)',
        r'^(?:the\s+)?(?:poll\s+)?question\s+(?:is|should\s+be)\s+',
        r'^(?:ask|poll)\s+(?:them|students|the\s+class)\s+',
        r'^(?:post\s+(?:this|the\s+following):\s*)',
        r'^(?:the\s+)?(?:post|message|content)\s+(?:is|should\s+be)\s+',
    ]

    for prefix in prefixes_to_remove:
        match = re.match(prefix, text, re.IGNORECASE)
        if match:
            text = text[match.end():].strip()
            break

    # Remove quotes if present
    if text.startswith('"') and text.endswith('"'):
        text = text[1:-1]
    elif text.startswith("'") and text.endswith("'"):
        text = text[1:-1]

    # Return None if the result is too short or looks like a command
    if len(text) < 2:
        return None

    # Check if this looks like an actual dictation (not a command)
    command_indicators = ['go to', 'navigate', 'open', 'show', 'create', 'start', 'stop', 'help']
    text_lower = text.lower()
    for indicator in command_indicators:
        if text_lower.startswith(indicator):
            return None

    return text


def extract_universal_dictation(transcript: str) -> Optional[Dict[str, str]]:
    """
    UNIVERSAL dictation extraction - works for ANY input field.
    Extracts field name and value from natural speech patterns.
    """
    text = transcript.strip()
    text_lower = text.lower()

    # Pattern: "the [field] is [value]" or "[field] is [value]"
    match = re.match(r'^(?:the\s+)?(\w+(?:\s+\w+)?)\s+(?:is|should\s+be|will\s+be)\s+(.+)$', text, re.IGNORECASE)
    if match:
        field = match.group(1).strip().lower().replace(' ', '-')
        value = match.group(2).strip()
        return {"field": field, "value": value}

    # Pattern: "set [field] to [value]"
    match = re.match(r'^(?:set|make|change)\s+(?:the\s+)?(\w+(?:\s+\w+)?)\s+(?:to|as)\s+(.+)$', text, re.IGNORECASE)
    if match:
        field = match.group(1).strip().lower().replace(' ', '-')
        value = match.group(2).strip()
        return {"field": field, "value": value}

    # Pattern: "[field]: [value]"
    match = re.match(r'^(\w+(?:\s+\w+)?):\s*(.+)$', text)
    if match:
        field = match.group(1).strip().lower().replace(' ', '-')
        value = match.group(2).strip()
        return {"field": field, "value": value}

    # Pattern: "for [field], use [value]"
    match = re.match(r'^for\s+(?:the\s+)?(\w+(?:\s+\w+)?),?\s+(?:use|put|enter|type|write)\s+(.+)$', text, re.IGNORECASE)
    if match:
        field = match.group(1).strip().lower().replace(' ', '-')
        value = match.group(2).strip()
        return {"field": field, "value": value}

    # Pattern: "type/enter/write [value]" - fill focused/first input
    match = re.match(r'^(?:type|enter|write|put|input|fill(?:\s+in)?)\s+(.+)$', text, re.IGNORECASE)
    if match:
        value = match.group(1).strip()
        return {"field": "focused-input", "value": value}

    # If nothing matched but it looks like content (not a command), treat as dictation for focused input
    command_starters = ['go', 'navigate', 'open', 'show', 'create', 'start', 'stop', 'help', 'select', 'choose', 'click', 'switch']
    first_word = text_lower.split()[0] if text_lower.split() else ""
    if first_word not in command_starters and len(text) > 3:
        return {"field": "focused-input", "value": text}

    return None


def extract_dropdown_hint(transcript: str) -> str:
    """Extract which dropdown the user is referring to, or return empty for any dropdown."""
    text_lower = transcript.lower()

    # Look for specific dropdown mentions
    # IMPORTANT: Order matters! Check more specific phrases BEFORE generic ones.
    dropdown_keywords = [
        # Multi-word phrases first (more specific)
        ('provider connection', 'select-provider-connection'),
        ('source provider', 'select-integration-provider'),
        ('external course', 'select-external-course'),
        ('target course', 'select-target-course'),
        ('target session', 'select-target-session'),
        ('saved mapping', 'select-integration-mapping'),
        # Single words last (less specific)
        ('connection', 'select-provider-connection'),
        ('provider', 'select-integration-provider'),
        ('mapping', 'select-integration-mapping'),
        ('course', 'select-course'),
        ('session', 'select-session'),
        ('student', 'select-student'),
        ('instructor', 'select-instructor'),
        ('status', 'select-status'),
        ('type', 'select-type'),
    ]

    for keyword, target in dropdown_keywords:
        if keyword in text_lower:
            return target

    return ""  # Empty means find any dropdown on the page


def extract_button_info(transcript: str) -> Dict[str, str]:
    """Extract button target from transcript for button clicks."""
    text_lower = transcript.lower()

    # Direct button mappings
    button_mappings = {
        'get started': 'intro-get-started',
        'start now': 'intro-get-started',
        'voice commands': 'intro-voice-commands',
        'voice command': 'intro-voice-commands',
        'open voice commands': 'intro-voice-commands',
        'notifications': 'notifications-button',
        'notification': 'notifications-button',
        'open notifications': 'notifications-button',
        'open notification': 'notifications-button',
        'top notification': 'notifications-button',
        'top-bar notification': 'notifications-button',
        'change language': 'toggle-language',
        'switch language': 'toggle-language',
        'toggle language': 'toggle-language',
        'language': 'toggle-language',
        'cambiar idioma': 'toggle-language',
        'cambiar el idioma': 'toggle-language',
        'notificaciones': 'notifications-button',
        'notificacion': 'notifications-button',
        'comandos de voz': 'intro-voice-commands',
        'comenzar': 'intro-get-started',
        'refresh poll results': 'refresh-poll-results',
        'refresh instructor requests': 'refresh-instructor-requests',
        'approve request': 'approve-instructor-request',
        'reject request': 'reject-instructor-request',
        'generate report': 'generate-report',
        'regenerate report': 'regenerate-report',
        'refresh': 'refresh',
        'start copilot': 'start-copilot',
        'stop copilot': 'stop-copilot',
        'create poll': 'create-poll',
        'post case': 'post-case',
        'go live': 'go-live',
        'complete session': 'complete-session',
        'edit session': 'edit-session',
        'modify session': 'edit-session',
        'delete session': 'delete-session',
        'remove session': 'delete-session',
        'enroll': 'enroll-students',
        'upload roster': 'upload-roster',
        'submit': 'submit-post',
        'create course': 'create-course-with-plans',
        'create session': 'create-session',
        'create and generate': 'create-course-with-plans',
        'generate plans': 'create-course-with-plans',
        'add connection': 'add-provider-connection',
        'connect canvas': 'connect-canvas-oauth',
        'connect upp': 'connect-canvas-oauth',
        'connect provider': 'connect-canvas-oauth',
        'test selected': 'test-provider-connection',
        'set default': 'activate-provider-connection',
        'create forum course': 'import-external-course',
        'save mapping': 'save-course-mapping',
        'sync all': 'sync-all-materials',
        'sync students': 'sync-roster',
        'import selected materials': 'import-external-materials',
        'import materials': 'import-external-materials',
        'select all materials': 'select-all-external-materials',
        'clear materials': 'clear-external-materials',
    }

    for phrase, target in button_mappings.items():
        if phrase in text_lower:
            return {"target": target, "label": phrase.title()}

    return {}


def extract_search_query(transcript: str) -> Optional[str]:
    """Extract the intended search query for workspace search navigation."""
    text = normalize_spanish_text((transcript or "").strip().lower())
    if not text:
        return None

    patterns = [
        r'^(?:search|find|look\s+for)\s+(?:for\s+)?(.+)$',
        r'^(?:busca|buscar)\s+(.+)$',
        r'^(?:open|go\s+to)\s+(.+?)\s+(?:using\s+)?search$',
        r'^(?:abrir|ir\s+a)\s+(.+?)\s+(?:con\s+)?busqueda$',
    ]

    query = None
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            query = match.group(1).strip()
            break

    if not query:
        if any(k in text for k in ["search", "find", "look for", "busca", "buscar"]):
            query = text
        else:
            return None

    # Remove common filler words that hurt matching.
    query = re.sub(r'\b(page|tab|section|panel|the|a|an|please|for me|por favor)\b', '', query).strip()
    query = re.sub(r'\s+', ' ', query)

    return query if len(query) >= 2 else None


def extract_student_name(transcript: str) -> Optional[str]:
    """Extract student name from transcript for student selection."""
    text = transcript.strip()

    # Remove common prefixes
    prefixes = [
        r'^(select|choose|pick|click|check|enroll)\s+(the\s+)?student\s+',
        r'^(select|choose|pick|click|check|enroll)\s+',
        r'^student\s+',
    ]
    for prefix in prefixes:
        text = re.sub(prefix, '', text, flags=re.IGNORECASE)

    # Remove common suffixes
    suffixes = [
        r'\s+(from|in)\s+(the\s+)?(student\s+)?pool$',
        r'\s+please$',
        r'\s+now$',
    ]
    for suffix in suffixes:
        text = re.sub(suffix, '', text, flags=re.IGNORECASE)

    # Clean up and return
    text = text.strip()
    if text and len(text) > 1:
        return text
    return None


def extract_tab_info(transcript: str) -> Dict[str, str]:
    """Extract tab name from transcript for universal tab switching."""
    text_lower = transcript.lower()

    # Remove common prefixes
    for prefix in ['go to', 'open', 'show', 'switch to', 'view', 'the']:
        text_lower = re.sub(rf'^{prefix}\s+', '', text_lower)

    # Remove tab/panel/section suffix
    text_lower = re.sub(r'\s*(tab|panel|section)\s*$', '', text_lower)

    # Clean up and extract the tab name
    tab_name = text_lower.strip()

    # Normalize common variations
    tab_aliases = {
        'ai copilot': 'copilot',
        'ai assistant': 'copilot',
        'copilot': 'copilot',
        # Polls tab - handle various transcriptions and mishearings
        'poll': 'polls',
        'polls': 'polls',
        'pulse': 'polls',
        'pose': 'polls',
        'pols': 'polls',
        'paul': 'polls',
        'polling': 'polls',
        'poles': 'polls',
        'pulls': 'polls',
        'bowls': 'polls',
        'goals': 'polls',
        # Cases tab
        'case': 'cases',
        'cases': 'cases',
        'case study': 'cases',
        'case studies': 'cases',
        'casestudies': 'cases',
        'post case': 'cases',
        'post cases': 'cases',
        # Requests tab
        'request': 'requests',
        'requests': 'requests',
        'instructor request': 'requests',
        'instructor requests': 'requests',
        # Roster tab
        'roster': 'roster',
        'student roster': 'roster',
        'class roster': 'roster',
        'roster upload': 'roster',
        # Courses advanced tab
        'advanced': 'advanced',
        'enroll': 'advanced',
        'enrollment': 'advanced',
        'enrollments': 'advanced',
        'instructor': 'advanced',
        'instructor access': 'advanced',
        'manage enrollment': 'advanced',
        'my performance': 'my-performance',
        'best practice': 'best-practice',
        'best practices': 'best-practice',
        # Session status management tab
        'manage': 'manage',
        'management': 'manage',
        'manage status': 'manage',
        'managestatus': 'manage',
        'status': 'manage',
        'session status': 'manage',
        'status control': 'manage',
        # AI Features tab (sessions page)
        'ai features': 'ai-features',
        'aifeatures': 'ai-features',
        'ai-features': 'ai-features',
        'a i features': 'ai-features',
        'ai feature': 'ai-features',
        'ai tools': 'ai-features',
        'enhanced features': 'ai-features',
        'enhanced ai': 'ai-features',
        # AI Insights tab (courses page)
        'ai insights': 'ai-insights',
        'aiinsights': 'ai-insights',
        'ai-insights': 'ai-insights',
        'a i insights': 'ai-insights',
        'ai insight': 'ai-insights',
        'ai analytics': 'ai-insights',
        'participation insights': 'ai-insights',
        'objective coverage': 'ai-insights',
        # Materials tab (sessions page)
        'materials': 'materials',
        'material': 'materials',
        'course materials': 'materials',
        'session materials': 'materials',
        'class materials': 'materials',
        'files': 'materials',
        'documents': 'materials',
        # Insights tab (sessions page)
        'insights': 'insights',
        'insight': 'insights',
        'session insights': 'insights',
        'analytics': 'insights',
        'session analytics': 'insights',
        'engagement': 'insights',
        'session engagement': 'insights',
        # Create tab
        'create': 'create',
        'creation': 'create',
        'create session': 'create',
        'new session': 'create',
        # View sessions tab
        'sessions': 'sessions',
        'session': 'sessions',
        'view sessions': 'sessions',
        'list': 'sessions',
        'session list': 'sessions',
        # Reports page tabs
        'summary': 'summary',
        'report summary': 'summary',
        'overview': 'summary',
        'participation': 'participation',
        'participation tab': 'participation',
        'scoring': 'scoring',
        'scores': 'scoring',
        'grades': 'scoring',
        'answer scores': 'scoring',
        'report analytics': 'analytics',
        'data analytics': 'analytics',
    }

    # First try exact match
    if tab_name in tab_aliases:
        return {"tabName": tab_aliases[tab_name]}

    # Then try partial match
    for alias, normalized in tab_aliases.items():
        if alias in tab_name or tab_name in alias:
            return {"tabName": normalized}

    return {"tabName": tab_name}


def extract_dropdown_selection(transcript: str) -> Dict[str, Any]:
    """Extract dropdown selection info from transcript."""
    text_lower = transcript.lower()

    # Extract ordinal or name
    ordinals = {
        'first': 0, 'second': 1, 'third': 2, 'fourth': 3, 'fifth': 4,
        'last': -1, '1st': 0, '2nd': 1, '3rd': 2, '4th': 3, '5th': 4,
        'one': 0, 'two': 1, 'three': 2, 'four': 3, 'five': 4,
    }

    for ordinal, index in ordinals.items():
        if ordinal in text_lower:
            return {"optionIndex": index, "optionName": ordinal}

    # Extract the selection name - remove command words
    for prefix in ['select', 'choose', 'pick', 'use', 'switch to', 'the']:
        text_lower = re.sub(rf'^{prefix}\s+', '', text_lower)

    # Remove type words
    for suffix in ['course', 'session', 'option', 'item']:
        text_lower = re.sub(rf'\s+{suffix}\s*$', '', text_lower)

    option_name = text_lower.strip()
    return {"optionName": option_name} if option_name else {}


def is_confirmation(text: str) -> bool:
    """Check if the text is a confirmation response."""
    confirmations = [
        'yes', 'yeah', 'yep', 'yup', 'sure', 'okay', 'ok', 'confirm',
        'proceed', 'do it', 'go ahead', 'please', 'absolutely',
        # Spanish confirmations (non-accented for speech recognition)
        'si', 'sí', 'claro', 'dale', 'vale', 'confirmar', 'hazlo',
        'adelante', 'por favor', 'correcto', 'exacto',
    ]
    text_lower = normalize_spanish_text(text.lower().strip())
    return any(conf in text_lower for conf in confirmations)
