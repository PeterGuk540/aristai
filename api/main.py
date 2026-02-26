from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from api.api.router import api_router
from api.core.config import get_settings

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan handler for startup and shutdown.

    Handles graceful shutdown of browser instances used for LMS integrations.
    """
    # Startup
    yield
    # Shutdown - close browser instances
    try:
        from api.services.integrations.browser_helper import close_browser
        await close_browser()
    except ImportError:
        pass  # Browser helper not installed
    except Exception:
        pass  # Ignore shutdown errors


app = FastAPI(
    title=settings.app_name,
    description="AI-powered platform for synchronous classroom discussions",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# CORS configuration for Vercel frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",  # Local Next.js development
        "https://localhost:3000",
        "https://*.vercel.app",  # Vercel preview deployments
        "https://forum.aristai.io",  # Production custom domain
        "http://forum.aristai.io",  # HTTP fallback (redirects to HTTPS)
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health", tags=["health"])
def health_check():
    """Health check endpoint."""
    return {"status": "ok"}


# Include API routes
app.include_router(api_router, prefix="/api")
