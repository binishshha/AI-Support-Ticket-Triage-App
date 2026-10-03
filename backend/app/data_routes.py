import json
from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from .config import DATA_PATH
from .rate_limiting import rate_limit

router = APIRouter()


@router.get("/api/health", dependencies=[Depends(rate_limit)])
async def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/api/tickets", dependencies=[Depends(rate_limit)])
async def tickets() -> list[dict[str, Any]]:
    try:
        with DATA_PATH.open(encoding="utf-8") as tickets_file:
            return json.load(tickets_file)
    except (OSError, json.JSONDecodeError) as error:
        raise HTTPException(
            status_code=500, detail="Ticket data is unavailable."
        ) from error
