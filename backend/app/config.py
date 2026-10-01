import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_PATH = BASE_DIR / "data" / "support_tickets.json"
CACHE_PATH = BASE_DIR / "data" / "analysis_cache.json"
RATE_LIMIT = int(os.environ.get("RATE_LIMIT_PER_MINUTE", "60"))
ALLOWED_ORIGINS = [
    origin.strip()
    for origin in os.environ.get("ALLOWED_ORIGINS", "http://localhost:3000").split(",")
    if origin.strip()
]