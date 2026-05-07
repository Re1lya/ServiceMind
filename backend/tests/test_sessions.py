"""Session endpoint tests."""

from fastapi.testclient import TestClient

from app.repositories.message_repository import MessageRepository
from app.repositories.session_repository import SessionRepository


def test_get_session_detail_returns_transcript(client: TestClient) -> None:
    """Session detail should include session metadata and ordered messages."""
    session_local = client.app.state.testing_session_local
    with session_local() as db:
        session = SessionRepository(db).create(user_id="u_001", channel="web")
        for idx in range(3):
            MessageRepository(db).create(
                session_id=session.session_id,
                role="user" if idx % 2 == 0 else "assistant",
                content=f"message_{idx}",
                trace_id="trace_test_1",
            )

    response = client.get(f"/api/v1/sessions/{session.session_id}?page=1&page_size=2")

    assert response.status_code == 200
    payload = response.json()
    assert payload["code"] == 0
    assert payload["data"]["session_id"] == session.session_id
    assert payload["data"]["user_id"] == "u_001"
    assert len(payload["data"]["messages"]) == 2
    assert payload["data"]["pagination"]["page"] == 1
    assert payload["data"]["pagination"]["page_size"] == 2
    assert payload["data"]["pagination"]["total"] == 3
    assert payload["data"]["pagination"]["has_more"] is True
    assert payload["data"]["messages"][0]["role"] == "user"
    assert payload["data"]["messages"][1]["role"] == "assistant"


def test_get_session_detail_returns_404_for_missing_session(client: TestClient) -> None:
    """Missing sessions should be normalized into the shared error envelope."""
    response = client.get("/api/v1/sessions/sess_missing")

    assert response.status_code == 404
    payload = response.json()
    assert payload["code"] == 40404
    assert payload["message"] == "session not found"
    assert payload["data"]["detail"]["session_id"] == "sess_missing"
    assert payload["data"]["trace_id"]
