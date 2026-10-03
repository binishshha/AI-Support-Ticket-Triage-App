export const URGENCY_LEVELS = ["Critical", "High", "Medium", "Low"];
export const CATEGORY_LEVELS = [
  "Billing",
  "Technical",
  "Account",
  "Feedback",
  "Other",
];
export const SENTIMENT_LEVELS = ["Angry", "Frustrated", "Neutral", "Happy"];
export const TICKET_PALETTE = {
  urgency: {
    Critical: { ink: "#a62e2e", wash: "#fde8e7" },
    High: { ink: "#a84e1f", wash: "#ffeddf" },
    Medium: { ink: "#8a6515", wash: "#fff5d5" },
    Low: { ink: "#26704f", wash: "#e4f3e8" },
  },
  sentiment: {
    Angry: { ink: "#a62e2e", wash: "#fde8e7" },
    Frustrated: { ink: "#a84e1f", wash: "#ffeddf" },
    Neutral: { ink: "#52616b", wash: "#e9eef1" },
    Happy: { ink: "#26704f", wash: "#e4f3e8" },
  },
  category: {
    Billing: { ink: "#7043a6", wash: "#f0e9fa" },
    Technical: { ink: "#176b81", wash: "#e4f3f7" },
    Account: { ink: "#465b9a", wash: "#e9edfa" },
    Feedback: { ink: "#9a4b75", wash: "#f8e9f1" },
    Other: { ink: "#52616b", wash: "#e9eef1" },
  },
  review: {
    "Pending review": { ink: "#a62e2e", wash: "#fde8e7" },
    Reviewed: { ink: "#26704f", wash: "#e4f3e8" },
    Routine: { ink: "#52616b", wash: "#e9eef1" },
    "Not analyzed": { ink: "#58666e", wash: "#edf1f2" },
  },
  sent: {
    Sent: { ink: "#26704f", wash: "#e4f3e8" },
    Unsent: { ink: "#52616b", wash: "#e9eef1" },
  },
  neutral: { value: { ink: "#58666e", wash: "#edf1f2" } },
};
export const urgencyRank = { Critical: 0, High: 1, Medium: 2, Low: 3 };
export const sentimentRank = { Angry: 0, Frustrated: 1, Neutral: 2, Happy: 3 };

export const ALL_URGENCY = "All urgency";
export const ALL_CATEGORIES = "All categories";
export const ALL_SENTIMENT = "All sentiment";
export const ALL_REVIEW = "all";
export const REVIEW_FILTERS = [
  { value: ALL_REVIEW, label: "All reviews" },
  { value: "pending_review", label: "Pending review" },
  { value: "reviewed", label: "Reviewed" },
  { value: "routine", label: "Routine" },
];

export const DEFAULT_FILTERS = {
  search: "",
  urgency: ALL_URGENCY,
  category: ALL_CATEGORIES,
  sentiment: ALL_SENTIMENT,
  review: ALL_REVIEW,
  sortKey: "original",
  descending: false,
};
