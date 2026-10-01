import asyncio
import json
import os
from tempfile import NamedTemporaryFile

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import ValidationError

try:
    from ..llm_ticket import (
        ServiceUnavailableError,
        analyze_tickets,
        load_sample_tickets,
    )
    from ..schema import BatchResult, Ticket
except ImportError:
    from llm_ticket import ServiceUnavailableError, analyze_tickets, load_sample_tickets
    from schema import BatchResult, Ticket

from .config import CACHE_PATH, DATA_PATH
from .models import BatchRequest
from .rate_limiting import rate_limit
from .validation import validate_tickets

router = APIRouter()
_rerun_lock = asyncio.Lock()


def _provider_error() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail="The analysis provider is temporarily unavailable.",
    )


async def _run_analysis(tickets: list[Ticket]) -> BatchResult:
    try:
        return await analyze_tickets(tickets)
    except ServiceUnavailableError as error:
        raise _provider_error() from error


@router.post("/api/analyze", dependencies=[Depends(rate_limit)])
async def analyze(request: BatchRequest) -> BatchResult:
    tickets_to_analyze = validate_tickets(request.tickets)
    return await _run_analysis(tickets_to_analyze)


@router.post("/api/analyze/ticket", dependencies=[Depends(rate_limit)])
async def analyze_ticket(ticket: Ticket) -> BatchResult:
    validate_tickets([ticket])
    return await _run_analysis([ticket])


@router.post("/api/analyze/rerun", dependencies=[Depends(rate_limit)])
async def rerun() -> BatchResult:
    if _rerun_lock.locked():
        raise HTTPException(
            status_code=409, detail="A cache rebuild is already running."
        )
    async with _rerun_lock:
        try:
            sample_tickets = load_sample_tickets(str(DATA_PATH))
            result = await _run_analysis(validate_tickets(sample_tickets))
            CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
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
                    cache_file.write(result.model_dump_json(indent=2))
                    cache_file.flush()
                    os.fsync(cache_file.fileno())
                os.replace(temporary_path, CACHE_PATH)
            finally:
                if temporary_path and os.path.exists(temporary_path):
                    os.unlink(temporary_path)
            return result
        except (OSError, ValidationError, json.JSONDecodeError) as error:
            raise HTTPException(
                status_code=500, detail="Unable to rebuild analysis cache."
            ) from error
