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
        description="1-2 sentences quoting the words in the message that decide the urgency."
    )
    category: Category
    urgency: Urgency
    sentiment: Sentiment
    confidence: Confidence
    needs_human_review: bool
    suggested_reply: str = ""
    status: AnalysisStatus = "ok"
    error: str | None = None


class TicketResult(BaseModel):
    id: int
    reasoning: str
    category: Category
    urgency: Urgency
    sentiment: Sentiment
    confidence: Confidence
    needs_human_review: bool
    suggested_reply: str
    status: AnalysisStatus
    error: str | None = None


class BatchSummary(BaseModel):
    total: int
    succeeded: int
    failed: int
    duration_ms: int


class BatchResult(BaseModel):
    results: list[TicketResult]
    summary: BatchSummary
