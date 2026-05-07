"""Health endpoint tests."""

from fastapi.testclient import TestClient

from app.schemas.common import HealthStatusData


def test_health_returns_standard_response(client: TestClient, monkeypatch) -> None:
    """Health endpoint should return the shared success envelope with component detail."""

    async def fake_build_health_status(*, trace_id: str | None = None) -> HealthStatusData:
        return HealthStatusData(
            app_name="ServiceMind Backend",
            app_env="test",
            status="ok",
            trace_id=trace_id,
            components={
                "api": "ok",
                "database": "ok",
                "redis": "ok",
                "llm": "ok",
            },
        )

    monkeypatch.setattr("app.api.v1.endpoints.health.build_health_status", fake_build_health_status)

    response = client.get("/api/v1/health")

    assert response.status_code == 200
    payload = response.json()

    assert payload["code"] == 0
    assert payload["message"] == "success"
    assert payload["data"]["status"] == "ok"
    assert payload["data"]["app_name"] == "ServiceMind Backend"
    assert payload["data"]["app_env"] == "test"
    assert payload["data"]["components"]["database"] == "ok"
    assert payload["data"]["components"]["redis"] == "ok"
    assert payload["data"]["components"]["llm"] == "ok"
    assert payload["data"]["trace_id"]
    assert response.headers["X-Trace-Id"] == payload["data"]["trace_id"]
