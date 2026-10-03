import asyncio
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.app.analysis_routes import _ticket_hash, _write_analysis_cache
from backend.app.config import DATA_PATH
from backend.app.validation import validate_tickets
from backend.llm_ticket import analyze_tickets, load_sample_tickets


def main() -> int:
    if not os.environ.get("GEMINI_API_KEY", "").strip():
        print("GEMINI_API_KEY is required to seed the analysis cache.", file=sys.stderr)
        return 1

    try:
        tickets = validate_tickets(load_sample_tickets(str(DATA_PATH)))
        result = asyncio.run(analyze_tickets(tickets))
    except Exception as error:
        print(f"Cache build failed: {error}", file=sys.stderr)
        return 1

    if len(result.results) != len(tickets) or any(
        item.status != "ok" for item in result.results
    ):
        print(
            "Cache build returned incomplete or failed analyses; cache unchanged.",
            file=sys.stderr,
        )
        return 1

    hashes = {ticket.id: _ticket_hash(ticket) for ticket in tickets}
    _write_analysis_cache(result.results, hashes)
    print(
        f"Saved {len(result.results)} analyses to {PROJECT_ROOT / 'backend/data/analysis_cache.json'}."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
