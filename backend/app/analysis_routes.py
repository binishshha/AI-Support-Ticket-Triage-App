import asyncio
import hashlib
import json
import logging
import math
import os
from tempfile import NamedTemporaryFile
from time import perf_counter
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import ValidationError

try:
    from ..llm_ticket import (
        AuthenticationError,
        QuotaExceededError,
        ServiceUnavailableError,
        analyze_tickets,
    )
    from .schemas import BatchResult, Ticket, TicketResult
except ImportError:
    from llm_ticket import (
        AuthenticationError,
        QuotaExceededError,
        ServiceUnavailableError,
        analyze_tickets,
    )
    from schemas import BatchResult, Ticket, TicketResult

from .config import CACHE_PATH, DATA_PATH
from .models import BatchRequest
from .rate_limiting import gemini_rate_limit, rate_limit
from .validation import validate_tickets

router = APIRouter()

_analysis_lock = asyncio.Lock()
logger = logging.getLogger(__name__)


def _provider_error() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail="The analysis provider is temporarily unavailable.",
    )


def _load_analysis_cache() -> dict[str, TicketResult]:
    """
    Load valid analysis results from the local cache.

    Failed results are retained for display, but are retried on the next
    analysis request.
    """
    if not CACHE_PATH.exists():
        return {}

    try:
        with CACHE_PATH.open(encoding="utf-8") as cache_file:
            cached_data = json.load(cache_file)

        if not isinstance(cached_data, dict):
            logger.warning("Analysis cache has an invalid root structure.")
            return {}

        cached_by_hash: dict[str, TicketResult] = {}
        old_hashes = cached_data.get("ticket_hashes", {})

        for item in cached_data.get("results", []):
            if not isinstance(item, dict):
                continue
            try:
                cached_result = TicketResult.model_validate(item)
            except ValidationError as error:
                logger.warning(
                    "Ignoring invalid cached ticket result: %s",
                    error,
                )
                continue

            content_hash = item.get("message_hash")
            if not isinstance(content_hash, str) and isinstance(old_hashes, dict):
                content_hash = old_hashes.get(str(cached_result.id))
                if not isinstance(content_hash, str):
                    content_hash = old_hashes.get(cached_result.id)
            if isinstance(content_hash, str):
                cached_by_hash[content_hash] = cached_result

        return cached_by_hash

    except (
        OSError,
        json.JSONDecodeError,
        TypeError,
        AttributeError,
    ) as error:
        logger.warning(
            "Ignoring unreadable analysis cache: %s",
            error,
        )
        return {}


def _ticket_hash(ticket: Ticket) -> str:
    return hashlib.sha256(ticket.message.encode("utf-8")).hexdigest()


def _write_analysis_cache(
    results: list[TicketResult],
    ticket_hashes: dict[int, str],
) -> None:
    """
    Save analysis results to analysis_cache.json.

    The file is written atomically using a temporary file so that
    a partially-written cache is not left behind if the process stops.
    """
    existing_results = _load_analysis_cache()

    for result in results:
        content_hash = ticket_hashes.get(result.id)
        if content_hash:
            existing_results[content_hash] = result

    cached_entries = [
        {"message_hash": content_hash, **result.model_dump()}
        for content_hash, result in existing_results.items()
    ]

    failed = sum(result.status == "failed" for result in existing_results.values())
    cache_data = {
        "results": cached_entries,
        "summary": {
            "total": len(cached_entries),
            "succeeded": len(cached_entries) - failed,
            "failed": failed,
            "duration_ms": 0,
        },
    }

    CACHE_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    temporary_path: str | None = None

    try:
        with NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=CACHE_PATH.parent,
            prefix="analysis_cache.",
            suffix=".tmp",
            delete=False,
        ) as cache_file:
            temporary_path = cache_file.name

            json.dump(cache_data, cache_file, indent=2, ensure_ascii=False)

            cache_file.flush()
            os.fsync(cache_file.fileno())

        os.replace(
            temporary_path,
            CACHE_PATH,
        )

    finally:
        if temporary_path and os.path.exists(temporary_path):
            os.unlink(temporary_path)


async def _run_analysis(
    tickets: list[Ticket],
) -> BatchResult:
    """
    Analyze only tickets that are not already successfully cached.

    This is the main quota-saving mechanism.

    Example:

        20 tickets
        15 cached
        5 uncached

    Only the 5 uncached tickets are sent to Gemini.
    """

    started = perf_counter()

    if not tickets:
        return BatchResult(
            results=[],
            summary={
                "total": 0,
                "succeeded": 0,
                "failed": 0,
                "duration_ms": 0,
            },
        )

    current_hashes = {ticket.id: _ticket_hash(ticket) for ticket in tickets}
    cached_results = _load_analysis_cache()

    def uncached_tickets(cache: dict[str, TicketResult]) -> list[Ticket]:
        pending_by_hash: dict[str, Ticket] = {}
        for ticket in tickets:
            content_hash = current_hashes[ticket.id]
            cached = cache.get(content_hash)
            if cached is None or cached.status != "ok":
                pending_by_hash.setdefault(content_hash, ticket)
        return list(pending_by_hash.values())

    tickets_to_analyze = uncached_tickets(cached_results)
    new_results: list[TicketResult] = []

    if tickets_to_analyze:
        async with _analysis_lock:
            cached_results = _load_analysis_cache()
            tickets_to_analyze = uncached_tickets(cached_results)

            logger.info(
                "Analysis request: %d tickets, %d cached, %d sent to Gemini.",
                len(tickets),
                len(tickets) - len(tickets_to_analyze),
                len(tickets_to_analyze),
            )

            if tickets_to_analyze:
                ticket_hash_by_id = {
                    ticket.id: current_hashes[ticket.id]
                    for ticket in tickets_to_analyze
                }
                try:
                    result = await analyze_tickets(tickets_to_analyze)

                except QuotaExceededError as error:
                    retry_after = error.retry_after_seconds
                    headers = (
                        {"Retry-After": str(max(1, retry_after))}
                        if retry_after is not None
                        else None
                    )
                    if retry_after is None:
                        detail = "AI quota reached. Please try again later."
                    elif retry_after < 3600:
                        detail = (
                            "AI rate limit reached. Try again in "
                            f"{max(1, retry_after)} seconds."
                        )
                    else:
                        hours = max(1, math.ceil(retry_after / 3600))
                        detail = f"Daily AI quota reached. Try again in {hours} hours."

                    raise HTTPException(
                        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                        detail=detail,
                        headers=headers,
                    ) from error

                except AuthenticationError as error:
                    logger.warning(
                        "Gemini authentication failed: %s",
                        error.__cause__ or error,
                    )

                    raise HTTPException(
                        status_code=error.status_code,
                        detail="Gemini authentication failed.",
                    ) from error

                except ServiceUnavailableError as error:
                    logger.exception(
                        "Analysis provider failure: %s",
                        error.__cause__ or error,
                    )

                    raise _provider_error() from error

                new_results = result.results

                try:
                    _write_analysis_cache(
                        new_results,
                        ticket_hash_by_id,
                    )

                except OSError as error:
                    logger.exception("Analysis completed but cache could not be saved.")

                    raise HTTPException(
                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        detail=(
                            "Analysis completed, but its results " "could not be saved."
                        ),
                    ) from error

            cached_results = _load_analysis_cache()

    # Return results in the same order as the requested tickets.
    final_results: list[TicketResult] = []

    for ticket in tickets:
        cached = cached_results.get(current_hashes[ticket.id])
        if cached is not None:
            final_results.append(cached.model_copy(update={"id": ticket.id}))

    failed = sum(result.status == "failed" for result in final_results)

    duration_ms = round((perf_counter() - started) * 1000)

    return BatchResult(
        results=final_results,
        summary={
            "total": len(final_results),
            "succeeded": len(final_results) - failed,
            "failed": failed,
            "duration_ms": duration_ms,
        },
    )


@router.post("/api/analyze", dependencies=[Depends(gemini_rate_limit)])
async def analyze(
    request: BatchRequest,
) -> BatchResult:
    """
    Analyze a batch of tickets.

    Cached successful results are reused.
    Only new tickets are sent to Gemini.
    """
    tickets_to_analyze = validate_tickets(request.tickets)

    return await _run_analysis(tickets_to_analyze)


@router.get("/api/analysis", dependencies=[Depends(rate_limit)])
async def analysis() -> dict[str, Any]:
    """
    Return the current analysis cache.

    This endpoint NEVER calls Gemini.
    """

    if not CACHE_PATH.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Analysis cache not found.",
        )

    try:
        with CACHE_PATH.open(encoding="utf-8") as cache_file:
            cached_data = json.load(cache_file)
        if not isinstance(cached_data, dict):
            raise ValueError("Analysis cache root must be an object.")

        with DATA_PATH.open(encoding="utf-8") as tickets_file:
            source_tickets = [
                Ticket.model_validate(item) for item in json.load(tickets_file)
            ]

        results_by_hash = _load_analysis_cache()
        results = [
            results_by_hash[_ticket_hash(ticket)]
            .model_copy(update={"id": ticket.id})
            .model_dump()
            for ticket in source_tickets
            if _ticket_hash(ticket) in results_by_hash
        ]
        failed = sum(result["status"] == "failed" for result in results)
        cache_summary = cached_data.get("summary")
        duration_ms = (
            cache_summary.get("duration_ms", 0)
            if isinstance(cache_summary, dict)
            else 0
        )
        return {
            "results": results,
            "summary": {
                "total": len(results),
                "succeeded": len(results) - failed,
                "failed": failed,
                "duration_ms": duration_ms,
            },
        }

    except (
        OSError,
        json.JSONDecodeError,
        TypeError,
        ValueError,
    ) as error:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Analysis cache is invalid.",
        ) from error
