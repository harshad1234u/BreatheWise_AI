import logging
import uuid
from datetime import datetime, timezone
from typing import Optional
from app.schemas.air_quality import NormalizedAirObservation
from app.schemas.plan import (
    DailyPlanResponse,
    HouseholdProfile,
    PlanRecommendation,
    StructuredSafetyGuidance,
)
from app.services.ai.gemini_provider import GeminiProvider
from app.services.ai.groq_provider import GroqProvider
from app.services.ai.validator import (
    generate_deterministic_fallback_plan,
    validate_and_guardrail_ai_plan,
)

logger = logging.getLogger(__name__)

DISCLAIMER_TEXT = (
    "Advisory lifestyle guidance based on available atmospheric telemetry and CPCB/MoHFW public-health guidelines. "
    "BreatheWise AI is not a medical device and does not substitute clinical diagnosis or emergency public health directives."
)


class AIManager:
    """
    Orchestrates the Dual-Provider GenAI Engine:
    Groq (Primary) -> Google Gemini (Backup) -> Deterministic Rule Generator (Offline Safety Fallback).
    Applies strict post-AI validation and public-health guardrails to every response.
    """

    def __init__(
        self,
        groq_provider: Optional[GroqProvider] = None,
        gemini_provider: Optional[GeminiProvider] = None
    ):
        self.groq_provider = groq_provider or GroqProvider()
        self.gemini_provider = gemini_provider or GeminiProvider()

    async def generate_plan(
        self,
        observation: NormalizedAirObservation,
        profile: HouseholdProfile,
        safety_guidance: StructuredSafetyGuidance,
        air_window_context: Optional[dict] = None,
    ) -> DailyPlanResponse:
        plan_id = f"plan_{uuid.uuid4().hex[:12]}"
        now = datetime.now(timezone.utc)
        provider_used = "groq"
        is_fallback = False
        final_dict = None

        # 1. Attempt Primary: Groq API
        logger.info("Attempting primary AI inference with Groq...")
        groq_raw = await self.groq_provider.generate_plan_json(
            observation, profile, safety_guidance, air_window_context=air_window_context
        )
        if groq_raw:
            validated = validate_and_guardrail_ai_plan(groq_raw, observation, profile, safety_guidance)
            if validated:
                final_dict = validated
                provider_used = "groq"
                is_fallback = False
                logger.info("Groq inference succeeded and passed all guardrails.")

        # 2. If Groq failed, attempt Backup: Google Gemini API
        if not final_dict:
            logger.warning("Groq unavailable or returned invalid schema. Attempting backup: Gemini...")
            gemini_raw = await self.gemini_provider.generate_plan_json(
                observation, profile, safety_guidance, air_window_context=air_window_context
            )
            if gemini_raw:
                validated = validate_and_guardrail_ai_plan(gemini_raw, observation, profile, safety_guidance)
                if validated:
                    final_dict = validated
                    provider_used = "gemini"
                    is_fallback = True
                    logger.info("Gemini backup inference succeeded and passed all guardrails.")

        # 3. If both failed, use Deterministic Pure-Python Fallback
        if not final_dict:
            logger.warning("All AI providers failed or unconfigured. Triggering deterministic safety fallback.")
            final_dict = generate_deterministic_fallback_plan(
                observation, profile, safety_guidance, air_window_context=air_window_context
            )
            provider_used = "deterministic_fallback"
            is_fallback = True

        # Convert dictionary to strongly-typed DailyPlanResponse
        morning_recs = [PlanRecommendation(**r) for r in final_dict["morning"]]
        afternoon_recs = [PlanRecommendation(**r) for r in final_dict["afternoon"]]
        evening_recs = [PlanRecommendation(**r) for r in final_dict["evening"]]

        return DailyPlanResponse(
            plan_id=plan_id,
            generated_at=now,
            ai_provider_used=provider_used,
            is_fallback=is_fallback,
            data_provenance=observation,
            household_profile=profile,
            safety_guidance=safety_guidance,
            morning=morning_recs,
            afternoon=afternoon_recs,
            evening=evening_recs,
            indoor_air_suggestions=final_dict["indoor_air_suggestions"],
            sustainable_alternatives=final_dict["sustainable_alternatives"],
            disclaimer=DISCLAIMER_TEXT,
        )


ai_manager = AIManager()
