import json
import logging
from typing import Any, Dict, Optional
import httpx
from app.core.config import settings
from app.core.http_client import acquire_http_client
from app.schemas.air_quality import NormalizedAirObservation
from app.schemas.plan import HouseholdProfile, StructuredSafetyGuidance
from app.services.ai.base import AIProvider
from app.services.ai.prompt_builder import build_system_prompt, build_user_prompt

logger = logging.getLogger(__name__)


class GroqProvider(AIProvider):
    """
    Primary AI Provider: Groq Cloud API.
    Provides ultra-low latency inference using configured Llama 3 models.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model_id: Optional[str] = None,
        http_client: Optional[httpx.AsyncClient] = None,
    ):
        self.api_key = api_key or settings.GROQ_API_KEY
        self.model_id = model_id or settings.GROQ_MODEL_ID
        self.endpoint = "https://api.groq.com/openai/v1/chat/completions"
        self.timeout_seconds = 4.5
        self.http_client = http_client

    async def generate_plan_json(
        self,
        observation: NormalizedAirObservation,
        profile: HouseholdProfile,
        safety_guidance: StructuredSafetyGuidance,
        air_window_context: Optional[Dict[str, Any]] = None,
    ) -> Optional[Dict[str, Any]]:
        if not self.api_key:
            logger.warning("Groq API key not configured. Yielding to backup provider.")
            return None

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        payload = {
            "model": self.model_id,
            "messages": [
                {"role": "system", "content": build_system_prompt()},
                {"role": "user", "content": build_user_prompt(observation, profile, safety_guidance, air_window_context)},
            ],
            "response_format": {"type": "json_object"},
            "temperature": 0.3,
            "max_tokens": 1500,
        }

        try:
            async with acquire_http_client(
                injected_client=self.http_client,
                timeout=self.timeout_seconds,
                client_factory=httpx.AsyncClient,
            ) as client:
                response = await client.post(
                    self.endpoint, headers=headers, json=payload, timeout=self.timeout_seconds
                )
                
                if response.status_code == 429:
                    logger.warning("Groq rate limit (HTTP 429) hit. Triggering fallback.")
                    return None
                elif response.status_code != 200:
                    logger.warning(f"Groq returned HTTP {response.status_code}. Triggering fallback.")
                    return None

                data = response.json()
                content = data["choices"][0]["message"]["content"].strip()
                if content.startswith("```"):
                    lines = content.splitlines()
                    if lines[0].startswith("```"):
                        lines = lines[1:]
                    if lines and lines[-1].startswith("```"):
                        lines = lines[:-1]
                    content = "\n".join(lines).strip()
                parsed = json.loads(content)
                return parsed

        except httpx.TimeoutException:
            logger.warning(f"Groq request timed out (> {self.timeout_seconds}s). Triggering fallback.")
            return None
        except Exception as e:
            logger.warning(f"Groq inference failed: {type(e).__name__}. Triggering fallback.")
            return None
