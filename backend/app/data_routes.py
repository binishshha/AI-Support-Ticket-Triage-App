import json
from typing import Any

from fastapi import APIRouter, HTTPException

from .config import CACHE_PATH, DATA_PATH

router = APIRouter()


@router.get("/api/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/api/tickets")
async def tickets() -> list[dict[str, Any]]:
    try:
        with DATA_PATH.open(encoding="utf-8") as tickets_file:
            return json.load(tickets_file)
    except (OSError, json.JSONDecodeError) as error:
        raise HTTPException(
            status_code=500, detail="Ticket data is unavailable."
        ) from error


@router.get("/api/analysis")
async def analysis() -> dict[str, Any]:
    if not CACHE_PATH.exists():
        raise HTTPException(status_code=404, detail="Analysis cache not found.")
    try:
        with CACHE_PATH.open(encoding="utf-8") as cache_file:
            return json.load(cache_file)
    except (OSError, json.JSONDecodeError) as error:
        raise HTTPException(
            status_code=500, detail="Analysis cache is invalid."
        ) from error
