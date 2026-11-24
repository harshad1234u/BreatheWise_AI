from datetime import datetime, timezone
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.api.endpoints.air_quality import router as air_quality_router
from app.api.endpoints.plan import router as plan_router
from app.api.endpoints.map import router as map_router

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="Urban Air Quality Assistant API with deterministic CPCB calculations and multi-tier telemetry."
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS or ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include Routers
app.include_router(air_quality_router, prefix="/api/v1", tags=["Air Quality"])
app.include_router(plan_router, prefix="/api/v1/plan", tags=["Daily Planner"])
app.include_router(map_router, prefix="/api/v1/map", tags=["Pollutant Map"])


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
