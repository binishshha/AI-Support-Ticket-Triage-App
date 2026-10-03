import { useCallback, useState } from "react";
import "./App.css";
import Toolbar from "./components/Toolbar";
import TicketTable from "./components/TicketTable";
import TicketCards from "./components/TicketCards";
import TicketDetail from "./components/TicketDetail";
import { useTickets } from "./hooks/useTickets";
import { useTicketFilters } from "./hooks/useTicketFilters";
import AnalyticsPanel from "./components/AnalyticsPanel";
import { useTicketWorkflow } from "./hooks/useTicketWorkflow";

function formatCooldown(seconds) {
  if (seconds >= 3600) {
    const hours = Math.floor(seconds / 3600);
    const minutes = Math.ceil((seconds % 3600) / 60);
    return `${hours}h ${minutes}m`;
  }
  if (seconds >= 60) {
    return `${Math.floor(seconds / 60)}m ${seconds % 60}s`;
  }
  return `${seconds}s`;
}

function App() {
  const {
    tickets,
    loading,
    analyzing,
    error,
    notice,
    cooldownSeconds,
    refresh,
    analyze,
  } = useTickets();
  const ticketWorkflow = useTicketWorkflow();
  const { filters, setFilter, clearFilters, toggleSort, visibleTickets } =
    useTicketFilters(tickets, ticketWorkflow.workflowById);

  // Store the id, not the ticket, so the panel always shows fresh data.
  const [selectedId, setSelectedId] = useState(null);
  const selectedIndex = visibleTickets.findIndex(
    (ticket) => ticket.id === selectedId,
  );
  const selected = selectedIndex >= 0 ? visibleTickets[selectedIndex] : null;
  const closeDetail = useCallback(() => setSelectedId(null), []);
  const moveSelection = useCallback(
    (offset) => {
      const ticket = visibleTickets[selectedIndex + offset];
      if (ticket) setSelectedId(ticket.id);
    },
    [selectedIndex, visibleTickets],
  );

  return (
    <main className="app">
      <header className="header">
        <div>
          <p className="eyebrow">TICKET SUPPORT</p>
          <h1>Support inbox</h1>
        </div>
        <div className="actions">
          <button
            type="button"
            onClick={refresh}
            disabled={loading || analyzing}
          >
            {loading ? "Loading…" : "Refresh"}
          </button>
          <button
            type="button"
            onClick={analyze}
            className={
              analyzing ? "analyze-button is-loading" : "analyze-button"
            }
            aria-busy={analyzing}
            disabled={
              !tickets.length || analyzing || loading || cooldownSeconds > 0
            }
          >
            {analyzing ? "Analyzing…" : "Analyze with AI"}
          </button>
        </div>
      </header>

      {error && (
        <p className="message error" role="alert">
          {error}
        </p>
      )}
      {notice && (
        <p className="message" role="status">
          {notice}
        </p>
      )}
      {cooldownSeconds > 0 && (
        <p className="message" role="status">
          Analyze again in {formatCooldown(cooldownSeconds)}.
        </p>
      )}
      {loading && tickets.length === 0 && (
        <section
          className="loading-skeleton"
          aria-label="Loading tickets"
          aria-busy="true"
        >
          <span className="sr-only">Loading tickets</span>
          <div className="skeleton-line skeleton-short" />
          <div className="skeleton-line" />
          <div className="skeleton-line" />
          <div className="skeleton-line skeleton-medium" />
        </section>
      )}
      {!loading && !error && tickets.length === 0 && (
        <p className="message">No tickets returned.</p>
      )}

      <Toolbar
        filters={filters}
        setFilter={setFilter}
        clearFilters={clearFilters}
        resultCount={visibleTickets.length}
        totalCount={tickets.length}
      />
      <AnalyticsPanel
        tickets={tickets}
        filters={filters}
        setFilter={setFilter}
        workflowById={ticketWorkflow.workflowById}
      />

      <section className="ticket-list" aria-label="Tickets">
        <TicketTable
          tickets={visibleTickets}
          workflowById={ticketWorkflow.workflowById}
          sortKey={filters.sortKey}
          descending={filters.descending}
          onToggleSort={toggleSort}
          onSelect={setSelectedId}
          onMarkReviewed={(ticketId) =>
            ticketWorkflow.setReviewed(ticketId, true)
          }
        />
        <TicketCards
          tickets={visibleTickets}
          workflowById={ticketWorkflow.workflowById}
          onSelect={setSelectedId}
          onMarkReviewed={(ticketId) =>
            ticketWorkflow.setReviewed(ticketId, true)
          }
        />
        {!loading && tickets.length > 0 && visibleTickets.length === 0 && (
          <p className="message">No tickets match these filters.</p>
        )}
      </section>

      {selected && (
        <TicketDetail
          key={selected.id}
          ticket={selected}
          onClose={closeDetail}
          onPrevious={() => moveSelection(-1)}
          onNext={() => moveSelection(1)}
          previousDisabled={selectedIndex <= 0}
          nextDisabled={selectedIndex >= visibleTickets.length - 1}
          workflow={ticketWorkflow.workflowById[selected.id]}
          onDraftChange={(draft) => ticketWorkflow.setDraft(selected.id, draft)}
          onDraftReset={() => ticketWorkflow.resetDraft(selected.id)}
          onSentChange={(sent) => ticketWorkflow.setSent(selected.id, sent)}
          onReviewedChange={(reviewed) =>
            ticketWorkflow.setReviewed(selected.id, reviewed)
          }
        />
      )}
    </main>
  );
}

export default App;
