from typing import Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from app.schemas.air_quality import NormalizedAirObservation
from app.schemas.plan import DailyPlanResponse, HouseholdProfile
from app.services.air_quality.data_manager import data_manager
from app.services.ai.ai_manager import ai_manager
from app.services.safety_engine import safety_engine

router = APIRouter()


class GeneratePlanRequest(BaseModel):
    city: str
    station_id: Optional[str] = None
    profile: Optional[HouseholdProfile] = None


@router.post("/generate", response_model=DailyPlanResponse)
async def generate_plan(request: GeneratePlanRequest):
    """
    Generates a personalized daily routine plan:
    1. Fetches verified air quality telemetry (3-Tier Ingestion).
    2. Runs deterministic CPCB / MoHFW safety rules engine.
    3. Invokes Groq Llama 3 (Primary) with automatic Gemini fallback.
    4. Applies post-AI validation and public-health guardrails.
    """
    profile = request.profile or HouseholdProfile(city=request.city)
    
    # 1. Fetch verified environmental data
    observation = await data_manager.get_air_quality(
        city_identifier=request.city,
        station_id=request.station_id
    )

    # 2. Evaluate deterministic safety rules
    safety_guidance = safety_engine.evaluate(observation, profile)

    # 3. Generate plan via AI with automatic fallback and guardrails
    plan_response = await ai_manager.generate_plan(observation, profile, safety_guidance)

    return plan_response
