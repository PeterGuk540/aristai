# Import individual route modules
from fastapi import APIRouter
from api.core.config import get_settings
from api.api.routes import users, courses, sessions, posts, polls, reports, enrollments, voice, debug

from .voice_converse_router import router as voice_converse_router
try:
    from .voice_synthesize import router as voice_synthesize_router
    print("✅ voice_synthesize router imported successfully")
except ImportError as e:
    print(f"❌ Error importing voice_synthesize: {e}")
    # Fallback to basic voice router only
    voice_synthesize_router = None

from mcp_server.router_integration import include_voice_loop_router

api_router = APIRouter()

# Import individual route modules
api_router.include_router(users.router, prefix="/users", tags=["users"])
api_router.include_router(courses.router, prefix="/courses", tags=["courses"])
api_router.include_router(sessions.router, prefix="/sessions", tags=["sessions"])
api_router.include_router(posts.router, prefix="/posts", tags=["posts"])
api_router.include_router(polls.router, prefix="/polls", tags=["polls"])
api_router.include_router(reports.router, prefix="/reports", tags=["reports"])
api_router.include_router(enrollments.router, prefix="/enrollments", tags=["enrollments"])
api_router.include_router(voice.router, prefix="/voice", tags=["voice"])
api_router.include_router(voice_converse_router)
api_router.include_router(voice_synthesize_router)
include_voice_loop_router(api_router)

# Debug routes only available when DEBUG=true
settings = get_settings()
if settings.debug:
    api_router.include_router(debug.router, prefix="/debug", tags=["debug"])

# Include all route modules
api_router.include_router(users.router, prefix="/users", tags=["users"])
api_router.include_router(courses.router, prefix="/courses", tags=["courses"])
api_router.include_router(sessions.router, prefix="/sessions", tags=["sessions"])
api_router.include_router(posts.router, prefix="/posts", tags=["posts"])
api_router.include_router(polls.router, prefix="/polls", tags=["polls"])
api_router.include_router(reports.router, prefix="/reports", tags=["reports"])
api_router.include_router(enrollments.router, prefix="/enrollments", tags=["enrollments"])
api_router.include_router(voice.router, prefix="/voice", tags=["voice"])
api_router.include_router(voice_converse_router)
api_router.include_router(voice_synthesize_router)
include_voice_loop_router(api_router)

# Debug routes only available when DEBUG=true
settings = get_settings()
if settings.debug:
    from api.api.routes import debug
    api_router.include_router(debug.router, prefix="/debug", tags=["debug"])
