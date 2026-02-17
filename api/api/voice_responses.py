"""Voice Response Templates and Bilingual Support.

This module provides:
1. Bilingual response templates (English and Spanish)
2. Page name translations
3. Status translations
4. Helper functions for getting localized responses
"""

from typing import Optional

# =============================================================================
# BILINGUAL RESPONSE TEMPLATES
# =============================================================================
# These templates are used to generate responses in the user's selected language.
# The language is passed from the frontend and determines which template to use.

RESPONSE_TEMPLATES = {
    'en': {
        # Navigation
        'navigate_to': "Taking you to {destination} now.",
        'navigate_open': "Opening {destination} for you.",
        'switch_tab': "Switching to the {tab} tab.",
        'switching_tabs': "Switching tabs.",

        # Courses
        'no_courses': "You don't have any courses yet. Would you like me to help you create one?",
        'one_course': "You have one course: {name}. Would you like me to open it?",
        'few_courses': "You have {count} courses: {names}. Which one would you like to work with?",
        'many_courses': "You have {count} courses, including {names}, and {more} more. Would you like to see them all?",
        'create_course': "Opening course creation. Tell me the course title, or I can help you set it up step by step.",
        'select_course': "Opening {name}. What would you like to do with it?",
        'selecting_course': "Selecting the course for you.",

        # Sessions
        'no_sessions': "No sessions found. Would you like to create a new session?",
        'live_sessions': "There {verb} {count} live session{plural}: {names}. Would you like to join one?",
        'sessions_none_live': "You have {count} sessions. None are live right now. Would you like to start one?",
        'create_session': "Opening session creation. What topic will this session cover?",
        'select_session': "Opening {name}. Status: {status}.",
        'selecting_session': "Selecting the session for you.",
        'session_live': "Session is now live! Students can join and start participating.",
        'session_ended': "Session has ended. Would you like me to generate a report?",
        'session_draft': "Session has been set to draft. You can edit it or go live when ready.",
        'session_completed': "Session has been marked as completed.",
        'session_scheduled': "Session has been scheduled.",

        # Actions
        'click_button': "Clicking {button}.",
        'clicking_button': "Clicking the button.",
        'opening_materials': "Opening the course materials. You can view and download uploaded files here.",

        # Confirmations
        'confirm_proceed': "Would you like me to proceed?",
        'confirm_yes': "Done!",
        'confirm_cancel': "Okay, cancelled.",

        # Errors
        'error_generic': "Sorry, there was an issue: {reason}",
        'error_not_found': "I couldn't find that. Please try again.",

        # Greetings
        'greeting': "Hello! How can I help you?",
        'ready': "I'm ready to help. What would you like to do?",

        # Dropdown
        'dropdown_options': "Your options are: {options}. Which would you like to select?",
        'dropdown_selected': "Selected {name}.",

        # Forum
        'forum_post_offer': "Would you like me to help you post something?",
        'forum_posting': "Posting to the forum.",

        # Polls
        'poll_create_offer': "Would you like to create a poll?",
        'poll_creating': "Creating the poll.",

        # AI Features
        'generating_summary': "Generating a summary of the discussion.",
        'generating_questions': "Generating quiz questions from the discussion.",
        'creating_groups': "Creating AI-powered student groups.",

        # Form filling
        'form_cancelled': "Form cancelled. What would you like to do?",
        'form_complete': "I've filled in all the required fields. Would you like me to submit the form?",
        'confirm_yes_no': "Please say 'yes' to confirm or 'no' to cancel.",
        'got_it_continue': "Got it! {prompt}",
        'skipped_syllabus_offer': "Skipped. Now for the syllabus. Would you like me to generate one, or would you prefer to dictate it? You can also say 'skip'.",
        'skipped_objectives_offer': "Skipped. Now for learning objectives. Would you like me to generate them, or would you prefer to dictate? You can also say 'skip'.",
        'skipped_session_plan_offer': "Skipped. Now for the session description. Would you like me to generate a session plan, or would you prefer to dictate it?",
        'syllabus_generate_offer': "I can generate a syllabus for '{course_name}'. Would you like me to create one?",
        'objectives_generate_offer': "I can generate learning objectives for '{course_name}'. Would you like me to create them?",
        'session_plan_generate_offer': "I can generate a session plan for '{topic}' including discussion prompts and a case study. Would you like me to create it?",
        'syllabus_dictate': "Okay, please dictate the syllabus now. Say what you'd like to include.",
        'objectives_dictate': "Okay, please dictate the learning objectives now.",
        'syllabus_generate_confirm': "Would you like me to generate a syllabus for you? Say 'yes' to generate, 'no' to dictate it yourself, or 'skip' to move on.",
        'objectives_generate_confirm': "Would you like me to generate learning objectives? Say 'yes' to generate, 'no' to dictate, or 'skip' to move on.",
        'syllabus_saved': "Syllabus saved! {next_prompt}",
        'syllabus_saved_objectives_offer': "Syllabus saved! Now for learning objectives. Would you like me to generate learning objectives based on the syllabus?",
        'syllabus_saved_ready': "Syllabus saved! The form is ready to submit. Would you like me to create the course?",
        'objectives_saved': "Objectives saved! {next_prompt}",
        'objectives_saved_ready': "Objectives saved! The course is ready to create. Would you like me to create it now and generate session plans?",
        'syllabus_edit': "The syllabus is in the form. You can edit it manually, or dictate a new one. Say 'done' when finished or 'skip' to move on.",
        'post_cancelled': "Post cancelled. What else can I help you with?",
        'poll_confirm': "Would you like to create a poll? Say yes or no.",
        'poll_cancelled': "Poll creation cancelled. What else can I help you with?",
        'cancelling_selection': "Cancelling selection. {nav_message}",
        'cancelling_form': "Cancelling form. {nav_message}",
        'cancelling_post': "Cancelling post. {nav_message}",
        'cancelling_poll': "Cancelling poll creation. {nav_message}",
        'cancelling_case': "Cancelling case creation. {nav_message}",
        'submitting_form': "Submitting the form. Clicking {button}.",
    },
    'es': {
        # Navigation
        'navigate_to': "Llevandote a {destination} ahora.",
        'navigate_open': "Abriendo {destination} para ti.",
        'switch_tab': "Cambiando a la pestana {tab}.",
        'switching_tabs': "Cambiando de pestana.",

        # Courses
        'no_courses': "Aun no tienes cursos. Te gustaria que te ayude a crear uno?",
        'one_course': "Tienes un curso: {name}. Te gustaria que lo abra?",
        'few_courses': "Tienes {count} cursos: {names}. Con cual te gustaria trabajar?",
        'many_courses': "Tienes {count} cursos, incluyendo {names}, y {more} mas. Te gustaria ver todos?",
        'create_course': "Abriendo creacion de curso. Dime el titulo del curso, o puedo ayudarte paso a paso.",
        'select_course': "Abriendo {name}. Que te gustaria hacer con el?",
        'selecting_course': "Seleccionando el curso para ti.",

        # Sessions
        'no_sessions': "No se encontraron sesiones. Te gustaria crear una nueva?",
        'live_sessions': "Hay {count} sesion{plural} en vivo: {names}. Te gustaria unirte a una?",
        'sessions_none_live': "Tienes {count} sesiones. Ninguna esta en vivo ahora. Te gustaria iniciar una?",
        'create_session': "Abriendo creacion de sesion. Cual sera el tema de esta sesion?",
        'select_session': "Abriendo {name}. Estado: {status}.",
        'selecting_session': "Seleccionando la sesion para ti.",
        'session_live': "La sesion esta en vivo! Los estudiantes pueden unirse y participar.",
        'session_ended': "La sesion ha terminado. Te gustaria que genere un reporte?",
        'session_draft': "La sesion se ha establecido como borrador. Puedes editarla o ponerla en vivo cuando estes listo.",
        'session_completed': "La sesion ha sido marcada como completada.",
        'session_scheduled': "La sesion ha sido programada.",

        # Actions
        'click_button': "Haciendo clic en {button}.",
        'clicking_button': "Haciendo clic en el boton.",
        'opening_materials': "Abriendo los materiales del curso. Puedes ver y descargar archivos aqui.",

        # Confirmations
        'confirm_proceed': "Te gustaria que proceda?",
        'confirm_yes': "Listo!",
        'confirm_cancel': "Esta bien, cancelado.",

        # Errors
        'error_generic': "Lo siento, hubo un problema: {reason}",
        'error_not_found': "No pude encontrar eso. Por favor intenta de nuevo.",

        # Greetings
        'greeting': "Hola! Como puedo ayudarte?",
        'ready': "Estoy listo para ayudar. Que te gustaria hacer?",

        # Dropdown
        'dropdown_options': "Tus opciones son: {options}. Cual te gustaria seleccionar?",
        'dropdown_selected': "Seleccionado {name}.",

        # Forum
        'forum_post_offer': "Te gustaria que te ayude a publicar algo?",
        'forum_posting': "Publicando en el foro.",

        # Polls
        'poll_create_offer': "Te gustaria crear una encuesta?",
        'poll_creating': "Creando la encuesta.",

        # AI Features
        'generating_summary': "Generando un resumen de la discusion.",
        'generating_questions': "Generando preguntas del cuestionario de la discusion.",
        'creating_groups': "Creando grupos de estudiantes con IA.",

        # Form filling
        'form_cancelled': "Formulario cancelado. Que te gustaria hacer?",
        'form_complete': "He completado todos los campos requeridos. Te gustaria que envie el formulario?",
        'confirm_yes_no': "Por favor di 'si' para confirmar o 'no' para cancelar.",
        'got_it_continue': "Entendido! {prompt}",
        'skipped_syllabus_offer': "Saltado. Ahora el programa de estudios. Te gustaria que genere uno, o prefieres dictarlo? Tambien puedes decir 'saltar'.",
        'skipped_objectives_offer': "Saltado. Ahora los objetivos de aprendizaje. Te gustaria que los genere, o prefieres dictarlos? Tambien puedes decir 'saltar'.",
        'skipped_session_plan_offer': "Saltado. Ahora la descripcion de la sesion. Te gustaria que genere un plan de sesion, o prefieres dictarlo?",
        'syllabus_generate_offer': "Puedo generar un programa de estudios para '{course_name}'. Te gustaria que cree uno?",
        'objectives_generate_offer': "Puedo generar objetivos de aprendizaje para '{course_name}'. Te gustaria que los cree?",
        'session_plan_generate_offer': "Puedo generar un plan de sesion para '{topic}' incluyendo temas de discusion y un caso de estudio. Te gustaria que lo cree?",
        'syllabus_dictate': "Bien, por favor dicta el programa de estudios ahora. Di lo que te gustaria incluir.",
        'objectives_dictate': "Bien, por favor dicta los objetivos de aprendizaje ahora.",
        'syllabus_generate_confirm': "Te gustaria que genere un programa de estudios? Di 'si' para generar, 'no' para dictarlo tu mismo, o 'saltar' para continuar.",
        'objectives_generate_confirm': "Te gustaria que genere objetivos de aprendizaje? Di 'si' para generar, 'no' para dictar, o 'saltar' para continuar.",
        'syllabus_saved': "Programa guardado! {next_prompt}",
        'syllabus_saved_objectives_offer': "Programa guardado! Ahora los objetivos de aprendizaje. Te gustaria que genere objetivos basados en el programa?",
        'syllabus_saved_ready': "Programa guardado! El formulario esta listo para enviar. Te gustaria que cree el curso?",
        'objectives_saved': "Objetivos guardados! {next_prompt}",
        'objectives_saved_ready': "Objetivos guardados! El curso esta listo para crear. Te gustaria que lo cree ahora y genere planes de sesion?",
        'syllabus_edit': "El programa esta en el formulario. Puedes editarlo manualmente, o dictar uno nuevo. Di 'listo' cuando termines o 'saltar' para continuar.",
        'post_cancelled': "Publicacion cancelada. En que mas puedo ayudarte?",
        'poll_confirm': "Te gustaria crear una encuesta? Di si o no.",
        'poll_cancelled': "Creacion de encuesta cancelada. En que mas puedo ayudarte?",
        'cancelling_selection': "Cancelando seleccion. {nav_message}",
        'cancelling_form': "Cancelando formulario. {nav_message}",
        'cancelling_post': "Cancelando publicacion. {nav_message}",
        'cancelling_poll': "Cancelando creacion de encuesta. {nav_message}",
        'cancelling_case': "Cancelando creacion de caso. {nav_message}",
        'submitting_form': "Enviando el formulario. Haciendo clic en {button}.",
    }
}

# Page names in both languages
PAGE_NAMES = {
    'en': {
        '/courses': 'courses',
        '/sessions': 'sessions',
        '/forum': 'forum',
        '/console': 'instructor console',
        '/reports': 'reports',
        '/integrations': 'integrations',
        '/platform-guide': 'introduction',
        '/dashboard': 'dashboard',
    },
    'es': {
        '/courses': 'cursos',
        '/sessions': 'sesiones',
        '/forum': 'foro',
        '/console': 'consola del instructor',
        '/reports': 'reportes',
        '/integrations': 'integraciones',
        '/platform-guide': 'introduccion',
        '/dashboard': 'panel principal',
    }
}

# Status translations
STATUS_NAMES = {
    'en': {
        'draft': 'draft',
        'live': 'live',
        'completed': 'completed',
        'scheduled': 'scheduled',
    },
    'es': {
        'draft': 'borrador',
        'live': 'en vivo',
        'completed': 'completada',
        'scheduled': 'programada',
    }
}


def get_response(key: str, language: str = 'en', **kwargs) -> str:
    """Get a response template in the specified language with formatting.

    Args:
        key: The template key to look up
        language: Language code ('en' or 'es')
        **kwargs: Format arguments for the template

    Returns:
        Formatted response string
    """
    lang = language if language in RESPONSE_TEMPLATES else 'en'
    templates = RESPONSE_TEMPLATES[lang]

    if key not in templates:
        # Fall back to English if key not found in target language
        templates = RESPONSE_TEMPLATES['en']

    if key not in templates:
        return kwargs.get('default', f"[{key}]")

    try:
        return templates[key].format(**kwargs)
    except KeyError:
        # If formatting fails, return the raw template
        return templates[key]


def get_page_name(path: str, language: str = 'en') -> str:
    """Get the localized page name for a path.

    Args:
        path: URL path (e.g., '/courses')
        language: Language code ('en' or 'es')

    Returns:
        Localized page name
    """
    lang = language if language in PAGE_NAMES else 'en'
    # Extract base path (e.g., '/courses/123' -> '/courses')
    base_path = '/' + path.strip('/').split('/')[0] if path else '/dashboard'
    return PAGE_NAMES[lang].get(base_path, path)


def get_status_name(status: str, language: str = 'en') -> str:
    """Get the localized status name.

    Args:
        status: Status key (e.g., 'live', 'draft')
        language: Language code ('en' or 'es')

    Returns:
        Localized status name
    """
    lang = language if language in STATUS_NAMES else 'en'
    return STATUS_NAMES[lang].get(status, status)
