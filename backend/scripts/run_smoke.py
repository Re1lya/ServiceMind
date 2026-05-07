"""Manual smoke test runner for a live ServiceMind backend."""

from __future__ import annotations

import argparse
import sys
import uuid

import httpx


def _assert_success(response: httpx.Response, *, label: str) -> dict:
    response.raise_for_status()
    payload = response.json()
    if payload.get("code") != 0:
        raise RuntimeError(f"{label} failed: {payload}")
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Run a live smoke test against a ServiceMind backend.")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000", help="Backend base URL, default http://127.0.0.1:8000")
    args = parser.parse_args()

    suffix = uuid.uuid4().hex[:8]
    faq_session = f"sess_smoke_faq_{suffix}"
    tool_session = f"sess_smoke_tool_{suffix}"

    try:
        with httpx.Client(base_url=args.base_url, timeout=15.0) as client:
            health = _assert_success(client.get("/api/v1/health"), label="health")
            print(f"[ok] health status={health['data']['status']} components={health['data']['components']}")

            _assert_success(
                client.post(
                    "/api/v1/kb/upload",
                    json={
                        "title": "退款规则",
                        "content": "平台支持七天无理由退款，商品需要保持完好。",
                        "source_type": "text",
                    },
                ),
                label="kb upload",
            )
            print("[ok] knowledge upload")

            faq_chat = _assert_success(
                client.post(
                    "/api/v1/chat/",
                    json={"message": "请问退款规则是什么？", "session_id": faq_session},
                ),
                label="faq chat",
            )
            print(f"[ok] faq chat route={faq_chat['data']['route']} source={faq_chat['data']['answer_source']}")

            order_chat = _assert_success(
                client.post(
                    "/api/v1/chat/",
                    json={
                        "message": "帮我查一下订单 ORD2026043001 的状态",
                        "user_id": "u_order_001",
                        "session_id": tool_session,
                    },
                ),
                label="order chat",
            )
            print(f"[ok] order chat route={order_chat['data']['route']} source={order_chat['data']['answer_source']}")

            logistics_chat = _assert_success(
                client.post(
                    "/api/v1/chat/",
                    json={
                        "message": "帮我查一下物流 SF2026043001 到哪了",
                        "user_id": "u_order_001",
                        "session_id": tool_session,
                    },
                ),
                label="logistics chat",
            )
            print(f"[ok] logistics chat route={logistics_chat['data']['route']} source={logistics_chat['data']['answer_source']}")

            logs = _assert_success(
                client.get(f"/api/v1/tools/logs?session_id={tool_session}&page=1&page_size=10"),
                label="tool logs",
            )
            print(f"[ok] tool logs total={logs['data']['pagination']['total']}")
    except Exception as exc:
        print(f"[fail] smoke test failed: {exc}", file=sys.stderr)
        return 1

    print("[ok] smoke test completed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
