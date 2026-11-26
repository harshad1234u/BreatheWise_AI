from contextlib import asynccontextmanager
from datetime import datetime, timezone
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.core.http_client import close_http_client, init_http_client
from app.api.endpoints.air_quality import router as air_quality_router
from app.api.endpoints.plan import router as plan_router
from app.api.endpoints.map import router as map_router
from app.api.endpoints.air_window import router as air_window_router


@asynccontextmanager
async def lifespan(application: FastAPI):
    application.state.http_client = await init_http_client()
    try:
        yield
    finally:
        application.state.http_client = None
        await close_http_client()


app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="Urban Air Quality Assistant API with deterministic CPCB calculations and multi-tier telemetry.",
    lifespan=lifespan,
)

# Configure CORS (fail-closed if ALLOWED_ORIGINS is empty; never fall back to '*')
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization"],
)

# Include Routers
app.include_router(air_quality_router, prefix="/api/v1", tags=["Air Quality"])
app.include_router(plan_router, prefix="/api/v1/plan", tags=["Daily Planner"])
app.include_router(map_router, prefix="/api/v1/map", tags=["Pollutant Map"])
app.include_router(air_window_router, prefix="/api/v1", tags=["Best Air Window"])


@app.get("/health", tags=["Health"])
async def health_check():
    """Service health and wake-up ping endpoint."""
    return {
        "status": "ok",
        "service": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "groq_model": settings.GROQ_MODEL_ID,
        "gemini_model": settings.GEMINI_MODEL_ID,
    }
