"""Offline tool-calling evaluation script."""

from __future__ import annotations

import argparse
import asyncio
from dataclasses import dataclass, field
import json
from pathlib import Path
import sys
from time import perf_counter
from typing import Any

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

BACKEND_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = BACKEND_ROOT.parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))


DEFAULT_DATASET_PATH = PROJECT_ROOT / "data" / "eval" / "tool_cases.json"
DEFAULT_REPORT_PATH = PROJECT_ROOT / "data" / "reports" / "tool_eval_report.md"


@dataclass(slots=True)
class ToolEvalCase:
    """Single tool-calling evaluation case."""

    case_id: str
    message: str
    expected_route: str
    expected_tool: str
    expected_status: str
    expected_answer_source: str = "tool"
    user_id: str | None = None
    channel: str = "eval"
    expected_slots: dict[str, str] = field(default_factory=dict)
    expected_reply_contains: list[str] = field(default_factory=list)


@dataclass(slots=True)
class ToolEvalResult:
    """Per-case tool-calling evaluation result."""

    case: ToolEvalCase
    route: str
    answer_source: str
    reply: str
    tool_name: str | None
    tool_status: str | None
    tool_output: dict[str, Any] | None
    latency_ms: float
    route_correct: bool
    tool_correct: bool
    status_correct: bool
    answer_source_correct: bool
    slot_correct: bool
    reply_contains_correct: bool


@dataclass(slots=True)
class ToolEvalSummary:
    """Aggregate tool-calling evaluation metrics."""

    total_cases: int
    route_accuracy: float
    tool_selection_accuracy: float
    status_accuracy: float
    answer_source_accuracy: float
    slot_accuracy: float
    reply_contains_accuracy: float
    end_to_end_accuracy: float
    average_latency_ms: float
    results: list[ToolEvalResult]


def load_cases(dataset_path: Path) -> list[ToolEvalCase]:
    """Load tool evaluation cases from JSON."""
    payload = json.loads(dataset_path.read_text(encoding="utf-8"))
    cases: list[ToolEvalCase] = []
    for item in payload:
        cases.append(
            ToolEvalCase(
                case_id=item["id"],
                message=item["message"],
                user_id=item.get("user_id"),
                channel=item.get("channel", "eval"),
                expected_route=item["expected_route"],
                expected_tool=item["expected_tool"],
                expected_status=item["expected_status"],
                expected_answer_source=item.get("expected_answer_source", "tool"),
                expected_slots=dict(item.get("expected_slots") or {}),
                expected_reply_contains=list(item.get("expected_reply_contains") or []),
            )
        )
    return cases


def _parse_json_payload(value: str | None) -> dict[str, Any] | None:
    if not value:
        return None
    payload = json.loads(value)
    return payload if isinstance(payload, dict) else None


def _latest_tool_log(db: Session, *, session_id: str):
    from app.repositories.tool_log_repository import ToolLogRepository

    logs = ToolLogRepository(db).list_logs(session_id=session_id, offset=0, limit=1)
    return logs[0] if logs else None


def _slots_match(tool_output: dict[str, Any] | None, expected_slots: dict[str, str]) -> bool:
    if not expected_slots:
        return True
    if not tool_output:
        return False
    return all(str(tool_output.get(key)) == expected for key, expected in expected_slots.items())


def _reply_contains(reply: str, expected_fragments: list[str]) -> bool:
    return all(fragment in reply for fragment in expected_fragments)


def _build_summary(results: list[ToolEvalResult]) -> ToolEvalSummary:
    total = len(results)
    if not total:
        return ToolEvalSummary(
            total_cases=0,
            route_accuracy=0.0,
            tool_selection_accuracy=0.0,
            status_accuracy=0.0,
            answer_source_accuracy=0.0,
            slot_accuracy=0.0,
            reply_contains_accuracy=0.0,
            end_to_end_accuracy=0.0,
            average_latency_ms=0.0,
            results=[],
        )

    end_to_end_count = sum(
        1
        for result in results
        if result.route_correct
        and result.tool_correct
        and result.status_correct
        and result.answer_source_correct
        and result.slot_correct
        and result.reply_contains_correct
    )
    return ToolEvalSummary(
        total_cases=total,
        route_accuracy=sum(1 for result in results if result.route_correct) / total,
        tool_selection_accuracy=sum(1 for result in results if result.tool_correct) / total,
        status_accuracy=sum(1 for result in results if result.status_correct) / total,
        answer_source_accuracy=sum(1 for result in results if result.answer_source_correct) / total,
        slot_accuracy=sum(1 for result in results if result.slot_correct) / total,
        reply_contains_accuracy=sum(1 for result in results if result.reply_contains_correct) / total,
        end_to_end_accuracy=end_to_end_count / total,
        average_latency_ms=sum(result.latency_ms for result in results) / total,
        results=results,
    )


async def evaluate_tools(db: Session, cases: list[ToolEvalCase]) -> ToolEvalSummary:
    """Evaluate the chat-to-tool path against fixed cases."""
    from app.schemas.chat import ChatRequest
    from app.services.chat_service import handle_chat_request

    results: list[ToolEvalResult] = []
    for index, case in enumerate(cases, start=1):
        session_id = f"sess_tool_eval_{case.case_id}_{index}"
        trace_id = f"trace_tool_eval_{case.case_id}_{index}"
        started_at = perf_counter()
        response = await handle_chat_request(
            db,
            ChatRequest(
                session_id=session_id,
                user_id=case.user_id,
                channel=case.channel,
                message=case.message,
            ),
            trace_id=trace_id,
        )
        latency_ms = round((perf_counter() - started_at) * 1000, 3)

        log = _latest_tool_log(db, session_id=session_id)
        tool_output = _parse_json_payload(log.tool_output) if log else None
        tool_name = log.tool_name if log else None
        tool_status = log.status if log else None

        route_correct = response.route == case.expected_route
        tool_correct = tool_name == case.expected_tool
        status_correct = tool_status == case.expected_status
        answer_source_correct = response.answer_source == case.expected_answer_source
        slot_correct = _slots_match(tool_output, case.expected_slots)
        reply_contains_correct = _reply_contains(response.reply, case.expected_reply_contains)

        results.append(
            ToolEvalResult(
                case=case,
                route=response.route,
                answer_source=response.answer_source,
                reply=response.reply,
                tool_name=tool_name,
                tool_status=tool_status,
                tool_output=tool_output,
                latency_ms=latency_ms,
                route_correct=route_correct,
                tool_correct=tool_correct,
                status_correct=status_correct,
                answer_source_correct=answer_source_correct,
                slot_correct=slot_correct,
                reply_contains_correct=reply_contains_correct,
            )
        )

    return _build_summary(results)


def _format_percent(value: float) -> str:
    return f"{value * 100:.2f}%"


def _summary_to_payload(summary: ToolEvalSummary) -> dict[str, Any]:
    return {
        "total_cases": summary.total_cases,
        "route_accuracy": summary.route_accuracy,
        "tool_selection_accuracy": summary.tool_selection_accuracy,
        "status_accuracy": summary.status_accuracy,
        "answer_source_accuracy": summary.answer_source_accuracy,
        "slot_accuracy": summary.slot_accuracy,
        "reply_contains_accuracy": summary.reply_contains_accuracy,
        "end_to_end_accuracy": summary.end_to_end_accuracy,
        "average_latency_ms": summary.average_latency_ms,
        "results": [
            {
                "id": result.case.case_id,
                "message": result.case.message,
                "user_id": result.case.user_id,
                "expected_route": result.case.expected_route,
                "route": result.route,
                "expected_tool": result.case.expected_tool,
                "tool_name": result.tool_name,
                "expected_status": result.case.expected_status,
                "tool_status": result.tool_status,
                "expected_answer_source": result.case.expected_answer_source,
                "answer_source": result.answer_source,
                "expected_slots": result.case.expected_slots,
                "tool_output": result.tool_output,
                "reply": result.reply,
                "latency_ms": result.latency_ms,
                "route_correct": result.route_correct,
                "tool_correct": result.tool_correct,
                "status_correct": result.status_correct,
                "answer_source_correct": result.answer_source_correct,
                "slot_correct": result.slot_correct,
                "reply_contains_correct": result.reply_contains_correct,
                "end_to_end_correct": (
                    result.route_correct
                    and result.tool_correct
                    and result.status_correct
                    and result.answer_source_correct
                    and result.slot_correct
                    and result.reply_contains_correct
                ),
            }
            for result in summary.results
        ],
    }


def write_report(summary: ToolEvalSummary, report_path: Path) -> None:
    """Write tool evaluation results as JSON or Markdown."""
    report_path.parent.mkdir(parents=True, exist_ok=True)
    if report_path.suffix.lower() == ".json":
        report_path.write_text(
            json.dumps(_summary_to_payload(summary), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return

    lines = [
        "# Tool Evaluation Report",
        "",
        f"- Total cases: `{summary.total_cases}`",
        f"- Route accuracy: `{_format_percent(summary.route_accuracy)}`",
        f"- Tool selection accuracy: `{_format_percent(summary.tool_selection_accuracy)}`",
        f"- Status accuracy: `{_format_percent(summary.status_accuracy)}`",
        f"- Answer source accuracy: `{_format_percent(summary.answer_source_accuracy)}`",
        f"- Slot accuracy: `{_format_percent(summary.slot_accuracy)}`",
        f"- Reply contains accuracy: `{_format_percent(summary.reply_contains_accuracy)}`",
        f"- End-to-end accuracy: `{_format_percent(summary.end_to_end_accuracy)}`",
        f"- Average latency: `{summary.average_latency_ms:.3f} ms`",
        "",
        "| Case ID | Message | Expected Route | Route | Tool | Status | Slots | Reply | Latency |",
        "|---|---|---|---|---|---|---:|---:|---:|",
    ]
    for result in summary.results:
        lines.append(
            f"| `{result.case.case_id}` | {result.case.message} | {result.case.expected_route} | "
            f"{result.route} | {result.tool_name or ''} | {result.tool_status or ''} | "
            f"{result.slot_correct} | {result.reply_contains_correct} | {result.latency_ms:.3f} ms |"
        )

    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _create_ephemeral_session() -> tuple[Session, Any]:
    from app.db.base import Base

    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        future=True,
    )
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)
    return SessionLocal(), engine


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate ServiceMind tool-calling quality.")
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET_PATH)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT_PATH)
    parser.add_argument(
        "--source",
        choices=["ephemeral", "database"],
        default="ephemeral",
        help="ephemeral uses a temporary SQLite DB; database uses app DB settings.",
    )
    return parser.parse_args()


def main() -> int:
    """Run tool-calling evaluation from the command line."""
    args = _parse_args()
    cases = load_cases(args.dataset)

    if args.source == "ephemeral":
        db, engine = _create_ephemeral_session()
        try:
            summary = asyncio.run(evaluate_tools(db, cases))
        finally:
            db.close()
            engine.dispose()
    else:
        from app.db.session import SessionLocal

        with SessionLocal() as db:
            summary = asyncio.run(evaluate_tools(db, cases))

    write_report(summary, args.report)
    print(
        "Tool eval finished: "
        f"cases={summary.total_cases}, route={_format_percent(summary.route_accuracy)}, "
        f"tool={_format_percent(summary.tool_selection_accuracy)}, "
        f"status={_format_percent(summary.status_accuracy)}, "
        f"slots={_format_percent(summary.slot_accuracy)}, "
        f"end_to_end={_format_percent(summary.end_to_end_accuracy)}, "
        f"report={args.report}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
