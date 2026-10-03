from pydantic import BaseModel, ConfigDict

from .schemas import Ticket


class BatchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tickets: list[Ticket]
