"""End-to-end smoke tests for the current MVP chain."""

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def fake_llm(monkeypatch):
    """Stub the LLM client so smoke tests stay deterministic."""
    captured_calls: list[dict] = []

    class FakeClient:
        async def chat_completion(self, *args, **kwargs):
            captured_calls.append(kwargs)
            return {
                "choices": [
                    {
                        "message": {
                            "content": "这是来自 smoke 测试的模型回复。",
                        }
                    }
                ]
            }

    monkeypatch.setattr("app.agents.orchestrator.get_llm_client", lambda: FakeClient())
    return captured_calls


def test_mvp_smoke_flow(client: TestClient, fake_llm) -> None:
    """The MVP chain should support health, FAQ chat, tool chat, and tool log lookup."""
    upload_response = client.post(
        "/api/v1/kb/upload",
        json={
            "title": "退款规则",
            "content": "平台支持七天无理由退款，商品需要保持完好。",
            "source_type": "text",
        },
    )
    assert upload_response.status_code == 200

    faq_response = client.post(
        "/api/v1/chat/",
        json={"message": "请问退款规则是什么？", "session_id": "sess_smoke_faq"},
    )
    assert faq_response.status_code == 200
    faq_payload = faq_response.json()
    assert faq_payload["data"]["route"] == "knowledge_qa"
    assert faq_payload["data"]["answer_source"] == "rag_llm"

    order_response = client.post(
        "/api/v1/chat/",
        json={
            "message": "帮我查一下订单 ORD2026043001 的状态",
            "user_id": "u_order_001",
            "session_id": "sess_smoke_tool",
        },
    )
    assert order_response.status_code == 200
    order_payload = order_response.json()
    assert order_payload["data"]["route"] == "order_query"
    assert order_payload["data"]["answer_source"] == "tool"

    logistics_response = client.post(
        "/api/v1/chat/",
        json={
            "message": "帮我查一下物流 SF2026043001 到哪了",
            "user_id": "u_order_001",
            "session_id": "sess_smoke_tool",
        },
    )
    assert logistics_response.status_code == 200
    logistics_payload = logistics_response.json()
    assert logistics_payload["data"]["route"] == "logistics_query"
    assert logistics_payload["data"]["answer_source"] == "tool"

    logs_response = client.get("/api/v1/tools/logs?session_id=sess_smoke_tool&page=1&page_size=10")
    assert logs_response.status_code == 200
    logs_payload = logs_response.json()
    assert logs_payload["data"]["pagination"]["total"] == 2
    assert logs_payload["data"]["items"][0]["tool_name"] == "logistics_query"
    assert logs_payload["data"]["items"][1]["tool_name"] == "order_query"
