import time
from collections import defaultdict, deque

from fastapi import HTTPException, Request

from .config import RATE_LIMIT

_rate_windows: dict[str, deque[float]] = defaultdict(deque)


def rate_limit(request: Request) -> None:
    client_host = request.client.host if request.client else "unknown"
    now = time.monotonic()
    window = _rate_windows[client_host]
    while window and now - window[0] >= 60:
        window.popleft()
    if len(window) >= RATE_LIMIT:
        raise HTTPException(status_code=429, detail="Rate limit exceeded.")
    window.append(now)