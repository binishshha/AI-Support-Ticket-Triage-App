import math
import time
from collections import defaultdict, deque

from fastapi import HTTPException, Request

from .config import GEMINI_RATE_LIMIT, RATE_LIMIT

_rate_windows: dict[str, deque[float]] = defaultdict(deque)
_gemini_rate_windows: dict[str, deque[float]] = defaultdict(deque)


def _client_ip(request: Request) -> str:
    forwarded_for = request.headers.get("x-forwarded-for", "")
    if forwarded_for.strip():
        forwarded_ip = forwarded_for.split(",", maxsplit=1)[0].strip()
        if forwarded_ip:
            return forwarded_ip
    return request.client.host if request.client else "unknown"


def _check_rate_limit(
    request: Request,
    windows: dict[str, deque[float]],
    limit: int,
) -> None:
    now = time.monotonic()
    window = windows[_client_ip(request)]
    while window and now - window[0] >= 60:
        window.popleft()
    if len(window) >= limit:
        retry_after = max(1, math.ceil(60 - (now - window[0])))
        raise HTTPException(
            status_code=429,
            detail="Rate limit exceeded.",
            headers={"Retry-After": str(retry_after)},
        )
    window.append(now)


def rate_limit(request: Request) -> None:
    _check_rate_limit(request, _rate_windows, RATE_LIMIT)


def gemini_rate_limit(request: Request) -> None:
    _check_rate_limit(request, _gemini_rate_windows, GEMINI_RATE_LIMIT)
