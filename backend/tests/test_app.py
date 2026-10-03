import asyncio
import hashlib
import json
from types import SimpleNamespace

import httpx
import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

import app as app_module
from app import analysis_routes, rate_limiting
import llm_ticket

try:
    from backend.scripts import build_cache
except ImportError:
    from scripts import build_cache
from llm_ticket import (
    AuthenticationError,
    QuotaExceededError,
    ServiceUnavailableError,
    TicketAnalysisItem,
    analyze_tickets,
)

BatchResult = analysis_routes.BatchResult
BatchSummary = BatchResult.model_fields["summary"].annotation
Ticket = analysis_routes.Ticket
TicketResult = analysis_routes.TicketResult

client = TestClient(app_module.app)


@pytest.fixture(autouse=True)
def clear_rate_limit_windows() -> None:
    rate_limiting._rate_windows.clear()
    rate_limiting._gemini_rate_windows.clear()


@pytest.fixture(autouse=True)
def clear_rate_limits() -> None:
    rate_limiting._rate_windows.clear()
    rate_limiting._gemini_rate_windows.clear()


def valid_ticket(
    ticket_id: int = 1, message: str = "Need help with my account"
) -> dict:
    return {"id": ticket_id, "message": message}


def successful_result(ticket_id: int = 1) -> TicketResult:
    return TicketResult(
        id=ticket_id,
        reasoning="The ticket asks for account help.",
        category="Account",
        urgency="Medium",
        sentiment="Neutral",
        confidence="High",
        suggested_reply="Thanks for contacting us. We can review this issue.",
        status="ok",
    )


def test_health() -> None:
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_cache_present_and_missing(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    cache_path = tmp_path / "analysis_cache.json"
    monkeypatch.setattr(analysis_routes, "CACHE_PATH", cache_path)
    assert client.get("/api/analysis").status_code == 404

    cache_path.write_text(json.dumps({"results": [], "summary": {}}), encoding="utf-8")
    response = client.get("/api/analysis")
    assert response.status_code == 200
    assert response.json()["results"] == []


def test_validation_rejects_invalid_batches(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(rate_limiting, "GEMINI_RATE_LIMIT", 100)
    cases = [
        {"tickets": []},
        {"tickets": [valid_ticket(1), valid_ticket(1)]},
        {"tickets": [valid_ticket(1, "   ")]},
        {"tickets": [valid_ticket(1, "x" * 2001)]},
        {"tickets": [{}]},
    ]
    for payload in cases:
        response = client.post("/api/analyze", json=payload)
        assert response.status_code == 422, payload

    malformed = client.post(
        "/api/analyze",
        content='{"tickets": [',
        headers={"content-type": "application/json"},
    )
    assert malformed.status_code == 422


def test_batch_ticket_count_cap() -> None:
    response = client.post(
        "/api/analyze",
        json={"tickets": [valid_ticket(index) for index in range(1, 27)]},
    )
    assert response.status_code == 422
    assert "25 tickets" in response.json()["detail"]


def test_batch_total_character_cap() -> None:
    tickets = [valid_ticket(index, "x" * 2000) for index in range(1, 14)]
    response = client.post("/api/analyze", json={"tickets": tickets})
    assert response.status_code == 422
    assert "25000 characters combined" in response.json()["detail"]


def test_support_ticket_file_is_analyzed_and_cached(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    cache_path = tmp_path / "analysis_cache.json"
    monkeypatch.setattr(analysis_routes, "CACHE_PATH", cache_path)
    source_tickets = client.get("/api/tickets").json()
    analyzed_batches = []

    async def fake_analyze(tickets):
        analyzed_batches.append(tickets)
        return BatchResult(
            results=[successful_result(ticket.id) for ticket in tickets],
            summary=BatchSummary(
                total=len(tickets), succeeded=len(tickets), failed=0, duration_ms=1
            ),
        )

    monkeypatch.setattr(analysis_routes, "analyze_tickets", fake_analyze)
    response = client.post("/api/analyze", json={"tickets": source_tickets})

    assert response.status_code == 200
    assert len(analyzed_batches) == 1
    assert [ticket.id for ticket in analyzed_batches[0]] == [
        ticket["id"] for ticket in source_tickets
    ]
    cached = json.loads(cache_path.read_text(encoding="utf-8"))
    assert {result["id"] for result in cached["results"]} == {
        ticket["id"] for ticket in source_tickets
    }
    assert all("message_hash" in result for result in cached["results"])
    assert all(result["status"] == "ok" for result in cached["results"])
    displayed = client.get("/api/analysis").json()
    assert displayed["results"] == [
        {key: value for key, value in result.items() if key != "message_hash"}
        for result in cached["results"]
    ]


def test_partial_failure_is_cached_and_merged(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    cache_path = tmp_path / "analysis_cache.json"
    cache_path.write_text(
        BatchResult(
            results=[successful_result(3)],
            summary=BatchSummary(total=1, succeeded=1, failed=0, duration_ms=1),
        ).model_dump_json(),
        encoding="utf-8",
    )
    monkeypatch.setattr(analysis_routes, "CACHE_PATH", cache_path)

    async def fake_analyze(tickets):
        return BatchResult(
            results=[
                successful_result(tickets[0].id),
                TicketResult(
                    id=tickets[1].id,
                    reasoning="Analysis failed before a reliable classification was produced.",
                    category="Other",
                    urgency="High",
                    sentiment="Neutral",
                    confidence="Low",
                    status="failed",
                    error="invalid output",
                ),
            ],
            summary=BatchSummary(total=2, succeeded=1, failed=1, duration_ms=2),
        )

    monkeypatch.setattr(analysis_routes, "analyze_tickets", fake_analyze)
    response = client.post(
        "/api/analyze",
        json={"tickets": [valid_ticket(), valid_ticket(2, "Different ticket")]},
    )
    assert response.status_code == 200
    assert response.json()["summary"]["failed"] == 1
    assert response.json()["results"][1]["urgency"] == "High"
    saved = json.loads(cache_path.read_text(encoding="utf-8"))
    assert {item["id"] for item in saved["results"]} == {1, 2}
    assert saved["summary"]["failed"] == 1


def test_auth_error_returns_503(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_analyze(tickets):
        raise ServiceUnavailableError("Gemini authentication failure")

    monkeypatch.setattr(analysis_routes, "analyze_tickets", fake_analyze)
    response = client.post("/api/analyze", json={"tickets": [valid_ticket()]})
    assert response.status_code == 503
    assert (
        response.json()["detail"] == "The analysis provider is temporarily unavailable."
    )


@pytest.mark.parametrize("status_code", [401, 403])
def test_authentication_error_preserves_status(
    monkeypatch: pytest.MonkeyPatch, status_code: int
) -> None:
    async def fake_analyze(tickets):
        raise AuthenticationError("Gemini authentication failure", status_code)

    monkeypatch.setattr(analysis_routes, "analyze_tickets", fake_analyze)
    response = client.post("/api/analyze", json={"tickets": [valid_ticket()]})
    assert response.status_code == status_code
    assert response.json()["detail"] == "Gemini authentication failed."


def test_quota_error_returns_429(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_analyze(tickets):
        raise QuotaExceededError("Gemini quota exhausted", retry_after_seconds=20917)

    monkeypatch.setattr(analysis_routes, "analyze_tickets", fake_analyze)
    response = client.post("/api/analyze", json={"tickets": [valid_ticket()]})
    assert response.status_code == 429
    assert response.json()["detail"] == "Daily AI quota reached. Try again in 6 hours."
    assert response.headers["retry-after"] == "20917"


def test_short_quota_retry_uses_seconds(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_analyze(tickets):
        raise QuotaExceededError("Gemini rate limit", retry_after_seconds=42)

    monkeypatch.setattr(analysis_routes, "analyze_tickets", fake_analyze)
    response = client.post("/api/analyze", json={"tickets": [valid_ticket()]})
    assert response.status_code == 429
    assert (
        response.json()["detail"] == "AI rate limit reached. Try again in 42 seconds."
    )
    assert response.headers["retry-after"] == "42"


def test_unknown_quota_retry_has_no_retry_after(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_analyze(tickets):
        raise QuotaExceededError("Gemini quota exhausted")

    monkeypatch.setattr(analysis_routes, "analyze_tickets", fake_analyze)
    response = client.post("/api/analyze", json={"tickets": [valid_ticket()]})
    assert response.status_code == 429
    assert response.json()["detail"] == "AI quota reached. Please try again later."
    assert "retry-after" not in response.headers


class FakeResponses:
    def __init__(self, outputs):
        self.outputs = iter(outputs)
        self.calls = []

    async def generate_content(self, **kwargs):
        self.calls.append(kwargs)
        output = next(self.outputs)
        if isinstance(output, BaseException):
            raise output
        return SimpleNamespace(parsed=output)


class FakeClient:
    def __init__(self, outputs):
        self.models = FakeResponses(outputs)
        self.aio = SimpleNamespace(models=self.models)


def test_gemini_resource_exhausted_raises_quota_error() -> None:
    class ProviderError(Exception):
        code = 429
        details = {
            "error": {
                "details": [
                    {
                        "@type": "type.googleapis.com/google.rpc.RetryInfo",
                        "retryDelay": "20917s",
                    }
                ]
            }
        }

    fake_client = FakeClient([ProviderError("RESOURCE_EXHAUSTED")])
    with pytest.raises(QuotaExceededError) as error:
        asyncio.run(analyze_tickets([Ticket(**valid_ticket())], client=fake_client))
    assert len(fake_client.models.calls) == 1
    assert error.value.retry_after_seconds == 20917


def valid_analysis() -> TicketAnalysisItem:
    return TicketAnalysisItem(
        id=1,
        reasoning="The user asks for account help.",
        category="Account",
        urgency="Medium",
        sentiment="Neutral",
        confidence="High",
        suggested_reply="Thanks for contacting us. We can review this issue.",
    )


def test_twenty_tickets_use_one_gemini_request() -> None:
    tickets = [
        Ticket(**valid_ticket(index, f"Ticket {index}")) for index in range(1, 21)
    ]
    fake_client = FakeClient(
        [[valid_analysis().model_copy(update={"id": ticket.id}) for ticket in tickets]]
    )
    result = asyncio.run(
        analyze_tickets(tickets, client=fake_client, model="test-model")
    )
    assert result.summary.succeeded == 20
    assert len(fake_client.models.calls) == 1
    assert '"id": 20' in fake_client.models.calls[0]["contents"]
    config = fake_client.models.calls[0]["config"]
    assert config.thinking_config.thinking_level.value.lower() == "low"
    assert "automatic_function_calling" not in config.model_fields_set


def test_timeout_fails_without_retry() -> None:
    fake_client = FakeClient([asyncio.TimeoutError()])
    result = asyncio.run(
        analyze_tickets([Ticket(**valid_ticket())], client=fake_client)
    )
    assert result.results[0].status == "failed"
    assert "timed out" in result.results[0].error
    assert len(fake_client.models.calls) == 1


def test_batch_retries_after_temporary_provider_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def no_wait(_seconds):
        return None

    monkeypatch.setattr("llm_ticket.asyncio.sleep", no_wait)

    class ProviderError(Exception):
        code = 503

    fake_client = FakeClient([ProviderError("UNAVAILABLE"), [valid_analysis()]])
    result = asyncio.run(
        analyze_tickets([Ticket(**valid_ticket())], client=fake_client)
    )

    assert result.results[0].status == "ok"
    assert len(fake_client.models.calls) == 2


def test_non_503_provider_error_is_not_retried() -> None:
    class ProviderError(Exception):
        code = 500

    fake_client = FakeClient([ProviderError("INTERNAL")])
    with pytest.raises(ProviderError):
        asyncio.run(analyze_tickets([Ticket(**valid_ticket())], client=fake_client))
    assert len(fake_client.models.calls) == 1


def test_repeated_provider_errors_return_structured_failures(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    delays = []

    async def no_wait(_seconds):
        delays.append(_seconds)

    monkeypatch.setattr("llm_ticket.asyncio.sleep", no_wait)

    class ProviderError(Exception):
        code = 503

    fake_client = FakeClient([ProviderError("UNAVAILABLE") for _ in range(2)])
    result = asyncio.run(
        analyze_tickets(
            [Ticket(**valid_ticket())],
            client=fake_client,
            model="gemini-3.8-flash",
        )
    )

    assert result.results[0].status == "failed"
    assert result.results[0].error == "Gemini is temporarily unavailable (HTTP 503)."
    assert result.summary.failed == 1
    assert len(fake_client.models.calls) == 2
    assert delays == [3]


def test_transient_failures_retry_with_bounded_backoff(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def no_wait(_seconds):
        return None

    monkeypatch.setattr("llm_ticket.asyncio.sleep", no_wait)

    class ProviderError(Exception):
        code = 503

    fake_client = FakeClient([ProviderError("UNAVAILABLE"), [valid_analysis()]])
    result = asyncio.run(
        analyze_tickets(
            [Ticket(**valid_ticket())],
            client=fake_client,
            model="gemini-3.8-flash",
        )
    )

    assert result.results[0].status == "ok"
    assert len(fake_client.models.calls) == 2


def test_invalid_batch_fails_without_retry() -> None:
    fake_client = FakeClient([SimpleNamespace()])
    result = asyncio.run(
        analyze_tickets([Ticket(**valid_ticket())], client=fake_client)
    )
    assert result.results[0].status == "failed"
    assert result.results[0].urgency == "High"
    assert result.results[0].category == "Other"
    assert result.results[0].confidence == "Low"
    assert len(fake_client.models.calls) == 1


def test_cache_reuses_unchanged_messages_and_reanalyzes_edits(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    cache_path = tmp_path / "analysis_cache.json"
    monkeypatch.setattr(analysis_routes, "CACHE_PATH", cache_path)
    analyzed_messages = []

    async def fake_analyze(tickets):
        analyzed_messages.extend(ticket.message for ticket in tickets)
        return BatchResult(
            results=[successful_result(ticket.id) for ticket in tickets],
            summary=BatchSummary(
                total=len(tickets), succeeded=len(tickets), failed=0, duration_ms=1
            ),
        )

    monkeypatch.setattr(analysis_routes, "analyze_tickets", fake_analyze)
    original = Ticket(**valid_ticket())
    edited = Ticket(**valid_ticket(message="The ticket text has changed"))

    asyncio.run(analysis_routes._run_analysis([original]))
    asyncio.run(analysis_routes._run_analysis([original]))
    asyncio.run(analysis_routes._run_analysis([edited]))

    assert analyzed_messages == [original.message, edited.message]
    saved = json.loads(cache_path.read_text(encoding="utf-8"))
    assert {result["message_hash"] for result in saved["results"]} == {
        hashlib.sha256(original.message.encode("utf-8")).hexdigest(),
        hashlib.sha256(edited.message.encode("utf-8")).hexdigest(),
    }


def test_same_id_with_different_messages_keeps_both_cache_entries(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    cache_path = tmp_path / "analysis_cache.json"
    monkeypatch.setattr(analysis_routes, "CACHE_PATH", cache_path)
    analyzed = []

    async def fake_analyze(tickets):
        analyzed.extend(ticket.message for ticket in tickets)
        return BatchResult(
            results=[
                successful_result(ticket.id).model_copy(
                    update={"reasoning": ticket.message}
                )
                for ticket in tickets
            ],
            summary=BatchSummary(
                total=len(tickets), succeeded=len(tickets), failed=0, duration_ms=1
            ),
        )

    monkeypatch.setattr(analysis_routes, "analyze_tickets", fake_analyze)
    first = Ticket(**valid_ticket(1, "First message"))
    second = Ticket(**valid_ticket(1, "Different message"))
    other_id = Ticket(**valid_ticket(99, "First message"))

    asyncio.run(analysis_routes._run_analysis([first]))
    asyncio.run(analysis_routes._run_analysis([second]))
    returned = asyncio.run(analysis_routes._run_analysis([other_id]))

    hashes = {
        hashlib.sha256(ticket.message.encode()).hexdigest()
        for ticket in (first, second)
    }
    cached = json.loads(cache_path.read_text(encoding="utf-8"))
    assert {entry["message_hash"] for entry in cached["results"]} == hashes
    assert analyzed == [first.message, second.message]
    assert returned.results[0].id == other_id.id
    assert returned.results[0].reasoning == first.message


def test_analysis_view_uses_source_ticket_content_not_matching_id(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    cache_path = tmp_path / "analysis_cache.json"
    source_path = tmp_path / "support_tickets.json"
    source_path.write_text(
        json.dumps([valid_ticket(1, "Source ticket content")]),
        encoding="utf-8",
    )
    monkeypatch.setattr(analysis_routes, "CACHE_PATH", cache_path)
    monkeypatch.setattr(analysis_routes, "DATA_PATH", source_path)

    async def fake_analyze(tickets):
        return BatchResult(
            results=[
                successful_result(ticket.id).model_copy(
                    update={"reasoning": ticket.message}
                )
                for ticket in tickets
            ],
            summary=BatchSummary(
                total=len(tickets), succeeded=len(tickets), failed=0, duration_ms=1
            ),
        )

    monkeypatch.setattr(analysis_routes, "analyze_tickets", fake_analyze)
    source = Ticket(**valid_ticket(1, "Source ticket content"))
    pasted = Ticket(**valid_ticket(1, "Pasted ticket content"))
    asyncio.run(analysis_routes._run_analysis([source]))
    asyncio.run(analysis_routes._run_analysis([pasted]))

    response = client.get("/api/analysis")

    assert response.status_code == 200
    assert len(response.json()["results"]) == 1
    assert response.json()["results"][0]["reasoning"] == source.message


def test_failed_cache_entry_is_reanalyzed(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    cache_path = tmp_path / "analysis_cache.json"
    ticket = Ticket(**valid_ticket())
    failed = TicketResult(
        id=ticket.id,
        reasoning="Analysis failed.",
        category="Other",
        urgency="High",
        sentiment="Neutral",
        confidence="Low",
        status="failed",
        error="previous provider failure",
    )
    cache_path.write_text(
        json.dumps(
            {
                "results": [
                    {
                        "message_hash": analysis_routes._ticket_hash(ticket),
                        **failed.model_dump(),
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(analysis_routes, "CACHE_PATH", cache_path)
    calls = []

    async def fake_analyze(tickets):
        calls.append(tickets)
        return BatchResult(
            results=[successful_result(ticket.id) for ticket in tickets],
            summary=BatchSummary(total=1, succeeded=1, failed=0, duration_ms=1),
        )

    monkeypatch.setattr(analysis_routes, "analyze_tickets", fake_analyze)
    result = asyncio.run(analysis_routes._run_analysis([ticket]))

    assert len(calls) == 1
    assert result.results[0].status == "ok"


def test_concurrent_identical_requests_share_one_analysis(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    monkeypatch.setattr(analysis_routes, "CACHE_PATH", tmp_path / "analysis_cache.json")
    calls = []

    async def fake_analyze(tickets):
        calls.append(tickets)
        await asyncio.sleep(0.05)
        return BatchResult(
            results=[successful_result(ticket.id) for ticket in tickets],
            summary=BatchSummary(
                total=len(tickets), succeeded=len(tickets), failed=0, duration_ms=1
            ),
        )

    monkeypatch.setattr(analysis_routes, "analyze_tickets", fake_analyze)

    async def send_requests():
        transport = httpx.ASGITransport(app=app_module.app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
            payload = {"tickets": [valid_ticket()]}
            return await asyncio.gather(
                c.post("/api/analyze", json=payload),
                c.post("/api/analyze", json=payload),
            )

    responses = asyncio.run(send_requests())

    assert [response.status_code for response in responses] == [200, 200]
    assert len(calls) == 1
    assert all(response.json()["results"][0]["id"] == 1 for response in responses)


def test_gemini_limiter_uses_forwarded_client_ip_and_retry_after(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    monkeypatch.setattr(rate_limiting, "GEMINI_RATE_LIMIT", 1)
    monkeypatch.setattr(analysis_routes, "CACHE_PATH", tmp_path / "analysis_cache.json")

    async def fake_analyze(tickets):
        return BatchResult(
            results=[successful_result(ticket.id) for ticket in tickets],
            summary=BatchSummary(total=1, succeeded=1, failed=0, duration_ms=1),
        )

    monkeypatch.setattr(analysis_routes, "analyze_tickets", fake_analyze)
    payload = {"tickets": [valid_ticket()]}
    with TestClient(app_module.app) as test_client:
        first = test_client.post(
            "/api/analyze",
            json=payload,
            headers={"X-Forwarded-For": "198.51.100.10, 10.0.0.1"},
        )
        limited = test_client.post(
            "/api/analyze",
            json=payload,
            headers={"X-Forwarded-For": "198.51.100.10, 10.0.0.2"},
        )
        other_ip = test_client.post(
            "/api/analyze",
            json=payload,
            headers={"X-Forwarded-For": "198.51.100.11, 10.0.0.1"},
        )

    assert first.status_code == 200
    assert limited.status_code == 429
    assert int(limited.headers["retry-after"]) > 0
    assert other_ip.status_code == 200


def test_generic_read_limiter_returns_retry_after(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(rate_limiting, "RATE_LIMIT", 1)
    assert client.get("/api/health").status_code == 200
    limited = client.get("/api/health")
    assert limited.status_code == 429
    assert int(limited.headers["retry-after"]) > 0


def test_lazy_genai_client_is_reused(monkeypatch: pytest.MonkeyPatch) -> None:
    created = []
    fake_client = object()

    def create_client(*, api_key):
        created.append(api_key)
        return fake_client

    monkeypatch.setattr(llm_ticket, "_client", None)
    monkeypatch.setattr(llm_ticket.genai, "Client", create_client)

    assert llm_ticket._get_client("test-key") is fake_client
    assert llm_ticket._get_client("test-key") is fake_client
    assert created == ["test-key"]


def test_suggested_reply_is_bounded_and_defaults_for_failures() -> None:
    with pytest.raises(ValidationError):
        TicketAnalysisItem.model_validate(
            {
                **valid_analysis().model_dump(),
                "suggested_reply": "x" * 601,
            }
        )

    failed = llm_ticket._failure_result(Ticket(**valid_ticket()), "provider error")
    assert failed.suggested_reply == ""


def test_legacy_cache_without_content_hashes_is_ignored(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    cache_path = tmp_path / "analysis_cache.json"
    cache_path.write_text(
        BatchResult(
            results=[successful_result()],
            summary=BatchSummary(total=1, succeeded=1, failed=0, duration_ms=1),
        ).model_dump_json(),
        encoding="utf-8",
    )
    monkeypatch.setattr(analysis_routes, "CACHE_PATH", cache_path)

    assert analysis_routes._load_analysis_cache() == {}


def test_content_cache_returns_results_in_caller_order(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    monkeypatch.setattr(analysis_routes, "CACHE_PATH", tmp_path / "analysis_cache.json")

    async def fake_analyze(tickets):
        return BatchResult(
            results=[
                successful_result(ticket.id).model_copy(
                    update={"reasoning": ticket.message}
                )
                for ticket in reversed(tickets)
            ],
            summary=BatchSummary(
                total=len(tickets), succeeded=len(tickets), failed=0, duration_ms=1
            ),
        )

    monkeypatch.setattr(analysis_routes, "analyze_tickets", fake_analyze)
    tickets = [
        Ticket(**valid_ticket(2, "Second")),
        Ticket(**valid_ticket(1, "First")),
    ]

    result = asyncio.run(analysis_routes._run_analysis(tickets))

    assert [item.id for item in result.results] == [2, 1]
    assert [item.reasoning for item in result.results] == ["Second", "First"]


@pytest.mark.parametrize("status", ["ok", "failed"])
def test_cache_seed_writes_only_when_all_results_succeed(
    monkeypatch: pytest.MonkeyPatch, status: str
) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "mock-key")
    ticket = Ticket(**valid_ticket())
    result_item = successful_result(ticket.id)
    if status == "failed":
        result_item = result_item.model_copy(update={"status": "failed"})
    batch = BatchResult(
        results=[result_item],
        summary=BatchSummary(
            total=1,
            succeeded=int(status == "ok"),
            failed=int(status == "failed"),
            duration_ms=1,
        ),
    )
    writes = []

    async def fake_analyze(_tickets):
        return batch

    monkeypatch.setattr(build_cache, "load_sample_tickets", lambda _path: [ticket])
    monkeypatch.setattr(build_cache, "validate_tickets", lambda tickets: tickets)
    monkeypatch.setattr(build_cache, "analyze_tickets", fake_analyze)
    monkeypatch.setattr(
        build_cache,
        "_write_analysis_cache",
        lambda results, hashes: writes.append((results, hashes)),
    )

    exit_code = build_cache.main()

    assert exit_code == int(status == "failed")
    assert len(writes) == int(status == "ok")
