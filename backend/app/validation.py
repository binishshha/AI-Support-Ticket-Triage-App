from fastapi import HTTPException

from .schemas import Ticket

MAX_TICKETS_PER_BATCH = 25
MAX_TOTAL_CHARS = 25_000


def validate_tickets(tickets: list[Ticket]) -> list[Ticket]:
    if not tickets:
        raise HTTPException(status_code=422, detail="At least one ticket is required.")
    if len(tickets) > MAX_TICKETS_PER_BATCH:
        raise HTTPException(
            status_code=422,
            detail=f"A batch cannot contain more than {MAX_TICKETS_PER_BATCH} tickets.",
        )

    ids = [ticket.id for ticket in tickets]
    if len(ids) != len(set(ids)):
        raise HTTPException(status_code=422, detail="Ticket ids must be unique.")
    for ticket in tickets:
        if not ticket.message.strip():
            raise HTTPException(
                status_code=422, detail="Ticket messages cannot be blank."
            )
        if len(ticket.message) > 2000:
            raise HTTPException(
                status_code=422, detail="Ticket messages cannot exceed 2000 characters."
            )
    if sum(len(ticket.message) for ticket in tickets) > MAX_TOTAL_CHARS:
        raise HTTPException(
            status_code=422,
            detail=f"Ticket messages cannot exceed {MAX_TOTAL_CHARS} characters combined.",
        )
    return tickets
