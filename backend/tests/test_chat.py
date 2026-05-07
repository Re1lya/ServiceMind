"""Chat endpoint tests."""

import httpx
import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def fake_llm(monkeypatch):
    """Stub the LLM client so chat tests stay deterministic."""
    captured_calls: list[dict] = []

    class FakeClient:
        async def chat_completion(self, *args, **kwargs):
            captured_calls.append(kwargs)
            return {
                "choices": [
                    {
                        "message": {
                            "content": "这是来自测试桩的模型回复。",
                        }
                    }
                ]
            }

    monkeypatch.setattr("app.agents.orchestrator.get_llm_client", lambda: FakeClient())
    return captured_calls


def test_chat_creates_session_and_persists_messages(client: TestClient, fake_llm) -> None:
    """Posting a chat message should create a session and store a two-message transcript."""
    response = client.post(
        "/api/v1/chat/",
        json={
            "message": "你好，帮我看看这个功能",
            "user_id": "u_chat_001",
            "channel": "web",
        },
    )

    assert response.status_code == 200
    payload = response.json()

    assert payload["code"] == 0
    assert payload["data"]["session_id"].startswith("sess_")
    assert payload["data"]["reply"]
    assert payload["data"]["route"] == "general_chat"
    assert payload["data"]["answer_source"] == "llm"
    assert payload["data"]["trace_id"]
    assert payload["data"]["user_message_id"].startswith("msg_")
    assert payload["data"]["assistant_message_id"].startswith("msg_")

    session_id = payload["data"]["session_id"]
    session_response = client.get(f"/api/v1/sessions/{session_id}?page=1&page_size=10")
    session_payload = session_response.json()

    assert session_response.status_code == 200
    assert session_payload["data"]["user_id"] == "u_chat_001"
    assert len(session_payload["data"]["messages"]) == 2
    assert session_payload["data"]["messages"][0]["role"] == "user"
    assert session_payload["data"]["messages"][1]["role"] == "assistant"


def test_chat_reuses_existing_session_id(client: TestClient, fake_llm) -> None:
    """Posting with a session_id should append messages to the same session."""
    first = client.post(
        "/api/v1/chat/",
        json={"message": "第一次消息", "session_id": "sess_existing_case"},
    )
    second = client.post(
        "/api/v1/chat/",
        json={"message": "第二次消息", "session_id": "sess_existing_case"},
    )

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["data"]["session_id"] == "sess_existing_case"
    assert second.json()["data"]["session_id"] == "sess_existing_case"
    assert first.json()["data"]["answer_source"] == "llm"
    assert second.json()["data"]["answer_source"] == "llm"

    session_response = client.get("/api/v1/sessions/sess_existing_case?page=1&page_size=10")
    session_payload = session_response.json()

    assert session_response.status_code == 200
    assert session_payload["data"]["pagination"]["total"] == 4
    assert session_payload["data"]["messages"][0]["content"] == "第一次消息"
    assert session_payload["data"]["messages"][2]["content"] == "第二次消息"


def test_chat_passes_recent_context_to_llm(client: TestClient, fake_llm) -> None:
    """A follow-up turn should include recent transcript context in the LLM request."""
    first = client.post(
        "/api/v1/chat/",
        json={"message": "第一轮：我想了解退款规则", "session_id": "sess_context_case"},
    )
    second = client.post(
        "/api/v1/chat/",
        json={"message": "第二轮：那发票怎么开", "session_id": "sess_context_case"},
    )

    assert first.status_code == 200
    assert second.status_code == 200
    assert len(fake_llm) >= 2

    second_call_messages = fake_llm[-1]["messages"]
    assert second_call_messages[1]["role"] == "user"
    assert second_call_messages[1]["content"] == "第一轮：我想了解退款规则"
    assert second_call_messages[2]["role"] == "assistant"
    assert second_call_messages[3]["role"] == "user"
    assert second_call_messages[3]["content"] == "第二轮：那发票怎么开"


def test_chat_rejects_blank_messages(client: TestClient, fake_llm) -> None:
    """Blank chat requests should fail at request validation."""
    response = client.post("/api/v1/chat/", json={"message": "   "})

    assert response.status_code == 422
    payload = response.json()
    assert payload["code"] == 422
    assert payload["message"] == "request validation failed"
    assert payload["data"]["trace_id"]


def test_chat_falls_back_when_llm_fails(client: TestClient, monkeypatch) -> None:
    """General chat should degrade gracefully when the upstream model call fails."""

    class FailingClient:
        async def chat_completion(self, *args, **kwargs):
            raise httpx.ConnectError("llm unavailable")

    monkeypatch.setattr("app.agents.orchestrator.get_llm_client", lambda: FailingClient())

    response = client.post("/api/v1/chat/", json={"message": "你好，简单介绍一下你自己"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["data"]["route"] == "general_chat"
    assert payload["data"]["answer_source"] == "fallback"
    assert payload["data"]["reply"]


def test_chat_uses_knowledge_hits_for_faq_queries(client: TestClient, fake_llm) -> None:
    """FAQ-style questions should inject matched knowledge into the LLM context."""
    upload_response = client.post(
        "/api/v1/kb/upload",
        json={
            "title": "退款规则",
            "content": "平台支持七天无理由退款，商品需要保持完好。",
        },
    )
    assert upload_response.status_code == 200

    response = client.post(
        "/api/v1/chat/",
        json={"message": "请问退款规则是什么？", "session_id": "sess_kb_case"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["data"]["route"] == "knowledge_qa"
    assert payload["data"]["answer_source"] == "rag_llm"
    assert payload["data"]["knowledge_sources"][0]["title"] == "退款规则"
    assert "七天无理由退款" in payload["data"]["knowledge_sources"][0]["snippet"]

    llm_messages = fake_llm[-1]["messages"]
    assert llm_messages[1]["role"] == "system"
    assert "退款规则" in llm_messages[1]["content"]
    assert "只能基于下方【知识库来源】回答" in llm_messages[1]["content"]
    assert "不要输出 <think>" in llm_messages[1]["content"]


def test_chat_strips_qwen_thinking_blocks(client: TestClient, monkeypatch) -> None:
    """Local thinking-model output should not expose internal reasoning to users."""

    class ThinkingClient:
        async def chat_completion(self, *args, **kwargs):
            return {
                "choices": [
                    {
                        "message": {
                            "content": "<think>先分析知识库。</think>根据《退款规则》，平台支持七天无理由退款。",
                        }
                    }
                ]
            }

    monkeypatch.setattr("app.agents.orchestrator.get_llm_client", lambda: ThinkingClient())
    upload_response = client.post(
        "/api/v1/kb/upload",
        json={
            "title": "退款规则",
            "content": "平台支持七天无理由退款，商品需要保持完好。",
        },
    )
    assert upload_response.status_code == 200

    response = client.post("/api/v1/chat/", json={"message": "请问退款规则是什么？"})

    assert response.status_code == 200
    reply = response.json()["data"]["reply"]
    assert "<think>" not in reply
    assert "先分析知识库" not in reply
    assert "根据《退款规则》" in reply


def test_chat_uses_order_tool_without_llm(client: TestClient, fake_llm) -> None:
    """Order questions should route to the tool layer instead of the LLM path."""
    response = client.post(
        "/api/v1/chat/",
        json={
            "message": "帮我查一下订单 ORD2026043001 的状态",
            "user_id": "u_order_001",
            "session_id": "sess_order_tool_case",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["data"]["route"] == "order_query"
    assert payload["data"]["answer_source"] == "tool"
    assert "ORD2026043001" in payload["data"]["reply"]
    assert fake_llm == []


def test_chat_order_tool_requests_more_input_for_ambiguous_user(client: TestClient, fake_llm) -> None:
    """When a user matches multiple orders, the tool should ask for an explicit order number."""
    response = client.post(
        "/api/v1/chat/",
        json={
            "message": "帮我查一下订单状态",
            "user_id": "u_multi_001",
            "session_id": "sess_order_ambiguous_case",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["data"]["route"] == "order_query"
    assert payload["data"]["answer_source"] == "tool"
    assert "补充订单号" in payload["data"]["reply"]
    assert fake_llm == []


def test_chat_uses_logistics_tool_without_llm(client: TestClient, fake_llm) -> None:
    """Logistics questions should route to the tool layer instead of the LLM path."""
    response = client.post(
        "/api/v1/chat/",
        json={
            "message": "帮我查一下物流 SF2026043001 到哪了",
            "user_id": "u_order_001",
            "session_id": "sess_logistics_tool_case",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["data"]["route"] == "logistics_query"
    assert payload["data"]["answer_source"] == "tool"
    assert "SF Express" in payload["data"]["reply"]
    assert fake_llm == []


def test_chat_logistics_tool_requests_more_input_for_ambiguous_user(client: TestClient, fake_llm) -> None:
    """When a user matches multiple shipments, the tool should ask for an explicit order or tracking number."""
    response = client.post(
        "/api/v1/chat/",
        json={
            "message": "帮我查一下物流状态",
            "user_id": "u_multi_001",
            "session_id": "sess_logistics_ambiguous_case",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["data"]["route"] == "logistics_query"
    assert payload["data"]["answer_source"] == "tool"
    assert "补充订单号或运单号" in payload["data"]["reply"]
    assert fake_llm == []


def test_chat_degrades_gracefully_when_order_tool_crashes(client: TestClient, fake_llm, monkeypatch) -> None:
    """Chat should return a fallback assistant message when the order tool crashes."""

    def exploding_tool(**kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr("app.services.tool_service.get_tool", lambda tool_name: exploding_tool)

    response = client.post(
        "/api/v1/chat/",
        json={
            "message": "帮我查一下订单 ORD2026043002 的状态",
            "user_id": "u_order_002",
            "session_id": "sess_order_tool_error_case",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["data"]["route"] == "order_query"
    assert payload["data"]["answer_source"] == "fallback"
    assert "订单查询服务暂时不可用" in payload["data"]["reply"]
    assert fake_llm == []
