import { useCallback, useMemo, useState } from "react";
import { DEFAULT_FILTERS } from "../constants";
import { filterAndSortTickets, uniqueValues } from "../lib/filterTickets";

export function useTicketFilters(tickets, workflowById = {}) {
  const [filters, setFilters] = useState(DEFAULT_FILTERS);

  const setFilter = useCallback(
    (name, value) => setFilters((f) => ({ ...f, [name]: value })),
    [],
  );

  const setSort = useCallback(
    (sortKey, descending) => setFilters((f) => ({ ...f, sortKey, descending })),
    [],
  );

  const clearFilters = useCallback(() => setFilters(DEFAULT_FILTERS), []);

  const toggleSort = useCallback((key) => {
    setFilters((f) =>
      f.sortKey === key
        ? { ...f, descending: !f.descending }
        : { ...f, sortKey: key, descending: false },
    );
  }, []);

  const categories = useMemo(
    () => uniqueValues(tickets, "category"),
    [tickets],
  );
  const sentiments = useMemo(
    () => uniqueValues(tickets, "sentiment"),
    [tickets],
  );
  const visibleTickets = useMemo(
    () => filterAndSortTickets(tickets, filters, workflowById),
    [tickets, filters, workflowById],
  );

  return {
    filters,
    setFilter,
    setSort,
    clearFilters,
    toggleSort,
    categories,
    sentiments,
    visibleTickets,
  };
}
