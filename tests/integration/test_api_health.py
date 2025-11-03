"""
Integration tests - API health endpoint.
This test expects `src.main.app` to exist and expose a /health endpoint.
"""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_health_endpoint(client: AsyncClient):
    """Ensure that the /health endpoint returns 200 and basic payload."""
    response = await client.get("/health")
    assert response.status_code == 200
    payload = response.json()
    # Basic shape checks
    assert "status" in payload
    assert payload["status"] == "ok"
