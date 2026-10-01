from pydantic import BaseModel, ConfigDict

try:
    from ..schema import Ticket
except ImportError:
    from schema import Ticket


class BatchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tickets: list[Ticket]