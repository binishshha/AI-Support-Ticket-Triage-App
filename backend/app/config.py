import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_PATH = BASE_DIR / "data" / "support_tickets.json"
CACHE_PATH = BASE_DIR / "data" / "analysis_cache.json"
RATE_LIMIT = int(os.environ.get("RATE_LIMIT_PER_MINUTE", "60"))
GEMINI_RATE_LIMIT = int(os.environ.get("GEMINI_RATE_LIMIT_PER_MINUTE", "3"))

ALLOWED_ORIGINS = [
    origin.strip()
    for origin in os.environ.get(
        "ALLOWED_ORIGINS",
        "http://localhost:5173,http://127.0.0.1:5173",
    ).split(",")
    if origin.strip()
]
