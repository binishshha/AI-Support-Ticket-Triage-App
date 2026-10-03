import { useMemo } from "react";
import {
  ALL_CATEGORIES,
  ALL_REVIEW,
  ALL_SENTIMENT,
  ALL_URGENCY,
  TICKET_PALETTE,
} from "../constants";
import { summarizeTickets } from "../lib/ticketAnalytics";

function Breakdown({ title, kind, items, filter, setFilter }) {
  const allValues = {
    category: ALL_CATEGORIES,
    urgency: ALL_URGENCY,
    sentiment: ALL_SENTIMENT,
  };

  return (
    <section className="breakdown" aria-label={`${title} breakdown`}>
      <h3>{title}</h3>
      <div className="breakdown-rows">
        {items.map(({ value, count, percent }) => {
          const active = filter === value;
          const color = TICKET_PALETTE[kind][value].ink;
          return (
            <button
              aria-pressed={active}
              className={`breakdown-row${active ? " is-active" : ""}`}
              key={value}
              onClick={() => setFilter(kind, active ? allValues[kind] : value)}
              type="button"
            >
              <span className="breakdown-label">{value}</span>
              <span aria-hidden="true" className="breakdown-track">
                <span
                  className="breakdown-fill"
                  style={{ width: `${percent}%`, backgroundColor: color }}
                />
              </span>
              <span className="breakdown-value">
                {count} <small>{percent}%</small>
              </span>
            </button>
          );
        })}
      </div>
    </section>
  );
}

export default function AnalyticsPanel({
  tickets,
  filters,
  setFilter,
  workflowById = {},
}) {
  const stats = useMemo(
    () => summarizeTickets(tickets, workflowById),
    [tickets, workflowById],
  );

  return (
    <section className="analytics" aria-label="Batch analytics">
      <div className="analytics-heading">
        <div>
          <p className="section-kicker">BATCH OVERVIEW</p>
          <h2>Ticket insights</h2>
        </div>
        <span className="analytics-subtitle">
          {stats.analyzed} of {stats.total} analyzed
        </span>
      </div>

      <div className="stat-grid">
        <article className="stat-card">
          <span>Total tickets</span>
          <strong>{stats.total}</strong>
        </article>
        <article className="stat-card">
          <span>Analyzed</span>
          <strong>{stats.analyzed}</strong>
        </article>
        <article
          className="stat-card stat-attention"
          style={{ "--stat-color": TICKET_PALETTE.urgency.High.ink }}
        >
          <span>Critical + High</span>
          <strong>{stats.criticalHigh}</strong>
        </article>
        <button
          className="stat-card stat-review"
          style={{
            "--stat-color": TICKET_PALETTE.review["Pending review"].ink,
          }}
          type="button"
          aria-pressed={filters.review === "pending_review"}
          onClick={() =>
            setFilter(
              "review",
              filters.review === "pending_review"
                ? ALL_REVIEW
                : "pending_review",
            )
          }
        >
          <span>Needs review</span>
          <strong>{stats.needsReview}</strong>
          <span className="stat-secondary">{stats.reviewed} reviewed</span>
          <span
            className="review-progress-track"
            role="meter"
            aria-label="Reviewed flagged tickets"
            aria-valuemin={0}
            aria-valuemax={Math.max(1, stats.flagged)}
            aria-valuenow={stats.reviewed}
          >
            <span style={{ width: `${stats.reviewProgress}%` }} />
          </span>
          <span className="stat-progress-label">
            Reviewed {stats.reviewed} of {stats.flagged} flagged
          </span>
        </button>
      </div>

      {stats.analyzed === 0 ? (
        <p className="analytics-empty">Run Analyze with AI to see insights.</p>
      ) : (
        <div className="breakdown-grid">
          <Breakdown
            title="Category"
            kind="category"
            items={stats.categories}
            filter={filters.category}
            setFilter={setFilter}
          />
          <Breakdown
            title="Urgency"
            kind="urgency"
            items={stats.urgencies}
            filter={filters.urgency}
            setFilter={setFilter}
          />
          <Breakdown
            title="Sentiment"
            kind="sentiment"
            items={stats.sentiments}
            filter={filters.sentiment}
            setFilter={setFilter}
          />
        </div>
      )}
    </section>
  );
}
