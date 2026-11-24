import pytest
from httpx import ASGITransport, AsyncClient
from app.main import app


@pytest.mark.asyncio
async def test_generate_plan_endpoint():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        payload = {
            "city": "delhi",
            "profile": {
                "display_name": "Test Delhi Family",
                "city": "delhi",
                "persona": "parent",
                "age_groups": ["child", "adult"],
                "has_respiratory_sensitivity": True,
                "commute_mode": "two_wheeler",
                "has_air_purifier": True,
                "kitchen_ventilation_type": "exhaust_fan"
            }
        }
        response = await client.post("/api/v1/plan/generate", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert "plan_id" in data
        assert "ai_provider_used" in data
        assert data["ai_provider_used"] in ["groq", "gemini", "deterministic_fallback"]
        assert "morning" in data
        assert "afternoon" in data
        assert "evening" in data
        assert "indoor_air_suggestions" in data
        assert "sustainable_alternatives" in data
        assert "safety_guidance" in data
        assert data["data_provenance"]["city"] == "Delhi NCR"
