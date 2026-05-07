"""Tool endpoint tests."""

import asyncio
from pathlib import Path
import uuid

from fastapi.testclient import TestClient


def test_order_tool_endpoint_returns_structured_result(client: TestClient) -> None:
    """Direct order query endpoint should return a structured tool payload and log metadata."""
    response = client.post(
        "/api/v1/tools/order-query",
        json={
            "query": "请帮我查一下订单 ORD2026043002 的状态",
            "user_id": "u_order_002",
            "session_id": "sess_tool_endpoint",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["code"] == 0
    assert payload["data"]["tool_name"] == "order_query"
    assert payload["data"]["status"] == "success"
    assert payload["data"]["log_id"].startswith("tlog_")
    assert payload["data"]["session_id"] == "sess_tool_endpoint"
    assert payload["data"]["result"]["order_no"] == "ORD2026043002"
    assert payload["data"]["result"]["status"] == "shipped"


def test_logistics_tool_endpoint_returns_structured_result(client: TestClient) -> None:
    """Direct logistics query endpoint should return a structured tool payload and log metadata."""
    response = client.post(
        "/api/v1/tools/logistics-query",
        json={
            "query": "请帮我查一下物流 SF2026043001 到哪了",
            "user_id": "u_order_001",
            "session_id": "sess_tool_logistics_endpoint",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["code"] == 0
    assert payload["data"]["tool_name"] == "logistics_query"
    assert payload["data"]["status"] == "success"
    assert payload["data"]["log_id"].startswith("tlog_")
    assert payload["data"]["session_id"] == "sess_tool_logistics_endpoint"
    assert payload["data"]["result"]["tracking_no"] == "SF2026043001"
    assert payload["data"]["result"]["carrier"] == "SF Express"


def test_tool_logs_endpoint_lists_recent_entries(client: TestClient) -> None:
    """Tool logs endpoint should return paginated invocation history."""
    first = client.post(
        "/api/v1/tools/order-query",
        json={
            "query": "请帮我查一下订单 ORD2026043002 的状态",
            "user_id": "u_order_002",
            "session_id": "sess_tool_logs_case",
        },
    )
    second = client.post(
        "/api/v1/tools/logistics-query",
        json={
            "query": "请帮我查一下物流 SF2026043001 到哪了",
            "user_id": "u_order_001",
            "session_id": "sess_tool_logs_case",
        },
    )

    assert first.status_code == 200
    assert second.status_code == 200

    response = client.get("/api/v1/tools/logs?session_id=sess_tool_logs_case&page=1&page_size=10")
    assert response.status_code == 200
    payload = response.json()

    assert payload["code"] == 0
    assert payload["data"]["pagination"]["total"] == 2
    assert payload["data"]["pagination"]["has_more"] is False
    assert len(payload["data"]["items"]) == 2
    assert payload["data"]["items"][0]["tool_name"] == "logistics_query"
    assert payload["data"]["items"][1]["tool_name"] == "order_query"


def test_tool_endpoint_returns_standard_error_when_handler_crashes(client: TestClient, monkeypatch) -> None:
    """Direct tool endpoint should emit a standardized 503 when the handler crashes."""

    def exploding_tool(**kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr("app.services.tool_service.get_tool", lambda tool_name: exploding_tool)

    response = client.post(
        "/api/v1/tools/order-query",
        json={
            "query": "请帮我查一下订单 ORD2026043002 的状态",
            "user_id": "u_order_002",
            "session_id": "sess_tool_error_case",
        },
    )

    assert response.status_code == 503
    payload = response.json()
    assert payload["code"] == 20001
    assert payload["message"] == "order_query invocation failed"


def test_evaluate_tools_script_computes_chat_tool_metrics(client: TestClient) -> None:
    """The tool evaluation helper should score route, tool, status, slots, and reply checks."""
    report_path = Path("D:/pythoncode/ServiceMind/backend/.tmp") / f"tool_eval_{uuid.uuid4().hex}.json"

    from scripts.evaluate_tools import ToolEvalCase, evaluate_tools, write_report

    try:
        session_local = client.app.state.testing_session_local
        with session_local() as db:
            summary = asyncio.run(
                evaluate_tools(
                    db,
                    [
                        ToolEvalCase(
                            case_id="tool_order_001",
                            message="帮我查一下订单 ORD2026043001 的状态",
                            user_id="u_order_001",
                            expected_route="order_query",
                            expected_tool="order_query",
                            expected_status="success",
                            expected_slots={"order_no": "ORD2026043001"},
                            expected_reply_contains=["ORD2026043001", "paid"],
                        ),
                        ToolEvalCase(
                            case_id="tool_logistics_001",
                            message="帮我查一下物流 SF2026043001 到哪了",
                            user_id="u_order_001",
                            expected_route="logistics_query",
                            expected_tool="logistics_query",
                            expected_status="success",
                            expected_slots={"tracking_no": "SF2026043001"},
                            expected_reply_contains=["SF Express", "上海转运中心"],
                        ),
                    ],
                )
            )
            write_report(summary, report_path)

        assert summary.total_cases == 2
        assert summary.route_accuracy == 1.0
        assert summary.tool_selection_accuracy == 1.0
        assert summary.status_accuracy == 1.0
        assert summary.answer_source_accuracy == 1.0
        assert summary.slot_accuracy == 1.0
        assert summary.reply_contains_accuracy == 1.0
        assert summary.end_to_end_accuracy == 1.0
        assert report_path.exists()
    finally:
        report_path.unlink(missing_ok=True)
