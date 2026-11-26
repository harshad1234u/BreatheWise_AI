import logging
from typing import Optional
from fastapi import APIRouter, Request
from pydantic import BaseModel
from app.core.config import settings
from app.core.rate_limiter import InMemorySlidingWindowRateLimiter, enforce_plan_rate_limit
from app.schemas.plan import DailyPlanResponse, HouseholdProfile
from app.services.air_quality.air_window import air_window_service
from app.services.air_quality.data_manager import data_manager
from app.services.ai.ai_manager import ai_manager
from app.services.safety_engine import safety_engine

logger = logging.getLogger(__name__)
router = APIRouter()
plan_rate_limiter = InMemorySlidingWindowRateLimiter(
    max_requests=settings.RATE_LIMIT_PLAN_REQUESTS,
    window_seconds=settings.RATE_LIMIT_PLAN_WINDOW_SECONDS,
)


class GeneratePlanRequest(BaseModel):
    city: str
    station_id: Optional[str] = None
    profile: Optional[HouseholdProfile] = None


@router.post("/generate", response_model=DailyPlanResponse)
async def generate_plan(payload: GeneratePlanRequest, request: Request):
    """
    Generates a personalized daily routine plan:
    0. Enforces per-IP sliding-window rate limit (HTTP 429 on abuse).
    1. Fetches verified air quality telemetry (3-Tier Ingestion).
    2. Runs deterministic CPCB / MoHFW safety rules engine.
    3. Retrieves atmospheric CAMS Best Air Window forecast context.
    4. Invokes Groq Llama 3 (Primary) with automatic Gemini fallback.
    5. Applies post-AI validation and public-health guardrails.
    """
    enforce_plan_rate_limit(request, plan_rate_limiter)
    profile = payload.profile or HouseholdProfile(city=payload.city)
    
    # 1. Fetch verified environmental data
    observation = await data_manager.get_air_quality(
        city_identifier=payload.city,
        station_id=payload.station_id
    )

    # 2. Evaluate deterministic safety rules
    safety_guidance = safety_engine.evaluate(observation, profile)

    # 3. Retrieve hourly forecast / Best Air Window context
    air_window_context = None
    try:
        is_vuln = profile.has_respiratory_sensitivity or profile.has_cardiovascular_sensitivity
        air_window_resp = await air_window_service.calculate_best_window(
            city_identifier=payload.city,
            activity="general_outdoor",
            is_vulnerable=is_vuln,
        )
        if air_window_resp.best_window:
            air_window_context = {
                "start_time": air_window_resp.best_window.start_time,
                "end_time": air_window_resp.best_window.end_time,
                "average_comparative_score": air_window_resp.best_window.average_comparative_score,
                "score_label": air_window_resp.best_window.score_label,
                "dominant_pollutant": air_window_resp.best_window.dominant_pollutant,
                "strenuous_outdoor_allowed": air_window_resp.best_window.strenuous_outdoor_allowed,
                "activity_suitability": air_window_resp.best_window.activity_suitability,
            }
    except Exception as e:
        logger.warning(f"Could not retrieve forecast window context for planner: {e}")

    # 4. Generate plan via AI with automatic fallback, guardrails, and forecast alignment
    plan_response = await ai_manager.generate_plan(
        observation, profile, safety_guidance, air_window_context=air_window_context
    )

    return plan_response
