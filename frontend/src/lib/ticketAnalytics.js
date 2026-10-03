import {
  CATEGORY_LEVELS,
  SENTIMENT_LEVELS,
  URGENCY_LEVELS,
} from "../constants";

export function isAnalyzedTicket(ticket) {
  return Boolean(
    ticket.status !== "failed" &&
    ticket.category &&
    ticket.urgency &&
    ticket.sentiment &&
    ticket.confidence,
  );
}

export function needsAttention(ticket) {
  return Boolean(
    isAnalyzedTicket(ticket) &&
    (ticket.urgency === "Critical" ||
      ticket.confidence === "Low" ||
      ticket.needs_human_review === true),
  );
}

export function attentionReasons(ticket) {
  if (!needsAttention(ticket)) return [];
  const reasons = [];
  if (ticket.urgency === "Critical") reasons.push("Critical urgency");
  if (ticket.confidence === "Low") reasons.push("Low AI confidence");
  if (ticket.needs_human_review === true) {
    reasons.push("Flagged for human review");
  }
  return reasons;
}

export function ticketReviewStatus(ticket, workflowById = {}) {
  if (!isAnalyzedTicket(ticket)) return "not_analyzed";
  if (!needsAttention(ticket)) return "routine";
  return workflowById[ticket.id]?.reviewed ? "reviewed" : "pending_review";
}

export function summarizeTickets(tickets, workflowById = {}) {
  const analyzed = tickets.filter(isAnalyzedTicket);
  const flagged = analyzed.filter(needsAttention);
  const reviewed = flagged.filter(
    (ticket) => workflowById[ticket.id]?.reviewed,
  ).length;
  const breakdown = (key, values) =>
    values.map((value) => {
      const count = analyzed.filter((ticket) => ticket[key] === value).length;
      return {
        value,
        count,
        percent: analyzed.length
          ? Math.round((count / analyzed.length) * 100)
          : 0,
      };
    });

  return {
    total: tickets.length,
    analyzed: analyzed.length,
    criticalHigh: analyzed.filter((ticket) =>
      ["Critical", "High"].includes(ticket.urgency),
    ).length,
    needsReview: flagged.length - reviewed,
    reviewed,
    flagged: flagged.length,
    reviewProgress: flagged.length
      ? Math.round((reviewed / flagged.length) * 100)
      : 0,
    categories: breakdown("category", CATEGORY_LEVELS),
    urgencies: breakdown("urgency", URGENCY_LEVELS),
    sentiments: breakdown("sentiment", SENTIMENT_LEVELS),
  };
}

export function reviewState(ticket) {
  if (!isAnalyzedTicket(ticket)) return "not_analyzed";
  return ticket.needs_human_review === true ? "review" : "ok";
}
