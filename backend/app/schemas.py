from typing import Literal

from pydantic import BaseModel, Field

Category = Literal["Billing", "Technical", "Account", "Feedback", "Other"]
Urgency = Literal["Critical", "High", "Medium", "Low"]
Sentiment = Literal["Angry", "Frustrated", "Neutral", "Happy"]
Confidence = Literal["High", "Medium", "Low"]
AnalysisStatus = Literal["ok", "failed"]


class Ticket(BaseModel):
    id: int
    message: str


class TicketAnalysis(BaseModel):
    """Structured analysis for one ticket."""

    reasoning: str = Field(
        description="One concise sentence grounded in the ticket message."
    )
    category: Category
    urgency: Urgency
    sentiment: Sentiment
    confidence: Confidence
    suggested_reply: str = Field(default="", max_length=600)


class TicketResult(BaseModel):
    id: int
    reasoning: str
    category: Category
    urgency: Urgency
    sentiment: Sentiment
    confidence: Confidence
    status: AnalysisStatus
    error: str | None = None
    suggested_reply: str = Field(default="", max_length=600)


class BatchSummary(BaseModel):
    total: int
    succeeded: int
    failed: int
    duration_ms: int


class BatchResult(BaseModel):
    results: list[TicketResult]
    summary: BatchSummary
