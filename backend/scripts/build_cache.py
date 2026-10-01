import asyncio
import os
from pathlib import Path
from tempfile import NamedTemporaryFile

try:
    from backend.llm_ticket import analyze_tickets, load_sample_tickets
except ImportError:
    try:
        from ..llm_ticket import analyze_tickets, load_sample_tickets
    except ImportError:
        from llm_ticket import analyze_tickets, load_sample_tickets

BASE_DIR = Path(__file__).resolve().parents[1]
DATA_PATH = BASE_DIR / "data" / "support_tickets.json"
CACHE_PATH = BASE_DIR / "data" / "analysis_cache.json"


async def build_cache() -> None:
    result = await analyze_tickets(load_sample_tickets(str(DATA_PATH)))
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


if __name__ == "__main__":
    asyncio.run(build_cache())
