from fastapi import HTTPException

try:
    from ..schema import Ticket
except ImportError:
    from schema import Ticket


def validate_tickets(tickets: list[Ticket]) -> list[Ticket]:
    if not tickets:
        raise HTTPException(status_code=422, detail="At least one ticket is required.")
    if len(tickets) > 50:
        raise HTTPException(
            status_code=422, detail="A maximum of 50 tickets is allowed."
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
    return tickets