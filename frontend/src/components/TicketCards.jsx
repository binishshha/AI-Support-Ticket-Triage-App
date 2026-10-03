import Tag from "./Tag";
import { ticketReviewStatus } from "../lib/ticketAnalytics";

export default function TicketCards({
  tickets,
  onSelect,
  workflowById = {},
  onMarkReviewed,
}) {
  return (
    <div className="mobile-list">
      {tickets.map((ticket) => {
        const review = ticketReviewStatus(ticket, workflowById);
        return (
          <article
            className="ticket-card"
            key={ticket.id}
            role="button"
            tabIndex={0}
            onClick={() => onSelect(ticket.id)}
            onKeyDown={(event) => {
              if (event.target !== event.currentTarget) return;
              if (event.key === "Enter" || event.key === " ") {
                event.preventDefault();
                onSelect(ticket.id);
              }
            }}
          >
            <div className="card-heading">
              <strong>#{ticket.id}</strong>
              <Tag kind="category" value={ticket.category} />
              <span
                className={`analysis-status ${ticket.status || "not-analyzed"}`}
              >
                {ticket.status === "failed"
                  ? "Failed"
                  : ticket.status === "ok"
                    ? "Analyzed"
                    : "Not analyzed"}
              </span>
              {workflowById[ticket.id]?.sent && (
                <Tag kind="sent" value="Sent" />
              )}
            </div>
            <p>{ticket.message}</p>
            <div className="card-tags">
              <Tag kind="urgency" value={ticket.urgency} />
              <Tag kind="sentiment" value={ticket.sentiment} />
              {review === "pending_review" ? (
                <>
                  <Tag kind="review" value="Pending review" />
                  <button
                    className="quick-review"
                    type="button"
                    onClick={(event) => {
                      event.stopPropagation();
                      onMarkReviewed?.(ticket.id);
                    }}
                  >
                    Mark reviewed
                  </button>
                </>
              ) : review === "reviewed" ? (
                <span className="reviewed-label">
                  <span aria-hidden="true">✓</span> Reviewed
                </span>
              ) : review === "routine" ? (
                <Tag kind="review" value="Routine" />
              ) : (
                <Tag kind="review" value="Not analyzed" />
              )}
            </div>
          </article>
        );
      })}
    </div>
  );
}
