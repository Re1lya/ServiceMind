"""Knowledge base endpoint and retrieval tests."""

from pathlib import Path
import asyncio
import shutil
import sys
from types import SimpleNamespace
import uuid

from fastapi.testclient import TestClient


def test_kb_upload_and_search(client: TestClient) -> None:
    """Uploading a knowledge document should make it searchable."""
    upload_response = client.post(
        "/api/v1/kb/upload",
        json={
            "title": "退款规则",
            "content": "平台支持七天无理由退款，用户需要保持商品完好。",
            "source_type": "text",
        },
    )

    assert upload_response.status_code == 200
    upload_payload = upload_response.json()
    assert upload_payload["code"] == 0
    assert upload_payload["data"]["document"]["title"] == "退款规则"
    assert upload_payload["data"]["vector_count"] >= 1

    search_response = client.get("/api/v1/kb/search?query=退款规则&top_k=3")
    assert search_response.status_code == 200
    search_payload = search_response.json()
    assert search_payload["code"] == 0
    assert len(search_payload["data"]["hits"]) >= 1
    assert search_payload["data"]["hits"][0]["title"] == "退款规则"


def test_kb_rebuild_loads_documents_from_raw_directory(client: TestClient) -> None:
    """Rebuild should load supported files from the configured raw data directory."""
    source_dir = Path("D:/pythoncode/ServiceMind/backend/.tmp") / f"kb_test_{uuid.uuid4().hex}"
    source_dir.mkdir(parents=True, exist_ok=True)
    knowledge_file = source_dir / "invoice_policy.txt"
    knowledge_file.write_text("发票开具规则：企业用户可申请增值税专票。", encoding="utf-8")

    from app.services.kb_service import rebuild_knowledge_index

    try:
        session_local = client.app.state.testing_session_local
        with session_local() as db:
            result = rebuild_knowledge_index(db, source_dir=source_dir)
            assert result.indexed_count == 1
            assert result.vector_count >= 1

        search_response = client.get("/api/v1/kb/search?query=发票&top_k=3")
        search_payload = search_response.json()
        assert search_response.status_code == 200
        assert search_payload["data"]["hits"][0]["title"] == "invoice_policy"
    finally:
        shutil.rmtree(source_dir, ignore_errors=True)


def test_kb_upload_chunks_long_documents_and_returns_source_metadata(client: TestClient) -> None:
    """Long knowledge content should be split into searchable chunks with source metadata."""
    long_content = "\n".join(
        [
            "退款规则：平台支持七天无理由退款，商品需要保持完好。",
            "发票规则：企业用户可申请增值税专票，需要填写抬头和税号。",
            "物流规则：偏远地区配送时效可能延长，系统会展示预计送达时间。",
        ]
        * 12
    )

    upload_response = client.post(
        "/api/v1/kb/upload",
        json={
            "title": "售后政策合集",
            "content": long_content,
            "source_type": "md",
            "source_path": "data/raw/after_sales.md",
        },
    )

    assert upload_response.status_code == 200
    upload_payload = upload_response.json()
    assert upload_payload["data"]["chunk_count"] > 1
    assert upload_payload["data"]["indexed_count"] == upload_payload["data"]["chunk_count"]
    assert upload_payload["data"]["vector_count"] == upload_payload["data"]["chunk_count"]

    search_response = client.get("/api/v1/kb/search?query=增值税专票&top_k=3")
    search_payload = search_response.json()

    assert search_response.status_code == 200
    assert search_payload["data"]["hits"]
    top_hit = search_payload["data"]["hits"][0]
    assert top_hit["source_type"] == "md"
    assert top_hit["source_path"] == "data/raw/after_sales.md"
    assert "发票" in top_hit["snippet"]


def test_vector_store_searches_uploaded_chunks(client: TestClient) -> None:
    """Uploaded knowledge chunks should be written to FAISS and searchable directly."""
    client.post(
        "/api/v1/kb/upload",
        json={
            "title": "会员售后规则",
            "content": "金卡会员支持优先退款审核。普通会员退款审核通常需要三个工作日。",
            "source_type": "text",
        },
    )

    from app.rag.vector_store import search_vector_store

    hits = search_vector_store("金卡会员怎么退款", top_k=3)

    assert hits
    assert hits[0].title == "会员售后规则"
    assert "金卡会员" in hits[0].content


def test_build_kb_script_builds_index_and_writes_report(client: TestClient) -> None:
    """The offline build script should process raw files and write a build report."""
    source_dir = Path("D:/pythoncode/ServiceMind/backend/.tmp") / f"build_kb_{uuid.uuid4().hex}"
    source_dir.mkdir(parents=True, exist_ok=True)
    report_path = source_dir / "report.json"

    (source_dir / "refund_policy.txt").write_text(
        "退款规则：平台支持七天无理由退款，商品需要保持完好。",
        encoding="utf-8",
    )
    (source_dir / "invoice_policy.md").write_text(
        "发票规则：企业用户可申请增值税专票，需要填写抬头和税号。",
        encoding="utf-8",
    )
    (source_dir / "empty.txt").write_text("   \n\n", encoding="utf-8")
    (source_dir / "ignored.csv").write_text("name,value", encoding="utf-8")

    from scripts.build_kb import build_knowledge_index, write_report

    try:
        session_local = client.app.state.testing_session_local
        with session_local() as db:
            report = build_knowledge_index(db, source_dir=source_dir)
            write_report(report, report_path)

        assert report.success is True
        assert report.files_seen == 4
        assert report.files_processed == 2
        assert report.files_skipped == 2
        assert report.files_failed == 0
        assert report.indexed_count == 2
        assert report.vector_count == 2
        assert report_path.exists()
        assert "refund_policy.txt" in report_path.read_text(encoding="utf-8")

        search_response = client.get("/api/v1/kb/search?query=增值税专票&top_k=3")
        assert search_response.status_code == 200
        search_payload = search_response.json()
        assert search_payload["data"]["hits"][0]["title"] == "invoice_policy"
    finally:
        shutil.rmtree(source_dir, ignore_errors=True)


def test_evaluate_retrieval_script_computes_metrics(client: TestClient) -> None:
    """The retrieval evaluation helper should compute positive and no-hit metrics."""
    report_path = Path("D:/pythoncode/ServiceMind/backend/.tmp") / f"retrieval_eval_{uuid.uuid4().hex}.json"

    client.post(
        "/api/v1/kb/upload",
        json={
            "title": "退款规则",
            "content": "平台支持七天无理由退款，商品需要保持完好。",
            "source_type": "text",
        },
    )

    from scripts.evaluate_retrieval import RetrievalEvalCase, evaluate_retrieval, write_report

    try:
        session_local = client.app.state.testing_session_local
        with session_local() as db:
            summary = evaluate_retrieval(
                db,
                [
                    RetrievalEvalCase(
                        case_id="faq_refund_001",
                        question="七天无理由退款规则是什么？",
                        gold_title="退款规则",
                        expected_keywords=["七天无理由", "退款"],
                    ),
                    RetrievalEvalCase(
                        case_id="faq_logistics_negative_001",
                        question="偏远地区物流多久能送到？",
                        expect_no_hit=True,
                    ),
                ],
                top_k=3,
            )
            write_report(summary, report_path)

        assert summary.total_cases == 2
        assert summary.positive_cases == 1
        assert summary.negative_cases == 1
        assert summary.hit_at_1 == 1.0
        assert summary.recall_at_k == 1.0
        assert summary.mrr == 1.0
        assert summary.no_hit_accuracy == 1.0
        assert report_path.exists()
    finally:
        report_path.unlink(missing_ok=True)


def test_evaluate_answer_script_computes_grounded_answer_metrics(client: TestClient) -> None:
    """The answer evaluation helper should score source-backed and no-hit answers."""
    report_path = Path("D:/pythoncode/ServiceMind/backend/.tmp") / f"answer_eval_{uuid.uuid4().hex}.json"

    client.post(
        "/api/v1/kb/upload",
        json={
            "title": "退款规则",
            "content": "平台支持七天无理由退款。已经拆封的商品需要按照售后审核结果处理，质量问题可以上传凭证。",
            "source_type": "text",
        },
    )

    from scripts.evaluate_answer import AnswerEvalCase, evaluate_answers, write_report

    try:
        session_local = client.app.state.testing_session_local
        with session_local() as db:
            summary = evaluate_answers(
                db,
                [
                    AnswerEvalCase(
                        case_id="answer_refund_001",
                        question="商品已经拆封还能直接退款吗？",
                        expected_source_title="退款规则",
                        expected_keywords=["已经拆封", "售后审核", "质量问题"],
                        must_not_include=["一定可以退", "无需审核"],
                    ),
                    AnswerEvalCase(
                        case_id="answer_negative_001",
                        question="礼品卡余额能提现吗？",
                        expect_no_hit=True,
                        must_not_include=["能提现"],
                    ),
                ],
                top_k=3,
            )
            write_report(summary, report_path)

        assert summary.total_cases == 2
        assert summary.positive_cases == 1
        assert summary.negative_cases == 1
        assert summary.source_return_rate == 1.0
        assert summary.source_match_rate == 1.0
        assert summary.keyword_coverage == 1.0
        assert summary.forbidden_violation_rate == 0.0
        assert summary.groundedness_rate == 1.0
        assert summary.no_hit_accuracy == 1.0
        assert summary.average_retrieval_latency_ms >= 0.0
        assert summary.average_generation_latency_ms >= 0.0
        assert summary.results[0].retrieval_latency_ms >= 0.0
        assert summary.results[0].generation_latency_ms >= 0.0
        assert report_path.exists()
    finally:
        report_path.unlink(missing_ok=True)


def test_evaluate_answer_script_supports_llm_mode(client: TestClient, monkeypatch) -> None:
    """LLM-mode answer evaluation should score real RAG replies with a stubbed model."""

    class FakeClient:
        async def chat_completion(self, *args, **kwargs):
            return {
                "choices": [
                    {
                        "message": {
                            "content": "根据《退款规则》，已经拆封的商品需要按照售后审核结果处理，质量问题可以上传凭证。",
                        }
                    }
                ]
            }

    monkeypatch.setattr("app.agents.orchestrator.get_llm_client", lambda: FakeClient())
    client.post(
        "/api/v1/kb/upload",
        json={
            "title": "退款规则",
            "content": "平台支持七天无理由退款。已经拆封的商品需要按照售后审核结果处理，质量问题可以上传凭证。",
            "source_type": "text",
        },
    )

    from scripts.evaluate_answer import AnswerEvalCase, evaluate_answers_with_llm

    session_local = client.app.state.testing_session_local
    with session_local() as db:
        summary = asyncio.run(
            evaluate_answers_with_llm(
                db,
                [
                    AnswerEvalCase(
                        case_id="answer_refund_llm_001",
                        question="商品已经拆封还能直接退款吗？",
                        expected_source_title="退款规则",
                        expected_keywords=["已经拆封", "售后审核", "质量问题"],
                        must_not_include=["一定可以退"],
                    ),
                    AnswerEvalCase(
                        case_id="answer_negative_llm_001",
                        question="礼品卡余额能提现吗？",
                        expect_no_hit=True,
                    ),
                ],
                top_k=3,
            )
        )

    assert summary.mode == "llm"
    assert summary.total_cases == 2
    assert summary.source_return_rate == 1.0
    assert summary.source_match_rate == 1.0
    assert summary.keyword_coverage == 1.0
    assert summary.no_hit_accuracy == 1.0
    assert summary.results[0].answer_source == "rag_llm"
    assert summary.results[1].answer_source == "no_hit_fallback"
    assert summary.average_retrieval_latency_ms >= 0.0
    assert summary.average_generation_latency_ms >= 0.0


def test_retrieval_reranks_with_keyword_validation(client: TestClient) -> None:
    """Retrieval should prefer documents with stronger distinct keyword coverage."""
    client.post(
        "/api/v1/kb/upload",
        json={
            "title": "商品活动规则",
            "content": "秒杀商品需要在限定时间内完成支付，超时订单会自动关闭。满减和优惠券不能无限叠加。",
            "source_type": "text",
        },
    )
    client.post(
        "/api/v1/kb/upload",
        json={
            "title": "支付规则",
            "content": "平台支持银行卡、支付宝、微信支付和余额支付。订单需要在规定时间内完成支付。",
            "source_type": "text",
        },
    )

    response = client.get("/api/v1/kb/search?query=秒杀订单超时未支付会怎样&top_k=3")
    payload = response.json()

    assert response.status_code == 200
    assert payload["data"]["hits"][0]["title"] == "商品活动规则"


def test_retrieval_filters_low_confidence_generic_queries(client: TestClient) -> None:
    """Generic or unsupported questions should not return weak single-term matches."""
    client.post(
        "/api/v1/kb/upload",
        json={
            "title": "支付规则",
            "content": "平台支持银行卡、支付宝、微信支付和余额支付。",
            "source_type": "text",
        },
    )

    response = client.get("/api/v1/kb/search?query=礼品卡余额能提现吗&top_k=3")
    payload = response.json()

    assert response.status_code == 200
    assert payload["data"]["hits"] == []


def test_retriever_prefers_jieba_terms(monkeypatch) -> None:
    """Lexical tokenization should use jieba terms when jieba is available."""
    from app.rag import retriever

    fake_jieba = SimpleNamespace(cut=lambda text, HMM=True: ["秒杀", "订单", "超时", "支付"])
    monkeypatch.setitem(sys.modules, "jieba", fake_jieba)

    terms = retriever._tokenize_lexical_terms("秒杀订单超时未支付会怎样")

    assert "秒杀" in terms
    assert "超时" in terms
    assert "支付" in terms
    assert "订单" not in terms


def test_retriever_falls_back_to_chinese_ngrams(monkeypatch) -> None:
    """Lexical tokenization should fall back to 2-4 character n-grams without jieba."""
    from app.rag import retriever

    monkeypatch.delitem(sys.modules, "jieba", raising=False)
    monkeypatch.setattr(retriever.importlib, "import_module", lambda name: (_ for _ in ()).throw(ImportError(name)))

    terms = retriever._tokenize_lexical_terms("秒杀订单超时")

    assert "秒杀" in terms
    assert "超时" in terms
    assert "秒杀订单" in terms
