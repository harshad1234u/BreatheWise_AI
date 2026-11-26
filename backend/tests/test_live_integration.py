import os
import pytest
from fastapi.testclient import TestClient

from app.main import app

RUN_LIVE = os.getenv("RUN_LIVE_INTEGRATION_TESTS") == "1"


@pytest.mark.skipif(not RUN_LIVE, reason="Live integration tests are opt-in via RUN_LIVE_INTEGRATION_TESTS=1")
def test_live_air_quality_and_air_window_smoke():
    client = TestClient(app)
    r_aq = client.get("/api/v1/air-quality?city=delhi")
    assert r_aq.status_code == 200
    assert r_aq.json()["city"] == "Delhi NCR"

    r_aw = client.get("/api/v1/air-window?city=delhi&activity=running")
    assert r_aw.status_code == 200
    assert r_aw.json()["status"] in ["available", "insufficient_data"]
