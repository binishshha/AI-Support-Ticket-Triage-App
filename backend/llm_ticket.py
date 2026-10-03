import asyncio
import json
import math
import os
import time
from collections.abc import Sequence
from typing import Any

from google import genai
from google.genai import types
from pydantic import RootModel, ValidationError

try:
    from .prompts import SYSTEM_PROMPT
    from .app.schemas import (
        BatchResult,
        BatchSummary,
        Ticket,
        TicketAnalysis,
        TicketResult,
    )
except ImportError:
    from prompts import SYSTEM_PROMPT
    from app.schemas import (
        BatchResult,
        BatchSummary,
        Ticket,
        TicketAnalysis,
        TicketResult,
    )


REQUEST_TIMEOUT_SECONDS = 90
MAX_TRANSIENT_RETRIES = 1
RETRY_BACKOFF_SECONDS = (3,)
_client: genai.Client | None = None


def _get_client(api_key: str) -> genai.Client:
    global _client
    if _client is None:
        _client = genai.Client(api_key=api_key)
    return _client


class ServiceUnavailableError(RuntimeError):
    """The provider cannot serve the request with the current credentials/quota."""


class QuotaExceededError(ServiceUnavailableError):
    """Provider quota or rate limit exhausted."""

    def __init__(
        self,
        message: str,
        retry_after_seconds: int | None = None,
    ) -> None:
        super().__init__(message)
        self.retry_after_seconds = retry_after_seconds


class AuthenticationError(ServiceUnavailableError):
    """Gemini rejected the configured credentials or permissions."""

    def __init__(self, message: str, status_code: int = 401) -> None:
        super().__init__(message)
        self.status_code = status_code


class TransientProviderError(RuntimeError):
    """The provider returned a retryable server error."""


class InvalidAnalysisError(ValueError):
    """The provider returned no valid structured analysis."""


class TicketAnalysisItem(TicketAnalysis):
    id: int


class TicketAnalysisList(RootModel[list[TicketAnalysisItem]]):
    pass


def _status_code(error: BaseException) -> int | None:
    for attribute in ("status_code", "code", "status"):
        value = getattr(error, attribute, None)

        try:
            return int(value)
        except (TypeError, ValueError):
            continue

    return None


def _is_quota_error(error: BaseException) -> bool:
    message = str(error).lower()

    return (
        _status_code(error) == 429
        or "resource_exhausted" in message
        or "quota" in message
    )


def _retry_after_seconds(error: BaseException) -> int | None:
    details = getattr(error, "details", None)
    if not isinstance(details, dict):
        return None

    error_details = details.get("error", details)
    if not isinstance(error_details, dict):
        return None

    for detail in error_details.get("details", []):
        if not isinstance(detail, dict) or not str(detail.get("@type", "")).endswith(
            "RetryInfo"
        ):
            continue

        retry_delay = detail.get("retryDelay")
        if isinstance(retry_delay, str) and retry_delay.endswith("s"):
            try:
                return max(0, math.ceil(float(retry_delay[:-1])))
            except ValueError:
                return None

    return None


def _is_auth_error(error: BaseException) -> bool:
    status_code = _status_code(error)
    message = str(error).lower()

    return (
        status_code in {401, 403}
        or "api key" in message
        or "api_key" in message
        or "permission_denied" in message
    )


def _failure_result(ticket: Ticket, error: str) -> TicketResult:
    return TicketResult(
        id=ticket.id,
        reasoning="Analysis failed before a reliable classification was produced.",
        category="Other",
        urgency="High",
        sentiment="Neutral",
        confidence="Low",
        status="failed",
        error=error,
    )


def _success_result(
    ticket: Ticket,
    analysis: TicketAnalysisItem,
) -> TicketResult:
    fields = analysis.model_dump(exclude={"id", "status", "error"})

    return TicketResult(
        id=ticket.id,
        **fields,
        status="ok",
        error=None,
    )


async def _request_analysis(
    client: genai.Client,
    tickets: Sequence[Ticket],
    model: str,
) -> list[TicketAnalysisItem]:

    ticket_payload = json.dumps(
        [
            {
                "id": ticket.id,
                "message": ticket.message,
            }
            for ticket in tickets
        ],
        ensure_ascii=False,
    )

    try:
        response = await asyncio.wait_for(
            client.aio.models.generate_content(
                model=model,
                contents=("Tickets:\n" f"{ticket_payload}"),
                config=types.GenerateContentConfig(
                    system_instruction=SYSTEM_PROMPT,
                    temperature=0.1,
                    response_mime_type="application/json",
                    response_schema=TicketAnalysisList,
                    thinking_config=types.ThinkingConfig(thinking_level="low"),
                ),
            ),
            timeout=REQUEST_TIMEOUT_SECONDS,
        )

    except asyncio.TimeoutError:
        raise

    except Exception as error:
        if _is_quota_error(error):
            raise QuotaExceededError(
                "Gemini quota or rate limit exhausted.",
                _retry_after_seconds(error),
            ) from error

        if _is_auth_error(error):
            status_code = _status_code(error)

            if status_code not in {401, 403}:
                status_code = 403 if "permission_denied" in str(error).lower() else 401

            raise AuthenticationError(
                "Gemini authentication or permission failure.",
                status_code,
            ) from error

        if _status_code(error) == 503:
            raise TransientProviderError(
                "Gemini is temporarily unavailable (HTTP 503)."
            ) from error

        # Do not hide unexpected provider/programming errors.
        raise

    parsed = getattr(response, "parsed", None)
    response_text = getattr(response, "text", None)

    # ---------------------------------------------------------
    # PARSE STRUCTURED RESPONSE
    # ---------------------------------------------------------

    if parsed is None:

        if not response_text:
            raise InvalidAnalysisError("The API returned no structured analyses.")

        try:
            analyses = TicketAnalysisList.model_validate_json(response_text).root

        except ValidationError as error:
            raise InvalidAnalysisError(
                "The API returned invalid structured analysis."
            ) from error

    else:

        try:
            analyses = TicketAnalysisList.model_validate(parsed).root

        except ValidationError as error:
            raise InvalidAnalysisError(
                "The API returned invalid structured analysis."
            ) from error

    # ---------------------------------------------------------
    # VALIDATE TICKET IDs
    # ---------------------------------------------------------

    ticket_ids = [ticket.id for ticket in tickets]

    analysis_ids = [analysis.id for analysis in analyses]

    if len(analysis_ids) != len(ticket_ids):
        raise InvalidAnalysisError(
            "The API did not return exactly one analysis per ticket."
        )

    if set(analysis_ids) != set(ticket_ids):
        raise InvalidAnalysisError(
            "The API returned analyses for the wrong ticket IDs."
        )

    if len(analysis_ids) != len(set(analysis_ids)):
        raise InvalidAnalysisError("The API returned duplicate ticket analyses.")

    return analyses


async def analyze_tickets(
    tickets: Sequence[Ticket],
    client: genai.Client | None = None,
    model: str | None = None,
) -> BatchResult:

    started = time.perf_counter()

    tickets = list(tickets)

    if not tickets:
        return BatchResult(
            results=[],
            summary=BatchSummary(
                total=0,
                succeeded=0,
                failed=0,
                duration_ms=0,
            ),
        )

    # ---------------------------------------------------------
    # GEMINI CLIENT
    # ---------------------------------------------------------

    api_key = os.environ.get(
        "GEMINI_API_KEY",
        "",
    ).strip()

    if client is None and not api_key:
        raise ServiceUnavailableError("GEMINI_API_KEY is not configured.")

    try:
        active_client = client or _get_client(api_key)

    except Exception as error:

        if _is_quota_error(error):
            raise QuotaExceededError("Gemini quota or rate limit exhausted.") from error

        if _is_auth_error(error) or "credential" in str(error).lower():
            status_code = _status_code(error)

            if status_code not in {401, 403}:
                status_code = 403 if "permission_denied" in str(error).lower() else 401

            raise AuthenticationError(
                "Gemini authentication or permission failure.",
                status_code,
            ) from error

        raise

    active_model = model or os.environ.get("GEMINI_MODEL", "gemini-3.8-flash")

    analyses: list[TicketAnalysisItem] | None = None
    last_error = "The provider returned an error while analyzing the tickets."

    for attempt in range(MAX_TRANSIENT_RETRIES + 1):
        try:
            analyses = await _request_analysis(
                active_client,
                tickets,
                active_model,
            )
            break

        except (QuotaExceededError, AuthenticationError):
            raise

        except asyncio.TimeoutError:
            last_error = "The provider timed out while analyzing the tickets."
            break

        except TransientProviderError as error:
            last_error = str(error)
            if attempt < MAX_TRANSIENT_RETRIES:
                await asyncio.sleep(RETRY_BACKOFF_SECONDS[attempt])

        except InvalidAnalysisError as error:
            last_error = str(error)
            break

    if analyses is None:
        results = [_failure_result(ticket, last_error) for ticket in tickets]
    else:
        analyses_by_id = {analysis.id: analysis for analysis in analyses}
        results = [
            _success_result(ticket, analyses_by_id[ticket.id]) for ticket in tickets
        ]

    failed = sum(result.status == "failed" for result in results)

    return BatchResult(
        results=results,
        summary=BatchSummary(
            total=len(results),
            succeeded=len(results) - failed,
            failed=failed,
            duration_ms=round((time.perf_counter() - started) * 1000),
        ),
    )


def load_sample_tickets(path: str) -> list[Ticket]:

    with open(
        path,
        encoding="utf-8",
    ) as tickets_file:

        raw_tickets: Any = json.load(tickets_file)

    return [Ticket.model_validate(ticket) for ticket in raw_tickets]
