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


class GeminiProvider(AIProvider):
    """
    Secondary Backup AI Provider: Google Gemini API.
    Provides robust structured generation when primary Groq fails, times out, or hits 429.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model_id: Optional[str] = None,
        http_client: Optional[httpx.AsyncClient] = None,
    ):
        self.api_key = api_key or settings.GEMINI_API_KEY
        self.model_id = model_id or settings.GEMINI_MODEL_ID
        self.timeout_seconds = 10.0
        self.http_client = http_client

    async def generate_plan_json(
        self,
        observation: NormalizedAirObservation,
        profile: HouseholdProfile,
        safety_guidance: StructuredSafetyGuidance,
        air_window_context: Optional[Dict[str, Any]] = None,
    ) -> Optional[Dict[str, Any]]:
        if not self.api_key:
            logger.warning("Gemini API key not configured. Cannot execute fallback.")
            return None

        endpoint = (
            f"https://generativelanguage.googleapis.com/v1beta/models/{self.model_id}:generateContent"
        )

        headers = {
            "Content-Type": "application/json",
            "x-goog-api-key": self.api_key,
        }

        payload = {
            "systemInstruction": {
                "parts": [{"text": build_system_prompt()}]
            },
            "contents": [
                {
                    "role": "user",
                    "parts": [{"text": build_user_prompt(observation, profile, safety_guidance, air_window_context)}]
                }
            ],
            "generationConfig": {
                "responseMimeType": "application/json",
                "temperature": 0.3,
                "maxOutputTokens": 4096,
                "thinkingConfig": {"thinkingBudget": 0},
            }
        }

        try:
            async with acquire_http_client(
                injected_client=self.http_client,
                timeout=self.timeout_seconds,
                client_factory=httpx.AsyncClient,
            ) as client:
                response = await client.post(
                    endpoint, headers=headers, json=payload, timeout=self.timeout_seconds
                )
                
                if response.status_code != 200:
                    logger.warning(f"Gemini returned HTTP {response.status_code}.")
                    return None

                data = response.json()
                candidates = data.get("candidates", [])
                if not candidates:
                    return None

                parts = candidates[0].get("content", {}).get("parts", [])
                if not parts:
                    return None

                text_content = parts[0].get("text", "").strip()
                if text_content.startswith("```"):
                    lines = text_content.splitlines()
                    if lines[0].startswith("```"):
                        lines = lines[1:]
                    if lines and lines[-1].startswith("```"):
                        lines = lines[:-1]
                    text_content = "\n".join(lines).strip()
                parsed = json.loads(text_content)
                return parsed

        except httpx.TimeoutException:
            logger.warning(f"Gemini request timed out (> {self.timeout_seconds}s).")
            return None
        except Exception as e:
            logger.warning(f"Gemini inference failed: {type(e).__name__}.")
            return None
