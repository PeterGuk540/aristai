"""
Conversational Voice Endpoint for AristAI

This module provides a conversational AI interface that:
1. Understands natural language queries
2. Determines intent (navigate, execute action, provide info)
3. Returns conversational responses with context
4. Executes MCP tools when appropriate

Add this router to your main API router.
"""

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from typing import Optional, List, Any, Dict, Tuple
import re

from sqlalchemy.orm import Session

from api.core.database import get_db
from api.models.course import Course
from api.models.session import Session as SessionModel, SessionStatus
from api.api.mcp_executor import invoke_tool_handler
from api.services.speech_filter import sanitize_speech
from api.services.tool_response import normalize_tool_result
from api.services.context_store import ContextStore
from api.services.voice_conversation_state import (
    VoiceConversationManager,
    ConversationState,
    DropdownOption,
)
from mcp_server.server import TOOL_REGISTRY
from workflows.voice_orchestrator import run_voice_orchestrator, generate_summary
from workflows.llm_utils import get_llm_with_tracking, invoke_llm_with_metrics, parse_json_response

# Initialize context store for voice memory
context_store = ContextStore()

# Initialize conversation state manager for conversational flows
conversation_manager = VoiceConversationManager()

# Import your existing dependencies
# from .auth import get_current_user
# from .database import get_db
# from ..mcp_server.server import mcp_server

router = APIRouter(prefix="/voice", tags=["voice"])


class LogoutRequest(BaseModel):
    user_id: Optional[int] = None


@router.post("/logout")
async def voice_logout(request: LogoutRequest):
    """Clear voice context on user logout."""
    if request.user_id:
        conversation_manager.clear_context(request.user_id)
        context_store.clear_context(request.user_id)
    return {"message": "Voice context cleared"}


class ConverseRequest(BaseModel):
    transcript: str
    context: Optional[List[str]] = None
    user_id: Optional[int] = None
    current_page: Optional[str] = None


class ActionResponse(BaseModel):
    type: str  # 'navigate', 'execute', 'info'
    target: Optional[str] = None
    executed: Optional[bool] = None


class ConverseResponse(BaseModel):
    message: str
    action: Optional[ActionResponse] = None
    results: Optional[List[Any]] = None
    suggestions: Optional[List[str]] = None


# Navigation intent patterns - expanded for better coverage (English + Spanish)
NAVIGATION_PATTERNS = {
    # Courses - English
    r'\b(go to|open|show|navigate to|take me to|view)\s+(the\s+)?(courses?|course list|my courses)\b': '/courses',
    r'\bcourses?\s*page\b': '/courses',
    # Courses - Spanish
    r'\b(ir a|abrir|mostrar|ver|llévame a)\s+(los\s+)?(cursos?|lista de cursos|mis cursos)\b': '/courses',
    r'\bpágina\s+de\s+cursos?\b': '/courses',
    # Sessions - English
    r'\b(go to|open|show|navigate to|take me to|view)\s+(the\s+)?(sessions?|session list|class)\b': '/sessions',
    r'\bsessions?\s*page\b': '/sessions',
    # Sessions - Spanish
    r'\b(ir a|abrir|mostrar|ver|llévame a)\s+(las\s+)?(sesiones?|lista de sesiones|clase)\b': '/sessions',
    r'\bpágina\s+de\s+sesiones?\b': '/sessions',
    # Forum - English
    r'\b(go to|open|show|navigate to|take me to|view)\s+(the\s+)?(forum|discussion|discussions|posts)\b': '/forum',
    r'\bforum\s*page\b': '/forum',
    # Forum - Spanish
    r'\b(ir a|abrir|mostrar|ver|llévame a)\s+(el\s+)?(foro|discusión|discusiones|publicaciones)\b': '/forum',
    r'\bpágina\s+del?\s+foro\b': '/forum',
    # Console - English
    r'\b(go to|open|show|navigate to|take me to|view)\s+(the\s+)?(console|instructor console|control panel)\b': '/console',
    r'\bconsole\s*page\b': '/console',
    # Console - Spanish
    r'\b(ir a|abrir|mostrar|ver|llévame a)\s+(la\s+)?(consola|consola del instructor|panel de control)\b': '/console',
    r'\bpágina\s+de\s+(la\s+)?consola\b': '/console',
    # Reports - English
    r'\b(go to|open|show|navigate to|take me to|view)\s+(the\s+)?(reports?|report page|analytics)\b': '/reports',
    r'\breports?\s*page\b': '/reports',
    # Reports - Spanish
    r'\b(ir a|abrir|mostrar|ver|llévame a)\s+(los\s+)?(reportes?|informes?|página de reportes|analíticas?)\b': '/reports',
    r'\bpágina\s+de\s+reportes?\b': '/reports',
    # Dashboard - English
    r'\b(go to|open|show|navigate to|take me to|view)\s+(the\s+)?(dashboard|home|main)\b': '/dashboard',
    r'\bdashboard\s*page\b': '/dashboard',
    # Dashboard - Spanish
    r'\b(ir a|abrir|mostrar|ver|llévame a)\s+(el\s+)?(tablero|inicio|principal)\b': '/dashboard',
    r'\bpágina\s+(de\s+)?inicio\b': '/dashboard',
}

# Action intent patterns - expanded for better voice command coverage (English + Spanish)
# IMPORTANT: Specific domain actions MUST come BEFORE generic UI actions
# because detect_action_intent returns the first match
ACTION_PATTERNS = {
    # === SPECIFIC DOMAIN ACTIONS (check these FIRST) ===
    # Course actions - English
    'create_course': [
        r'\bcreate\s+(a\s+)?(new\s+)?course\b',
        r'\bmake\s+(a\s+)?(new\s+)?course\b',
        r'\badd\s+(a\s+)?(new\s+)?course\b',
        r'\bnew\s+course\b',
        r'\bset\s*up\s+(a\s+)?course\b',
        r'\bstart\s+(a\s+)?new\s+course\b',
        # Spanish
        r'\bcrear\s+(un\s+)?(nuevo\s+)?curso\b',
        r'\bhacer\s+(un\s+)?(nuevo\s+)?curso\b',
        r'\bañadir\s+(un\s+)?(nuevo\s+)?curso\b',
        r'\bnuevo\s+curso\b',
        r'\bconfigurar\s+(un\s+)?curso\b',
    ],
    'list_courses': [
        r'\b(list|show|get|what are|display|see)\s+(all\s+)?(my\s+)?courses\b',
        r'\bmy courses\b',
        r'\bcourse list\b',
        r'\bwhat courses\b',
        r'\bhow many courses\b',
        # Spanish
        r'\b(listar|mostrar|ver|cuáles son)\s+(todos\s+)?(mis\s+)?cursos\b',
        r'\bmis cursos\b',
        r'\blista de cursos\b',
        r'\bqué cursos\b',
        r'\bcuántos cursos\b',
    ],
    # Session actions - English + Spanish
    'create_session': [
        r'\bcreate\s+(a\s+)?(new\s+)?session\b',
        r'\bmake\s+(a\s+)?(new\s+)?session\b',
        r'\badd\s+(a\s+)?(new\s+)?session\b',
        r'\bnew\s+session\b',
        r'\bschedule\s+(a\s+)?session\b',
        r'\bset\s*up\s+(a\s+)?session\b',
        # Spanish
        r'\bcrear\s+(una\s+)?(nueva\s+)?sesión\b',
        r'\bhacer\s+(una\s+)?(nueva\s+)?sesión\b',
        r'\bañadir\s+(una\s+)?(nueva\s+)?sesión\b',
        r'\bnueva\s+sesión\b',
        r'\bprogramar\s+(una\s+)?sesión\b',
    ],
    'go_live': [
        r'\bgo\s+live\b',
        r'\bstart\s+(the\s+)?(live\s+)?session\b',
        r'\bbegin\s+(the\s+)?session\b',
        r'\blaunch\s+(the\s+)?session\b',
        r'\bmake\s+(the\s+)?session\s+live\b',
        r'\bactivate\s+(the\s+)?session\b',
        # Spanish
        r'\b(iniciar|comenzar|empezar)\s+(la\s+)?sesión(\s+en\s+vivo)?\b',
        r'\bponer\s+(la\s+)?sesión\s+en\s+vivo\b',
        r'\bactivar\s+(la\s+)?sesión\b',
        r'\ben\s+vivo\b',
    ],
    'end_session': [
        r'\bend\s+(the\s+)?(live\s+)?session\b',
        r'\bstop\s+(the\s+)?session\b',
        r'\bclose\s+(the\s+)?session\b',
        r'\bfinish\s+(the\s+)?session\b',
        r'\bterminate\s+(the\s+)?session\b',
        # Spanish
        r'\b(terminar|finalizar|cerrar)\s+(la\s+)?sesión\b',
        r'\bdetener\s+(la\s+)?sesión\b',
        r'\bacabar\s+(la\s+)?sesión\b',
    ],
    # Materials actions - English + Spanish
    'view_materials': [
        r'\b(view|show|open|see)\s+(the\s+)?(course\s+)?materials?\b',
        r'\bmaterials?\s+(tab|page|section)\b',
        r'\b(go\s+to|open)\s+(the\s+)?materials?\b',
        r'\bshow\s+(me\s+)?(the\s+)?materials?\b',
        r'\b(view|see)\s+(the\s+)?(uploaded\s+)?(files?|documents?|readings?)\b',
        r'\bcourse\s+(files?|documents?|readings?)\b',
        # Spanish
        r'\b(ver|mostrar|abrir)\s+(los\s+)?materiales?\b',
        r'\bmateriales?\s+(pestaña|página|sección)\b',
        r'\b(ir a|abrir)\s+(los\s+)?materiales?\b',
        r'\bmuéstrame\s+(los\s+)?materiales?\b',
        r'\b(ver|mostrar)\s+(los\s+)?(archivos?|documentos?|lecturas?)\b',
    ],
    # Copilot actions - English + Spanish
    'start_copilot': [
        r'\bstart\s+(the\s+)?copilot\b',
        r'\bactivate\s+(the\s+)?copilot\b',
        r'\bturn on\s+(the\s+)?copilot\b',
        r'\benable\s+(the\s+)?copilot\b',
        r'\blaunch\s+(the\s+)?copilot\b',
        r'\bcopilot\s+on\b',
        r'\bbegin\s+(the\s+)?copilot\b',
        # Spanish
        r'\b(iniciar|activar|encender)\s+(el\s+)?copilot\b',
        r'\bhabilitar\s+(el\s+)?copilot\b',
        r'\bcopilot\s+(encendido|activado)\b',
        r'\b(iniciar|activar)\s+(el\s+)?asistente\b',
    ],
    'stop_copilot': [
        r'\bstop\s+(the\s+)?copilot\b',
        r'\bdeactivate\s+(the\s+)?copilot\b',
        r'\bturn off\s+(the\s+)?copilot\b',
        r'\bdisable\s+(the\s+)?copilot\b',
        r'\bcopilot\s+off\b',
        r'\bend\s+(the\s+)?copilot\b',
        r'\bpause\s+(the\s+)?copilot\b',
        # Spanish
        r'\b(detener|desactivar|apagar)\s+(el\s+)?copilot\b',
        r'\bdeshabilitar\s+(el\s+)?copilot\b',
        r'\bcopilot\s+(apagado|desactivado)\b',
        r'\bpausar\s+(el\s+)?copilot\b',
    ],
    'refresh_interventions': [
        r'\brefresh\s+(the\s+)?interventions?\b',
        r'\bupdate\s+(the\s+)?interventions?\b',
        r'\breload\s+(the\s+)?interventions?\b',
        r'\bget\s+(new\s+)?interventions?\b',
        r'\bfetch\s+(the\s+)?interventions?\b',
        r'\bcheck\s+(for\s+)?(new\s+)?interventions?\b',
        r'\binterventions?\s+refresh\b',
        # Spanish
        r'\b(actualizar|refrescar)\s+(las\s+)?intervenciones?\b',
        r'\brecargar\s+(las\s+)?intervenciones?\b',
        r'\bobtener\s+(nuevas?\s+)?intervenciones?\b',
        r'\bver\s+(las\s+)?intervenciones?\b',
    ],
    # Session status management - English + Spanish
    'set_session_draft': [
        r'\bset\s+(to\s+)?draft\b',
        r'\b(change|switch)\s+(to\s+)?draft\b',
        r'\bdraft\s+(the\s+)?session\b',
        r'\bmake\s+(it\s+)?draft\b',
        r'\brevert\s+to\s+draft\b',
        r'\bback\s+to\s+draft\b',
        # Spanish
        r'\bponer\s+(en\s+)?borrador\b',
        r'\b(cambiar|pasar)\s+(a\s+)?borrador\b',
        r'\bvolver\s+a\s+borrador\b',
    ],
    'set_session_live': [
        r'\bgo\s+live\b',
        r'\bset\s+(to\s+)?live\b',
        r'\b(change|switch)\s+(to\s+)?live\b',
        r'\bstart\s+(the\s+)?session\b',
        r'\bmake\s+(it\s+)?live\b',
        r'\blaunch\s+(the\s+)?session\b',
        # Spanish
        r'\bponer\s+en\s+vivo\b',
        r'\b(cambiar|pasar)\s+a\s+en\s+vivo\b',
        r'\bactivar\s+(la\s+)?sesión\b',
    ],
    'set_session_completed': [
        r'\bcomplete(\s+session)?\b',
        r'\bset\s+(to\s+)?complete(d)?\b',
        r'\b(change|switch)\s+(to\s+)?complete(d)?\b',
        r'\bend\s+(the\s+)?session\b',
        r'\bfinish\s+(the\s+)?session\b',
        r'\bmark\s+(as\s+)?complete(d)?\b',
        # Spanish
        r'\bcompletar(\s+sesión)?\b',
        r'\b(marcar|poner)\s+(como\s+)?completad[oa]\b',
        r'\bterminar\s+(la\s+)?sesión\b',
        r'\bfinalizar\s+(la\s+)?sesión\b',
    ],
    'schedule_session': [
        r'\bschedule(\s+session)?\b',
        r'\bset\s+(to\s+)?schedule(d)?\b',
        r'\b(change|switch)\s+(to\s+)?schedule(d)?\b',
        # Spanish
        r'\bprogramar(\s+sesión)?\b',
        r'\bagendar(\s+sesión)?\b',
        r'\b(poner|marcar)\s+(como\s+)?programad[oa]\b',
    ],
    # Report actions - English + Spanish
    'refresh_report': [
        r'\brefresh\s+(the\s+)?report\b',
        r'\breload\s+(the\s+)?report\b',
        r'\bupdate\s+(the\s+)?report\b',
        r'\bget\s+(the\s+)?(latest|new)\s+report\b',
        # Spanish
        r'\b(actualizar|refrescar)\s+(el\s+)?reporte\b',
        r'\brecargar\s+(el\s+)?reporte\b',
        r'\b(actualizar|refrescar)\s+(el\s+)?informe\b',
    ],
    'regenerate_report': [
        r'\bregenerate\s+(the\s+)?report\b',
        r'\bgenerate\s+(a\s+)?(new\s+)?report\b',
        r'\bcreate\s+(a\s+)?(new\s+)?report\b',
        r'\brebuild\s+(the\s+)?report\b',
        r'\bredo\s+(the\s+)?report\b',
        # Spanish
        r'\bregenerar\s+(el\s+)?reporte\b',
        r'\bgenerar\s+(un\s+)?(nuevo\s+)?reporte\b',
        r'\bcrear\s+(un\s+)?(nuevo\s+)?reporte\b',
        r'\brehacer\s+(el\s+)?reporte\b',
    ],
    # Theme and user menu actions
    'toggle_theme': [
        r'\b(toggle|switch|change)\s+(the\s+)?(theme|mode)\b',
        r'\b(dark|light)\s+mode\b',
        r'\b(enable|disable|turn\s+on|turn\s+off)\s+(dark|light)\s+mode\b',
        r'\bswitch\s+to\s+(dark|light)\b',
    ],
    'open_user_menu': [
        r'\b(open|show)\s+(the\s+)?(user\s+)?menu\b',
        r'\b(open|show)\s+(the\s+)?account(\s+menu)?\b',
        r'\bmy\s+account\b',
    ],
    'view_voice_guide': [
        r'\b(view|show|open)\s+(the\s+)?voice\s+(guide|commands?)\b',
        r'\bvoice\s+(guide|commands?)\b',
        r'\bhelp\s+with\s+voice\b',
        r'\bshow\s+(me\s+)?(voice\s+)?commands?\b',
        r'\bwhat\s+can\s+i\s+say\b',
        r'\blist\s+commands?\b',
    ],
    'forum_instructions': [
        r'\b(view|show|open)\s+(the\s+)?(forum|platform)\s+instructions?\b',
        r'\b(forum|platform)\s+instructions?\b',
        r'\b(forum|platform)\s+guide\b',
        r'\bhow\s+to\s+use\s+(the\s+)?(forum|platform|app)\b',
        r'\bplatform\s+help\b',
    ],
    'open_profile': [
        r'\b(open|view|show)\s+(my\s+)?profile\b',
        r'\b(go\s+to|view)\s+(my\s+)?settings\b',
        r'\bmy\s+profile\b',
        r'\baccount\s+settings\b',
    ],
    'sign_out': [
        r'\b(sign|log)\s*(out|off)\b',
        r'\blogout\b',
        r'\bsignout\b',
        r'\bexit\s+(the\s+)?app\b',
    ],
    'close_modal': [
        r'\bgot\s+it\b',
        r'\bi\s+got\s+it\b',
        r'\bokay\b',
        r'\bok\b',
        r'\bclose\s+(this|the)?\s*(window|modal|dialog|guide)?\b',
        r'\bdismiss\b',
        r'\bdone\b',
    ],
    # Poll actions
    'create_poll': [
        r'\bcreate\s+(a\s+)?poll\b',
        r'\bmake\s+(a\s+)?poll\b',
        r'\bstart\s+(a\s+)?poll\b',
        r'\bnew\s+poll\b',
        r'\badd\s+(a\s+)?poll\b',
        r'\blaunch\s+(a\s+)?poll\b',
        r'\bquick\s+poll\b',
        r'\bask\s+(the\s+)?(class|students)\s+(a\s+)?question\b',
    ],
    # Forum actions
    'post_case': [
        r'\bpost\s+(a\s+)?case(\s+study)?\b',
        r'\bcreate\s+(a\s+)?case(\s+study)?\b',
        r'\badd\s+(a\s+)?case(\s+study)?\b',
        r'\bnew\s+case(\s+study)?\b',
        r'\bshare\s+(a\s+)?case\b',
    ],
    # Post to forum discussion (different from post_case which is for case studies)
    'post_to_discussion': [
        r'\bpost\s+(to\s+)?(the\s+)?discussion\b',
        r'\b(make|create|write|add)\s+(a\s+)?(forum\s+)?post\b',
        r'\b(i\s+)?(want\s+to|would\s+like\s+to|let\s+me)\s+post\b',
        r'\bpost\s+something\b',
        r'\bshare\s+(my\s+)?(thoughts?|response|comment)\b',
        r'\b(write|add)\s+(a\s+)?(comment|response|reply)\b',
        r'\bcontribute\s+to\s+(the\s+)?discussion\b',
    ],
    # Report actions
    'generate_report': [
        r'\bgenerate\s+(a\s+)?(session\s+)?report\b',
        r'\bcreate\s+(a\s+)?(session\s+)?report\b',
        r'\bmake\s+(a\s+)?(session\s+)?report\b',
        r'\bbuild\s+(a\s+)?report\b',
        r'\bget\s+(the\s+)?report\b',
        r'\bshow\s+(the\s+)?report\b',
        r'\breport\s+(please|now)\b',
        r'\bsession\s+summary\b',
        r'\bclass\s+report\b',
    ],

    # === UNIVERSAL UI ELEMENT INTERACTIONS (check these AFTER specific actions) ===
    # Universal dropdown expansion - MUST come BEFORE ui_select_dropdown
    # Matches "select course", "select another course", "change course", "show options", "expand dropdown"
    'ui_expand_dropdown': [
        # Simple "select course" / "select session" / "select live session" (user wants to see options)
        r'^(select|choose|pick)\s+(a\s+)?(live\s+)?(course|session)\.?$',
        r'\b(select|choose|pick)\s+(the\s+)?(live\s+)?session\b',
        r'\b(select|choose|pick)\s+(another|a\s+different|other)\s+(live\s+)?(course|session)\b',
        r'\b(change|switch)\s+(the\s+)?(live\s+)?(course|session)\b',
        r'\bwhat\s+(live\s+)?(courses?|sessions?)\s+(are\s+)?(available|there)\b',
        r'\b(expand|open|show)\s+(the\s+)?(\w+\s+)?(dropdown|menu|list|options|select)\b',
        r'\b(show|see|view|what\s+are)\s+(the\s+)?(available\s+)?(\w+\s+)?(options|choices|items)\b',
        r'\blet\s+me\s+(see|choose|pick)\b',
    ],
    # Universal dropdown selection - direct selection like "select the first course"
    'ui_select_dropdown': [
        r'\b(select|choose|pick)\s+(the\s+)?(first|second|third|last|\d+(?:st|nd|rd|th)?)\s+(\w+)\b',
        r'\buse\s+(the\s+)?(\w+)\s+(.+)',
    ],
    # Universal tab switching - works for ANY tab name
    'ui_switch_tab': [
        # With "tab/panel/section" suffix
        r'\b(go\s+to|open|show|switch\s+to|view)\s+(the\s+)?(.+?)\s*(tab|panel|section)\b',
        r'\b(.+?)\s+(tab|panel|section)\b',
        # Without suffix - for known tab names (must list explicitly to avoid false matches)
        # Note: "ai copilot" and "ai assistant" added for voice recognition of "AI Copilot" tab
        # Note: Both "poll" and "polls" supported for voice recognition
        r'\b(go\s+to|open|show|switch\s+to|view)\s+(the\s+)?(discussion|cases|case\s+studies|summary|participation|scoring|enrollment|create|manage|sessions|courses|ai\s+copilot|ai\s+assistant|copilot|polls?|requests|roster)\b',
        # Simple "switch to X" for common tabs
        r'^(switch\s+to|go\s+to)\s+(discussion|cases|case\s+studies|summary|participation|scoring|enrollment|create|manage|sessions|ai\s+copilot|copilot|polls?)$',
    ],
    # Universal button clicks - works for ANY button
    # Also handles form submission triggers like "submit", "create it", "post it"
    'ui_click_button': [
        r'\b(click|press|hit|tap)\s+(the\s+)?(.+?)\s*(button)?\b',
        r'\b(click|press)\s+(on\s+)?(.+)\b',
        r'\b(submit|confirm|send|post)\s*(it|this|the\s+form|now)?\s*$',
        r'\b(create|make)\s+(it|this|the\s+course|the\s+session|the\s+poll)\s*$',
        r'\byes,?\s*(submit|create|post|do\s+it)\b',
    ],
    # === UNIVERSAL FORM DICTATION ===
    # Detects when user is providing content for ANY input field
    'ui_dictate_input': [
        # "the title is Introduction to AI"
        r'\b(the\s+)?(\w+)\s+(is|should\s+be|will\s+be)\s+(.+)',
        # "set title to Introduction to AI"
        r'\b(set|make|change)\s+(the\s+)?(\w+)\s+(to|as)\s+(.+)',
        # "title: Introduction to AI"
        r'^(\w+):\s*(.+)$',
        # "for title, use Introduction to AI"
        r'\bfor\s+(the\s+)?(\w+),?\s+(use|put|enter|type|write)\s+(.+)',
        # "type Introduction to AI"
        r'\b(type|enter|write|put|input)\s+(.+)',
        # "fill in Introduction to AI"
        r'\b(fill\s+in|fill)\s+(.+)',
    ],
    # === CONTEXT/STATUS ACTIONS ===
    'get_status': [
        r'\b(what|where)\s+(am\s+I|is\s+this|page)\b',
        r'\b(current|this)\s+(page|status|state)\b',
        r'\bwhat\s+can\s+I\s+do\b',
        r'\bwhat\'?s\s+(happening|going\s+on)\b',
        r'\bstatus\s+update\b',
        r'\bgive\s+me\s+(a\s+)?summary\b',
    ],
    'get_help': [
        r'\bhelp(\s+me)?\b',
        r'\bwhat\s+can\s+you\s+do\b',
        r'\bwhat\s+are\s+(my|the)\s+options\b',
        r'\bshow\s+(me\s+)?(the\s+)?commands\b',
    ],
    # === UNDO/CONTEXT ACTIONS ===
    'undo_action': [
        r'\bundo\b',
        r'\bundo\s+(that|this|the\s+last|last\s+action)\b',
        r'\brevert\b',
        r'\bgo\s+back\b',
        r'\bcancel\s+(that|this|the\s+last)\b',
        r'\bnever\s*mind\b',
        r'\btake\s+(that|it)\s+back\b',
    ],
    'get_context': [
        r'\bwhat\s+(course|session)\s+(am\s+I|is)\s+(on|in|using|selected)\b',
        r'\bwhich\s+(course|session)\s+(is\s+)?(active|selected|current)\b',
        r'\bmy\s+(current|active)\s+(course|session)\b',
        r'\bwhat\'?s\s+my\s+context\b',
    ],
    'clear_context': [
        r'\b(clear|reset)\s+(my\s+)?(context|selection|choices)\b',
        r'\bstart\s+(fresh|over|again)\b',
        r'\bforget\s+(everything|all|my\s+selections)\b',
    ],
    # === ADDITIONAL COURSE ACTIONS ===
    'select_course': [
        r'\b(select|choose|pick|open)\s+(the\s+)?(first|second|third|last|\d+(?:st|nd|rd|th)?)\s+course\b',
        r'\b(select|choose|pick|open)\s+course\s+(\d+|one|two|three)\b',
        r'\bgo\s+(to|into)\s+(the\s+)?(first|second|third|last)\s+course\b',
    ],
    'view_course_details': [
        r'\b(view|show|see|display)\s+(the\s+)?course\s+(details?|info|information)\b',
        r'\bcourse\s+(details?|info|information)\b',
        r'\babout\s+(this|the)\s+course\b',
    ],
    # === SESSION ACTIONS ===
    'list_sessions': [
        r'\b(list|show|get|what are|display|see)\s+(the\s+)?(live\s+)?sessions\b',
        r'\blive sessions\b',
        r'\bactive sessions\b',
        r'\bcurrent sessions?\b',
        r'\bwhat sessions\b',
    ],
    'select_session': [
        r'\b(select|choose|pick|open)\s+(the\s+)?(first|second|third|last|\d+(?:st|nd|rd|th)?)\s+session\b',
        r'\b(select|choose|pick|open)\s+session\s+(\d+|one|two|three)\b',
        r'\bgo\s+(to|into)\s+(the\s+)?(first|second|third|last)\s+session\b',
    ],
    # === COPILOT ACTIONS ===
    'get_interventions': [
        r'\b(show|get|what are|display)\s+(the\s+)?(copilot\s+)?suggestions\b',
        r'\binterventions\b',
        r'\bconfusion points\b',
        r'\bcopilot\s+(suggestions|insights|recommendations)\b',
        r'\bwhat does\s+(the\s+)?copilot\s+(suggest|recommend|say)\b',
        r'\bany\s+suggestions\b',
    ],
    # === ENROLLMENT ACTIONS ===
    'list_enrollments': [
        r'\b(list|show|who are|display|get)\s+(the\s+)?(enrolled\s+)?students\b',
        r'\benrollment\s+(list|status)\b',
        r'\bhow many students\b',
        r'\bstudent\s+(list|count|roster)\b',
        r'\bwho\s+is\s+enrolled\b',
        r'\bclass\s+roster\b',
    ],
    'manage_enrollments': [
        r'\bmanage\s+(the\s+)?(student\s+)?enrollments?\b',
        r'\benroll\s+(new\s+)?students?\b',
        r'\badd\s+students?\s+(to|into)\b',
        r'\bstudent\s+management\b',
        r'\benrollment\s+management\b',
    ],
    'list_student_pool': [
        r'\b(select|choose|pick)\s+(a\s+)?student\s+(from\s+)?(the\s+)?(student\s+)?pool\b',
        r'\b(show|list|see)\s+(the\s+)?(student\s+)?pool\b',
        r'\b(available|unenrolled)\s+students\b',
        r'\bwho\s+(can|is available to)\s+enroll\b',
        r'\bstudent\s+pool\b',
    ],
    'enroll_selected': [
        r'\b(click\s+)?(enroll|add)\s+(the\s+)?selected(\s+students?)?\b',
        r'\benroll\s+selected\b',
        r'\badd\s+selected\s+students?\b',
    ],
    'enroll_all': [
        r'\b(click\s+)?(enroll|add)\s+all(\s+students?)?\b',
        r'\benroll\s+all\b',
        r'\badd\s+all\s+students?\b',
    ],
    'select_student': [
        r'\b(select|choose|pick|click|check)\s+(the\s+)?student\s+(.+)\b',
        r'\b(select|choose|pick|click|check)\s+(.+?)\s+(from|in)\s+(the\s+)?(student\s+)?pool\b',
    ],
    # === FORUM ACTIONS ===
    'view_posts': [
        r'\b(show|view|see|display)\s+(the\s+)?(forum\s+)?posts\b',
        r'\b(show|view|see)\s+(the\s+)?discussions?\b',
        r'\bwhat\s+(are\s+)?(students|people)\s+(saying|discussing|posting)\b',
        r'\brecent\s+posts\b',
        r'\blatest\s+posts\b',
    ],
    'get_pinned_posts': [
        r'\b(show|view|get|what are)\s+(the\s+)?pinned\s+(posts|discussions)?\b',
        r'\bpinned\s+(posts|content|discussions)\b',
        r'\bimportant\s+posts\b',
    ],
    'summarize_discussion': [
        r'\bsummarize\s+(the\s+)?(forum|discussion|posts)\b',
        r'\b(discussion|forum)\s+summary\b',
        r'\bwhat\s+are\s+(students|people)\s+talking\s+about\b',
        r'\bkey\s+(points|themes|topics)\b',
        r'\bmain\s+(discussion|points)\b',
    ],
    'get_student_questions': [
        r'\b(show|what are|any)\s+(student\s+)?questions\b',
        r'\bquestions\s+from\s+(students|class)\b',
        r'\bany\s+(confusion|misconceptions)\b',
        r'\bwhat\s+(do\s+)?students\s+(need|want|ask)\b',
    ],
    # === NEW HIGH-IMPACT VOICE FEATURES ===
    # Class status overview - "How's the class doing?"
    'class_status': [
        r'\bhow\'?s\s+(the\s+)?(class|session|discussion)\s+(doing|going)\b',
        r'\bclass\s+(status|overview|update)\b',
        r'\bhow\s+(is|are)\s+(the\s+)?(students?|class|everyone)\s+(doing|performing)\b',
        r'\bgive\s+me\s+(a\s+)?(quick\s+)?(status|update|overview)\b',
        r'\bquick\s+(status|update|overview)\b',
        r'\bsession\s+(status|overview)\b',
        r'\bwhat\'?s\s+happening\s+(in\s+)?(the\s+)?(class|session|discussion)\b',
        r'\bsituation\s+report\b',
        r'\bsitrep\b',
    ],
    # Who needs help - identify struggling students
    'who_needs_help': [
        r'\bwho\s+(needs|requires)\s+help\b',
        r'\bwho\'?s\s+struggling\b',
        r'\bstruggling\s+students\b',
        r'\bstudents?\s+(who\s+)?(need|needs|requiring)\s+(help|attention|support)\b',
        r'\bwho\s+(is|are)\s+confused\b',
        r'\bconfused\s+students\b',
        r'\bwho\s+(hasn\'?t|have\s*n\'?t|has\s+not)\s+(participated|posted)\b',
        r'\bnon[-\s]?participants\b',
        r'\bwho\'?s\s+behind\b',
        r'\bat[-\s]?risk\s+students\b',
        r'\bwho\s+should\s+i\s+(help|focus\s+on|pay\s+attention\s+to)\b',
    ],
    # Report Q&A - ask about misconceptions
    'ask_misconceptions': [
        r'\bwhat\s+(were|are)\s+(the\s+)?(main\s+)?misconceptions?\b',
        r'\bwhat\s+did\s+students\s+get\s+wrong\b',
        r'\bcommon\s+(mistakes?|errors?|misconceptions?)\b',
        r'\bwhat\s+(concepts?|topics?)\s+confused\s+(them|students)\b',
        r'\bwhere\s+did\s+(students|they)\s+(struggle|fail|have\s+trouble)\b',
        r'\bmisunderstandings?\b',
    ],
    # Report Q&A - ask about scores
    'ask_scores': [
        r'\bhow\s+did\s+(students|the\s+class|everyone)\s+(do|perform|score)\b',
        r'\bwhat\s+(were|are)\s+(the\s+)?scores?\b',
        r'\bstudent\s+scores?\b',
        r'\bclass\s+(performance|scores?|results?)\b',
        r'\baverage\s+score\b',
        r'\bwho\s+(scored|did)\s+(best|highest|lowest|worst)\b',
        r'\btop\s+(performers?|students?|scores?)\b',
        r'\blow\s+(performers?|students?|scores?)\b',
        r'\bgrade\s+(distribution|breakdown)\b',
    ],
    # Report Q&A - ask about participation
    'ask_participation': [
        r'\bhow\s+(was|is)\s+(the\s+)?participation\b',
        r'\bparticipation\s+(rate|stats?|statistics?)\b',
        r'\bhow\s+many\s+(students\s+)?(participated|posted)\b',
        r'\bwho\s+(participated|posted)\b',
        r'\bwho\s+(didn\'?t|did\s+not)\s+(participate|post)\b',
        r'\bparticipation\s+(level|overview)\b',
        r'\bengagement\s+(level|rate|stats?)\b',
    ],
    # Read latest posts aloud
    'read_posts': [
        r'\bread\s+(the\s+)?(latest|recent|last)\s+(posts?|comments?|messages?)\b',
        r'\bread\s+(me\s+)?(the\s+)?posts?\b',
        r'\bwhat\s+(are\s+)?(the\s+)?(latest|recent)\s+posts?\b',
        r'\bwhat\s+did\s+(students|they)\s+(post|say|write)\b',
        r'\blatest\s+(from\s+)?(the\s+)?discussion\b',
        r'\brecent\s+(activity|posts?|comments?)\b',
        r'\bshow\s+(me\s+)?(the\s+)?recent\s+(posts?|activity)\b',
    ],
    # What did copilot suggest
    'copilot_suggestions': [
        r'\bwhat\s+(did|does)\s+(the\s+)?copilot\s+(suggest|recommend|say|think)\b',
        r'\bcopilot\s+(suggestions?|recommendations?|insights?)\b',
        r'\bwhat\s+(are\s+)?(the\s+)?copilot\'?s?\s+(suggestions?|thoughts?)\b',
        r'\bai\s+(suggestions?|recommendations?|insights?)\b',
        r'\bwhat\s+should\s+i\s+(do|say|ask)\s+next\b',
        r'\bany\s+(teaching\s+)?(suggestions?|recommendations?|tips?)\b',
        r'\bcopilot\s+update\b',
        r'\bteaching\s+(tips?|suggestions?|advice)\b',
    ],
    # Student performance lookup
    'student_lookup': [
        r'\bhow\s+is\s+(\w+)\s+(doing|performing)\b',
        r'\btell\s+me\s+about\s+(\w+)\'?s?\s+(performance|participation|scores?)\b',
        r'\bwhat\s+about\s+(\w+)\b',
        r'\b(\w+)\'?s?\s+(score|performance|participation|status)\b',
        r'\bcheck\s+(on\s+)?(\w+)\b',
        r'\blook\s+up\s+(\w+)\b',
    ],
}

CONFIRMATION_PATTERNS = (
    r"\b(yes|yeah|yep|confirm|confirmed|approve|approved|proceed|go ahead|do it|sounds good|ok|okay)\b"
)


def detect_navigation_intent(text: str) -> Optional[str]:
    """Detect if user wants to navigate somewhere"""
    text_lower = text.lower()
    for pattern, path in NAVIGATION_PATTERNS.items():
        if re.search(pattern, text_lower):
            return path
    return None


def detect_action_intent(text: str) -> Optional[str]:
    """Detect if user wants to perform an action"""
    text_lower = text.lower()
    for action, patterns in ACTION_PATTERNS.items():
        for pattern in patterns:
            if re.search(pattern, text_lower):
                return action
    return None


def extract_ui_target(text: str, action: str) -> Dict[str, Any]:
    """Extract the target value from a UI interaction command."""
    text_lower = text.lower().strip()
    result = {"action": action}

    if action == 'ui_select_course':
        # Extract course name or ordinal
        # Try to find the course name after "course"
        match = re.search(r'(course|class)\s+(.+?)(?:\s+please|\s+now|\s*$)', text_lower)
        if match:
            result["target"] = "select-course"
            result["optionName"] = match.group(2).strip()
        # Check for ordinal patterns
        ordinal_match = re.search(r'(first|second|third|last|\d+(?:st|nd|rd|th)?)\s+(course|class)', text_lower)
        if ordinal_match:
            result["target"] = "select-course"
            result["optionName"] = ordinal_match.group(1)

    elif action == 'ui_select_session':
        # Extract session name or ordinal
        match = re.search(r'session\s+(.+?)(?:\s+please|\s+now|\s*$)', text_lower)
        if match:
            result["target"] = "select-session"
            result["optionName"] = match.group(1).strip()
        # Check for ordinal patterns
        ordinal_match = re.search(r'(first|second|third|last|\d+(?:st|nd|rd|th)?)\s+session', text_lower)
        if ordinal_match:
            result["target"] = "select-session"
            result["optionName"] = ordinal_match.group(1)

    elif action == 'ui_switch_tab':
        # Extract tab name - order matters (longer phrases first)
        tab_keywords = [
            'case studies', 'case-studies',  # Two-word tab name - check first
            'ai copilot', 'ai assistant',  # Multi-word copilot variations
            'summary', 'participation', 'scoring', 'enrollment', 'create',
            'manage', 'sessions', 'courses', 'discussion', 'cases',
            'copilot', 'polls', 'poll', 'requests', 'roster', 'my-performance', 'best-practice'
        ]
        for keyword in tab_keywords:
            keyword_normalized = keyword.replace('-', ' ')
            if keyword in text_lower or keyword_normalized in text_lower:
                # Normalize multi-word tab names to their actual tab values
                if keyword in ['case studies', 'case-studies']:
                    tab_value = 'cases'
                elif keyword in ['ai copilot', 'ai assistant']:
                    tab_value = 'copilot'
                elif keyword == 'poll':
                    tab_value = 'polls'
                else:
                    tab_value = keyword.replace('-', '')
                result["tabName"] = tab_value
                result["target"] = f"tab-{tab_value}"
                break

    elif action == 'ui_click_button':
        # Extract button target
        button_mappings = {
            'generate report': 'generate-report',
            'regenerate report': 'regenerate-report',
            'refresh': 'refresh',
            'refresh report': 'refresh-report',
            'start copilot': 'start-copilot',
            'stop copilot': 'stop-copilot',
            'create poll': 'create-poll',
            'post case': 'post-case',
            'go live': 'go-live',
            'complete': 'complete-session',
            'complete session': 'complete-session',
            'enroll': 'enroll-students',
            'upload roster': 'upload-roster',
            'submit': 'submit-post',
            'create course': 'create-course',
            'create session': 'create-session',
        }
        for phrase, target in button_mappings.items():
            if phrase in text_lower:
                result["target"] = target
                result["buttonLabel"] = phrase
                break

    return result


def is_confirmation(text: str) -> bool:
    """Return True if transcript is a confirmation to proceed."""
    return bool(re.search(CONFIRMATION_PATTERNS, text.lower()))


def build_confirmation_message(steps: List[Dict[str, Any]]) -> str:
    """Build a confirmation prompt for write actions."""
    summaries = []
    for step in steps:
        tool_name = step.get("tool_name", "unknown_tool")
        args = step.get("args", {})
        if args:
            arg_preview = ", ".join(f"{key}={value!r}" for key, value in list(args.items())[:3])
            summaries.append(f"{tool_name} ({arg_preview})")
        else:
            summaries.append(tool_name)
    actions = "; ".join(summaries) if summaries else "the requested action"
    return f"I can proceed with: {actions}. Would you like me to go ahead?"


def detect_navigation_intent_llm(
    text: str,
    context: Optional[List[str]],
    current_page: Optional[str],
) -> Optional[str]:
    llm, model_name = get_llm_with_tracking()
    if not llm:
        return None

    available_routes = {
        "/courses": "Courses list",
        "/sessions": "Sessions list",
        "/forum": "Forum discussions",
        "/console": "Instructor console",
        "/reports": "Reports",
        "/dashboard": "Dashboard home",
    }
    routes_description = "\n".join([f"- {route}: {desc}" for route, desc in available_routes.items()])

    prompt = (
        "You are routing a voice request to a known page in the AristAI app.\n"
        "Select the best matching route for the instructor request.\n"
        "If none apply, return null.\n\n"
        f"Available routes:\n{routes_description}\n\n"
        f"Current page: {current_page or 'unknown'}\n"
        f"Conversation context: {context or []}\n"
        f"Transcript: \"{text}\"\n\n"
        "Respond with ONLY valid JSON matching:\n"
        "{\"route\": \"/courses|/sessions|/forum|/console|/reports|/dashboard|null\","
        " \"confidence\": 0.0-1.0, \"reason\": \"short\"}"
    )

    response = invoke_llm_with_metrics(llm, prompt, model_name)
    if not response.success:
        return None

    parsed = parse_json_response(response.content or "")
    if not parsed:
        return None

    route = parsed.get("route")
    confidence = parsed.get("confidence", 0)
    if route in available_routes and isinstance(confidence, (int, float)) and confidence >= 0.5:
        return route

    return None


def _validate_tool_args(tool_name: str, args: dict, schema: dict) -> Optional[str]:
    required = schema.get("required", [])
    properties = schema.get("properties", {})

    for field in required:
        if field not in args:
            return f"Missing required field '{field}' for tool '{tool_name}'"

    for field, value in args.items():
        expected = properties.get(field, {}).get("type")
        if not expected:
            continue
        if expected == "integer" and not isinstance(value, int):
            return f"Field '{field}' must be integer"
        if expected == "string" and not isinstance(value, str):
            return f"Field '{field}' must be string"
        if expected == "array" and not isinstance(value, list):
            return f"Field '{field}' must be array"
        if expected == "boolean" and not isinstance(value, bool):
            return f"Field '{field}' must be boolean"
    return None


def generate_conversational_response(
    intent_type: str,
    intent_value: str,
    results: Optional[Any] = None,
    context: Optional[List[str]] = None,
    current_page: Optional[str] = None,
) -> str:
    """Generate a natural conversational response for various intents."""

    if intent_type == 'navigate':
        page_names = {
            '/courses': 'courses',
            '/sessions': 'sessions',
            '/forum': 'forum',
            '/console': 'instructor console',
            '/reports': 'reports',
            '/dashboard': 'dashboard',
        }
        page_name = page_names.get(intent_value, intent_value)
        responses = [
            f"Taking you to {page_name} now.",
            f"Opening {page_name} for you.",
            f"Let me open the {page_name} page.",
        ]
        return responses[hash(intent_value) % len(responses)]

    if intent_type == 'execute':
        # Handle result that might be a dict with message/error
        if isinstance(results, dict):
            if results.get("message"):
                return results["message"]
            if results.get("error"):
                return f"Sorry, there was an issue: {results['error']}"

        # === UI INTERACTION RESPONSES ===
        if intent_value == 'ui_select_course':
            if isinstance(results, dict):
                available = results.get("available_options", [])
                if available and len(available) > 0:
                    return f"Selecting the course. You have {len(available)} courses available."
            return "Selecting the course for you."

        if intent_value == 'ui_select_session':
            return "Selecting the session for you."

        if intent_value == 'ui_switch_tab':
            if isinstance(results, dict):
                tab_name = results.get("ui_actions", [{}])[0].get("payload", {}).get("tabName", "")
                if tab_name:
                    return f"Switching to the {tab_name} tab."
            return "Switching tabs."

        if intent_value == 'ui_click_button':
            if isinstance(results, dict):
                button_label = results.get("ui_actions", [{}])[0].get("payload", {}).get("buttonLabel", "")
                if button_label:
                    return f"Clicking {button_label}."
            return "Clicking the button."

        # === COURSE RESPONSES ===
        if intent_value == 'list_courses':
            if isinstance(results, list) and len(results) > 0:
                course_names = [c.get('title', 'Untitled') for c in results[:5]]
                if len(results) == 1:
                    return f"You have one course: {course_names[0]}. Would you like me to open it?"
                elif len(results) <= 3:
                    return f"You have {len(results)} courses: {', '.join(course_names)}. Which one would you like to work with?"
                else:
                    return f"You have {len(results)} courses, including {', '.join(course_names[:3])}, and {len(results) - 3} more. Would you like to see them all?"
            return "You don't have any courses yet. Would you like me to help you create one?"

        if intent_value == 'create_course':
            return "Opening course creation. Tell me the course title, or I can help you set it up step by step."

        if intent_value == 'select_course':
            if isinstance(results, dict) and results.get("course"):
                course = results["course"]
                return f"Opening {course.get('title', 'the course')}. What would you like to do with it?"
            return "I'll open the first course for you. You can also say 'open second course' or specify a course name."

        if intent_value == 'view_course_details':
            if isinstance(results, dict) and results.get("title"):
                return f"Here's {results['title']}. It has {results.get('session_count', 0)} sessions."
            return "I couldn't find the course details. Make sure you're on a course page."

        # === SESSION RESPONSES ===
        if intent_value == 'list_sessions':
            if isinstance(results, list) and len(results) > 0:
                live = [s for s in results if s.get('status') == 'live']
                if live:
                    return f"There {'is' if len(live) == 1 else 'are'} {len(live)} live session{'s' if len(live) > 1 else ''}: {', '.join(s.get('title', 'Untitled') for s in live[:3])}. Would you like to join one?"
                return f"You have {len(results)} sessions. None are live right now. Would you like to start one?"
            return "No sessions found. Would you like to create a new session?"

        if intent_value == 'create_session':
            return "Opening session creation. What topic will this session cover?"

        if intent_value == 'select_session':
            if isinstance(results, dict) and results.get("session"):
                session = results["session"]
                return f"Opening {session.get('title', 'the session')}. Status: {session.get('status', 'unknown')}."
            return "Opening the first session. You can also say 'open second session' or specify a session name."

        if intent_value == 'go_live':
            return "Session is now live! Students can join and start participating. The copilot is ready when you need it."

        if intent_value == 'end_session':
            return "Session has ended. Would you like me to generate a report?"

        if intent_value == 'view_materials':
            return "Opening the course materials. You can view and download uploaded files here."

        # === SESSION STATUS MANAGEMENT RESPONSES ===
        if intent_value == 'set_session_draft':
            return "Session has been set to draft. You can edit it or go live when ready."

        if intent_value == 'set_session_live':
            return "Session is now live! Students can join and start participating."

        if intent_value == 'set_session_completed':
            return "Session has been completed. You can now generate a report for this session."

        if intent_value == 'schedule_session':
            return "Session has been scheduled. You can go live when you're ready to start."

        # === REPORT RESPONSES ===
        if intent_value == 'refresh_report':
            return "Refreshing the report to show the latest data."

        if intent_value == 'regenerate_report':
            return "Regenerating the report. This may take a moment to complete."

        # === THEME AND USER MENU RESPONSES ===
        if intent_value == 'toggle_theme':
            return "Toggling between light and dark mode."

        if intent_value == 'open_user_menu':
            return "Opening the user menu."

        if intent_value == 'view_voice_guide':
            return "Opening the voice command guide to show all available voice commands."

        if intent_value == 'forum_instructions':
            return "Opening the platform instructions to show how to use AristAI."

        if intent_value == 'open_profile':
            return "Opening your profile settings."

        if intent_value == 'sign_out':
            return "Signing you out. Goodbye!"

        if intent_value == 'close_modal':
            return "Closing the window."

        # === COPILOT RESPONSES ===
        if intent_value == 'start_copilot':
            return "Copilot is now active! It will monitor the discussion and provide suggestions every 90 seconds."

        if intent_value == 'stop_copilot':
            return "Copilot has been stopped. You can restart it anytime by saying 'start copilot'."

        if intent_value == 'refresh_interventions':
            return "Refreshing interventions from the copilot."

        if intent_value == 'get_interventions':
            if isinstance(results, list) and len(results) > 0:
                latest = results[0]
                suggestion = latest.get('suggestion_json', {})
                summary = suggestion.get('rolling_summary', '')
                confusion = suggestion.get('confusion_points', [])
                response = f"Here's the copilot insight: {summary}" if summary else "I have suggestions from the copilot."
                if confusion:
                    response += f" Detected {len(confusion)} confusion point{'s' if len(confusion) > 1 else ''}: {confusion[0].get('issue', 'Unknown')}."
                return response
            return "No suggestions yet. The copilot analyzes every 90 seconds when active."

        # === POLL RESPONSES ===
        if intent_value == 'create_poll':
            return "Great! What question would you like to ask in the poll?"

        # === REPORT RESPONSES ===
        if intent_value == 'generate_report':
            return "Generating the session report. This takes a moment to analyze all discussion posts."

        # === ENROLLMENT RESPONSES ===
        if intent_value == 'list_enrollments':
            if isinstance(results, list):
                return f"There are {len(results)} students enrolled. Would you like me to list them or show participation stats?"
            return "I couldn't retrieve the enrollment information."

        if intent_value == 'manage_enrollments':
            return "Opening enrollment management. You can add students by email or upload a roster."

        if intent_value == 'list_student_pool':
            if isinstance(results, dict) and results.get("students"):
                count = len(results.get("students", []))
                return f"There are {count} students available in the pool. Say a student's name to select them."
            return "I'll show you the available students."

        if intent_value == 'select_student':
            return "Student selected. Say another name to select more, or 'enroll selected' to enroll them."

        if intent_value == 'enroll_selected':
            return "Enrolling the selected students."

        if intent_value == 'enroll_all':
            return "Enrolling all available students."

        # === FORUM RESPONSES ===
        if intent_value == 'post_case':
            return "Opening case study creation. What scenario would you like students to discuss?"

        if intent_value == 'post_to_discussion':
            if isinstance(results, dict):
                if results.get("post_offer"):
                    return results.get("message", "Would you like to post something to the discussion?")
                if results.get("error") == "no_session":
                    return results.get("message", "Please select a live session first.")
            return "Would you like to post something to the discussion?"

        if intent_value == 'view_posts':
            if isinstance(results, dict) and results.get("posts"):
                posts = results["posts"]
                if len(posts) > 0:
                    return f"There are {len(posts)} posts in the forum. The latest is about: {posts[0].get('content', '')[:50]}..."
            return "No posts yet in this session's forum."

        if intent_value == 'get_pinned_posts':
            if isinstance(results, dict):
                count = results.get("count", 0)
                if count > 0:
                    return f"There are {count} pinned posts. These are the important discussions highlighted by the instructor."
                return "No pinned posts yet. You can pin important posts to highlight them."
            return "No pinned posts found."

        if intent_value == 'summarize_discussion':
            if isinstance(results, dict):
                if results.get("summary"):
                    return results["summary"]
                if results.get("error"):
                    return results["error"]
            return "I couldn't summarize the discussion. Make sure you're in a live session."

        if intent_value == 'get_student_questions':
            if isinstance(results, dict):
                count = results.get("count", 0)
                if count > 0:
                    questions = results.get("questions", [])
                    first_q = questions[0].get('content', '')[:80] if questions else ""
                    return f"Found {count} questions. The most recent: {first_q}..."
                return "No questions from students yet."
            return "I couldn't find any questions."

        if intent_value == 'get_status':
            if isinstance(results, dict):
                message = results.get("message", "")
                actions = results.get("available_actions", [])
                if actions:
                    return f"{message} You can: {', '.join(actions[:4])}."
                return message
            return "I'm not sure what page you're on."

        if intent_value == 'get_help':
            if isinstance(results, dict) and results.get("message"):
                return results["message"]
            return "I can help with navigation, courses, sessions, polls, forum, and reports."

        # === UNDO/CONTEXT RESPONSES ===
        if intent_value == 'undo_action':
            if isinstance(results, dict):
                if results.get("error"):
                    return results["error"]
                if results.get("message"):
                    return results["message"]
            return "I've undone the last action."

        if intent_value == 'get_context':
            if isinstance(results, dict):
                if results.get("message"):
                    return results["message"]
                course = results.get("course_name", "none")
                session = results.get("session_name", "none")
                return f"Your active course is {course} and session is {session}."
            return "You don't have any active context."

        if intent_value == 'clear_context':
            return "Context cleared! Starting fresh."

    # Default fallback
    return "I can help you navigate pages, manage courses and sessions, create polls, generate reports, and more. What would you like to do?"


@router.post("/converse", response_model=ConverseResponse)
async def voice_converse(request: ConverseRequest, db: Session = Depends(get_db)):
    """
    Conversational voice endpoint that processes natural language
    and returns appropriate responses with actions.

    CONVERSATIONAL FLOW:
    1. Check conversation state (awaiting input, confirmation, dropdown selection)
    2. Process based on state if active
    3. Regex navigation check (instant)
    4. Regex action check (instant)
    5. LLM orchestrator (only for complex requests)
    6. Template-based summary (no LLM)
    """
    transcript = request.transcript.strip()

    if not transcript:
        return ConverseResponse(
            message=sanitize_speech("I didn't catch that. Could you say it again?"),
            suggestions=["Show my courses", "Start a session", "Open forum"]
        )

    # === CHECK CONVERSATION STATE FIRST ===
    # Handle ongoing conversational flows (form filling, dropdown selection, confirmation)
    conv_context = conversation_manager.get_context(request.user_id)
    print(f"🔍 VOICE STATE: user_id={request.user_id}, state={conv_context.state}, transcript='{transcript[:50]}...'")

    # --- Handle confirmation state ---
    if conv_context.state == ConversationState.AWAITING_CONFIRMATION:
        # Check if user confirmed or denied
        confirmed = is_confirmation(transcript)
        denial_words = ['no', 'nope', 'cancel', 'stop', 'never mind', 'nevermind']
        denied = any(word in transcript.lower() for word in denial_words)

        if confirmed or denied:
            result = conversation_manager.process_confirmation(request.user_id, confirmed)
            if result["confirmed"] and result["action"]:
                # For ui_click_button, use action_data directly instead of execute_action
                # (because process_confirmation already cleared pending_action_data)
                if result["action"] == "ui_click_button" and result.get("action_data"):
                    action_data = result["action_data"]
                    button_target = action_data.get("voice_id")
                    form_name = action_data.get("form_name", "")
                    button_label = form_name.replace("_", " ").title() if form_name else "Submit"

                    # Debug logging
                    print(f"🔘 CONFIRMATION: Clicking button '{button_target}' for form '{form_name}'")
                    print(f"🔘 action_data: {action_data}")

                    conversation_manager.reset_retry_count(request.user_id)
                    return ConverseResponse(
                        message=sanitize_speech(f"Submitting the form. Clicking {button_label}."),
                        action=ActionResponse(type='execute', executed=True),
                        results=[{
                            "action": "click_button",
                            "ui_actions": [
                                {"type": "ui.clickButton", "payload": {"target": button_target}},
                                {"type": "ui.toast", "payload": {"message": f"{button_label} submitted", "type": "success"}},
                            ],
                        }],
                        suggestions=["What's next?", "Go to another page"],
                    )

                # For other actions, use execute_action
                action_result = await execute_action(
                    result["action"],
                    request.user_id,
                    request.current_page,
                    db,
                    transcript
                )
                conversation_manager.reset_retry_count(request.user_id)
                return ConverseResponse(
                    message=sanitize_speech(result["message"]),
                    action=ActionResponse(type='execute', executed=True),
                    results=[action_result] if action_result else None,
                    suggestions=get_action_suggestions(result["action"]),
                )
            else:
                return ConverseResponse(
                    message=sanitize_speech(result["message"]),
                    action=ActionResponse(type='info'),
                    suggestions=["Show my courses", "Go to forum", "What can I do?"],
                )
        # If not clear confirmation/denial, ask again
        return ConverseResponse(
            message=sanitize_speech("Please say 'yes' to confirm or 'no' to cancel."),
            action=ActionResponse(type='info'),
            suggestions=["Yes, proceed", "No, cancel"],
        )

    # --- Handle dropdown selection state ---
    if conv_context.state == ConversationState.AWAITING_DROPDOWN_SELECTION:
        print(f"🔍 DROPDOWN STATE: Checking cancel for transcript: '{transcript}'")
        print(f"🔍 DROPDOWN STATE: active_dropdown={conv_context.active_dropdown}, options_count={len(conv_context.dropdown_options)}")

        # Check for cancel/exit keywords BEFORE trying to match selection
        cancel_words = ['cancel', 'stop', 'exit', 'quit', 'abort', 'nevermind', 'never mind', 'go back', 'no thanks', "don't want", "dont want", "no one", "nobody", "none", "no", "nope", "skip"]
        transcript_lower = transcript.lower()
        matched_cancel = [word for word in cancel_words if word in transcript_lower]
        print(f"🔍 DROPDOWN STATE: Cancel words matched: {matched_cancel}")

        if matched_cancel:
            result = conversation_manager.cancel_dropdown_selection(request.user_id)
            return ConverseResponse(
                message=sanitize_speech(result["message"]),
                action=ActionResponse(type='info'),
                suggestions=["Go to sessions", "View courses", "Help"],
            )

        # Check for navigation intent - user wants to go somewhere else
        nav_path = detect_navigation_intent(transcript)
        if nav_path:
            conversation_manager.cancel_dropdown_selection(request.user_id)
            message = sanitize_speech(f"Cancelling selection. {generate_conversational_response('navigate', nav_path)}")
            return ConverseResponse(
                message=message,
                action=ActionResponse(type='navigate', target=nav_path),
                results=[{
                    "ui_actions": [
                        {"type": "ui.navigate", "payload": {"path": nav_path}},
                    ]
                }],
                suggestions=["What's next?", "Go back", "Help me"],
            )

        result = conversation_manager.select_dropdown_option(request.user_id, transcript)
        if result["success"]:
            selected = result["selected"]
            voice_id = result["voice_id"]
            conversation_manager.reset_retry_count(request.user_id)

            # Update context memory based on what was selected
            if request.user_id and selected.value:
                try:
                    selected_id = int(selected.value)
                    if voice_id and 'course' in voice_id.lower():
                        # Course was selected - update active course
                        context_store.update_context(request.user_id, active_course_id=selected_id)
                        print(f"🔍 Updated active_course_id to {selected_id} for user {request.user_id}")
                    elif voice_id and 'session' in voice_id.lower():
                        # Session was selected - update active session
                        context_store.update_context(request.user_id, active_session_id=selected_id)
                        print(f"🔍 Updated active_session_id to {selected_id} for user {request.user_id}")
                except (ValueError, TypeError):
                    pass  # Value wasn't a numeric ID

            return ConverseResponse(
                message=sanitize_speech(result["message"]),
                action=ActionResponse(type='execute', executed=True),
                results=[{
                    "ui_actions": [
                        {"type": "ui.selectDropdown", "payload": {
                            "target": voice_id,
                            "value": selected.value,
                            "optionName": selected.label,
                        }},
                        {"type": "ui.toast", "payload": {"message": f"Selected: {selected.label}", "type": "success"}},
                    ]
                }],
                suggestions=["What's next?", "Go to another page", "Help me"],
            )
        else:
            # Couldn't match selection, offer options again
            return ConverseResponse(
                message=sanitize_speech(result["message"]),
                action=ActionResponse(type='info'),
                suggestions=["Say the number", "Say the name", "Cancel"],
            )

    # --- Handle form field input state ---
    if conv_context.state == ConversationState.AWAITING_FIELD_INPUT:
        current_field = conversation_manager.get_current_field(request.user_id)
        if current_field:
            # FIRST: Check if user wants to navigate away or switch tabs (escape from form)
            # Check for navigation intent
            nav_path = detect_navigation_intent(transcript)
            if nav_path:
                # User wants to navigate - cancel form and navigate
                conversation_manager.cancel_form(request.user_id)
                message = sanitize_speech(f"Cancelling form. {generate_conversational_response('navigate', nav_path)}")
                return ConverseResponse(
                    message=message,
                    action=ActionResponse(type='navigate', target=nav_path),
                    results=[{
                        "ui_actions": [
                            {"type": "ui.navigate", "payload": {"path": nav_path}},
                        ]
                    }],
                    suggestions=get_page_suggestions(nav_path)
                )

            # Check for tab switching intent (e.g., "go to manage status tab")
            tab_patterns = [
                (r'\b(go\s+to|switch\s+to|open)\s+(the\s+)?(manage\s*status|management)\s*(tab)?\b', 'manage'),
                (r'\b(go\s+to|switch\s+to|open)\s+(the\s+)?(create|creation)\s*(tab)?\b', 'create'),
                (r'\b(go\s+to|switch\s+to|open)\s+(the\s+)?(view|sessions?|list)\s*(tab)?\b', 'sessions'),
                (r'\b(go\s+to|switch\s+to|open)\s+(the\s+)?(enrollment|enroll)\s*(tab)?\b', 'enrollment'),
            ]
            for pattern, tab_name in tab_patterns:
                if re.search(pattern, transcript.lower()):
                    # User wants to switch tabs - cancel form and switch
                    conversation_manager.cancel_form(request.user_id)

                    # Special handling for manage status tab - offer status options
                    if tab_name == 'manage':
                        return ConverseResponse(
                            message=sanitize_speech("Cancelling form. Switching to manage status tab. You can say 'go live', 'set to draft', 'complete', or 'schedule' to change the session status."),
                            action=ActionResponse(type='execute', executed=True),
                            results=[{
                                "ui_actions": [
                                    {"type": "ui.switchTab", "payload": {"tabName": tab_name}},
                                    {"type": "ui.toast", "payload": {"message": "Switched to manage status", "type": "info"}},
                                ]
                            }],
                            suggestions=["Go live", "Set to draft", "Complete session", "Schedule"],
                        )

                    return ConverseResponse(
                        message=sanitize_speech(f"Cancelling form. Switching to {tab_name} tab."),
                        action=ActionResponse(type='execute', executed=True),
                        results=[{
                            "ui_actions": [
                                {"type": "ui.switchTab", "payload": {"tabName": tab_name}},
                                {"type": "ui.toast", "payload": {"message": f"Switched to {tab_name}", "type": "info"}},
                            ]
                        }],
                        suggestions=["Go live", "View sessions", "Create session"],
                    )

            # Check for cancel/exit keywords
            cancel_words = ['cancel', 'stop', 'exit', 'quit', 'abort', 'nevermind', 'never mind']
            if any(word in transcript.lower() for word in cancel_words):
                conversation_manager.cancel_form(request.user_id)
                return ConverseResponse(
                    message=sanitize_speech("Form cancelled. What would you like to do?"),
                    action=ActionResponse(type='info'),
                    suggestions=["Create course", "Create session", "Go to forum"],
                )

            # Check for skip/next keywords
            skip_words = ['skip', 'next', 'pass', 'later', 'none', 'nothing']
            if any(word in transcript.lower() for word in skip_words):
                skip_result = conversation_manager.skip_current_field(request.user_id)
                return ConverseResponse(
                    message=sanitize_speech(skip_result["message"]),
                    action=ActionResponse(type='info'),
                    suggestions=["Continue", "Cancel form", "Help"],
                )

            # Check if this is the course title field - save it for later generation
            if current_field.voice_id == "course-title":
                # Save the course name for potential AI generation
                conv_context = conversation_manager.get_context(request.user_id)
                conv_context.course_name_for_generation = transcript.strip().rstrip('.!?,')
                conversation_manager.save_context(request.user_id, conv_context)

            # Check if we're on the syllabus field - offer AI generation
            if current_field.voice_id == "syllabus":
                # Check if user wants AI to generate it
                generate_words = ['generate', 'create', 'make', 'write', 'ai', 'auto', 'automatic', 'yes please', 'help me']
                if any(word in transcript.lower() for word in generate_words):
                    conv_context = conversation_manager.get_context(request.user_id)
                    course_name = conv_context.course_name_for_generation or conv_context.collected_values.get("course-title", "this course")
                    conv_context.state = ConversationState.AWAITING_SYLLABUS_GENERATION_CONFIRM
                    conversation_manager.save_context(request.user_id, conv_context)
                    return ConverseResponse(
                        message=sanitize_speech(f"I can generate a syllabus for '{course_name}'. Would you like me to create one?"),
                        action=ActionResponse(type='info'),
                        suggestions=["Yes, generate it", "No, I'll dictate", "Skip"],
                    )

            # Check if we're on the learning objectives field - offer AI generation
            if current_field.voice_id == "learning-objectives":
                # Check if user wants AI to generate it
                generate_words = ['generate', 'create', 'make', 'write', 'ai', 'auto', 'automatic', 'yes please', 'help me']
                if any(word in transcript.lower() for word in generate_words):
                    conv_context = conversation_manager.get_context(request.user_id)
                    course_name = conv_context.course_name_for_generation or conv_context.collected_values.get("course-title", "this course")
                    conv_context.state = ConversationState.AWAITING_OBJECTIVES_GENERATION_CONFIRM
                    conversation_manager.save_context(request.user_id, conv_context)
                    return ConverseResponse(
                        message=sanitize_speech(f"I can generate learning objectives for '{course_name}'. Would you like me to create them?"),
                        action=ActionResponse(type='info'),
                        suggestions=["Yes, generate them", "No, I'll dictate", "Skip"],
                    )

            # Check if we're on session description field - offer AI session plan generation
            if current_field.voice_id == "textarea-session-description":
                generate_words = ['generate', 'create', 'make', 'write', 'ai', 'auto', 'automatic', 'yes please', 'help me', 'session plan', 'case study', 'discussion']
                if any(word in transcript.lower() for word in generate_words):
                    conv_context = conversation_manager.get_context(request.user_id)
                    session_topic = conv_context.collected_values.get("input-session-title", "this session")
                    conv_context.state = ConversationState.AWAITING_SESSION_PLAN_GENERATION_CONFIRM
                    conversation_manager.save_context(request.user_id, conv_context)
                    return ConverseResponse(
                        message=sanitize_speech(f"I can generate a session plan for '{session_topic}' including discussion prompts and a case study. Would you like me to create it?"),
                        action=ActionResponse(type='info'),
                        suggestions=["Yes, generate it", "No, I'll dictate", "Skip"],
                    )

            # Record the user's answer and fill the field
            result = conversation_manager.record_field_value(request.user_id, transcript)
            field_to_fill = result["field_to_fill"]

            ui_actions = []
            if field_to_fill:
                # Use sanitized value from all_values (trailing punctuation removed)
                sanitized_value = result["all_values"].get(field_to_fill.voice_id, transcript)
                ui_actions.append({
                    "type": "ui.fillInput",
                    "payload": {
                        "target": field_to_fill.voice_id,
                        "value": sanitized_value,
                    }
                })
                ui_actions.append({
                    "type": "ui.toast",
                    "payload": {"message": f"{field_to_fill.name} filled", "type": "success"}
                })

            if result["done"]:
                conversation_manager.reset_retry_count(request.user_id)

            return ConverseResponse(
                message=sanitize_speech(result["next_prompt"] or "Form complete!"),
                action=ActionResponse(type='execute', executed=True),
                results=[{"ui_actions": ui_actions, "all_values": result["all_values"]}],
                suggestions=["Submit", "Cancel", "Go back"] if result["done"] else ["Skip", "Cancel"],
            )

    # --- Handle forum post offer response state ---
    if conv_context.state == ConversationState.AWAITING_POST_OFFER_RESPONSE:
        # Check if user accepted or declined
        accept_words = ['yes', 'yeah', 'yep', 'sure', 'okay', 'ok', 'please', 'go ahead', "i'd like to", "i would like"]
        decline_words = ['no', 'nope', 'not now', 'hold on', 'wait', 'no thanks', 'later', 'nevermind', 'never mind']

        transcript_lower = transcript.lower()
        accepted = any(word in transcript_lower for word in accept_words)
        declined = any(word in transcript_lower for word in decline_words)

        if accepted and not declined:
            result = conversation_manager.handle_post_offer_response(request.user_id, True)
            return ConverseResponse(
                message=sanitize_speech(result["message"]),
                action=ActionResponse(type='info'),
                suggestions=["I'm done", "Cancel"],
            )
        elif declined:
            result = conversation_manager.handle_post_offer_response(request.user_id, False)
            return ConverseResponse(
                message=sanitize_speech(result["message"]),
                action=ActionResponse(type='info'),
                suggestions=["Switch to case studies", "Select another session", "Go to courses"],
            )
        else:
            # Unclear response - ask again
            return ConverseResponse(
                message=sanitize_speech("Would you like to post something to the discussion? Say yes or no."),
                action=ActionResponse(type='info'),
                suggestions=["Yes, I'd like to post", "No thanks"],
            )

    # --- Handle forum post dictation state ---
    if conv_context.state == ConversationState.AWAITING_POST_DICTATION:
        transcript_lower = transcript.lower().strip()

        # Check for navigation/escape intent first
        nav_path = detect_navigation_intent(transcript)
        if nav_path:
            conversation_manager.reset_post_offer(request.user_id)
            message = sanitize_speech(f"Cancelling post. {generate_conversational_response('navigate', nav_path)}")
            return ConverseResponse(
                message=message,
                action=ActionResponse(type='navigate', target=nav_path),
                results=[{
                    "ui_actions": [
                        {"type": "ui.navigate", "payload": {"path": nav_path}},
                    ]
                }],
                suggestions=get_page_suggestions(nav_path)
            )

        # Check for cancel keywords
        cancel_words = ['cancel', 'stop', 'abort', 'quit', 'nevermind', 'never mind']
        if any(word in transcript_lower for word in cancel_words):
            conversation_manager.reset_post_offer(request.user_id)
            return ConverseResponse(
                message=sanitize_speech("Post cancelled. What else can I help you with?"),
                action=ActionResponse(type='execute', executed=True),
                results=[{
                    "ui_actions": [
                        {"type": "ui.clearInput", "payload": {"target": "textarea-post-content"}},
                    ]
                }],
                suggestions=["Switch to case studies", "Select another session"],
            )

        # Check for "I'm done" / "finished" patterns
        done_patterns = [
            (r'\b(i\'?m\s+done|i\s+am\s+done)\b', 'done'),
            (r'\b(that\'?s\s+it|that\s+is\s+it)\b', 'that'),
            (r'\b(finished|i\'?m\s+finished|i\s+am\s+finished)\b', 'finished'),
            (r'\b(it\'?s\s+over|it\s+is\s+over)\b', 'over'),
            (r'\b(end|done|complete|finish)\s*(it|now|dictation|post)?\s*$', 'end'),
            (r'^done\.?$', 'done'),
            (r'^finished\.?$', 'finished'),
        ]

        # Check if any done pattern matches
        done_match = None
        content_before_done = None
        for pattern, _ in done_patterns:
            match = re.search(pattern, transcript_lower)
            if match:
                done_match = match
                # Extract content BEFORE the done keyword (user might say "This is my post. Finished.")
                content_before_done = transcript[:match.start()].strip()
                # Clean up trailing punctuation from the content
                content_before_done = re.sub(r'[.,;:!?\s]+$', '', content_before_done)
                break

        if done_match:
            # If there's content before the "done" keyword, save it first!
            if content_before_done:
                conversation_manager.append_post_content(request.user_id, content_before_done)

            result = conversation_manager.finish_post_dictation(request.user_id)
            if result["has_content"]:
                # Fill the textarea with the accumulated content before asking for confirmation
                return ConverseResponse(
                    message=sanitize_speech(result["message"]),
                    action=ActionResponse(type='execute', executed=True),
                    results=[{
                        "ui_actions": [
                            {"type": "ui.fillInput", "payload": {"target": "textarea-post-content", "value": result["content"]}},
                        ]
                    }],
                    suggestions=["Yes, post it", "No, cancel"],
                )
            else:
                return ConverseResponse(
                    message=sanitize_speech(result["message"]),
                    action=ActionResponse(type='info'),
                    suggestions=["Yes, let me try again", "No, cancel"],
                )

        # Otherwise, this is dictation content - append it
        result = conversation_manager.append_post_content(request.user_id, transcript)

        # Update the textarea with current accumulated content
        return ConverseResponse(
            message=sanitize_speech(result["message"]),
            action=ActionResponse(type='execute', executed=True),
            results=[{
                "ui_actions": [
                    {"type": "ui.fillInput", "payload": {"target": "textarea-post-content", "value": result["content"]}},
                ]
            }],
            suggestions=["I'm done", "Cancel"],
        )

    # --- Handle forum post submit confirmation state ---
    if conv_context.state == ConversationState.AWAITING_POST_SUBMIT_CONFIRMATION:
        transcript_lower = transcript.lower()

        # Check for confirmation or denial
        confirm_words = ['yes', 'yeah', 'yep', 'sure', 'okay', 'ok', 'post it', 'submit', 'go ahead', 'do it']
        deny_words = ['no', 'nope', 'cancel', 'delete', 'clear', 'no thanks', 'nevermind', 'never mind']

        confirmed = any(word in transcript_lower for word in confirm_words)
        denied = any(word in transcript_lower for word in deny_words)

        if confirmed and not denied:
            result = conversation_manager.handle_post_submit_response(request.user_id, True)
            # Click the submit button
            return ConverseResponse(
                message=sanitize_speech(result["message"]),
                action=ActionResponse(type='execute', executed=True),
                results=[{
                    "ui_actions": [
                        {"type": "ui.clickButton", "payload": {"target": "submit-post"}},
                        {"type": "ui.toast", "payload": {"message": "Post submitted!", "type": "success"}},
                    ]
                }],
                suggestions=["View posts", "Switch to case studies", "Select another session"],
            )
        elif denied:
            # Don't fully reset - ask if they want to try again
            conversation_manager.handle_post_submit_response(request.user_id, False)
            # Set state back to offer response so they can say yes/no to try again
            offer_prompt = conversation_manager.offer_forum_post(request.user_id)
            # Clear the textarea and ask if they want to try again
            return ConverseResponse(
                message=sanitize_speech("Okay, I've cleared the post. Would you like to try again?"),
                action=ActionResponse(type='execute', executed=True),
                results=[{
                    "ui_actions": [
                        {"type": "ui.clearInput", "payload": {"target": "textarea-post-content"}},
                        {"type": "ui.toast", "payload": {"message": "Post cleared", "type": "info"}},
                    ]
                }],
                suggestions=["Yes, let me try again", "No thanks"],
            )
        else:
            # Unclear response - ask again
            return ConverseResponse(
                message=sanitize_speech("Should I post this? Say yes to post or no to cancel."),
                action=ActionResponse(type='info'),
                suggestions=["Yes, post it", "No, cancel"],
            )

    # --- Handle poll offer response state ---
    if conv_context.state == ConversationState.AWAITING_POLL_OFFER_RESPONSE:
        # Check if user accepted or declined
        accept_words = ['yes', 'yeah', 'yep', 'sure', 'okay', 'ok', 'please', 'go ahead', "i'd like to", "i would like", "let's do it", "create one"]
        decline_words = ['no', 'nope', 'not now', 'hold on', 'wait', 'no thanks', 'later', 'nevermind', 'never mind']

        transcript_lower = transcript.lower()
        accepted = any(word in transcript_lower for word in accept_words)
        declined = any(word in transcript_lower for word in decline_words)

        if accepted and not declined:
            result = conversation_manager.handle_poll_offer_response(request.user_id, True)
            return ConverseResponse(
                message=sanitize_speech(result["message"]),
                action=ActionResponse(type='info'),
                suggestions=["Cancel"],
            )
        elif declined:
            result = conversation_manager.handle_poll_offer_response(request.user_id, False)
            return ConverseResponse(
                message=sanitize_speech(result["message"]),
                action=ActionResponse(type='info'),
                suggestions=["Switch to copilot", "Switch to roster", "Go to courses"],
            )
        else:
            # Unclear response - ask again
            return ConverseResponse(
                message=sanitize_speech("Would you like to create a poll? Say yes or no."),
                action=ActionResponse(type='info'),
                suggestions=["Yes, create a poll", "No thanks"],
            )

    # --- Handle poll question state ---
    if conv_context.state == ConversationState.AWAITING_POLL_QUESTION:
        transcript_lower = transcript.lower().strip()

        # Check for navigation/escape intent first
        nav_path = detect_navigation_intent(transcript)
        if nav_path:
            conversation_manager.reset_poll_offer(request.user_id)
            message = sanitize_speech(f"Cancelling poll creation. {generate_conversational_response('navigate', nav_path)}")
            return ConverseResponse(
                message=message,
                action=ActionResponse(type='navigate', target=nav_path),
                results=[{
                    "ui_actions": [
                        {"type": "ui.navigate", "payload": {"path": nav_path}},
                    ]
                }],
                suggestions=get_page_suggestions(nav_path)
            )

        # Check for cancel keywords
        cancel_words = ['cancel', 'stop', 'abort', 'quit', 'nevermind', 'never mind']
        if any(word in transcript_lower for word in cancel_words):
            conversation_manager.reset_poll_offer(request.user_id)
            return ConverseResponse(
                message=sanitize_speech("Poll creation cancelled. What else can I help you with?"),
                action=ActionResponse(type='info'),
                suggestions=["Switch to copilot", "Switch to roster"],
            )

        # This is the poll question
        result = conversation_manager.set_poll_question(request.user_id, transcript)
        ui_actions = []
        for action_item in result.get("ui_actions", []):
            ui_actions.append({
                "type": f"ui.{action_item['action']}",
                "payload": {"target": action_item["voiceId"], "value": action_item.get("value", "")}
            })

        return ConverseResponse(
            message=sanitize_speech(result["message"]),
            action=ActionResponse(type='execute', executed=True),
            results=[{"ui_actions": ui_actions}],
            suggestions=["Cancel"],
        )

    # --- Handle poll option state ---
    if conv_context.state == ConversationState.AWAITING_POLL_OPTION:
        transcript_lower = transcript.lower().strip()

        # Check for navigation/escape intent first
        nav_path = detect_navigation_intent(transcript)
        if nav_path:
            conversation_manager.reset_poll_offer(request.user_id)
            message = sanitize_speech(f"Cancelling poll creation. {generate_conversational_response('navigate', nav_path)}")
            return ConverseResponse(
                message=message,
                action=ActionResponse(type='navigate', target=nav_path),
                results=[{
                    "ui_actions": [
                        {"type": "ui.navigate", "payload": {"path": nav_path}},
                    ]
                }],
                suggestions=get_page_suggestions(nav_path)
            )

        # Check for cancel keywords
        cancel_words = ['cancel', 'stop', 'abort', 'quit', 'nevermind', 'never mind']
        if any(word in transcript_lower for word in cancel_words):
            conversation_manager.reset_poll_offer(request.user_id)
            return ConverseResponse(
                message=sanitize_speech("Poll creation cancelled. What else can I help you with?"),
                action=ActionResponse(type='info'),
                suggestions=["Switch to copilot", "Switch to roster"],
            )

        # This is a poll option
        result = conversation_manager.add_poll_option(request.user_id, transcript)
        ui_actions = []
        for action_item in result.get("ui_actions", []):
            ui_actions.append({
                "type": f"ui.{action_item['action']}",
                "payload": {"target": action_item["voiceId"], "value": action_item.get("value", "")}
            })

        suggestions = ["Cancel"]
        if result.get("ask_for_more"):
            suggestions = ["Yes, add more", "No, that's enough", "Cancel"]

        return ConverseResponse(
            message=sanitize_speech(result["message"]),
            action=ActionResponse(type='execute', executed=True),
            results=[{"ui_actions": ui_actions}],
            suggestions=suggestions,
        )

    # --- Handle poll more options response state ---
    if conv_context.state == ConversationState.AWAITING_POLL_MORE_OPTIONS:
        transcript_lower = transcript.lower()

        # Check for yes/no response
        yes_words = ['yes', 'yeah', 'yep', 'sure', 'okay', 'ok', 'another', 'more', 'add more', 'one more']
        no_words = ['no', 'nope', 'enough', "that's it", 'that is it', "that's enough", 'that is enough', 'done', "i'm done", 'finished', 'no more']

        wants_more = any(word in transcript_lower for word in yes_words)
        is_done = any(word in transcript_lower for word in no_words)

        if wants_more and not is_done:
            result = conversation_manager.handle_more_options_response(request.user_id, True)
            ui_actions = []
            for action_item in result.get("ui_actions", []):
                ui_actions.append({
                    "type": f"ui.{action_item['action']}",
                    "payload": {"target": action_item["voiceId"]}
                })

            return ConverseResponse(
                message=sanitize_speech(result["message"]),
                action=ActionResponse(type='execute', executed=True),
                results=[{"ui_actions": ui_actions}],
                suggestions=["Cancel"],
            )
        elif is_done:
            result = conversation_manager.handle_more_options_response(request.user_id, False)
            return ConverseResponse(
                message=sanitize_speech(result["message"]),
                action=ActionResponse(type='info'),
                suggestions=["Yes, create it", "No, cancel"],
            )
        else:
            # Unclear response - ask again
            return ConverseResponse(
                message=sanitize_speech("Would you like to add another option? Say yes or no."),
                action=ActionResponse(type='info'),
                suggestions=["Yes, add more", "No, that's enough"],
            )

    # --- Handle poll confirmation state ---
    if conv_context.state == ConversationState.AWAITING_POLL_CONFIRM:
        transcript_lower = transcript.lower()

        # Check for confirmation or denial
        confirm_words = ['yes', 'yeah', 'yep', 'sure', 'okay', 'ok', 'create it', 'submit', 'go ahead', 'do it', 'post it']
        deny_words = ['no', 'nope', 'cancel', 'delete', 'clear', 'no thanks', 'nevermind', 'never mind']

        confirmed = any(word in transcript_lower for word in confirm_words)
        denied = any(word in transcript_lower for word in deny_words)

        if confirmed and not denied:
            result = conversation_manager.handle_poll_confirm(request.user_id, True)
            ui_actions = []
            for action_item in result.get("ui_actions", []):
                ui_actions.append({
                    "type": f"ui.{action_item['action']}",
                    "payload": {"target": action_item["voiceId"]}
                })
            ui_actions.append({"type": "ui.toast", "payload": {"message": "Poll created!", "type": "success"}})

            return ConverseResponse(
                message=sanitize_speech(result["message"]),
                action=ActionResponse(type='execute', executed=True),
                results=[{"ui_actions": ui_actions}],
                suggestions=["Create another poll", "Switch to copilot", "View roster"],
            )
        elif denied:
            conversation_manager.reset_poll_offer(request.user_id)
            return ConverseResponse(
                message=sanitize_speech("Okay, poll creation cancelled. What else can I help you with?"),
                action=ActionResponse(type='info'),
                suggestions=["Create a new poll", "Switch to copilot", "View roster"],
            )
        else:
            # Unclear response - ask again
            return ConverseResponse(
                message=sanitize_speech("Should I create this poll? Say yes to create or no to cancel."),
                action=ActionResponse(type='info'),
                suggestions=["Yes, create it", "No, cancel"],
            )

    # --- Handle case offer response state ---
    if conv_context.state == ConversationState.AWAITING_CASE_OFFER_RESPONSE:
        # Check if user accepted or declined
        accept_words = ['yes', 'yeah', 'yep', 'sure', 'okay', 'ok', 'please', 'go ahead', "i'd like to", "i would like", "let's do it", "create one", "post one"]
        decline_words = ['no', 'nope', 'not now', 'hold on', 'wait', 'no thanks', 'later', 'nevermind', 'never mind']

        transcript_lower = transcript.lower()
        accepted = any(word in transcript_lower for word in accept_words)
        declined = any(word in transcript_lower for word in decline_words)

        if accepted and not declined:
            result = conversation_manager.handle_case_offer_response(request.user_id, True)
            return ConverseResponse(
                message=sanitize_speech(result["message"]),
                action=ActionResponse(type='info'),
                suggestions=["Cancel"],
            )
        elif declined:
            result = conversation_manager.handle_case_offer_response(request.user_id, False)
            return ConverseResponse(
                message=sanitize_speech(result["message"]),
                action=ActionResponse(type='info'),
                suggestions=["Switch to polls", "Switch to copilot", "Go to forum"],
            )
        else:
            # Unclear response - ask again
            return ConverseResponse(
                message=sanitize_speech("Would you like to post a case study? Say yes or no."),
                action=ActionResponse(type='info'),
                suggestions=["Yes, post a case", "No thanks"],
            )

    # --- Handle case prompt dictation state ---
    if conv_context.state == ConversationState.AWAITING_CASE_PROMPT:
        transcript_lower = transcript.lower().strip()

        # Check for navigation/escape intent first
        nav_path = detect_navigation_intent(transcript)
        if nav_path:
            conversation_manager.reset_case_offer(request.user_id)
            message = sanitize_speech(f"Cancelling case creation. {generate_conversational_response('navigate', nav_path)}")
            return ConverseResponse(
                message=message,
                action=ActionResponse(type='navigate', target=nav_path),
                results=[{
                    "ui_actions": [
                        {"type": "ui.navigate", "payload": {"path": nav_path}},
                    ]
                }],
                suggestions=get_page_suggestions(nav_path)
            )

        # Check for cancel keywords
        cancel_words = ['cancel', 'stop', 'abort', 'quit', 'nevermind', 'never mind']
        if any(word in transcript_lower for word in cancel_words):
            conversation_manager.reset_case_offer(request.user_id)
            return ConverseResponse(
                message=sanitize_speech("Case creation cancelled. What else can I help you with?"),
                action=ActionResponse(type='info'),
                suggestions=["Switch to polls", "Switch to copilot"],
            )

        # Check for "done" or "finished" keywords to finish dictation
        done_words = ['done', "i'm done", "that's it", "that is it", 'finished', 'post it', 'submit', "that's all", "that is all"]
        if any(word in transcript_lower for word in done_words):
            result = conversation_manager.finish_case_dictation(request.user_id)

            if result.get("ready_to_confirm"):
                return ConverseResponse(
                    message=sanitize_speech(result["message"]),
                    action=ActionResponse(type='info'),
                    suggestions=["Yes, post it", "No, cancel"],
                )
            else:
                # No content yet - ask again
                return ConverseResponse(
                    message=sanitize_speech(result["message"]),
                    action=ActionResponse(type='info'),
                    suggestions=["Cancel"],
                )

        # This is case content - append it
        result = conversation_manager.append_case_content(request.user_id, transcript)
        ui_actions = []
        for action_item in result.get("ui_actions", []):
            ui_actions.append({
                "type": f"ui.{action_item['action']}",
                "payload": {"target": action_item["voiceId"], "value": action_item.get("value", "")}
            })

        return ConverseResponse(
            message=sanitize_speech(result["message"]),
            action=ActionResponse(type='execute', executed=True),
            results=[{"ui_actions": ui_actions}],
            suggestions=["Done", "Cancel"],
        )

    # --- Handle case confirmation state ---
    if conv_context.state == ConversationState.AWAITING_CASE_CONFIRM:
        transcript_lower = transcript.lower()

        # Check for confirmation or denial
        confirm_words = ['yes', 'yeah', 'yep', 'sure', 'okay', 'ok', 'post it', 'submit', 'go ahead', 'do it', 'create it']
        deny_words = ['no', 'nope', 'cancel', 'delete', 'clear', 'no thanks', 'nevermind', 'never mind']

        confirmed = any(word in transcript_lower for word in confirm_words)
        denied = any(word in transcript_lower for word in deny_words)

        if confirmed and not denied:
            result = conversation_manager.handle_case_confirm(request.user_id, True)
            ui_actions = []
            for action_item in result.get("ui_actions", []):
                ui_actions.append({
                    "type": f"ui.{action_item['action']}",
                    "payload": {"target": action_item["voiceId"]}
                })
            ui_actions.append({"type": "ui.toast", "payload": {"message": "Case study posted!", "type": "success"}})

            return ConverseResponse(
                message=sanitize_speech(result["message"]),
                action=ActionResponse(type='execute', executed=True),
                results=[{"ui_actions": ui_actions}],
                suggestions=["Post another case", "Switch to polls", "View forum"],
            )
        elif denied:
            conversation_manager.reset_case_offer(request.user_id)
            return ConverseResponse(
                message=sanitize_speech("Okay, case posting cancelled. The content is still in the form if you want to edit it."),
                action=ActionResponse(type='info'),
                suggestions=["Post a new case", "Switch to polls", "View forum"],
            )
        else:
            # Unclear response - ask again
            return ConverseResponse(
                message=sanitize_speech("Should I post this case study? Say yes to post or no to cancel."),
                action=ActionResponse(type='info'),
                suggestions=["Yes, post it", "No, cancel"],
            )

    # --- Handle AI syllabus generation confirmation state ---
    if conv_context.state == ConversationState.AWAITING_SYLLABUS_GENERATION_CONFIRM:
        transcript_lower = transcript.lower()
        yes_words = ['yes', 'yeah', 'yep', 'sure', 'okay', 'ok', 'generate', 'create', 'please', 'go ahead', 'do it']
        no_words = ['no', 'nope', 'dictate', "i'll type", "i will type", "i'll write", "i will write", 'manual', 'myself', 'skip']

        accepted = any(word in transcript_lower for word in yes_words)
        declined = any(word in transcript_lower for word in no_words)

        if accepted and not declined:
            # Generate syllabus using AI
            course_name = conv_context.course_name_for_generation or "the course"

            # Call the content generation tool via MCP registry
            try:
                gen_result = _execute_tool(db, 'generate_syllabus', {"course_name": course_name})
            except Exception as e:
                import logging
                logging.getLogger(__name__).error(f"Syllabus generation error: {e}")
                gen_result = None

            if gen_result and gen_result.get("success") and gen_result.get("syllabus"):
                syllabus = gen_result["syllabus"]
                # Save the generated syllabus
                conv_context.generated_syllabus = syllabus
                conv_context.state = ConversationState.AWAITING_SYLLABUS_REVIEW
                conversation_manager.save_context(request.user_id, conv_context)

                # Preview (first 150 chars)
                preview = syllabus[:150] + "..." if len(syllabus) > 150 else syllabus

                return ConverseResponse(
                    message=sanitize_speech(f"I've generated a syllabus for '{course_name}'. Here's a preview: {preview}. Should I use this syllabus?"),
                    action=ActionResponse(type='info'),
                    results=[{
                        "ui_actions": [
                            {"type": "ui.fillInput", "payload": {"target": "syllabus", "value": syllabus}},
                        ]
                    }],
                    suggestions=["Yes, use it", "No, let me edit", "Skip syllabus"],
                )
            else:
                # Generation failed - fallback to manual
                conv_context.state = ConversationState.AWAITING_FIELD_INPUT
                conversation_manager.save_context(request.user_id, conv_context)
                error_msg = gen_result.get("error", "Generation failed") if gen_result else "Tool not available"
                return ConverseResponse(
                    message=sanitize_speech(f"Sorry, I couldn't generate the syllabus: {error_msg}. Please dictate the syllabus or say 'skip'."),
                    action=ActionResponse(type='info'),
                    suggestions=["Skip", "Cancel form"],
                )

        elif declined or 'skip' in transcript_lower:
            # User wants to dictate or skip
            if 'skip' in transcript_lower:
                skip_result = conversation_manager.skip_current_field(request.user_id)
                return ConverseResponse(
                    message=sanitize_speech(skip_result["message"]),
                    action=ActionResponse(type='info'),
                    suggestions=["Continue", "Cancel form"],
                )
            else:
                conv_context.state = ConversationState.AWAITING_FIELD_INPUT
                conversation_manager.save_context(request.user_id, conv_context)
                return ConverseResponse(
                    message=sanitize_speech("Okay, please dictate the syllabus now. Say what you'd like to include."),
                    action=ActionResponse(type='info'),
                    suggestions=["Skip", "Cancel form"],
                )
        else:
            return ConverseResponse(
                message=sanitize_speech("Would you like me to generate a syllabus for you? Say 'yes' to generate, 'no' to dictate it yourself, or 'skip' to move on."),
                action=ActionResponse(type='info'),
                suggestions=["Yes, generate it", "No, I'll dictate", "Skip"],
            )

    # --- Handle syllabus review state ---
    if conv_context.state == ConversationState.AWAITING_SYLLABUS_REVIEW:
        transcript_lower = transcript.lower()
        accept_words = ['yes', 'yeah', 'yep', 'sure', 'okay', 'ok', 'use it', 'looks good', 'perfect', 'great', 'accept', 'good']
        edit_words = ['no', 'edit', 'change', 'modify', 'different', 'regenerate', 'try again']
        skip_words = ['skip', 'next', 'move on']

        accepted = any(word in transcript_lower for word in accept_words)
        wants_edit = any(word in transcript_lower for word in edit_words)
        wants_skip = any(word in transcript_lower for word in skip_words)

        if accepted and not wants_edit:
            # Accept the generated syllabus and move to next field
            conv_context.collected_values["syllabus"] = conv_context.generated_syllabus
            conv_context.current_field_index += 1
            conv_context.generated_syllabus = ""
            conv_context.state = ConversationState.AWAITING_FIELD_INPUT
            conversation_manager.save_context(request.user_id, conv_context)

            # Get next field prompt
            next_field = conversation_manager.get_current_field(request.user_id)
            if next_field:
                # Offer AI generation for objectives too
                if next_field.voice_id == "learning-objectives":
                    conv_context.state = ConversationState.AWAITING_OBJECTIVES_GENERATION_CONFIRM
                    conversation_manager.save_context(request.user_id, conv_context)
                    return ConverseResponse(
                        message=sanitize_speech(f"Syllabus saved! Now for learning objectives. Would you like me to generate learning objectives based on the syllabus?"),
                        action=ActionResponse(type='info'),
                        suggestions=["Yes, generate them", "No, I'll dictate", "Skip"],
                    )
                return ConverseResponse(
                    message=sanitize_speech(f"Syllabus saved! {next_field.prompt}"),
                    action=ActionResponse(type='info'),
                    suggestions=["Skip", "Cancel form"],
                )
            else:
                return ConverseResponse(
                    message=sanitize_speech("Syllabus saved! The form is ready to submit. Would you like me to create the course?"),
                    action=ActionResponse(type='info'),
                    suggestions=["Yes, create course", "No, cancel"],
                )

        elif wants_skip:
            skip_result = conversation_manager.skip_current_field(request.user_id)
            conv_context.generated_syllabus = ""
            conversation_manager.save_context(request.user_id, conv_context)
            return ConverseResponse(
                message=sanitize_speech(skip_result["message"]),
                action=ActionResponse(type='info'),
                results=[{
                    "ui_actions": [
                        {"type": "ui.clearInput", "payload": {"target": "syllabus"}},
                    ]
                }],
                suggestions=["Continue", "Cancel form"],
            )

        else:
            # User wants to edit - keep the text in the form for manual editing
            conv_context.state = ConversationState.AWAITING_FIELD_INPUT
            conversation_manager.save_context(request.user_id, conv_context)
            return ConverseResponse(
                message=sanitize_speech("The syllabus is in the form. You can edit it manually, or dictate a new one. Say 'done' when finished or 'skip' to move on."),
                action=ActionResponse(type='info'),
                suggestions=["Skip", "Cancel form"],
            )

    # --- Handle AI objectives generation confirmation state ---
    if conv_context.state == ConversationState.AWAITING_OBJECTIVES_GENERATION_CONFIRM:
        transcript_lower = transcript.lower()
        yes_words = ['yes', 'yeah', 'yep', 'sure', 'okay', 'ok', 'generate', 'create', 'please', 'go ahead', 'do it']
        no_words = ['no', 'nope', 'dictate', "i'll type", "i will type", "i'll write", "i will write", 'manual', 'myself', 'skip']

        accepted = any(word in transcript_lower for word in yes_words)
        declined = any(word in transcript_lower for word in no_words)

        if accepted and not declined:
            # Generate objectives using AI
            course_name = conv_context.course_name_for_generation or "the course"
            syllabus = conv_context.collected_values.get("syllabus", "")

            try:
                gen_result = _execute_tool(db, 'generate_objectives', {"course_name": course_name, "syllabus": syllabus})
            except Exception as e:
                import logging
                logging.getLogger(__name__).error(f"Objectives generation error: {e}")
                gen_result = None

            if gen_result and gen_result.get("success") and gen_result.get("objectives"):
                objectives = gen_result["objectives"]
                objectives_text = "\n".join(f"- {obj}" for obj in objectives)

                # Save the generated objectives
                conv_context.generated_objectives = objectives
                conv_context.state = ConversationState.AWAITING_OBJECTIVES_REVIEW
                conversation_manager.save_context(request.user_id, conv_context)

                # Preview (first 3 objectives)
                preview = ", ".join(objectives[:3])
                if len(objectives) > 3:
                    preview += f", and {len(objectives) - 3} more"

                return ConverseResponse(
                    message=sanitize_speech(f"I've generated {len(objectives)} learning objectives. Here are the first few: {preview}. Should I use these objectives?"),
                    action=ActionResponse(type='info'),
                    results=[{
                        "ui_actions": [
                            {"type": "ui.fillInput", "payload": {"target": "learning-objectives", "value": objectives_text}},
                        ]
                    }],
                    suggestions=["Yes, use them", "No, let me edit", "Skip objectives"],
                )
            else:
                # Generation failed
                conv_context.state = ConversationState.AWAITING_FIELD_INPUT
                conversation_manager.save_context(request.user_id, conv_context)
                error_msg = gen_result.get("error", "Generation failed") if gen_result else "Tool not available"
                return ConverseResponse(
                    message=sanitize_speech(f"Sorry, I couldn't generate objectives: {error_msg}. Please dictate them or say 'skip'."),
                    action=ActionResponse(type='info'),
                    suggestions=["Skip", "Cancel form"],
                )

        elif declined or 'skip' in transcript_lower:
            if 'skip' in transcript_lower:
                skip_result = conversation_manager.skip_current_field(request.user_id)
                return ConverseResponse(
                    message=sanitize_speech(skip_result["message"]),
                    action=ActionResponse(type='info'),
                    suggestions=["Continue", "Cancel form"],
                )
            else:
                conv_context.state = ConversationState.AWAITING_FIELD_INPUT
                conversation_manager.save_context(request.user_id, conv_context)
                return ConverseResponse(
                    message=sanitize_speech("Okay, please dictate the learning objectives now."),
                    action=ActionResponse(type='info'),
                    suggestions=["Skip", "Cancel form"],
                )
        else:
            return ConverseResponse(
                message=sanitize_speech("Would you like me to generate learning objectives? Say 'yes' to generate, 'no' to dictate them, or 'skip'."),
                action=ActionResponse(type='info'),
                suggestions=["Yes, generate them", "No, I'll dictate", "Skip"],
            )

    # --- Handle objectives review state ---
    if conv_context.state == ConversationState.AWAITING_OBJECTIVES_REVIEW:
        transcript_lower = transcript.lower()
        accept_words = ['yes', 'yeah', 'yep', 'sure', 'okay', 'ok', 'use them', 'looks good', 'perfect', 'great', 'accept', 'good']
        edit_words = ['no', 'edit', 'change', 'modify', 'different', 'regenerate', 'try again']
        skip_words = ['skip', 'next', 'move on']

        accepted = any(word in transcript_lower for word in accept_words)
        wants_edit = any(word in transcript_lower for word in edit_words)
        wants_skip = any(word in transcript_lower for word in skip_words)

        if accepted and not wants_edit:
            # Accept the generated objectives
            objectives_text = "\n".join(f"- {obj}" for obj in conv_context.generated_objectives)
            conv_context.collected_values["learning-objectives"] = objectives_text
            conv_context.current_field_index += 1
            conv_context.generated_objectives = []
            conv_context.state = ConversationState.AWAITING_CONFIRMATION
            conv_context.pending_action = "ui_click_button"
            conv_context.pending_action_data = {
                "voice_id": "create-course-with-plans",
                "form_name": "create_course",
            }
            conversation_manager.save_context(request.user_id, conv_context)

            return ConverseResponse(
                message=sanitize_speech("Objectives saved! The course is ready to create. Would you like me to create it now and generate session plans?"),
                action=ActionResponse(type='info'),
                suggestions=["Yes, create it", "No, cancel"],
            )

        elif wants_skip:
            skip_result = conversation_manager.skip_current_field(request.user_id)
            conv_context.generated_objectives = []
            conversation_manager.save_context(request.user_id, conv_context)
            return ConverseResponse(
                message=sanitize_speech(skip_result["message"]),
                action=ActionResponse(type='info'),
                results=[{
                    "ui_actions": [
                        {"type": "ui.clearInput", "payload": {"target": "learning-objectives"}},
                    ]
                }],
                suggestions=["Continue", "Cancel form"],
            )

        else:
            # User wants to edit
            conv_context.state = ConversationState.AWAITING_FIELD_INPUT
            conversation_manager.save_context(request.user_id, conv_context)
            return ConverseResponse(
                message=sanitize_speech("The objectives are in the form. You can edit them manually, or dictate new ones. Say 'done' when finished or 'skip' to move on."),
                action=ActionResponse(type='info'),
                suggestions=["Skip", "Cancel form"],
            )

    # --- Handle AI session plan generation confirmation state ---
    if conv_context.state == ConversationState.AWAITING_SESSION_PLAN_GENERATION_CONFIRM:
        transcript_lower = transcript.lower()
        yes_words = ['yes', 'yeah', 'yep', 'sure', 'okay', 'ok', 'generate', 'create', 'please', 'go ahead', 'do it']
        no_words = ['no', 'nope', 'dictate', "i'll type", "i will type", "i'll write", "i will write", 'manual', 'myself', 'skip']

        accepted = any(word in transcript_lower for word in yes_words)
        declined = any(word in transcript_lower for word in no_words)

        if accepted and not declined:
            # Generate session plan using AI
            session_topic = conv_context.collected_values.get("input-session-title", "the session")
            # Get course info from context if available
            course_id = context_store.get_context(request.user_id).get("active_course_id") if request.user_id else None
            course_name = "the course"
            syllabus = None

            if course_id and db:
                course = db.query(Course).filter(Course.id == course_id).first()
                if course:
                    course_name = course.title
                    syllabus = course.syllabus_text

            try:
                gen_result = _execute_tool(db, 'generate_session_plan', {
                    "course_name": course_name,
                    "session_topic": session_topic,
                    "syllabus": syllabus,
                })
            except Exception as e:
                import logging
                logging.getLogger(__name__).error(f"Session plan generation error: {e}")
                gen_result = None

            if gen_result and gen_result.get("success") and gen_result.get("plan"):
                plan = gen_result["plan"]
                # Format the plan as a description
                description_parts = []
                if plan.get("goals"):
                    description_parts.append("Learning Goals:\n" + "\n".join(f"- {g}" for g in plan["goals"]))
                if plan.get("key_concepts"):
                    description_parts.append("\nKey Concepts:\n" + "\n".join(f"- {c}" for c in plan["key_concepts"]))
                if plan.get("discussion_prompts"):
                    description_parts.append("\nDiscussion Prompts:\n" + "\n".join(f"- {p}" for p in plan["discussion_prompts"]))
                if plan.get("case_prompt"):
                    description_parts.append(f"\nCase Study:\n{plan['case_prompt']}")

                description = "\n".join(description_parts)

                # Save the generated plan
                conv_context.generated_session_plan = plan
                conv_context.state = ConversationState.AWAITING_SESSION_PLAN_REVIEW
                conversation_manager.save_context(request.user_id, conv_context)

                # Create a voice-friendly summary
                prompt_count = len(plan.get("discussion_prompts", []))
                summary = f"I've generated a session plan for '{session_topic}' with {prompt_count} discussion prompts"
                if plan.get("case_prompt"):
                    summary += " and a case study"
                summary += ". Should I use this plan?"

                return ConverseResponse(
                    message=sanitize_speech(summary),
                    action=ActionResponse(type='info'),
                    results=[{
                        "ui_actions": [
                            {"type": "ui.fillInput", "payload": {"target": "textarea-session-description", "value": description}},
                        ]
                    }],
                    suggestions=["Yes, use it", "No, let me edit", "Skip"],
                )
            else:
                # Generation failed
                conv_context.state = ConversationState.AWAITING_FIELD_INPUT
                conversation_manager.save_context(request.user_id, conv_context)
                error_msg = gen_result.get("error", "Generation failed") if gen_result else "Tool not available"
                return ConverseResponse(
                    message=sanitize_speech(f"Sorry, I couldn't generate the session plan: {error_msg}. Please dictate a description or say 'skip'."),
                    action=ActionResponse(type='info'),
                    suggestions=["Skip", "Cancel form"],
                )

        elif declined or 'skip' in transcript_lower:
            if 'skip' in transcript_lower:
                skip_result = conversation_manager.skip_current_field(request.user_id)
                return ConverseResponse(
                    message=sanitize_speech(skip_result["message"]),
                    action=ActionResponse(type='info'),
                    suggestions=["Create session", "Cancel form"],
                )
            else:
                conv_context.state = ConversationState.AWAITING_FIELD_INPUT
                conversation_manager.save_context(request.user_id, conv_context)
                return ConverseResponse(
                    message=sanitize_speech("Okay, please dictate the session description now."),
                    action=ActionResponse(type='info'),
                    suggestions=["Skip", "Cancel form"],
                )
        else:
            return ConverseResponse(
                message=sanitize_speech("Would you like me to generate a session plan with discussion prompts and a case study? Say 'yes' to generate, 'no' to dictate, or 'skip'."),
                action=ActionResponse(type='info'),
                suggestions=["Yes, generate it", "No, I'll dictate", "Skip"],
            )

    # --- Handle session plan review state ---
    if conv_context.state == ConversationState.AWAITING_SESSION_PLAN_REVIEW:
        transcript_lower = transcript.lower()
        accept_words = ['yes', 'yeah', 'yep', 'sure', 'okay', 'ok', 'use it', 'looks good', 'perfect', 'great', 'accept', 'good']
        edit_words = ['no', 'edit', 'change', 'modify', 'different', 'regenerate', 'try again']
        skip_words = ['skip', 'next', 'move on']

        accepted = any(word in transcript_lower for word in accept_words)
        wants_edit = any(word in transcript_lower for word in edit_words)
        wants_skip = any(word in transcript_lower for word in skip_words)

        if accepted and not wants_edit:
            # Accept the generated plan
            plan = conv_context.generated_session_plan
            description_parts = []
            if plan.get("goals"):
                description_parts.append("Learning Goals:\n" + "\n".join(f"- {g}" for g in plan["goals"]))
            if plan.get("key_concepts"):
                description_parts.append("\nKey Concepts:\n" + "\n".join(f"- {c}" for c in plan["key_concepts"]))
            if plan.get("discussion_prompts"):
                description_parts.append("\nDiscussion Prompts:\n" + "\n".join(f"- {p}" for p in plan["discussion_prompts"]))
            if plan.get("case_prompt"):
                description_parts.append(f"\nCase Study:\n{plan['case_prompt']}")
            description = "\n".join(description_parts)

            conv_context.collected_values["textarea-session-description"] = description
            conv_context.current_field_index += 1
            conv_context.generated_session_plan = {}
            conv_context.state = ConversationState.AWAITING_CONFIRMATION
            conv_context.pending_action = "ui_click_button"
            conv_context.pending_action_data = {
                "voice_id": "create-session",
                "form_name": "create_session",
            }
            conversation_manager.save_context(request.user_id, conv_context)

            return ConverseResponse(
                message=sanitize_speech("Session plan saved! The session is ready to create. Would you like me to create it now?"),
                action=ActionResponse(type='info'),
                suggestions=["Yes, create it", "No, cancel"],
            )

        elif wants_skip:
            skip_result = conversation_manager.skip_current_field(request.user_id)
            conv_context.generated_session_plan = {}
            conversation_manager.save_context(request.user_id, conv_context)
            return ConverseResponse(
                message=sanitize_speech(skip_result["message"]),
                action=ActionResponse(type='info'),
                results=[{
                    "ui_actions": [
                        {"type": "ui.clearInput", "payload": {"target": "textarea-session-description"}},
                    ]
                }],
                suggestions=["Create session", "Cancel form"],
            )

        else:
            # User wants to edit
            conv_context.state = ConversationState.AWAITING_FIELD_INPUT
            conversation_manager.save_context(request.user_id, conv_context)
            return ConverseResponse(
                message=sanitize_speech("The session plan is in the form. You can edit it manually, or dictate a new description. Say 'done' when finished or 'skip'."),
                action=ActionResponse(type='info'),
                suggestions=["Skip", "Cancel form"],
            )

    # 1. Check for navigation intent first (fast regex - instant)
    nav_path = detect_navigation_intent(transcript)
    if nav_path:
        message = sanitize_speech(generate_conversational_response('navigate', nav_path))
        # Include ui_actions for navigation so frontend executes the navigation
        return ConverseResponse(
            message=message,
            action=ActionResponse(type='navigate', target=nav_path),
            results=[{
                "ui_actions": [
                    {"type": "ui.navigate", "payload": {"path": nav_path}},
                    {"type": "ui.toast", "payload": {"message": f"Navigating to {nav_path}", "type": "info"}},
                ]
            }],
            suggestions=get_page_suggestions(nav_path)
        )

    # 2. Check for action intent via regex BEFORE expensive LLM call (fast - instant)
    action = detect_action_intent(transcript)
    if action:
        result = await execute_action(action, request.user_id, request.current_page, db, transcript)
        # Wrap result in a list if it's not already (ConverseResponse.results expects List)
        results_list = [result] if result and not isinstance(result, list) else result
        return ConverseResponse(
            message=sanitize_speech(generate_conversational_response(
                'execute',
                action,
                results=result,  # Pass original for response generation
                context=request.context,
                current_page=request.current_page,
            )),
            action=ActionResponse(type='execute', executed=True),
            results=results_list,  # Pass list for Pydantic validation
            suggestions=get_action_suggestions(action),
        )

    # 3. FAST MODE: Skip slow LLM orchestrator for instant response
    # The regex patterns above should handle 95%+ of commands
    # Only use LLM for truly complex multi-step requests (disabled by default for speed)
    USE_LLM_ORCHESTRATOR = False  # Set to True if you need complex multi-step planning

    if USE_LLM_ORCHESTRATOR:
        plan_result = run_voice_orchestrator(
            transcript,
            context=request.context,
            current_page=request.current_page,
        )
        plan = plan_result.get("plan") if plan_result else None
        if plan and plan.get("steps"):
            steps = plan.get("steps", [])
            required_confirmations = set(plan.get("required_confirmations") or [])
            write_steps = [
                step
                for step in steps
                if step.get("mode") == "write" or step.get("tool_name") in required_confirmations
            ]

            if write_steps and not is_confirmation(transcript):
                pending_results = [
                    {
                        "tool": step.get("tool_name"),
                        "status": "pending_confirmation",
                        "args": step.get("args", {}),
                    }
                    for step in write_steps
                ]
                return ConverseResponse(
                    message=sanitize_speech(build_confirmation_message(write_steps)),
                    action=ActionResponse(type="execute", executed=False),
                    results=pending_results,
                    suggestions=["Yes, proceed", "No, cancel"],
                )

            # Execute and use fast template summary (no LLM call)
            results, summary = execute_plan_steps(steps, db)
            return ConverseResponse(
                message=sanitize_speech(summary),
                action=ActionResponse(type='execute', executed=True),
                results=results,
                suggestions=["Anything else I can help with?"],
            )

    # 4. No clear intent - provide helpful fallback instantly (no LLM call)
    fallback_message = generate_fallback_response(transcript, request.context)

    return ConverseResponse(
        message=sanitize_speech(fallback_message),
        action=ActionResponse(type='info'),
        suggestions=["Show my courses", "Go to forum", "Start copilot", "Create a poll"],
    )


def _parse_ids_from_path(current_page: Optional[str]) -> Tuple[Optional[int], Optional[int]]:
    """Extract course/session IDs from the current URL path."""
    if not current_page:
        return None, None
    course_match = re.search(r"/courses/(\d+)", current_page)
    session_match = re.search(r"/sessions/(\d+)", current_page)
    course_id = int(course_match.group(1)) if course_match else None
    session_id = int(session_match.group(1)) if session_match else None
    return course_id, session_id


def _resolve_course_id(db: Session, current_page: Optional[str], user_id: Optional[int] = None) -> Optional[int]:
    """Resolve course ID from URL, context memory, or database.

    Priority:
    1. Course ID in URL path
    2. Active course from user context memory
    3. Most recently created course (fallback)
    """
    course_id, _ = _parse_ids_from_path(current_page)
    if course_id:
        # Update context with this course
        if user_id:
            context_store.update_context(user_id, active_course_id=course_id)
        return course_id

    # Check context memory for active course
    if user_id:
        active_course_id = context_store.get_active_course_id(user_id)
        if active_course_id:
            return active_course_id

    # Fallback to most recent course
    course = db.query(Course).order_by(Course.created_at.desc()).first()
    return course.id if course else None


def _resolve_session_id(db: Session, current_page: Optional[str], user_id: Optional[int] = None, course_id: Optional[int] = None) -> Optional[int]:
    """Resolve session ID from URL, context memory, or database.

    Priority:
    1. Session ID in URL path
    2. Active session from user context memory
    3. Live session (filtered by course_id if provided)
    4. Most recently created session (filtered by course_id if provided)

    Args:
        db: Database session
        current_page: Current URL path
        user_id: User ID for context memory lookup
        course_id: Optional course ID to filter sessions by
    """
    _, session_id = _parse_ids_from_path(current_page)
    if session_id:
        # Update context with this session
        if user_id:
            context_store.update_context(user_id, active_session_id=session_id)
        return session_id

    # Check context memory for active session
    if user_id:
        active_session_id = context_store.get_active_session_id(user_id)
        if active_session_id:
            return active_session_id

    # Try to find a live session (filtered by course if provided)
    query = db.query(SessionModel).filter(SessionModel.status == SessionStatus.live)
    if course_id:
        query = query.filter(SessionModel.course_id == course_id)
    session = query.order_by(SessionModel.created_at.desc()).first()
    if session:
        return session.id

    # Fallback to most recent session (filtered by course if provided)
    query = db.query(SessionModel)
    if course_id:
        query = query.filter(SessionModel.course_id == course_id)
    session = query.order_by(SessionModel.created_at.desc()).first()
    return session.id if session else None


def _extract_dictated_content(transcript: str, action: str) -> Optional[str]:
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


def _extract_universal_dictation(transcript: str) -> Optional[Dict[str, str]]:
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


def _extract_dropdown_hint(transcript: str) -> str:
    """Extract which dropdown the user is referring to, or return empty for any dropdown."""
    text_lower = transcript.lower()

    # Look for specific dropdown mentions
    dropdown_keywords = {
        'course': 'select-course',
        'session': 'select-session',
        'student': 'select-student',
        'instructor': 'select-instructor',
        'status': 'select-status',
        'type': 'select-type',
    }

    for keyword, target in dropdown_keywords.items():
        if keyword in text_lower:
            return target

    return ""  # Empty means find any dropdown on the page


def _extract_button_info(transcript: str) -> Dict[str, str]:
    """Extract button target from transcript for button clicks."""
    text_lower = transcript.lower()

    # Direct button mappings
    button_mappings = {
        'generate report': 'generate-report',
        'regenerate report': 'regenerate-report',
        'refresh': 'refresh',
        'start copilot': 'start-copilot',
        'stop copilot': 'stop-copilot',
        'create poll': 'create-poll',
        'post case': 'post-case',
        'go live': 'go-live',
        'complete session': 'complete-session',
        'enroll': 'enroll-students',
        'upload roster': 'upload-roster',
        'submit': 'submit-post',
        'create course': 'create-course-with-plans',
        'create session': 'create-session',
        'create and generate': 'create-course-with-plans',
        'generate plans': 'create-course-with-plans',
    }

    for phrase, target in button_mappings.items():
        if phrase in text_lower:
            return {"target": target, "label": phrase.title()}

    return {}


def _extract_student_name(transcript: str) -> Optional[str]:
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


def _extract_tab_info(transcript: str) -> Dict[str, str]:
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
    # Note: Speech recognition may confuse similar-sounding words
    tab_aliases = {
        'ai copilot': 'copilot',
        'ai assistant': 'copilot',
        'copilot': 'copilot',
        # Polls tab - handle various transcriptions and mishearings
        'poll': 'polls',
        'polls': 'polls',
        'pulse': 'polls',   # Common mishearing
        'pose': 'polls',    # Common mishearing
        'pols': 'polls',    # Common mishearing
        'paul': 'polls',    # Common mishearing
        'polling': 'polls',
        'poles': 'polls',   # Common mishearing
        'pulls': 'polls',   # Common mishearing
        'bowls': 'polls',   # Common mishearing
        'goals': 'polls',   # Common mishearing (unlikely but possible)
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
        # Other tabs
        'enroll': 'enrollment',
        'enrollment': 'enrollment',
        'enrollments': 'enrollment',
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
    }

    # First try exact match
    if tab_name in tab_aliases:
        return {"tabName": tab_aliases[tab_name]}

    # Then try partial match - if the tab_name contains a key word
    for alias, normalized in tab_aliases.items():
        if alias in tab_name or tab_name in alias:
            return {"tabName": normalized}

    return {"tabName": tab_name}


def _extract_dropdown_selection(transcript: str) -> Dict[str, Any]:
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


def _execute_tool(db: Session, tool_name: str, args: Dict[str, Any]) -> Optional[Any]:
    tool_info = TOOL_REGISTRY.get(tool_name)
    if not tool_info:
        return None
    handler = tool_info["handler"]
    return invoke_tool_handler(handler, args, db=db)


def _get_page_context(db: Session, current_page: Optional[str]) -> Dict[str, Any]:
    """Get intelligent context about the current page and available actions."""
    page = current_page or "/dashboard"

    # Determine page type
    if "/courses" in page:
        course_id = _resolve_course_id(db, current_page)
        if course_id:
            course = _execute_tool(db, 'get_course', {"course_id": course_id})
            result = _execute_tool(db, 'list_sessions', {"course_id": course_id})
            sessions = result.get("sessions", []) if isinstance(result, dict) else []
            return {
                "page": "course_detail",
                "course": course,
                "session_count": len(sessions),
                "message": f"You're viewing {course.get('title', 'a course')} with {len(sessions)} sessions.",
                "available_actions": ["Create session", "View sessions", "Manage enrollments", "Go to forum"],
            }
        else:
            result = _execute_tool(db, 'list_courses', {"skip": 0, "limit": 100})
            courses = result.get("courses", []) if isinstance(result, dict) else []
            return {
                "page": "courses_list",
                "course_count": len(courses),
                "message": f"You're on the courses page. You have {len(courses)} courses.",
                "available_actions": ["Create course", "Select a course", "View sessions"],
            }

    elif "/sessions" in page:
        course_id = _resolve_course_id(db, current_page, user_id)
        session_id = _resolve_session_id(db, current_page, user_id, course_id)
        if session_id:
            session = _execute_tool(db, 'get_session', {"session_id": session_id})
            status = session.get('status', 'unknown') if session else 'unknown'
            return {
                "page": "session_detail",
                "session": session,
                "status": status,
                "message": f"You're viewing a session. Status: {status}.",
                "available_actions": ["Go live", "End session", "Start copilot", "Create poll", "Go to forum"] if status != 'live'
                                     else ["End session", "Start copilot", "Create poll", "View suggestions"],
            }
        return {
            "page": "sessions_list",
            "message": "You're on the sessions page. Select a course to view sessions.",
            "available_actions": ["Select course", "Create session", "Go to courses"],
        }

    elif "/forum" in page:
        course_id = _resolve_course_id(db, current_page, user_id)
        session_id = _resolve_session_id(db, current_page, user_id, course_id)
        if session_id:
            posts = _execute_tool(db, 'get_session_posts', {"session_id": session_id})
            pinned = [p for p in posts if p.get('pinned')] if posts else []
            return {
                "page": "forum",
                "post_count": len(posts) if posts else 0,
                "pinned_count": len(pinned),
                "message": f"You're in the forum with {len(posts) if posts else 0} posts and {len(pinned)} pinned.",
                "available_actions": ["View posts", "Show pinned", "Summarize discussion", "Post case", "Show questions"],
            }
        return {
            "page": "forum",
            "message": "You're on the forum page. Select a live session to view discussions.",
            "available_actions": ["Select session", "Go to sessions"],
        }

    elif "/console" in page:
        course_id = _resolve_course_id(db, current_page, user_id)
        session_id = _resolve_session_id(db, current_page, user_id, course_id)
        copilot_status = _execute_tool(db, 'get_copilot_status', {"session_id": session_id}) if session_id else None
        is_active = copilot_status.get('is_active', False) if copilot_status else False
        return {
            "page": "console",
            "copilot_active": is_active,
            "message": f"You're in the console. Copilot is {'active' if is_active else 'inactive'}.",
            "available_actions": ["Stop copilot", "View suggestions", "Create poll"] if is_active
                                 else ["Start copilot", "Create poll", "Go to forum"],
        }

    elif "/reports" in page:
        return {
            "page": "reports",
            "message": "You're on the reports page. Select a session to view or generate reports.",
            "available_actions": ["Generate report", "View analytics", "Go to sessions"],
        }

    # Default dashboard
    result = _execute_tool(db, 'list_courses', {"skip": 0, "limit": 100})
    courses = result.get("courses", []) if isinstance(result, dict) else []
    return {
        "page": "dashboard",
        "course_count": len(courses),
        "message": f"You're on the dashboard. You have {len(courses)} courses.",
        "available_actions": ["Show courses", "Go to sessions", "Go to forum", "Go to console"],
    }


async def execute_action(
    action: str,
    user_id: Optional[int],
    current_page: Optional[str],
    db: Session,
    transcript: Optional[str] = None,
) -> Optional[Any]:
    """Execute an MCP tool and return results, including UI actions for frontend."""
    try:
        # === UNIVERSAL UI ELEMENT INTERACTIONS ===
        # All UI actions now use universal handlers that work across all pages

        # === UNIVERSAL FORM DICTATION ===
        # Works for ANY input field - title, syllabus, objectives, poll question, post content, etc.
        if action == 'ui_dictate_input':
            extracted = _extract_universal_dictation(transcript or "")
            if extracted:
                field_name = extracted.get("field", "input")
                value = extracted.get("value", "")
                return {
                    "action": "fill_input",
                    "message": f"Setting {field_name} to: {value[:50]}{'...' if len(value) > 50 else ''}",
                    "ui_actions": [
                        {"type": "ui.fillInput", "payload": {"target": field_name, "value": value}},
                        {"type": "ui.toast", "payload": {"message": f"{field_name.title()} set", "type": "success"}},
                    ],
                }
            return {"message": "Please specify what you'd like to fill in."}

        # === UNIVERSAL DROPDOWN EXPANSION ===
        # Works for ANY dropdown on any page - fetches options and reads them verbally
        if action == 'ui_expand_dropdown':
            # Extract which dropdown from transcript, or default to finding any dropdown
            dropdown_hint = _extract_dropdown_hint(transcript or "")

            # Fetch options based on dropdown type
            options: list[DropdownOption] = []
            if 'course' in dropdown_hint or not dropdown_hint:
                # Fetch courses - result is {"courses": [...]}
                result = _execute_tool(db, 'list_courses', {"skip": 0, "limit": 10})
                courses = result.get("courses", []) if isinstance(result, dict) else []
                if courses:
                    options = [DropdownOption(label=c.get('title', f"Course {c['id']}"), value=str(c['id'])) for c in courses]
                    dropdown_hint = dropdown_hint or "select-course"
            elif 'session' in dropdown_hint:
                # Fetch sessions for active course - result is {"sessions": [...]}
                course_id = _resolve_course_id(db, current_page, user_id)
                if course_id:
                    # Check if user wants only live sessions
                    # Note: "live" can be pronounced two ways and transcribed differently
                    transcript_lower = (transcript or "").lower()
                    status_filter = None
                    # Check for "live" - various transcriptions for both pronunciations
                    live_keywords = ['live', 'alive', 'active', 'ongoing', 'running', 'in progress', 'current']
                    if any(kw in transcript_lower for kw in live_keywords):
                        status_filter = 'live'
                    elif 'draft' in transcript_lower:
                        status_filter = 'draft'
                    elif 'completed' in transcript_lower or 'complete' in transcript_lower or 'ended' in transcript_lower:
                        status_filter = 'completed'
                    elif 'scheduled' in transcript_lower:
                        status_filter = 'scheduled'

                    list_params = {"course_id": course_id}
                    if status_filter:
                        list_params["status"] = status_filter

                    result = _execute_tool(db, 'list_sessions', list_params)
                    sessions = result.get("sessions", []) if isinstance(result, dict) else []
                    if sessions:
                        # Include status in label for clarity
                        options = []
                        for s in sessions:
                            session_id = s['id']
                            title = s.get('title', f'Session {session_id}')
                            status = s.get('status', 'unknown')
                            options.append(DropdownOption(label=f"{title} ({status})", value=str(session_id)))
                else:
                    # No course selected - prompt user to select course first
                    return {
                        "action": "expand_dropdown",
                        "message": "Please select a course first before choosing a session.",
                        "ui_actions": [],
                        "needs_course": True,
                    }

            if options:
                # Start dropdown selection flow with verbal listing
                prompt = conversation_manager.start_dropdown_selection(
                    user_id, dropdown_hint, options, current_page or "/dashboard"
                )
                return {
                    "action": "expand_dropdown",
                    "message": prompt,
                    "ui_actions": [
                        {"type": "ui.expandDropdown", "payload": {"target": dropdown_hint, "findAny": True}},
                    ],
                    "options": [{"label": o.label, "value": o.value} for o in options],
                    "conversation_state": "dropdown_selection",
                }
            else:
                return {
                    "action": "expand_dropdown",
                    "message": "The dropdown is empty. There are no options available.",
                    "ui_actions": [
                        {"type": "ui.expandDropdown", "payload": {"target": dropdown_hint, "findAny": True}},
                    ],
                }

        # === UNIVERSAL TAB SWITCHING ===
        # The ui_switch_tab action now works universally for any tab name
        if action == 'ui_switch_tab':
            tab_info = _extract_tab_info(transcript or "")
            tab_name = tab_info.get("tabName", "")

            # Special handling for forum discussion tab - offer to help post
            if current_page and '/forum' in current_page and tab_name == 'discussion':
                # Check if user hasn't already declined the offer
                conv_context = conversation_manager.get_context(user_id)
                if not conv_context.post_offer_declined:
                    # Offer to help post after switching to discussion tab
                    offer_prompt = conversation_manager.offer_forum_post(user_id)
                    if offer_prompt:
                        return {
                            "action": "switch_tab_with_post_offer",
                            "message": f"Switching to discussion. {offer_prompt}",
                            "ui_actions": [
                                {"type": "ui.switchTab", "payload": {"tabName": tab_name, "target": f"tab-{tab_name}"}},
                            ],
                            "post_offer": True,
                        }

            # Special handling for console polls tab - offer to help create poll
            if current_page and '/console' in current_page and tab_name == 'polls':
                # Check if user hasn't already declined the offer
                conv_context = conversation_manager.get_context(user_id)
                if not conv_context.poll_offer_declined:
                    # Offer to help create poll after switching to polls tab
                    offer_prompt = conversation_manager.offer_poll_creation(user_id)
                    if offer_prompt:
                        return {
                            "action": "switch_tab_with_poll_offer",
                            "message": f"Switching to polls. {offer_prompt}",
                            "ui_actions": [
                                {"type": "ui.switchTab", "payload": {"tabName": tab_name, "target": f"tab-{tab_name}"}},
                            ],
                            "poll_offer": True,
                        }

            # Special handling for sessions page manage status tab - offer status options
            if current_page and '/sessions' in current_page and tab_name in ['manage', 'management', 'manage status', 'managestatus']:
                return {
                    "action": "switch_tab_with_status_offer",
                    "message": "Switching to manage status. You can say 'go live', 'set to draft', 'complete', or 'schedule' to change the session status.",
                    "ui_actions": [
                        {"type": "ui.switchTab", "payload": {"tabName": "manage", "target": "tab-manage"}},
                        {"type": "ui.toast", "payload": {"message": "Switched to manage status", "type": "info"}},
                    ],
                    "status_offer": True,
                }

            return {
                "action": "switch_tab",
                "message": f"Switching to {tab_name} tab.",
                "ui_actions": [
                    {"type": "ui.switchTab", "payload": {"tabName": tab_name, "target": f"tab-{tab_name}"}},
                    {"type": "ui.toast", "payload": {"message": f"Switched to {tab_name}", "type": "info"}},
                ],
            }

        # === UNIVERSAL DROPDOWN SELECTION ===
        if action == 'ui_select_dropdown':
            selection_info = _extract_dropdown_selection(transcript or "")
            return {
                "action": "select_dropdown",
                "message": f"Selecting {selection_info.get('optionName', 'option')}",
                "ui_actions": [
                    {"type": "ui.selectDropdown", "payload": selection_info},
                ],
            }

        # === UNIVERSAL BUTTON CLICK ===
        # Handles button clicks from form submission confirmations and direct commands
        if action == 'ui_click_button':
            # Get button target from conversation context (for confirmations) or extract from transcript
            conv_context = conversation_manager.get_context(user_id)
            button_target = None
            button_label = None

            # Check if we have action_data from confirmation flow
            if conv_context.pending_action_data and conv_context.pending_action_data.get("voice_id"):
                button_target = conv_context.pending_action_data.get("voice_id")
                form_name = conv_context.pending_action_data.get("form_name", "")
                button_label = form_name.replace("_", " ").title() if form_name else "Submit"
            else:
                # Extract from transcript
                button_info = _extract_button_info(transcript or "")
                button_target = button_info.get("target")
                button_label = button_info.get("label", "button")

            if button_target:
                # Clear confirmation state after clicking
                conv_context.state = ConversationState.IDLE
                conv_context.pending_action = None
                conv_context.pending_action_data = {}
                conv_context.active_form = None
                conversation_manager.save_context(user_id, conv_context)

                return {
                    "action": "click_button",
                    "message": f"Clicking {button_label}.",
                    "ui_actions": [
                        {"type": "ui.clickButton", "payload": {"target": button_target}},
                        {"type": "ui.toast", "payload": {"message": f"{button_label} clicked", "type": "success"}},
                    ],
                }
            return {"message": "I couldn't determine which button to click."}

        # Note: Specific tab handlers (open_enrollment_tab, open_create_tab, open_manage_tab)
        # are now handled by the universal ui_switch_tab action above

        # === UNDO/CONTEXT ACTIONS ===
        if action == 'undo_action':
            if not user_id:
                return {"error": "Cannot undo without user context."}

            last_action = context_store.get_last_undoable_action(user_id)
            if not last_action:
                return {
                    "message": "Nothing to undo. Your recent actions don't have undo data.",
                    "ui_actions": [{"type": "ui.toast", "payload": {"message": "Nothing to undo", "type": "info"}}],
                }

            action_type = last_action.get("action_type", "unknown")
            undo_data = last_action.get("undo_data", {})

            # Mark as undone
            context_store.mark_action_undone(user_id, last_action.get("timestamp", 0))

            return {
                "message": f"Undone: {action_type}. The action has been reversed.",
                "undone_action": action_type,
                "undo_data": undo_data,
                "ui_actions": [
                    {"type": "ui.toast", "payload": {"message": f"Undone: {action_type}", "type": "success"}},
                ],
            }

        if action == 'get_context':
            if not user_id:
                return {"message": "No user context available."}

            context = context_store.get_context(user_id)
            summary = context_store.get_context_summary(user_id)

            # Get names for the IDs
            course_name = None
            session_name = None

            if context.get("active_course_id"):
                course = _execute_tool(db, 'get_course', {"course_id": context["active_course_id"]})
                course_name = course.get("title") if course else None

            if context.get("active_session_id"):
                session = _execute_tool(db, 'get_session', {"session_id": context["active_session_id"]})
                session_name = session.get("title") if session else None

            return {
                "message": f"Your current context: {summary}",
                "context": context,
                "course_name": course_name,
                "session_name": session_name,
                "ui_actions": [{"type": "ui.toast", "payload": {"message": summary, "type": "info"}}],
            }

        if action == 'clear_context':
            if user_id:
                context_store.clear_context(user_id)
            return {
                "message": "Context cleared. Starting fresh!",
                "ui_actions": [{"type": "ui.toast", "payload": {"message": "Context cleared", "type": "success"}}],
            }

        # === CONTEXT/STATUS ACTIONS ===
        if action == 'get_status':
            return _get_page_context(db, current_page)

        if action == 'get_help':
            return {
                "message": "I can help you with: navigating pages, listing courses and sessions, "
                           "starting copilot, creating polls, viewing forum discussions, pinning posts, "
                           "generating reports, and managing enrollments. Just ask!",
                "available_commands": [
                    "Show my courses", "Go to forum", "Start copilot",
                    "Create a poll", "Show pinned posts", "Summarize discussion",
                    "Generate report", "Go live", "End session"
                ]
            }

        # === COURSE ACTIONS ===
        if action == 'list_courses':
            return _execute_tool(db, 'list_courses', {"skip": 0, "limit": 100})

        if action == 'create_course':
            # Start conversational form-filling flow
            first_question = conversation_manager.start_form_filling(
                user_id, "create_course", "/courses"
            )
            return {
                "action": "create_course",
                "ui_actions": [
                    {"type": "ui.navigate", "payload": {"path": "/courses"}},
                    {"type": "ui.switchTab", "payload": {"tabName": "create", "target": "tab-create"}},
                ],
                "message": first_question or "Opening course creation. What would you like to name the course?",
                "conversation_state": "form_filling",
            }

        if action == 'select_course':
            result = _execute_tool(db, 'list_courses', {"skip": 0, "limit": 10})
            courses = result.get("courses", []) if isinstance(result, dict) else []
            if courses and len(courses) > 0:
                first_course = courses[0]
                # Update context memory with selected course
                if user_id:
                    context_store.update_context(user_id, active_course_id=first_course['id'])
                return {
                    "action": "select_course",
                    "course": first_course,
                    "ui_actions": [
                        {"type": "ui.navigate", "payload": {"path": f"/courses/{first_course['id']}"}},
                        {"type": "ui.toast", "payload": {"message": f"Selected: {first_course.get('title', 'course')}", "type": "success"}},
                    ],
                }
            return {"error": "No courses found to select."}

        if action == 'view_course_details':
            course_id = _resolve_course_id(db, current_page, user_id)
            if course_id:
                return _execute_tool(db, 'get_course', {"course_id": course_id})
            return {"error": "No course selected. Please navigate to a course first."}

        # === SESSION ACTIONS ===
        if action == 'list_sessions':
            course_id = _resolve_course_id(db, current_page, user_id)
            if not course_id:
                return {"message": "Please select a course first to view sessions.", "sessions": []}

            # Check if user wants only live sessions
            # Note: "live" can be pronounced two ways and transcribed differently
            transcript_lower = (transcript or "").lower()
            status_filter = None
            live_keywords = ['live', 'alive', 'active', 'ongoing', 'running', 'in progress', 'current']
            if any(kw in transcript_lower for kw in live_keywords):
                status_filter = 'live'

            list_params = {"course_id": course_id}
            if status_filter:
                list_params["status"] = status_filter

            return _execute_tool(db, 'list_sessions', list_params)

        if action == 'create_session':
            course_id = _resolve_course_id(db, current_page, user_id)
            # Start conversational form-filling flow
            first_question = conversation_manager.start_form_filling(
                user_id, "create_session", "/sessions"
            )
            return {
                "action": "create_session",
                "course_id": course_id,
                "ui_actions": [
                    {"type": "ui.navigate", "payload": {"path": "/sessions"}},
                    {"type": "ui.switchTab", "payload": {"tabName": "create", "target": "tab-create"}},
                ],
                "message": first_question or "Opening session creation. What would you like to call this session?",
                "conversation_state": "form_filling",
            }

        if action == 'select_session':
            course_id = _resolve_course_id(db, current_page, user_id)
            if not course_id:
                return {"message": "Please select a course first before choosing a session."}

            # Check if user wants only live sessions
            # Note: "live" can be pronounced two ways and transcribed differently
            transcript_lower = (transcript or "").lower()
            status_filter = None
            live_keywords = ['live', 'alive', 'active', 'ongoing', 'running', 'in progress', 'current']
            if any(kw in transcript_lower for kw in live_keywords):
                status_filter = 'live'
            elif 'draft' in transcript_lower:
                status_filter = 'draft'

            list_params = {"course_id": course_id}
            if status_filter:
                list_params["status"] = status_filter

            result = _execute_tool(db, 'list_sessions', list_params)
            sessions = result.get("sessions", []) if isinstance(result, dict) else []

            if not sessions:
                status_msg = f" with status '{status_filter}'" if status_filter else ""
                return {"message": f"No sessions found{status_msg} for this course."}

            # If only one session, select it directly
            if len(sessions) == 1:
                session = sessions[0]
                if user_id:
                    context_store.update_context(user_id, active_session_id=session['id'])
                return {
                    "action": "select_session",
                    "session": session,
                    "ui_actions": [
                        {"type": "ui.selectDropdown", "payload": {"target": "select-session", "value": str(session['id'])}},
                        {"type": "ui.toast", "payload": {"message": f"Selected: {session.get('title', 'session')}", "type": "success"}},
                    ],
                }

            # Multiple sessions - start dropdown selection flow
            options = []
            for s in sessions:
                session_id = s['id']
                title = s.get('title', f'Session {session_id}')
                status = s.get('status', 'unknown')
                options.append(DropdownOption(label=f"{title} ({status})", value=str(session_id)))
            prompt = conversation_manager.start_dropdown_selection(
                user_id, "select-session", options, current_page or "/sessions"
            )
            return {
                "action": "select_session",
                "message": prompt,
                "ui_actions": [
                    {"type": "ui.expandDropdown", "payload": {"target": "select-session"}},
                ],
                "options": [{"label": o.label, "value": o.value} for o in options],
                "conversation_state": "dropdown_selection",
            }

        if action == 'go_live' or action == 'set_session_live':
            # If on sessions page manage tab, just click the button - frontend handles API call
            if current_page and '/sessions' in current_page:
                return {
                    "action": "set_session_live",
                    "message": "Setting session to live...",
                    "ui_actions": [
                        {"type": "ui.clickButton", "payload": {"target": "go-live"}},
                    ],
                }
            # On other pages, update via backend and navigate to console
            course_id = _resolve_course_id(db, current_page, user_id)
            session_id = _resolve_session_id(db, current_page, user_id, course_id)
            if session_id:
                result = _execute_tool(db, 'update_session_status', {"session_id": session_id, "status": "live"})
                if result:
                    # Record action for undo
                    if user_id:
                        context_store.record_action(
                            user_id,
                            action_type="go_live",
                            action_data={"session_id": session_id},
                            undo_data={"session_id": session_id, "previous_status": "draft"},
                        )
                    result["ui_actions"] = [
                        {"type": "ui.navigate", "payload": {"path": f"/console?session={session_id}"}},
                        {"type": "ui.toast", "payload": {"message": "Session is now LIVE!", "type": "success"}},
                    ]
                return result
            return {"error": "No session found to go live."}

        if action == 'end_session' or action == 'set_session_completed':
            # If on sessions page manage tab, just click the button - frontend handles API call
            if current_page and '/sessions' in current_page:
                return {
                    "action": "set_session_completed",
                    "message": "Completing session...",
                    "ui_actions": [
                        {"type": "ui.clickButton", "payload": {"target": "complete-session"}},
                    ],
                }
            # On other pages, use confirmation flow
            course_id = _resolve_course_id(db, current_page, user_id)
            session_id = _resolve_session_id(db, current_page, user_id, course_id)
            if not session_id:
                return {"error": "No active session found to end."}

            # Check if already confirmed (from confirmation flow)
            conv_context = conversation_manager.get_context(user_id)
            if conv_context.state != ConversationState.IDLE or not conv_context.pending_action:
                # Request confirmation first (destructive action)
                confirmation_prompt = conversation_manager.request_confirmation(
                    user_id,
                    "end_session",
                    {"session_id": session_id, "voice_id": "btn-end-session"},
                    current_page or "/console"
                )
                return {
                    "action": "end_session",
                    "message": confirmation_prompt,
                    "ui_actions": [],
                    "needs_confirmation": True,
                    "conversation_state": "awaiting_confirmation",
                }

            # Execute the action (already confirmed)
            result = _execute_tool(db, 'update_session_status', {"session_id": session_id, "status": "completed"})
            if result and user_id:
                context_store.record_action(
                    user_id,
                    action_type="end_session",
                    action_data={"session_id": session_id},
                    undo_data={"session_id": session_id, "previous_status": "live"},
                )
                result["ui_actions"] = [
                    {"type": "ui.toast", "payload": {"message": "Session ended", "type": "info"}},
                ]
            return result

        # === MATERIALS ACTIONS ===
        if action == 'view_materials':
            # Navigate to sessions page with materials tab
            return {
                "action": "view_materials",
                "message": "Opening the course materials tab.",
                "ui_actions": [
                    {"type": "ui.openModal", "payload": {"modal": "viewMaterials"}},
                ],
            }

        # === COPILOT ACTIONS ===
        if action == 'get_interventions':
            course_id = _resolve_course_id(db, current_page, user_id)
            session_id = _resolve_session_id(db, current_page, user_id, course_id)
            if not session_id:
                return []
            return _execute_tool(db, 'get_copilot_suggestions', {"session_id": session_id})

        if action == 'start_copilot':
            course_id = _resolve_course_id(db, current_page, user_id)
            session_id = _resolve_session_id(db, current_page, user_id, course_id)
            if not session_id:
                return None
            result = _execute_tool(db, 'start_copilot', {"session_id": session_id})
            if result and user_id:
                context_store.record_action(
                    user_id,
                    action_type="start_copilot",
                    action_data={"session_id": session_id},
                    undo_data={"session_id": session_id},
                )
            if result:
                result["ui_actions"] = [
                    {"type": "ui.clickButton", "payload": {"target": "start-copilot"}},
                    {"type": "ui.toast", "payload": {"message": "Copilot is now active!", "type": "success"}},
                ]
            return result

        if action == 'stop_copilot':
            course_id = _resolve_course_id(db, current_page, user_id)
            session_id = _resolve_session_id(db, current_page, user_id, course_id)
            if not session_id:
                return None

            # Check if already confirmed (from confirmation flow)
            conv_context = conversation_manager.get_context(user_id)
            if conv_context.state != ConversationState.IDLE or not conv_context.pending_action:
                # Request confirmation first (destructive action)
                confirmation_prompt = conversation_manager.request_confirmation(
                    user_id,
                    "stop_copilot",
                    {"session_id": session_id, "voice_id": "stop-copilot"},
                    current_page or "/console"
                )
                return {
                    "action": "stop_copilot",
                    "message": confirmation_prompt,
                    "ui_actions": [],
                    "needs_confirmation": True,
                    "conversation_state": "awaiting_confirmation",
                }

            # Execute the action (already confirmed)
            result = _execute_tool(db, 'stop_copilot', {"session_id": session_id})
            if result and user_id:
                context_store.record_action(
                    user_id,
                    action_type="stop_copilot",
                    action_data={"session_id": session_id},
                    undo_data={"session_id": session_id},
                )
            if result:
                result["ui_actions"] = [
                    {"type": "ui.clickButton", "payload": {"target": "stop-copilot"}},
                    {"type": "ui.toast", "payload": {"message": "Copilot stopped", "type": "info"}},
                ]
            return result

        if action == 'refresh_interventions':
            return {
                "action": "refresh_interventions",
                "message": "Refreshing interventions...",
                "ui_actions": [
                    {"type": "ui.clickButton", "payload": {"target": "refresh-interventions"}},
                    {"type": "ui.toast", "payload": {"message": "Interventions refreshed", "type": "success"}},
                ],
            }

        # === SESSION STATUS MANAGEMENT (on sessions page) ===
        if action == 'set_session_draft':
            return {
                "action": "set_session_draft",
                "message": "Setting session to draft...",
                "ui_actions": [
                    {"type": "ui.clickButton", "payload": {"target": "set-to-draft"}},
                ],
            }

        if action == 'schedule_session':
            return {
                "action": "schedule_session",
                "message": "Scheduling session...",
                "ui_actions": [
                    {"type": "ui.clickButton", "payload": {"target": "schedule-session"}},
                    {"type": "ui.toast", "payload": {"message": "Session scheduled", "type": "success"}},
                ],
            }

        # === REPORT ACTIONS ===
        if action == 'refresh_report':
            return {
                "action": "refresh_report",
                "message": "Refreshing report...",
                "ui_actions": [
                    {"type": "ui.clickButton", "payload": {"target": "refresh-report"}},
                ],
            }

        if action == 'regenerate_report':
            return {
                "action": "regenerate_report",
                "message": "Regenerating report. This may take a moment...",
                "ui_actions": [
                    {"type": "ui.clickButton", "payload": {"target": "regenerate-report"}},
                ],
            }

        # === THEME AND USER MENU ACTIONS ===
        if action == 'toggle_theme':
            return {
                "action": "toggle_theme",
                "message": "Toggling theme...",
                "ui_actions": [
                    {"type": "ui.clickButton", "payload": {"target": "toggle-theme"}},
                ],
            }

        if action == 'open_user_menu':
            return {
                "action": "open_user_menu",
                "message": "Opening user menu...",
                "ui_actions": [
                    {"type": "ui.clickButton", "payload": {"target": "user-menu"}},
                ],
            }

        if action == 'view_voice_guide':
            return {
                "action": "view_voice_guide",
                "message": "Opening voice commands guide...",
                "ui_actions": [
                    {"type": "voice-menu-action", "payload": {"action": "view-voice-guide"}},
                ],
            }

        if action == 'open_profile':
            return {
                "action": "open_profile",
                "message": "Opening profile...",
                "ui_actions": [
                    {"type": "voice-menu-action", "payload": {"action": "open-profile"}},
                ],
            }

        if action == 'sign_out':
            return {
                "action": "sign_out",
                "message": "Signing out...",
                "ui_actions": [
                    {"type": "voice-menu-action", "payload": {"action": "sign-out"}},
                ],
            }

        if action == 'forum_instructions':
            return {
                "action": "forum_instructions",
                "message": "Opening platform instructions...",
                "ui_actions": [
                    {"type": "voice-menu-action", "payload": {"action": "forum-instructions"}},
                ],
            }

        if action == 'close_modal':
            # Try to click "Got It" buttons in any open modal
            return {
                "action": "close_modal",
                "message": "Closing...",
                "ui_actions": [
                    {"type": "ui.clickButton", "payload": {"target": "got-it-voice-guide"}},
                    {"type": "ui.clickButton", "payload": {"target": "got-it-platform-guide"}},
                ],
            }

        # === HIGH-IMPACT VOICE INTELLIGENCE FEATURES ===

        # "How's the class doing?" - Quick class status summary
        if action == 'class_status':
            course_id = _resolve_course_id(db, current_page, user_id)
            session_id = _resolve_session_id(db, current_page, user_id, course_id)

            if not session_id:
                return {
                    "action": "class_status",
                    "message": "Please select a session first to check on the class.",
                }

            # Gather data from multiple sources
            status_parts = []

            # Get session info
            session = db.query(SessionModel).filter(SessionModel.id == session_id).first()
            if session:
                status_parts.append(f"Session '{session.title}' is {session.status.value if hasattr(session.status, 'value') else session.status}.")

            # Get participation stats
            participation_result = _execute_tool(db, 'get_participation_stats', {"session_id": session_id})
            if participation_result and not participation_result.get("error"):
                participated = participation_result.get("participated_count", 0)
                total = participation_result.get("enrolled_count", 0)
                rate = participation_result.get("participation_rate", 0)
                if total > 0:
                    status_parts.append(f"{participated} of {total} students have participated ({rate}%).")
                non_participants = participation_result.get("non_participants", [])
                if non_participants and len(non_participants) <= 3:
                    names = [s.get("name", "Unknown") for s in non_participants[:3]]
                    status_parts.append(f"Still waiting on: {', '.join(names)}.")
                elif non_participants:
                    status_parts.append(f"{len(non_participants)} students haven't posted yet.")

            # Get post count
            posts_result = _execute_tool(db, 'get_session_posts', {"session_id": session_id, "include_content": False})
            if posts_result and not posts_result.get("error"):
                post_count = posts_result.get("count", 0)
                student_posts = posts_result.get("student_posts", 0)
                if post_count > 0:
                    status_parts.append(f"There are {post_count} posts total, {student_posts} from students.")

            # Get copilot status if available
            if session and session.copilot_active == 1:
                copilot_result = _execute_tool(db, 'get_copilot_suggestions', {"session_id": session_id, "count": 1})
                if copilot_result and not copilot_result.get("error"):
                    latest = copilot_result.get("latest")
                    if latest:
                        # Check engagement level
                        engagement = latest.get("engagement_level")
                        understanding = latest.get("understanding_level")
                        if engagement:
                            status_parts.append(f"Engagement level: {engagement}.")
                        if understanding:
                            status_parts.append(f"Understanding level: {understanding}.")
                        # Check confusion points
                        confusion_points = latest.get("confusion_points", [])
                        if confusion_points:
                            status_parts.append(f"Copilot detected {len(confusion_points)} confusion point{'s' if len(confusion_points) != 1 else ''}.")
                        # Get recommendation
                        recommendation = latest.get("recommendation")
                        if recommendation:
                            status_parts.append(f"Recommendation: {recommendation}")

            message = " ".join(status_parts) if status_parts else "No status information available for this session."

            return {
                "action": "class_status",
                "message": message,
                "session_id": session_id,
                "ui_actions": [
                    {"type": "ui.toast", "payload": {"message": "Class status retrieved", "type": "info"}},
                ],
            }

        # "Who needs help?" - Identify struggling students
        if action == 'who_needs_help':
            course_id = _resolve_course_id(db, current_page, user_id)
            session_id = _resolve_session_id(db, current_page, user_id, course_id)

            if not session_id:
                return {
                    "action": "who_needs_help",
                    "message": "Please select a session first to identify students who need help.",
                }

            help_parts = []
            students_needing_help = []

            # Get non-participants
            participation_result = _execute_tool(db, 'get_participation_stats', {"session_id": session_id})
            if participation_result and not participation_result.get("error"):
                non_participants = participation_result.get("non_participants", [])
                if non_participants:
                    names = [s.get("name", "Unknown") for s in non_participants[:5]]
                    help_parts.append(f"Students who haven't participated: {', '.join(names)}")
                    if len(non_participants) > 5:
                        help_parts.append(f"and {len(non_participants) - 5} more.")
                    students_needing_help.extend(non_participants)

            # Get confusion points from copilot
            copilot_result = _execute_tool(db, 'get_copilot_suggestions', {"session_id": session_id, "count": 1})
            if copilot_result and not copilot_result.get("error"):
                latest = copilot_result.get("latest")
                if latest and latest.get("confusion_points"):
                    confusion_points = latest["confusion_points"]
                    help_parts.append(f"Copilot detected {len(confusion_points)} area{'s' if len(confusion_points) != 1 else ''} of confusion:")
                    for i, cp in enumerate(confusion_points[:3], 1):
                        issue = cp.get("issue", "Unknown issue")
                        help_parts.append(f"{i}. {issue[:100]}")

            # Get low scorers if report exists
            scores_result = _execute_tool(db, 'get_student_scores', {"session_id": session_id})
            if scores_result and not scores_result.get("error") and scores_result.get("has_scores"):
                furthest = scores_result.get("furthest_from_correct", {})
                if furthest.get("user_name"):
                    help_parts.append(f"Lowest scorer: {furthest['user_name']} with {furthest.get('score', 0)} points.")

                # Check for students below 50
                student_scores = scores_result.get("student_scores", [])
                low_scorers = [s for s in student_scores if s.get("score", 100) < 50]
                if low_scorers:
                    names = [s.get("user_name", "Unknown") for s in low_scorers[:3]]
                    help_parts.append(f"Students scoring below 50: {', '.join(names)}")

            if not help_parts:
                message = "Good news! No immediate concerns detected. All students seem to be on track."
            else:
                message = " ".join(help_parts)

            return {
                "action": "who_needs_help",
                "message": message,
                "session_id": session_id,
                "students_needing_help": students_needing_help,
                "ui_actions": [
                    {"type": "ui.toast", "payload": {"message": "Help analysis complete", "type": "info"}},
                ],
            }

        # "What were the misconceptions?" - Report Q&A about misconceptions
        if action == 'ask_misconceptions':
            course_id = _resolve_course_id(db, current_page, user_id)
            session_id = _resolve_session_id(db, current_page, user_id, course_id)

            if not session_id:
                return {
                    "action": "ask_misconceptions",
                    "message": "Please select a session first to view misconceptions.",
                }

            # Get report data
            report_result = _execute_tool(db, 'get_report', {"session_id": session_id})
            if report_result and report_result.get("error"):
                return report_result

            if not report_result or not report_result.get("has_report"):
                # Try to get from copilot instead
                copilot_result = _execute_tool(db, 'get_copilot_suggestions', {"session_id": session_id, "count": 1})
                if copilot_result and not copilot_result.get("error"):
                    latest = copilot_result.get("latest")
                    if latest and latest.get("confusion_points"):
                        confusion_points = latest["confusion_points"]
                        parts = [f"From copilot analysis, {len(confusion_points)} confusion point{'s' if len(confusion_points) != 1 else ''} detected:"]
                        for i, cp in enumerate(confusion_points[:5], 1):
                            issue = cp.get("issue", "Unknown")
                            parts.append(f"{i}. {issue}")
                        return {
                            "action": "ask_misconceptions",
                            "message": " ".join(parts),
                            "source": "copilot",
                            "confusion_points": confusion_points,
                        }

                return {
                    "action": "ask_misconceptions",
                    "message": "No report available for this session yet. Generate a report first or start the copilot for real-time analysis.",
                }

            misconceptions = report_result.get("misconceptions", [])
            if not misconceptions:
                return {
                    "action": "ask_misconceptions",
                    "message": "No misconceptions were identified in this session's report. Students seem to have understood the material well.",
                }

            parts = [f"The report identified {len(misconceptions)} misconception{'s' if len(misconceptions) != 1 else ''}:"]
            for i, misc in enumerate(misconceptions[:5], 1):
                misconception = misc.get("misconception", "Unknown")
                parts.append(f"{i}. {misconception[:150]}")

            return {
                "action": "ask_misconceptions",
                "message": " ".join(parts),
                "misconceptions": misconceptions,
                "count": len(misconceptions),
            }

        # "How did students score?" - Report Q&A about scores
        if action == 'ask_scores':
            course_id = _resolve_course_id(db, current_page, user_id)
            session_id = _resolve_session_id(db, current_page, user_id, course_id)

            if not session_id:
                return {
                    "action": "ask_scores",
                    "message": "Please select a session first to view scores.",
                }

            scores_result = _execute_tool(db, 'get_student_scores', {"session_id": session_id})
            if scores_result and scores_result.get("error"):
                return scores_result

            if not scores_result or not scores_result.get("has_scores"):
                return {
                    "action": "ask_scores",
                    "message": "No scores available yet. Generate a report for this session first.",
                }

            parts = []
            avg = scores_result.get("average_score")
            if avg is not None:
                parts.append(f"The class average is {avg} out of 100.")

            highest = scores_result.get("highest_score")
            lowest = scores_result.get("lowest_score")
            if highest is not None and lowest is not None:
                parts.append(f"Scores range from {lowest} to {highest}.")

            closest = scores_result.get("closest_to_correct", {})
            if closest.get("user_name"):
                parts.append(f"Top performer: {closest['user_name']} with {closest.get('score', 0)}.")

            furthest = scores_result.get("furthest_from_correct", {})
            if furthest.get("user_name"):
                parts.append(f"Lowest scorer: {furthest['user_name']} with {furthest.get('score', 0)}.")

            # Score distribution
            distribution = scores_result.get("score_distribution", {})
            if distribution:
                high_performers = sum(v for k, v in distribution.items() if int(k.split('-')[0]) >= 80)
                low_performers = sum(v for k, v in distribution.items() if int(k.split('-')[0]) < 50)
                if high_performers:
                    parts.append(f"{high_performers} student{'s' if high_performers != 1 else ''} scored 80 or above.")
                if low_performers:
                    parts.append(f"{low_performers} student{'s' if low_performers != 1 else ''} scored below 50.")

            return {
                "action": "ask_scores",
                "message": " ".join(parts) if parts else "Score information is available in the report.",
                "average_score": avg,
                "student_scores": scores_result.get("student_scores", []),
            }

        # "How was participation?" - Report Q&A about participation
        if action == 'ask_participation':
            course_id = _resolve_course_id(db, current_page, user_id)
            session_id = _resolve_session_id(db, current_page, user_id, course_id)

            if not session_id:
                return {
                    "action": "ask_participation",
                    "message": "Please select a session first to view participation stats.",
                }

            result = _execute_tool(db, 'get_participation_stats', {"session_id": session_id})
            if result and result.get("error"):
                return result

            # The tool already returns a voice-friendly message
            return {
                "action": "ask_participation",
                "message": result.get("message", "Participation data retrieved."),
                "participation_rate": result.get("participation_rate"),
                "participants": result.get("participants", []),
                "non_participants": result.get("non_participants", []),
            }

        # "Read the latest posts" - Read posts aloud
        if action == 'read_posts':
            course_id = _resolve_course_id(db, current_page, user_id)
            session_id = _resolve_session_id(db, current_page, user_id, course_id)

            if not session_id:
                return {
                    "action": "read_posts",
                    "message": "Please select a session first to read posts.",
                }

            result = _execute_tool(db, 'get_latest_posts', {"session_id": session_id, "count": 3})
            if result and result.get("error"):
                return result

            posts = result.get("posts", [])
            if not posts:
                return {
                    "action": "read_posts",
                    "message": "There are no posts in this discussion yet.",
                }

            # Format posts for voice reading
            parts = [f"Here are the {len(posts)} most recent posts:"]
            for i, post in enumerate(posts, 1):
                name = post.get("user_name", "Someone")
                content = post.get("content", "")[:200]
                # Clean content for speech
                content = content.replace("\n", " ").strip()
                parts.append(f"{i}. {name} wrote: {content}")

            return {
                "action": "read_posts",
                "message": " ".join(parts),
                "posts": posts,
                "count": len(posts),
            }

        # "What did copilot suggest?" - Copilot suggestions summary
        if action == 'copilot_suggestions':
            course_id = _resolve_course_id(db, current_page, user_id)
            session_id = _resolve_session_id(db, current_page, user_id, course_id)

            if not session_id:
                return {
                    "action": "copilot_suggestions",
                    "message": "Please select a session first to get copilot suggestions.",
                }

            # Check if copilot is active
            session = db.query(SessionModel).filter(SessionModel.id == session_id).first()

            result = _execute_tool(db, 'get_copilot_suggestions', {"session_id": session_id, "count": 1})
            if result and result.get("error"):
                return result

            if not result or not result.get("suggestions"):
                if session and session.copilot_active != 1:
                    return {
                        "action": "copilot_suggestions",
                        "message": "The copilot is not running. Say 'start copilot' to begin monitoring.",
                    }
                return {
                    "action": "copilot_suggestions",
                    "message": "No suggestions from the copilot yet. It analyzes the discussion every 90 seconds.",
                }

            latest = result.get("latest", {})
            parts = ["Here's what the copilot suggests:"]

            # Rolling summary
            summary = latest.get("summary")
            if summary:
                parts.append(f"Discussion summary: {summary[:200]}")

            # Confusion points
            confusion_points = latest.get("confusion_points", [])
            if confusion_points:
                parts.append(f"Confusion detected in {len(confusion_points)} area{'s' if len(confusion_points) != 1 else ''}.")
                first_cp = confusion_points[0]
                parts.append(f"Main issue: {first_cp.get('issue', 'Unknown')[:100]}")

            # Suggested prompts
            prompts = latest.get("instructor_prompts", [])
            if prompts:
                parts.append("Suggested question to ask:")
                first_prompt = prompts[0]
                parts.append(f"\"{first_prompt.get('prompt', '')[:150]}\"")

            # Poll suggestion
            poll = latest.get("poll_suggestion")
            if poll:
                parts.append(f"Poll idea: {poll.get('question', '')[:100]}")

            # Overall recommendation
            recommendation = latest.get("recommendation")
            if recommendation:
                parts.append(f"Recommendation: {recommendation}")

            return {
                "action": "copilot_suggestions",
                "message": " ".join(parts),
                "latest": latest,
            }

        # Student lookup - "How is [student] doing?"
        if action == 'student_lookup':
            course_id = _resolve_course_id(db, current_page, user_id)
            session_id = _resolve_session_id(db, current_page, user_id, course_id)

            # Try to extract student name from transcript
            student_name = None
            name_patterns = [
                r'\bhow\s+is\s+(\w+)\s+(doing|performing)\b',
                r'\btell\s+me\s+about\s+(\w+)',
                r'\bcheck\s+(?:on\s+)?(\w+)\b',
                r'\blook\s+up\s+(\w+)\b',
                r'\bwhat\s+about\s+(\w+)\b',
            ]
            for pattern in name_patterns:
                match = re.search(pattern, transcript.lower())
                if match:
                    student_name = match.group(1)
                    break

            if not student_name:
                return {
                    "action": "student_lookup",
                    "message": "Which student would you like to know about? Say 'How is [name] doing?'",
                }

            if not session_id:
                return {
                    "action": "student_lookup",
                    "message": f"Please select a session first to check on {student_name}.",
                }

            # Search for student in participation data
            participation_result = _execute_tool(db, 'get_participation_stats', {"session_id": session_id})
            participants = participation_result.get("participants", []) if participation_result else []
            non_participants = participation_result.get("non_participants", []) if participation_result else []

            # Find the student (fuzzy match)
            student_name_lower = student_name.lower()
            found_participant = None
            found_non_participant = None

            for p in participants:
                if student_name_lower in p.get("name", "").lower():
                    found_participant = p
                    break

            for np in non_participants:
                if student_name_lower in np.get("name", "").lower():
                    found_non_participant = np
                    break

            parts = []

            if found_participant:
                name = found_participant.get("name", student_name)
                post_count = found_participant.get("post_count", 0)
                parts.append(f"{name} has participated with {post_count} post{'s' if post_count != 1 else ''}.")

                # Check if they have a score in the report
                scores_result = _execute_tool(db, 'get_student_scores', {"session_id": session_id})
                if scores_result and scores_result.get("has_scores"):
                    student_scores = scores_result.get("student_scores", [])
                    for s in student_scores:
                        if student_name_lower in s.get("user_name", "").lower():
                            parts.append(f"Their score is {s.get('score', 'N/A')} out of 100.")
                            break
            elif found_non_participant:
                name = found_non_participant.get("name", student_name)
                parts.append(f"{name} has not participated in this session yet.")
            else:
                parts.append(f"I couldn't find a student named '{student_name}' in this session.")

            return {
                "action": "student_lookup",
                "message": " ".join(parts),
                "student_name": student_name,
            }

        # Summarize discussion (enhanced version)
        if action == 'summarize_discussion':
            course_id = _resolve_course_id(db, current_page, user_id)
            session_id = _resolve_session_id(db, current_page, user_id, course_id)

            if not session_id:
                return {
                    "action": "summarize_discussion",
                    "message": "Please select a session first to summarize the discussion.",
                }

            # Try to get summary from copilot first (most up-to-date)
            copilot_result = _execute_tool(db, 'get_copilot_suggestions', {"session_id": session_id, "count": 1})
            if copilot_result and not copilot_result.get("error"):
                latest = copilot_result.get("latest")
                if latest and latest.get("summary"):
                    return {
                        "action": "summarize_discussion",
                        "message": f"Discussion summary: {latest['summary']}",
                        "source": "copilot",
                    }

            # Fall back to report themes
            report_result = _execute_tool(db, 'get_report', {"session_id": session_id})
            if report_result and report_result.get("has_report"):
                themes = report_result.get("themes", [])
                if themes:
                    theme_names = [t.get("theme", "") for t in themes[:5]]
                    parts = [f"Main themes discussed: {', '.join(theme_names)}."]

                    # Add misconceptions if any
                    misconceptions = report_result.get("misconceptions", [])
                    if misconceptions:
                        parts.append(f"Key misconception: {misconceptions[0].get('misconception', '')[:100]}")

                    return {
                        "action": "summarize_discussion",
                        "message": " ".join(parts),
                        "source": "report",
                        "themes": themes,
                    }

            # Fall back to post count
            posts_result = _execute_tool(db, 'get_session_posts', {"session_id": session_id, "include_content": False})
            if posts_result and not posts_result.get("error"):
                count = posts_result.get("count", 0)
                student_posts = posts_result.get("student_posts", 0)
                return {
                    "action": "summarize_discussion",
                    "message": f"There are {count} posts in this discussion, {student_posts} from students. Start the copilot for a detailed summary.",
                    "source": "posts",
                }

            return {
                "action": "summarize_discussion",
                "message": "No discussion content to summarize yet.",
            }

        # === POLL ACTIONS ===
        if action == 'create_poll':
            course_id = _resolve_course_id(db, current_page, user_id)
            session_id = _resolve_session_id(db, current_page, user_id, course_id)
            # Start conversational poll creation flow
            # First, offer to create a poll (or go directly to asking for question)
            conv_context = conversation_manager.get_context(user_id)
            conv_context.state = ConversationState.AWAITING_POLL_QUESTION
            conv_context.poll_question = ""
            conv_context.poll_options = []
            conv_context.poll_current_option_index = 1
            conversation_manager.save_context(user_id, conv_context)

            return {
                "action": "create_poll",
                "session_id": session_id,
                "ui_actions": [
                    {"type": "ui.switchTab", "payload": {"tabName": "polls", "target": "tab-polls"}},
                    {"type": "ui.toast", "payload": {"message": "Opening poll creator...", "type": "info"}},
                ],
                "message": "Great! What question would you like to ask in the poll?",
                "conversation_state": "poll_creation",
            }

        # === REPORT ACTIONS ===
        if action == 'generate_report':
            course_id = _resolve_course_id(db, current_page, user_id)
            session_id = _resolve_session_id(db, current_page, user_id, course_id)
            if not session_id:
                return None
            result = _execute_tool(db, 'generate_report', {"session_id": session_id})
            if result and user_id:
                context_store.record_action(
                    user_id,
                    action_type="generate_report",
                    action_data={"session_id": session_id},
                    undo_data=None,  # Reports can't be undone
                )
            if result:
                result["ui_actions"] = [
                    {"type": "ui.navigate", "payload": {"path": "/reports"}},
                    {"type": "ui.toast", "payload": {"message": "Generating report...", "type": "info"}},
                ]
            return result

        # === ENROLLMENT ACTIONS ===
        if action == 'list_enrollments':
            course_id = _resolve_course_id(db, current_page, user_id)
            if not course_id:
                return []
            return _execute_tool(db, 'get_enrolled_students', {"course_id": course_id})

        if action == 'manage_enrollments':
            course_id = _resolve_course_id(db, current_page, user_id)
            return {
                "action": "manage_enrollments",
                "course_id": course_id,
                "ui_actions": [
                    {"type": "ui.navigate", "payload": {"path": f"/courses/{course_id}" if course_id else "/courses"}},
                    {"type": "ui.openModal", "payload": {"modal": "manageEnrollments", "courseId": course_id}},
                ],
                "message": "Opening enrollment management.",
            }

        if action == 'list_student_pool':
            # List available students (not enrolled) for selection
            course_id = _resolve_course_id(db, current_page, user_id)
            if not course_id:
                return {"message": "Please select a course first to see the student pool."}

            # Get all students using get_users with role=student
            result = _execute_tool(db, 'get_users', {"role": "student"})
            all_students = result.get("users", []) if isinstance(result, dict) else (result if isinstance(result, list) else [])

            # Get enrolled students
            enrolled_result = _execute_tool(db, 'get_enrolled_students', {"course_id": course_id})
            enrolled_students = enrolled_result.get("students", []) if isinstance(enrolled_result, dict) else (enrolled_result if isinstance(enrolled_result, list) else [])
            enrolled_ids = {s.get("user_id") or s.get("id") for s in enrolled_students}

            # Filter to available (not enrolled) students
            available_students = [s for s in all_students if s.get("id") not in enrolled_ids]

            if not available_students:
                return {"message": "The student pool is empty. All students are already enrolled in this course."}

            # Create options for dropdown-style selection
            options = [DropdownOption(label=s.get("name") or s.get("email", f"Student {s['id']}"), value=str(s["id"])) for s in available_students[:10]]

            # Start selection flow
            prompt = conversation_manager.start_dropdown_selection(
                user_id, "student-pool", options, current_page or "/courses"
            )

            return {
                "action": "list_student_pool",
                "message": prompt,
                "students": available_students[:10],
                "ui_actions": [
                    {"type": "ui.toast", "payload": {"message": f"{len(available_students)} students available", "type": "info"}},
                ],
            }

        if action == 'enroll_selected':
            return {
                "action": "enroll_selected",
                "message": "Enrolling the selected students.",
                "ui_actions": [
                    {"type": "ui.clickButton", "payload": {"target": "enroll-selected"}},
                ],
            }

        if action == 'enroll_all':
            return {
                "action": "enroll_all",
                "message": "Enrolling all available students.",
                "ui_actions": [
                    {"type": "ui.clickButton", "payload": {"target": "enroll-all"}},
                ],
            }

        if action == 'select_student':
            # Extract student name from transcript
            student_name = _extract_student_name(transcript or "")
            if not student_name:
                return {"message": "I couldn't hear the student name. Please say the student's name clearly."}

            return {
                "action": "select_student",
                "message": f"Selected {student_name}. Say another student name to select more, or say 'enroll selected' to enroll them.",
                "ui_actions": [
                    {"type": "ui.selectListItem", "payload": {"itemName": student_name, "target": "student-pool"}},
                ],
            }

        # === FORUM/CASE ACTIONS ===
        if action == 'post_case':
            course_id = _resolve_course_id(db, current_page, user_id)
            session_id = _resolve_session_id(db, current_page, user_id, course_id)

            # Check if we're on the console page - offer conversational case creation
            if current_page and '/console' in current_page:
                # Offer to help create a case using conversational flow
                offer_prompt = conversation_manager.offer_case_posting(user_id)
                if offer_prompt:
                    return {
                        "action": "post_case",
                        "session_id": session_id,
                        "ui_actions": [
                            {"type": "ui.switchTab", "payload": {"tabName": "cases", "target": "tab-cases"}},
                        ],
                        "message": f"Switching to the Post Case tab. {offer_prompt}",
                        "case_offer": True,
                    }
                else:
                    # User already declined the offer - just switch tab
                    return {
                        "action": "post_case",
                        "session_id": session_id,
                        "ui_actions": [
                            {"type": "ui.switchTab", "payload": {"tabName": "cases", "target": "tab-cases"}},
                            {"type": "ui.toast", "payload": {"message": "Switched to Post Case tab", "type": "info"}},
                        ],
                        "message": "Switching to the Post Case tab. You can type your case study here.",
                    }

            # If on forum page, switch to cases tab there
            if current_page and '/forum' in current_page:
                return {
                    "action": "post_case",
                    "session_id": session_id,
                    "ui_actions": [
                        {"type": "ui.switchTab", "payload": {"tabName": "cases", "target": "tab-cases"}},
                        {"type": "ui.toast", "payload": {"message": "Switched to Case Studies tab", "type": "info"}},
                    ],
                    "message": "Switching to the Case Studies tab.",
                }

            # Otherwise navigate to console page and switch to cases tab with offer
            offer_prompt = conversation_manager.offer_case_posting(user_id)
            return {
                "action": "post_case",
                "session_id": session_id,
                "ui_actions": [
                    {"type": "ui.navigate", "payload": {"path": "/console"}},
                    {"type": "ui.switchTab", "payload": {"tabName": "cases", "target": "tab-cases"}},
                ],
                "message": f"Opening the console. {offer_prompt or 'You can type your case study here.'}",
                "case_offer": bool(offer_prompt),
            }

        if action == 'post_to_discussion':
            # Check if we have a session selected
            course_id = _resolve_course_id(db, current_page, user_id)
            session_id = _resolve_session_id(db, current_page, user_id, course_id)
            if not session_id:
                return {
                    "action": "post_to_discussion",
                    "error": "no_session",
                    "message": "Please select a live session first before posting to the discussion.",
                    "ui_actions": [
                        {"type": "ui.navigate", "payload": {"path": "/forum"}},
                    ],
                }

            # Trigger the forum post offer flow
            offer_prompt = conversation_manager.offer_forum_post(user_id)
            if offer_prompt:
                return {
                    "action": "post_to_discussion",
                    "session_id": session_id,
                    "message": offer_prompt,
                    "ui_actions": [
                        {"type": "ui.switchTab", "payload": {"tabName": "discussion", "target": "tab-discussion"}},
                    ],
                    "post_offer": True,
                }
            else:
                # User already declined the offer this session
                return {
                    "action": "post_to_discussion",
                    "message": "You've already declined to post. Let me know if you change your mind!",
                }

        if action == 'view_posts':
            course_id = _resolve_course_id(db, current_page, user_id)
            session_id = _resolve_session_id(db, current_page, user_id, course_id)
            if session_id:
                posts = _execute_tool(db, 'get_session_posts', {"session_id": session_id})
                if posts:
                    posts_result = {"posts": posts, "count": len(posts)}
                    posts_result["ui_actions"] = [{"type": "ui.navigate", "payload": {"path": "/forum"}}]
                    return posts_result
            return {
                "posts": [],
                "ui_actions": [{"type": "ui.navigate", "payload": {"path": "/forum"}}],
            }

        if action == 'get_pinned_posts':
            course_id = _resolve_course_id(db, current_page, user_id)
            session_id = _resolve_session_id(db, current_page, user_id, course_id)
            if session_id:
                pinned = _execute_tool(db, 'get_pinned_posts', {"session_id": session_id})
                return {
                    "pinned_posts": pinned or [],
                    "count": len(pinned) if pinned else 0,
                    "ui_actions": [{"type": "ui.navigate", "payload": {"path": "/forum"}}],
                }
            return {"pinned_posts": [], "count": 0}

        if action == 'summarize_discussion':
            course_id = _resolve_course_id(db, current_page, user_id)
            session_id = _resolve_session_id(db, current_page, user_id, course_id)
            if session_id:
                posts = _execute_tool(db, 'get_session_posts', {"session_id": session_id})
                if posts and len(posts) > 0:
                    # Extract key info from posts
                    total = len(posts)
                    # Find posts with labels
                    questions = [p for p in posts if p.get('labels_json') and 'question' in p.get('labels_json', [])]
                    misconceptions = [p for p in posts if p.get('labels_json') and 'misconception' in p.get('labels_json', [])]
                    insightful = [p for p in posts if p.get('labels_json') and 'insightful' in p.get('labels_json', [])]
                    pinned = [p for p in posts if p.get('pinned')]

                    return {
                        "total_posts": total,
                        "questions": len(questions),
                        "misconceptions": len(misconceptions),
                        "insightful": len(insightful),
                        "pinned": len(pinned),
                        "latest_topic": posts[0].get('content', '')[:100] if posts else None,
                        "summary": f"The discussion has {total} posts. "
                                   f"{len(questions)} questions, {len(misconceptions)} misconceptions identified, "
                                   f"and {len(insightful)} insightful contributions.",
                    }
                return {"summary": "No posts in this discussion yet.", "total_posts": 0}
            return {"error": "No active session. Select a live session first."}

        if action == 'get_student_questions':
            course_id = _resolve_course_id(db, current_page, user_id)
            session_id = _resolve_session_id(db, current_page, user_id, course_id)
            if session_id:
                posts = _execute_tool(db, 'get_session_posts', {"session_id": session_id})
                if posts:
                    # Filter for posts labeled as questions or containing question marks
                    questions = [
                        p for p in posts
                        if (p.get('labels_json') and 'question' in p.get('labels_json', []))
                        or '?' in p.get('content', '')
                    ]
                    return {
                        "questions": questions,
                        "count": len(questions),
                        "message": f"Found {len(questions)} questions from students."
                    }
                return {"questions": [], "count": 0, "message": "No questions found yet."}
            return {"error": "No active session. Select a live session first."}

        # For actions that need more info, return guidance
        return {"message": f"Action '{action}' recognized but needs more details."}

    except Exception as e:
        print(f"Action execution failed: {e}")
        # Record error and check if we should retry
        if user_id:
            retry_result = conversation_manager.record_error(user_id, str(e))
            if retry_result["should_retry"]:
                return {
                    "error": str(e),
                    "message": retry_result["message"],
                    "retry_count": retry_result["retry_count"],
                    "should_retry": True,
                }
            else:
                return {
                    "error": str(e),
                    "message": retry_result["message"],
                    "retry_count": retry_result["retry_count"],
                    "should_retry": False,
                }
        return {"error": str(e)}


def execute_plan_steps(steps: List[Dict[str, Any]], db: Session) -> tuple[list[dict], str]:
    results = []
    for step in steps:
        tool_name = step.get("tool_name")
        args = step.get("args", {})
        tool_entry = TOOL_REGISTRY.get(tool_name)
        if not tool_entry:
            normalized = normalize_tool_result({"error": f"Unknown tool: {tool_name}"}, tool_name)
            results.append({"tool": tool_name, "success": False, **normalized})
            continue

        error = _validate_tool_args(tool_name, args, tool_entry.get("parameters", {}))
        if error:
            normalized = normalize_tool_result({"error": error}, tool_name)
            results.append({"tool": tool_name, "success": False, **normalized})
            continue

        try:
            normalized = normalize_tool_result(
                invoke_tool_handler(tool_entry["handler"], args, db=db),
                tool_name,
            )
            results.append({"tool": tool_name, "success": normalized.get("ok", True), **normalized})
        except Exception as exc:
            normalized = normalize_tool_result({"error": str(exc)}, tool_name)
            results.append({"tool": tool_name, "success": False, **normalized})

    summary = generate_summary(results)
    return results, summary


def get_page_suggestions(path: str) -> List[str]:
    """Get contextual suggestions for a page"""
    suggestions = {
        '/courses': ["Create a new course", "Generate session plans", "View enrollments"],
        '/sessions': ["Start a session", "View session details", "Check copilot status"],
        '/forum': ["Post a case study", "View recent posts", "Pin a post"],
        '/console': ["Start copilot", "Create a poll", "View suggestions"],
        '/reports': ["Generate a report", "View participation", "Check scores"],
    }
    return suggestions.get(path, ["How can I help?"])


def get_action_suggestions(action: str) -> List[str]:
    """Get follow-up suggestions after an action"""
    suggestions = {
        # UI interaction suggestions
        'ui_select_course': ["Select a session", "Go to enrollment tab", "Generate report"],
        'ui_select_session': ["Go live", "Start copilot", "View forum"],
        'ui_switch_tab': ["What's on this page?", "Go back", "Help me"],
        'ui_click_button': ["What happened?", "What's next?", "Go to another page"],
        # Undo/context suggestions
        'undo_action': ["What's my context?", "Show my courses", "Continue where I was"],
        'get_context': ["Clear context", "Change course", "Change session"],
        'clear_context': ["Show my courses", "Go to sessions", "Help me"],
        # Context/status suggestions
        'get_status': ["Show my courses", "Go to forum", "Start copilot"],
        'get_help': ["Show my courses", "Go to forum", "Create poll"],
        # Course suggestions
        'list_courses': ["Open a course", "Create new course", "View sessions"],
        'create_course': ["Add syllabus", "Set objectives", "Add students"],
        'select_course': ["View sessions", "Manage enrollments", "Create session"],
        'view_course_details': ["Create session", "View sessions", "Go to forum"],
        # Session suggestions
        'list_sessions': ["Start a session", "Go live", "View details"],
        'create_session': ["Go live", "Set schedule", "View sessions"],
        'select_session': ["Go live", "View details", "Start copilot"],
        'go_live': ["Start copilot", "Create poll", "Post case"],
        'end_session': ["Generate report", "View posts", "Create new session"],
        'view_materials': ["Download file", "View sessions", "Go to forum"],
        # Copilot suggestions
        'start_copilot': ["View suggestions", "Create a poll", "Post case"],
        'stop_copilot': ["Generate report", "View interventions", "Go to forum"],
        'get_interventions': ["Create suggested poll", "Post to forum", "View details"],
        # Poll suggestions
        'create_poll': ["View responses", "Create another poll", "Post case"],
        # Report suggestions
        'generate_report': ["View analytics", "Export report", "Start new session"],
        # Enrollment suggestions
        'list_enrollments': ["Add students", "View participation", "Go to sessions"],
        'manage_enrollments': ["Add by email", "Upload roster", "View enrolled"],
        # Forum suggestions
        'post_case': ["View responses", "Pin post", "Create poll"],
        'post_to_discussion': ["View posts", "Switch to case studies", "Select another session"],
        'view_posts': ["Pin a post", "Label post", "Summarize discussion"],
        'get_pinned_posts': ["View all posts", "Post case", "Create poll"],
        'summarize_discussion': ["Show questions", "View pinned", "Create poll"],
        'get_student_questions': ["View posts", "Create poll", "Pin a post"],
        # High-impact intelligence features
        'class_status': ["Who needs help?", "What did copilot suggest?", "Read latest posts"],
        'who_needs_help': ["Check on a student", "Summarize discussion", "Create poll"],
        'ask_misconceptions': ["How did students score?", "Who needs help?", "Create poll"],
        'ask_scores': ["Who needs help?", "View participation", "Generate report"],
        'ask_participation': ["Who needs help?", "Read latest posts", "Create poll"],
        'read_posts': ["Summarize discussion", "Pin a post", "Create poll"],
        'copilot_suggestions': ["Create suggested poll", "Post to discussion", "Who needs help?"],
        'student_lookup': ["Check another student", "Who needs help?", "View participation"],
    }
    return suggestions.get(action, ["What else can I help with?"])


def generate_fallback_response(transcript: str, context: Optional[List[str]]) -> str:
    """Generate a helpful response when intent is unclear"""
    
    # Check for greetings
    greetings = ['hi', 'hello', 'hey', 'good morning', 'good afternoon']
    if any(g in transcript.lower() for g in greetings):
        return "Hello! How can I help you today? You can ask me to show your courses, start a session, or navigate to any page."
    
    # Check for thanks
    thanks = ['thank', 'thanks', 'appreciate']
    if any(t in transcript.lower() for t in thanks):
        return "You're welcome! Is there anything else I can help you with?"
    
    # Check for help
    if 'help' in transcript.lower():
        return "I can help you with: navigating pages, listing your courses and sessions, starting the AI copilot, creating polls, and generating reports. What would you like to do?"
    
    # Default
    return f"I heard '{transcript}', but I'm not sure what you'd like me to do. Try saying 'show my courses', 'go to forum', or 'start copilot'."
