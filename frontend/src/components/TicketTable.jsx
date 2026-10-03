import Tag from "./Tag";
import { ticketReviewStatus } from "../lib/ticketAnalytics";

function SortHeader({ label, sortKey, active, descending, onToggle }) {
  const ariaSort = active ? (descending ? "descending" : "ascending") : "none";
  return (
    <th aria-sort={ariaSort}>
      <button className="sort" type="button" onClick={() => onToggle(sortKey)}>
        {label} {active ? (descending ? "↓" : "↑") : ""}
      </button>
    </th>
  );
}

export default function TicketTable({
  tickets,
  sortKey,
  descending,
  onToggleSort,
  onSelect,
  workflowById = {},
  onMarkReviewed,
}) {
  const header = (label, key) => (
    <SortHeader
      label={label}
      sortKey={key}
      active={sortKey === key}
      descending={descending}
      onToggle={onToggleSort}
    />
  );

  return (
    <div className="desktop-list">
      <table>
        <thead>
          <tr>
            {header("ID", "id")}
            <th>Ticket</th>
            {header("Category", "category")}
            {header("Urgency", "urgency")}
            {header("Sentiment", "sentiment")}
            {header("Review", "review")}
            <th>Status</th>
          </tr>
        </thead>
        <tbody>
          {tickets.map((ticket) => {
            const review = ticketReviewStatus(ticket, workflowById);
            return (
              <tr
                key={ticket.id}
                onClick={() => onSelect(ticket.id)}
                tabIndex={0}
                onKeyDown={(event) => {
                  if (event.target !== event.currentTarget) return;
                  if (event.key === "Enter" || event.key === " ") {
                    event.preventDefault(); // stop Space from scrolling the page
                    onSelect(ticket.id);
                  }
                }}
              >
                <td className="ticket-id">#{ticket.id}</td>
                <td>
                  <span className="message-preview">{ticket.message}</span>
                </td>
                <td>
                  <Tag
                    kind="category"
                    value={ticket.category || "Not analyzed"}
                  />
                </td>
                <td>
                  <Tag kind="urgency" value={ticket.urgency} />
                </td>
                <td>
                  <Tag kind="sentiment" value={ticket.sentiment} />
                </td>
                <td>
                  {review === "pending_review" ? (
                    <div className="review-cell-content">
                      <button
                        className="quick-review"
                        type="button"
                        aria-label={`Mark ticket ${ticket.id} reviewed`}
                        onClick={(event) => {
                          event.stopPropagation();
                          onMarkReviewed?.(ticket.id);
                        }}
                      >
                        Mark reviewed
                      </button>
                    </div>
                  ) : review === "reviewed" ? (
                    <span className="reviewed-label">
                      <span aria-hidden="true">✓</span> Reviewed
                    </span>
                  ) : review === "routine" ? (
                    <Tag kind="review" value="Routine" />
                  ) : (
                    <Tag kind="review" value="Not analyzed" />
                  )}
                </td>
                <td>
                  {workflowById[ticket.id]?.sent && (
                    <Tag kind="sent" value="Sent" />
                  )}
                  <span
                    className={`analysis-status ${ticket.status || "pending"}`}
                  >
                    {ticket.status === "failed"
                      ? "Failed"
                      : ticket.status === "ok"
                        ? "Analyzed"
                        : "Not analyzed"}
                  </span>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
