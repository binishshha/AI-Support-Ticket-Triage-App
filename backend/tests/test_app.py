import asyncio
import json
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from backend import app as app_module
from backend.app import analysis_routes, data_routes
from backend.llm_ticket import ServiceUnavailableError, analyze_one
from backend.schema import (
    BatchResult,
    BatchSummary,
    Ticket,
    TicketAnalysis,
    TicketResult,
)

client = TestClient(app_module.app)


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
        needs_human_review=False,
        suggested_reply="An agent can review this request.",
        status="ok",
    )


def test_health() -> None:
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_cache_present_and_missing(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    cache_path = tmp_path / "analysis_cache.json"
    monkeypatch.setattr(data_routes, "CACHE_PATH", cache_path)
    assert client.get("/api/analysis").status_code == 404

    cache_path.write_text(json.dumps({"results": [], "summary": {}}), encoding="utf-8")
    response = client.get("/api/analysis")
    assert response.status_code == 200
    assert response.json()["results"] == []


def test_validation_rejects_invalid_batches() -> None:
    cases = [
        {"tickets": []},
        {"tickets": [valid_ticket(index) for index in range(51)]},
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


def test_partial_failure(monkeypatch: pytest.MonkeyPatch) -> None:
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
                    needs_human_review=True,
                    suggested_reply="This ticket needs human review before a response is sent.",
                    status="failed",
                    error="invalid output",
                ),
            ],
            summary=BatchSummary(total=2, succeeded=1, failed=1, duration_ms=2),
        )

    monkeypatch.setattr(analysis_routes, "analyze_tickets", fake_analyze)
    response = client.post(
        "/api/analyze", json={"tickets": [valid_ticket(), valid_ticket(2)]}
    )
    assert response.status_code == 200
    assert response.json()["summary"]["failed"] == 1
    assert response.json()["results"][1]["urgency"] == "High"


def test_auth_error_returns_503(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_analyze(tickets):
        raise ServiceUnavailableError("OpenAI authentication failure")

    monkeypatch.setattr(analysis_routes, "analyze_tickets", fake_analyze)
    response = client.post("/api/analyze/ticket", json=valid_ticket())
    assert response.status_code == 503
    assert (
        response.json()["detail"] == "The analysis provider is temporarily unavailable."
    )


class FakeResponses:
    def __init__(self, outputs):
        self.outputs = iter(outputs)
        self.calls = 0

    async def parse(self, **kwargs):
        self.calls += 1
        output = next(self.outputs)
        if isinstance(output, BaseException):
            raise output
        return SimpleNamespace(output_parsed=output)


class FakeClient:
    def __init__(self, outputs):
        self.responses = FakeResponses(outputs)


def valid_analysis() -> TicketAnalysis:
    return TicketAnalysis(
        reasoning="The user asks for account help.",
        category="Account",
        urgency="Medium",
        sentiment="Neutral",
        confidence="High",
        needs_human_review=False,
        suggested_reply="An agent can review this request.",
    )


def test_retry_then_success() -> None:
    fake_client = FakeClient([asyncio.TimeoutError(), valid_analysis()])
    result = asyncio.run(
        analyze_one(
            fake_client, Ticket(**valid_ticket()), asyncio.Semaphore(5), "test-model"
        )
    )
    assert result.status == "ok"
    assert fake_client.responses.calls == 2


def test_invalid_output_retries_once_then_fails() -> None:
    fake_client = FakeClient([SimpleNamespace(), SimpleNamespace()])
    result = asyncio.run(
        analyze_one(
            fake_client, Ticket(**valid_ticket()), asyncio.Semaphore(5), "test-model"
        )
    )
    assert result.status == "failed"
    assert result.urgency == "High"
    assert result.needs_human_review is True
    assert fake_client.responses.calls == 2
