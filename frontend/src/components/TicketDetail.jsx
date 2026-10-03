import { useEffect, useRef, useState } from "react";
import Tag from "./Tag";
import { attentionReasons, needsAttention } from "../lib/ticketAnalytics";

const FOCUSABLE =
  'button:not([disabled]), input, select, [href], [tabindex]:not([tabindex="-1"])';

export default function TicketDetail({
  ticket,
  onClose,
  onPrevious,
  onNext,
  previousDisabled,
  nextDisabled,
  workflow,
  onDraftChange,
  onDraftReset,
  onSentChange,
  onReviewedChange,
}) {
  const [copied, setCopied] = useState(false);
  const [copyError, setCopyError] = useState("");
  const dialogRef = useRef(null);
  const copiedTimer = useRef(null);
  const aiReply = ticket.suggested_reply || "";
  const reply = workflow?.draft ?? aiReply;
  const draftEdited = Object.hasOwn(workflow || {}, "draft");
  const attention = needsAttention(ticket);
  const reasons = attentionReasons(ticket);

  // Move focus into the dialog, and hand it back when the dialog closes.
  useEffect(() => {
    const previous = document.activeElement;
    dialogRef.current?.focus();
    return () => previous?.focus?.();
  }, []);

  // Escape closes; Tab is kept inside the dialog.
  useEffect(() => {
    function onKeyDown(event) {
      if (event.key === "Escape") {
        onClose();
        return;
      }
      if (event.key !== "Tab" || !dialogRef.current) return;
      const items = dialogRef.current.querySelectorAll(FOCUSABLE);
      if (!items.length) return;
      const first = items[0];
      const last = items[items.length - 1];
      const active = document.activeElement;
      if (
        event.shiftKey &&
        (active === first || active === dialogRef.current)
      ) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && active === last) {
        event.preventDefault();
        first.focus();
      }
    }
    document.addEventListener("keydown", onKeyDown);
    return () => document.removeEventListener("keydown", onKeyDown);
  }, [onClose]);

  useEffect(() => () => window.clearTimeout(copiedTimer.current), []);

  async function copyReply() {
    try {
      await navigator.clipboard.writeText(reply);
      setCopied(true);
      setCopyError("");
      window.clearTimeout(copiedTimer.current);
      copiedTimer.current = window.setTimeout(() => setCopied(false), 2000);
    } catch {
      setCopied(false);
      setCopyError("Could not copy the reply. Select and copy it manually.");
    }
  }

  return (
    <div className="overlay" onMouseDown={onClose}>
      <aside
        ref={dialogRef}
        tabIndex={-1}
        className="detail"
        role="dialog"
        aria-modal="true"
        aria-label={`Ticket ${ticket.id}`}
        onMouseDown={(event) => event.stopPropagation()}
      >
        <header className="detail-head">
          <div className="detail-navigation" aria-label="Ticket navigation">
            <button
              type="button"
              onClick={onPrevious}
              disabled={previousDisabled}
              aria-label="Previous ticket"
            >
              Previous
            </button>
            <button
              type="button"
              onClick={onNext}
              disabled={nextDisabled}
              aria-label="Next ticket"
            >
              Next
            </button>
          </div>
          <h2>Ticket #{ticket.id}</h2>
          <button type="button" onClick={onClose} aria-label="Close details">
            Close
          </button>
        </header>
        <p className="tag-row">
          <Tag kind="urgency" value={ticket.urgency} />
          <Tag kind="sentiment" value={ticket.sentiment} />
          <Tag kind="category" value={ticket.category} />
          <Tag kind="confidence" value={ticket.confidence} />
          <span className={`workflow-badge${workflow?.sent ? " is-sent" : ""}`}>
            {workflow?.sent ? "Sent" : "Unsent"}
          </span>
          <span className={`analysis-status ${ticket.status || "pending"}`}>
            {ticket.status === "failed"
              ? "Analysis failed"
              : ticket.status === "ok"
                ? "Analyzed"
                : "Not analyzed"}
          </span>
        </p>
        {attention && (
          <section className="attention-panel" aria-label="Review required">
            <div>
              <strong>Needs review</strong>
              <p>{reasons.join(" · ")}</p>
            </div>
            {workflow?.reviewed ? (
              <div className="reviewed-state">
                <span>
                  ✓ Reviewed at{" "}
                  {new Date(workflow.reviewedAt).toLocaleTimeString([], {
                    hour: "numeric",
                    minute: "2-digit",
                  })}
                </span>
                <button type="button" onClick={() => onReviewedChange(false)}>
                  Undo
                </button>
              </div>
            ) : (
              <button
                className="review-action"
                type="button"
                onClick={() => onReviewedChange(true)}
              >
                Yes, I&apos;ve reviewed this
              </button>
            )}
          </section>
        )}
        <h3>Full message</h3>
        <p>{ticket.message}</p>
        <h3>
          AI reasoning{" "}
          <small>{ticket.confidence || "Pending"} confidence</small>
        </h3>
        <p>{ticket.reasoning || "AI analysis is not available yet."}</p>
        {ticket.status === "failed" && ticket.error && (
          <p className="analysis-error">{ticket.error}</p>
        )}
        <div className="reply-heading">
          <h3>Suggested reply</h3>
          {draftEdited && (
            <button type="button" onClick={onDraftReset}>
              Reset to AI draft
            </button>
          )}
        </div>
        <textarea
          aria-label="Suggested reply"
          rows={6}
          value={reply}
          onChange={(event) => onDraftChange(event.target.value)}
          placeholder="No suggested reply available."
        />
        <p className="reply-helper">
          Drafts are AI-generated. Review and edit before sending.
        </p>
        {copyError && (
          <p className="copy-error" role="alert">
            {copyError}
          </p>
        )}
        <div className="detail-action-bar">
          <button type="button" onClick={copyReply} disabled={!reply}>
            {copied ? "Copied" : "Copy reply"}
          </button>
          {workflow?.sent ? (
            <div className="sent-actions">
              <button type="button" disabled>
                Marked as sent
              </button>
              <button type="button" onClick={() => onSentChange(false)}>
                Undo
              </button>
            </div>
          ) : (
            <button
              className="primary-action"
              type="button"
              onClick={() => onSentChange(true)}
            >
              Mark as sent
            </button>
          )}
          {attention && !workflow?.reviewed && (
            <button type="button" onClick={() => onReviewedChange(true)}>
              Reviewed
            </button>
          )}
        </div>
      </aside>
    </div>
  );
}
