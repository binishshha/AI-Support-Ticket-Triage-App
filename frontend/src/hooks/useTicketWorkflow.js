import { useCallback, useEffect, useState } from "react";

const STORAGE_KEY = "ticket-support-workflow-v1";

function readWorkflow() {
  try {
    const saved = window.localStorage.getItem(STORAGE_KEY);
    const parsed = saved ? JSON.parse(saved) : {};
    return parsed && typeof parsed === "object" && !Array.isArray(parsed)
      ? parsed
      : {};
  } catch {
    return {};
  }
}

export function useTicketWorkflow() {
  const [workflowById, setWorkflowById] = useState(readWorkflow);

  useEffect(() => {
    try {
      window.localStorage.setItem(STORAGE_KEY, JSON.stringify(workflowById));
    } catch {
      // The workflow remains usable for this session if storage is unavailable.
    }
  }, [workflowById]);

  const setDraft = useCallback((ticketId, draft) => {
    setWorkflowById((current) => ({
      ...current,
      [ticketId]: { ...current[ticketId], draft },
    }));
  }, []);

  const resetDraft = useCallback((ticketId) => {
    setWorkflowById((current) => {
      const next = { ...current };
      const workflow = { ...next[ticketId] };
      delete workflow.draft;
      if (Object.keys(workflow).length) next[ticketId] = workflow;
      else delete next[ticketId];
      return next;
    });
  }, []);

  const setSent = useCallback((ticketId, sent) => {
    setWorkflowById((current) => ({
      ...current,
      [ticketId]: { ...current[ticketId], sent },
    }));
  }, []);

  const setReviewed = useCallback((ticketId, reviewed) => {
    setWorkflowById((current) => ({
      ...current,
      [ticketId]: {
        ...current[ticketId],
        reviewed,
        reviewedAt: reviewed ? Date.now() : null,
      },
    }));
  }, []);

  return { workflowById, setDraft, resetDraft, setSent, setReviewed };
}
