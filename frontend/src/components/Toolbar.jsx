import { useEffect, useRef, useState } from "react";
import {
  ALL_CATEGORIES,
  ALL_SENTIMENT,
  ALL_URGENCY,
  CATEGORY_LEVELS,
  REVIEW_FILTERS,
  SENTIMENT_LEVELS,
  URGENCY_LEVELS,
} from "../constants";

export default function Toolbar({
  filters,
  setFilter,
  clearFilters,
  resultCount,
  totalCount,
}) {
  const [filtersOpen, setFiltersOpen] = useState(false);
  const filterTriggerRef = useRef(null);
  const filterSheetRef = useRef(null);
  const activeFilters = [
    filters.search && ["search", `Search: ${filters.search}`],
    filters.urgency !== ALL_URGENCY && ["urgency", filters.urgency],
    filters.category !== ALL_CATEGORIES && ["category", filters.category],
    filters.sentiment !== ALL_SENTIMENT && ["sentiment", filters.sentiment],
    filters.review !== REVIEW_FILTERS[0].value && [
      "review",
      REVIEW_FILTERS.find((item) => item.value === filters.review)?.label,
    ],
  ].filter(Boolean);

  function resetFilter(name) {
    const defaults = {
      search: "",
      urgency: ALL_URGENCY,
      category: ALL_CATEGORIES,
      sentiment: ALL_SENTIMENT,
      review: REVIEW_FILTERS[0].value,
    };
    setFilter(name, defaults[name]);
  }

  useEffect(() => {
    if (!filtersOpen) return undefined;
    const previousFocus = document.activeElement;
    const filterTrigger = filterTriggerRef.current;
    const focusable = filterSheetRef.current?.querySelectorAll(
      'button:not([disabled]), input, select, [tabindex]:not([tabindex="-1"])',
    );
    focusable?.[0]?.focus();

    function handleKeyDown(event) {
      if (event.key === "Escape") {
        setFiltersOpen(false);
        return;
      }
      if (event.key !== "Tab" || !focusable?.length) return;
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    }

    document.addEventListener("keydown", handleKeyDown);
    return () => {
      document.removeEventListener("keydown", handleKeyDown);
      (filterTrigger || previousFocus)?.focus?.();
    };
  }, [filtersOpen]);

  return (
    <section className="list-controls" aria-label="Ticket filters">
      <div className="filter-summary">
        <span>
          {resultCount} of {totalCount} tickets
        </span>
        <button
          ref={filterTriggerRef}
          className="mobile-filter-trigger"
          type="button"
          onClick={() => setFiltersOpen(true)}
          aria-expanded={filtersOpen}
          aria-label={`Open filters${activeFilters.length ? `, ${activeFilters.length} active` : ""}`}
        >
          Filters{activeFilters.length ? ` (${activeFilters.length})` : ""}
        </button>
        {activeFilters.length > 0 && (
          <div className="filter-chips" aria-label="Active filters">
            {activeFilters.map(([name, label]) => (
              <button
                aria-label={`Remove filter ${label}`}
                className="filter-chip"
                key={name}
                onClick={() => resetFilter(name)}
                type="button"
              >
                {label} <span aria-hidden="true">×</span>
              </button>
            ))}
            <button
              className="clear-filters"
              onClick={clearFilters}
              type="button"
            >
              Clear all
            </button>
          </div>
        )}
      </div>
      {filtersOpen && (
        <button
          className="filter-sheet-backdrop"
          aria-label="Close filters"
          onClick={() => setFiltersOpen(false)}
          type="button"
        />
      )}
      <div
        ref={filterSheetRef}
        className={`filter-sheet${filtersOpen ? " is-open" : ""}`}
        role={filtersOpen ? "dialog" : undefined}
        aria-modal={filtersOpen ? "true" : undefined}
        aria-label={filtersOpen ? "Ticket filters" : undefined}
      >
        <header className="filter-sheet-header">
          <h2>Filters</h2>
          <button
            type="button"
            onClick={() => setFiltersOpen(false)}
            aria-label="Close filters"
          >
            Close
          </button>
        </header>
        <div className="toolbar">
          <label className="search-field">
            <span className="sr-only">Search tickets</span>
            <input
              type="search"
              value={filters.search}
              onChange={(e) => setFilter("search", e.target.value)}
              placeholder="Search tickets"
              aria-label="Search tickets"
            />
          </label>
          <select
            value={filters.urgency}
            onChange={(e) => setFilter("urgency", e.target.value)}
            aria-label="Filter by urgency"
          >
            <option>{ALL_URGENCY}</option>
            {URGENCY_LEVELS.map((value) => (
              <option key={value}>{value}</option>
            ))}
          </select>
          <select
            value={filters.category}
            onChange={(e) => setFilter("category", e.target.value)}
            aria-label="Filter by category"
          >
            <option>{ALL_CATEGORIES}</option>
            {CATEGORY_LEVELS.map((value) => (
              <option key={value}>{value}</option>
            ))}
          </select>
          <select
            value={filters.sentiment}
            onChange={(e) => setFilter("sentiment", e.target.value)}
            aria-label="Filter by sentiment"
          >
            <option>{ALL_SENTIMENT}</option>
            {SENTIMENT_LEVELS.map((value) => (
              <option key={value}>{value}</option>
            ))}
          </select>
          <select
            value={filters.review}
            onChange={(event) => setFilter("review", event.target.value)}
            aria-label="Filter by review status"
          >
            {REVIEW_FILTERS.map((item) => (
              <option key={item.value} value={item.value}>
                {item.label}
              </option>
            ))}
          </select>
        </div>
        <div className="filter-sheet-actions">
          <button type="button" onClick={clearFilters}>
            Clear all
          </button>
          <button
            className="filter-done"
            type="button"
            onClick={() => setFiltersOpen(false)}
          >
            Show {resultCount} tickets
          </button>
        </div>
      </div>
    </section>
  );
}
