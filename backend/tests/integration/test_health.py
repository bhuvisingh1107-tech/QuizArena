"""Integration tests for API endpoints."""

from fastapi.testclient import TestClient

from app.main import create_app


def test_health_endpoint_returns_healthy():
    app = create_app()
    with TestClient(app) as client:
        response = client.get("/api/v1/health")

    assert response.status_code == 200
    body = response.json()
    assert body["data"]["status"] == "healthy"
    assert body["data"]["database"] == "connected"
    assert "requestId" in body["meta"]
    assert "X-Request-ID" in response.headers
