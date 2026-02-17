"""Voice Command Helper Functions.

This module provides helper functions for voice command processing:
1. Page-specific suggestions
2. Action-specific follow-up suggestions
3. Fallback response generation
"""

from typing import List, Optional

from api.api.voice_extraction import normalize_spanish_text


def get_page_suggestions(path: str, language: str = 'en') -> List[str]:
    """Get contextual suggestions for a page in the specified language."""
    suggestions = {
        'en': {
            '/courses': ["Create a new course", "Generate session plans", "View enrollments"],
            '/sessions': ["Start a session", "View session details", "Check copilot status"],
            '/forum': ["Post a case study", "View recent posts", "Pin a post"],
            '/console': ["Start copilot", "Create a poll", "View suggestions"],
            '/reports': ["Generate a report", "View participation", "Check scores"],
            '/integrations': ["Add connection", "Sync materials", "View mappings"],
            '/dashboard': ["Go to courses", "Go to sessions", "Go to forum"],
        },
        'es': {
            '/courses': ["Crear un curso", "Generar planes de sesion", "Ver inscripciones"],
            '/sessions': ["Iniciar sesion", "Ver detalles", "Ver estado del copiloto"],
            '/forum': ["Publicar caso de estudio", "Ver publicaciones recientes", "Fijar publicacion"],
            '/console': ["Iniciar copiloto", "Crear encuesta", "Ver sugerencias"],
            '/reports': ["Generar reporte", "Ver participacion", "Ver calificaciones"],
            '/integrations': ["Agregar conexion", "Sincronizar materiales", "Ver mapeos"],
            '/dashboard': ["Ir a cursos", "Ir a sesiones", "Ir a foro"],
        }
    }
    lang = language if language in suggestions else 'en'

    # Extract base path for matching
    if path:
        base_path = '/' + path.strip('/').split('/')[0]
    else:
        base_path = '/dashboard'

    default = ["Como puedo ayudarte?"] if lang == 'es' else ["How can I help?"]
    return suggestions[lang].get(base_path, default)


def get_action_suggestions(action: str, language: str = 'en') -> List[str]:
    """Get follow-up suggestions after an action in the specified language."""
    suggestions_en = {
        # UI interaction suggestions
        'ui_select_course': ["Select a session", "Go to advanced tab", "Generate report"],
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
        'open_question': ["Tell me more", "Show me an example", "What else can you do?"],
        # Course suggestions
        'list_courses': ["Open a course", "Create new course", "View sessions"],
        'create_course': ["Add syllabus", "Set objectives", "Add students"],
        'create_course_flow': ["Add syllabus", "Set objectives", "Add students"],
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
        'generate_summary': ["View details", "Create poll", "Post to forum"],
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

    suggestions_es = {
        # UI interaction suggestions
        'ui_select_course': ["Seleccionar sesion", "Ir a pestana avanzada", "Generar reporte"],
        'ui_select_session': ["Iniciar en vivo", "Iniciar copiloto", "Ver foro"],
        'ui_switch_tab': ["Que hay en esta pagina?", "Volver", "Ayudame"],
        'ui_click_button': ["Que paso?", "Que sigue?", "Ir a otra pagina"],
        # Course suggestions
        'list_courses': ["Abrir un curso", "Crear curso nuevo", "Ver sesiones"],
        'create_course': ["Agregar programa", "Definir objetivos", "Agregar estudiantes"],
        'create_course_flow': ["Agregar programa", "Definir objetivos", "Agregar estudiantes"],
        'select_course': ["Ver sesiones", "Gestionar inscripciones", "Crear sesion"],
        # Session suggestions
        'list_sessions': ["Iniciar sesion", "Ir en vivo", "Ver detalles"],
        'create_session': ["Ir en vivo", "Programar", "Ver sesiones"],
        'select_session': ["Ir en vivo", "Ver detalles", "Iniciar copiloto"],
        'go_live': ["Iniciar copiloto", "Crear encuesta", "Publicar caso"],
        'end_session': ["Generar reporte", "Ver publicaciones", "Crear nueva sesion"],
        # Copilot suggestions
        'start_copilot': ["Ver sugerencias", "Crear encuesta", "Publicar caso"],
        'stop_copilot': ["Generar reporte", "Ver intervenciones", "Ir al foro"],
        # Poll suggestions
        'create_poll': ["Ver respuestas", "Crear otra encuesta", "Publicar caso"],
        # Report suggestions
        'generate_report': ["Ver analiticas", "Exportar reporte", "Nueva sesion"],
        'generate_summary': ["Ver detalles", "Crear encuesta", "Publicar en foro"],
    }

    if language == 'es':
        return suggestions_es.get(action, ["En que mas puedo ayudarte?"])
    return suggestions_en.get(action, ["What else can I help with?"])


def generate_fallback_response(
    transcript: str,
    context: Optional[List[str]],
    current_page: Optional[str] = None,
    language: str = 'en'
) -> str:
    """Generate a helpful response when intent is unclear.

    Provides page-specific suggestions based on the user's current location.
    """
    lang = language if language in ['en', 'es'] else 'en'
    # Normalize transcript for matching
    transcript_lower = normalize_spanish_text(transcript.lower())

    # Check for greetings (English + Spanish)
    greetings = ['hi', 'hello', 'hey', 'good morning', 'good afternoon',
                 'hola', 'buenos dias', 'buenas tardes', 'buenas noches']
    if any(g in transcript_lower for g in greetings):
        suggestions = get_page_suggestions(current_page, lang)
        if lang == 'es':
            return f"Hola! Como puedo ayudarte hoy? En esta pagina puedes: {', '.join(suggestions)}."
        return f"Hello! How can I help you today? On this page you can: {', '.join(suggestions)}."

    # Check for thanks (English + Spanish)
    thanks = ['thank', 'thanks', 'appreciate', 'gracias', 'muchas gracias']
    if any(t in transcript_lower for t in thanks):
        if lang == 'es':
            return "De nada! Hay algo mas en que pueda ayudarte?"
        return "You're welcome! Is there anything else I can help you with?"

    # Check for help (English + Spanish)
    help_words = ['help', 'ayuda', 'ayudame']
    if any(h in transcript_lower for h in help_words):
        suggestions = get_page_suggestions(current_page, lang)
        if lang == 'es':
            return f"En esta pagina puedes: {', '.join(suggestions)}. Que te gustaria hacer?"
        return f"On this page, you can: {', '.join(suggestions)}. What would you like to do?"

    # Page-specific fallback suggestions
    page_specific_hints = {
        'en': {
            '/courses': "Try saying 'create a course', 'show my courses', or 'view materials'.",
            '/sessions': "Try saying 'create a session', 'go live', or 'select a session'.",
            '/forum': "Try saying 'post to discussion', 'view posts', or 'switch to case studies'.",
            '/console': "Try saying 'start copilot', 'create a poll', or 'view roster'.",
            '/reports': "Try saying 'generate report', 'view participation', or 'check scores'.",
            '/dashboard': "Try saying 'go to courses', 'go to sessions', or 'go to forum'.",
            '/integrations': "Try saying 'add connection', 'sync materials', or 'view mappings'.",
        },
        'es': {
            '/courses': "Intenta decir 'crear un curso', 'mostrar mis cursos', o 'ver materiales'.",
            '/sessions': "Intenta decir 'crear una sesion', 'iniciar transmision', o 'seleccionar sesion'.",
            '/forum': "Intenta decir 'publicar en discusion', 'ver publicaciones', o 'cambiar a casos'.",
            '/console': "Intenta decir 'iniciar copilot', 'crear encuesta', o 'ver lista'.",
            '/reports': "Intenta decir 'generar informe', 'ver participacion', o 'ver puntuaciones'.",
            '/dashboard': "Intenta decir 'ir a cursos', 'ir a sesiones', o 'ir a foro'.",
            '/integrations': "Intenta decir 'agregar conexion', 'sincronizar materiales', o 'ver mapeos'.",
        }
    }

    default_hint = {
        'en': "Try saying 'show my courses', 'go to forum', or 'start copilot'.",
        'es': "Intenta decir 'mostrar mis cursos', 'ir a foro', o 'iniciar copilot'.",
    }

    # Extract base path for matching
    base_path = None
    if current_page:
        base_path = '/' + current_page.strip('/').split('/')[0]

    hint = page_specific_hints.get(lang, {}).get(base_path, default_hint.get(lang, default_hint['en']))

    if lang == 'es':
        return f"Escuche '{transcript}', pero no estoy seguro de que te gustaria que hiciera. {hint}"
    return f"I heard '{transcript}', but I'm not sure what you'd like me to do. {hint}"
