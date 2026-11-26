import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
import httpx
import pytest
from fastapi.testclient import TestClient

from app.core.http_client import get_shared_http_client
from app.main import app
from app.schemas.air_quality import NormalizedAirObservation
from app.schemas.plan import HouseholdProfile
from app.services.ai.gemini_provider import GeminiProvider
from app.services.ai.groq_provider import GroqProvider
from app.services.air_quality.air_window import AirWindowService
from app.services.air_quality.map_service import MapService
from app.services.air_quality.open_meteo_provider import OpenMeteoProvider
from app.services.air_quality.openaq_provider import OpenAQProvider
from app.services.air_quality.waqi_provider import WAQIProvider
from app.services.safety_engine import safety_engine


def test_fastapi_lifespan_initializes_and_closes_shared_http_client():
    """Tests 1, 3 & 7: App lifespan starts shared AsyncClient and closes it cleanly on shutdown."""
    assert get_shared_http_client() is None

    with TestClient(app) as client:
        resp = client.get("/health")
        assert resp.status_code == 200
        shared_client = getattr(app.state, "http_client", None)
        assert isinstance(shared_client, httpx.AsyncClient)
        assert not shared_client.is_closed

    assert shared_client.is_closed
    assert getattr(app.state, "http_client", None) is None
    assert get_shared_http_client() is None


@pytest.mark.asyncio
async def test_shared_http_client_reused_across_providers_and_isolated_on_failures():
    """Tests 2, 4, 5, 6 & 7: Multiple providers reuse one open pooled client during lifespan."""
    from datetime import datetime, timezone

    async with app.router.lifespan_context(app):
        shared = get_shared_http_client()
        assert shared is not None and not shared.is_closed

        ok_waqi = MagicMock()
        ok_waqi.status_code = 200
        ok_waqi.json.return_value = {
            "status": "ok",
            "data": {
                "aqi": 85,
                "city": {"name": "Delhi"},
                "time": {"iso": datetime.now(timezone.utc).isoformat()},
                "iaqi": {"pm25": {"v": 85}},
            },
        }
        err_resp = MagicMock()
        err_resp.status_code = 502

        # Spy on shared.get and shared.post while asserting no new AsyncClient is created per request
        with patch.object(shared, "get", new=AsyncMock(side_effect=[ok_waqi, err_resp])) as spy_get, \
             patch.object(httpx, "AsyncClient") as spy_ctor:
            waqi = WAQIProvider(api_token="tok")
            meteo = OpenMeteoProvider()

            r1, r2 = await asyncio.gather(
                waqi.get_air_quality("Delhi NCR", 28.6, 77.2),
                meteo.get_air_quality("Delhi NCR", 28.6, 77.2),
            )

        assert spy_ctor.call_count == 0
        assert spy_get.call_count == 2
        assert r1 is not None and r2 is None
        assert not shared.is_closed

        # AI providers also reuse shared client without leaking on failure
        obs = r1
        prof = HouseholdProfile(city="delhi", persona="general")
        safety = safety_engine.evaluate(obs, prof)

        bad_ai = MagicMock()
        bad_ai.status_code = 500
        with patch.object(shared, "post", new=AsyncMock(return_value=bad_ai)) as spy_post, \
             patch.object(httpx, "AsyncClient") as spy_ctor_ai:
            groq = GroqProvider(api_key="g_key")
            gemini = GeminiProvider(api_key="gem_key")
            assert await groq.generate_plan_json(obs, prof, safety) is None
            assert await gemini.generate_plan_json(obs, prof, safety) is None

        assert spy_ctor_ai.call_count == 0
        assert spy_post.call_count == 2
        assert not shared.is_closed

        # F-16: OpenAQProvider, MapService, and AirWindowService also reuse shared client
        err_service_resp = MagicMock()
        err_service_resp.status_code = 502
        with patch.object(shared, "get", new=AsyncMock(return_value=err_service_resp)) as spy_rest_get, \
             patch.object(httpx, "AsyncClient") as spy_ctor_rest:
            openaq = OpenAQProvider(api_key="oaq_key")
            map_svc = MapService()
            air_window_svc = AirWindowService()

            oaq_res = await openaq.get_air_quality("Delhi NCR", 28.6, 77.2)
            map_res = await map_svc.get_city_pollutant_map("delhi", "pm25")
            aw_res = await air_window_svc.calculate_best_window("delhi", "running")

        assert oaq_res is None
        assert map_res.selected_city == "Delhi NCR"
        assert aw_res.city == "Delhi NCR"
        assert spy_ctor_rest.call_count == 0
        assert spy_rest_get.call_count >= 3
        assert not shared.is_closed

    assert shared.is_closed
    assert get_shared_http_client() is None


@pytest.mark.asyncio
async def test_closed_injected_client_is_never_used():
    """Test 7: A closed injected client never receives requests."""
    closed_client = httpx.AsyncClient()
    await closed_client.aclose()
    assert closed_client.is_closed

    provider = OpenMeteoProvider(http_client=closed_client)
    fallback_resp = MagicMock()
    fallback_resp.status_code = 500

    with patch("app.services.air_quality.open_meteo_provider.httpx.AsyncClient") as mock_ctor:
        ephemeral = AsyncMock()
        ephemeral.get.return_value = fallback_resp
        mock_ctor.return_value.__aenter__.return_value = ephemeral
        res = await provider.get_air_quality("Delhi NCR", 28.6, 77.2)

    assert res is None
    assert mock_ctor.call_count == 1
