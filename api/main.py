from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from api.api.router import api_router
from api.core.config import get_settings

settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    description="AI-powered platform for synchronous classroom discussions",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS configuration for Vercel frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",  # Local Next.js development
        "https://localhost:3000",
        "https://*.vercel.app",  # Vercel preview deployments
        # Add your production Vercel domain here, e.g.:
        # "https://aristai.vercel.app",
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
