import { filterAndSortTickets, uniqueValues } from "../lib/filterTickets";
import { DEFAULT_FILTERS } from "../constants";
import {
  needsAttention,
  summarizeTickets,
  ticketReviewStatus,
} from "../lib/ticketAnalytics";

const tickets = [
  {
    id: 10,
    message: "Refund please",
    category: "Billing",
    urgency: "Low",
    sentiment: "Happy",
    confidence: "High",
    needs_human_review: false,
  },
  {
    id: 2,
    message: "App crashes on login",
    category: "Technical",
    urgency: "Critical",
    sentiment: "Angry",
    confidence: "High",
    needs_human_review: true,
  },
  {
    id: 3,
    message: "Where is my invoice?",
    category: "Billing",
    urgency: "Critical",
    sentiment: "Neutral",
    confidence: "Medium",
    needs_human_review: false,
  },
  { id: 4, message: "Not analyzed yet" },
];
const run = (overrides = {}) =>
  filterAndSortTickets(tickets, { ...DEFAULT_FILTERS, ...overrides }).map(
    (t) => t.id,
  );

describe("filterAndSortTickets", () => {
  it("preserves source order by default", () => {
    expect(run()).toEqual([10, 2, 3, 4]);
  });

  it("sorts by urgency, breaks ties by source order, and puts pending last", () => {
    expect(run({ sortKey: "urgency" })).toEqual([2, 3, 10, 4]);
  });

  it("keeps unanalysed tickets last in descending AI sorts", () => {
    expect(run({ sortKey: "urgency", descending: true })).toEqual([
      10, 2, 3, 4,
    ]);
  });

  it("sorts by numeric ID when selected", () => {
    expect(run({ sortKey: "id" })).toEqual([2, 3, 4, 10]);
  });

  it("filters to tickets explicitly needing human review", () => {
    const withReview = tickets.map((ticket) =>
      ticket.id === 2
        ? { ...ticket, confidence: "High", needs_human_review: true }
        : ticket,
    );
    expect(
      filterAndSortTickets(withReview, {
        ...DEFAULT_FILTERS,
        review: "pending_review",
      }).map((ticket) => ticket.id),
    ).toEqual([2]);
  });

  it("breaks ties numerically even when ids are strings", () => {
    const stringIds = [
      { id: "10", urgency: "High", message: "" },
      { id: "9", urgency: "High", message: "" },
    ];
    const ids = filterAndSortTickets(stringIds, {
      ...DEFAULT_FILTERS,
      sortKey: "id",
    }).map((t) => t.id);
    expect(ids).toEqual(["9", "10"]);
  });

  it("sorts by sentiment and category", () => {
    expect(run({ sortKey: "sentiment" })).toEqual([2, 3, 10, 4]);
    expect(run({ sortKey: "category" })).toEqual([10, 3, 2, 4]);
  });

  it("sorts review status with pending items first", () => {
    const workflow = { 3: { reviewed: true } };
    expect(
      filterAndSortTickets(
        tickets,
        {
          ...DEFAULT_FILTERS,
          sortKey: "review",
        },
        workflow,
      ).map((ticket) => ticket.id),
    ).toEqual([2, 3, 10, 4]);
  });

  it("filters by urgency, category and sentiment", () => {
    expect(run({ urgency: "Critical" })).toEqual([2, 3]);
    expect(run({ category: "Billing" })).toEqual([3, 10]);
    expect(run({ sentiment: "Angry" })).toEqual([2]);
  });

  it("searches id, message and category case-insensitively", () => {
    expect(run({ search: "  CRASHES " })).toEqual([2]);
    expect(run({ search: "billing" })).toEqual([3, 10]);
    expect(run({ search: "10" })).toEqual([10]);
  });

  it("returns nothing when filters conflict", () => {
    expect(run({ urgency: "Low", sentiment: "Angry" })).toEqual([]);
  });
});

describe("uniqueValues", () => {
  it("returns sorted unique non-empty values", () => {
    expect(uniqueValues(tickets, "category")).toEqual(["Billing", "Technical"]);
  });
});

describe("summarizeTickets", () => {
  it("excludes unanalyzed tickets and reports batch counts and percentages", () => {
    const summary = summarizeTickets([
      {
        id: 1,
        category: "Billing",
        urgency: "Critical",
        sentiment: "Angry",
        confidence: "High",
        needs_human_review: true,
      },
      {
        id: 2,
        category: "Billing",
        urgency: "Medium",
        sentiment: "Neutral",
        confidence: "Medium",
        needs_human_review: false,
      },
      {
        id: 4,
        category: "Technical",
        urgency: "Critical",
        sentiment: "Angry",
        confidence: "Low",
        needs_human_review: true,
        status: "failed",
      },
      { id: 3, message: "Not analyzed yet" },
    ]);

    expect(summary).toMatchObject({
      total: 4,
      analyzed: 2,
      criticalHigh: 1,
      needsReview: 1,
      reviewed: 0,
      flagged: 1,
    });
    expect(summary.categories[0]).toEqual({
      value: "Billing",
      count: 2,
      percent: 100,
    });
    expect(summary.urgencies[0]).toEqual({
      value: "Critical",
      count: 1,
      percent: 50,
    });
  });

  it("separates pending and reviewed attention counts", () => {
    const rows = [
      {
        id: 1,
        category: "Technical",
        urgency: "High",
        sentiment: "Neutral",
        confidence: "Low",
      },
      {
        id: 2,
        category: "Billing",
        urgency: "Critical",
        sentiment: "Frustrated",
        confidence: "High",
      },
    ];
    const summary = summarizeTickets(rows, { 1: { reviewed: true } });
    expect(summary).toMatchObject({
      flagged: 2,
      reviewed: 1,
      needsReview: 1,
      reviewProgress: 50,
    });
  });
});

describe("needsAttention", () => {
  it("uses critical urgency, low confidence, or AI review flag only for analyzed tickets", () => {
    expect(needsAttention(tickets[0])).toBe(false);
    expect(needsAttention(tickets[1])).toBe(true);
    expect(
      needsAttention({
        id: 7,
        category: "Billing",
        urgency: "High",
        sentiment: "Neutral",
        confidence: "Low",
        status: "ok",
      }),
    ).toBe(true);
    expect(
      needsAttention({
        id: 8,
        category: "Technical",
        urgency: "Critical",
        sentiment: "Neutral",
        confidence: "High",
        status: "failed",
      }),
    ).toBe(false);
  });

  it("maps local workflow to pending, reviewed, and routine states", () => {
    expect(ticketReviewStatus(tickets[1])).toBe("pending_review");
    expect(ticketReviewStatus(tickets[1], { 2: { reviewed: true } })).toBe(
      "reviewed",
    );
    expect(ticketReviewStatus(tickets[0])).toBe("routine");
    expect(ticketReviewStatus(tickets[3])).toBe("not_analyzed");
  });
});
