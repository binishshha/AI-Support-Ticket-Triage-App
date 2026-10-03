import {
  ALL_CATEGORIES,
  ALL_REVIEW,
  ALL_SENTIMENT,
  ALL_URGENCY,
  sentimentRank,
  urgencyRank,
} from "../constants";
import { isAnalyzedTicket, ticketReviewStatus } from "./ticketAnalytics";

const compareIds = (a, b) =>
  String(a.id).localeCompare(String(b.id), undefined, { numeric: true });

function compareBy(sortKey, a, b, workflowById) {
  if (sortKey === "id") return compareIds(a, b);
  if (sortKey === "urgency") {
    return (urgencyRank[a.urgency] ?? 4) - (urgencyRank[b.urgency] ?? 4);
  }
  if (sortKey === "sentiment") {
    return (
      (sentimentRank[a.sentiment] ?? 4) - (sentimentRank[b.sentiment] ?? 4)
    );
  }
  if (sortKey === "category") {
    return (a.category || "").localeCompare(b.category || "");
  }
  if (sortKey === "review") {
    const rank = {
      pending_review: 0,
      reviewed: 1,
      routine: 2,
      not_analyzed: 3,
    };
    return (
      rank[ticketReviewStatus(a, workflowById)] -
      rank[ticketReviewStatus(b, workflowById)]
    );
  }
  return 0;
}

export function uniqueValues(tickets, key) {
  return [...new Set(tickets.map((t) => t[key]).filter(Boolean))].sort();
}

export function filterAndSortTickets(tickets, filters, workflowById = {}) {
  const { search, urgency, category, sentiment, review, sortKey, descending } =
    filters;
  const term = search.trim().toLowerCase();

  const filtered = tickets
    .filter((t) => urgency === ALL_URGENCY || t.urgency === urgency)
    .filter((t) => category === ALL_CATEGORIES || t.category === category)
    .filter((t) => sentiment === ALL_SENTIMENT || t.sentiment === sentiment)
    .filter(
      (ticket) =>
        review === ALL_REVIEW ||
        ticketReviewStatus(ticket, workflowById) === review,
    )
    .filter(
      (t) =>
        !term ||
        `${t.id} ${t.message} ${t.category || ""}`.toLowerCase().includes(term),
    );
  if (sortKey === "original") return filtered;

  const isAiSort = ["urgency", "category", "sentiment"].includes(sortKey);
  return filtered
    .map((ticket, index) => ({ ticket, index }))
    .sort((a, b) => {
      if (
        isAiSort &&
        isAnalyzedTicket(a.ticket) !== isAnalyzedTicket(b.ticket)
      ) {
        return isAnalyzedTicket(a.ticket) ? -1 : 1;
      }
      const comparison = compareBy(sortKey, a.ticket, b.ticket, workflowById);
      if (comparison) return comparison * (descending ? -1 : 1);
      if (sortKey !== "id") {
        return a.index - b.index;
      }
      return a.index - b.index;
    })
    .map(({ ticket }) => ticket);
}
