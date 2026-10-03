import { useCallback, useEffect, useRef, useState } from "react";
import {
  analyzeTickets,
  describeError,
  fetchTickets,
  mergeResults,
} from "../api";

export function useTickets() {
  const [tickets, setTickets] = useState([]);
  const [loading, setLoading] = useState(true);
  const [analyzing, setAnalyzing] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [cooldownUntil, setCooldownUntil] = useState(0);
  const [cooldownSeconds, setCooldownSeconds] = useState(0);
  const controllerRef = useRef(null);
  const requestInFlightRef = useRef(false);

  useEffect(() => {
    if (!cooldownUntil) return undefined;
    const interval = window.setInterval(() => {
      const remaining = Math.max(
        0,
        Math.ceil((cooldownUntil - Date.now()) / 1000),
      );
      setCooldownSeconds(remaining);
      if (!remaining) setCooldownUntil(0);
    }, 1000);
    return () => window.clearInterval(interval);
  }, [cooldownUntil]);

  const refresh = useCallback(async () => {
    if (requestInFlightRef.current) return;
    requestInFlightRef.current = true;
    const controller = new AbortController();
    controllerRef.current = controller;
    setLoading(true);
    setError("");
    setNotice("");
    try {
      const data = await fetchTickets(controller.signal);
      if (!controller.signal.aborted) setTickets(data);
    } catch (requestError) {
      if (requestError.name !== "AbortError") {
        setError(describeError(requestError));
      }
    } finally {
      if (controllerRef.current === controller) setLoading(false);
      requestInFlightRef.current = false;
    }
  }, []);

  useEffect(() => {
    const initialLoad = window.setTimeout(refresh, 0);
    return () => {
      window.clearTimeout(initialLoad);
      controllerRef.current?.abort();
    };
  }, [refresh]);

  const analyze = useCallback(async () => {
    if (requestInFlightRef.current) return;
    requestInFlightRef.current = true;
    setAnalyzing(true);
    setError("");
    setNotice("");
    try {
      const results = await analyzeTickets(tickets);
      const analyzed = results.filter((r) => r.status !== "failed");
      setTickets((current) => mergeResults(current, analyzed));
      if (results.some((result) => result.status === "failed")) {
        setCooldownUntil(Date.now() + 30_000);
        setCooldownSeconds(30);
      }
      const analyzedIds = new Set(results.map((r) => r.id));
      const missing = tickets.filter((t) => !analyzedIds.has(t.id)).length;
      if (missing > 0) {
        setNotice(
          `${missing} ticket${missing === 1 ? " was" : "s were"} not analyzed and may show older results.`,
        );
      }
    } catch (requestError) {
      const keyHint = [401, 403].includes(requestError.status)
        ? "Check the backend's GEMINI_API_KEY."
        : "";
      setError(describeError(requestError, keyHint));
      const seconds = Math.max(30, Number(requestError.retryAfter) || 0);
      setCooldownUntil(Date.now() + seconds * 1000);
      setCooldownSeconds(seconds);
    } finally {
      setAnalyzing(false);
      requestInFlightRef.current = false;
    }
  }, [tickets]);

  return {
    tickets,
    loading,
    analyzing,
    error,
    notice,
    cooldownSeconds,
    refresh,
    analyze,
  };
}
