from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from app.schemas.air_quality import NormalizedAirObservation
from app.schemas.plan import HouseholdProfile, StructuredSafetyGuidance


class AIProvider(ABC):
    """Abstract interface that Groq and Gemini AI providers must implement."""

    @abstractmethod
    async def generate_plan_json(
        self,
        observation: NormalizedAirObservation,
        profile: HouseholdProfile,
        safety_guidance: StructuredSafetyGuidance
    ) -> Optional[Dict[str, Any]]:
        """
        Sends structured prompt context to LLM and returns parsed JSON dictionary.
        Returns None if request fails, times out, or returns invalid format.
        """
        pass
