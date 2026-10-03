export class ApiError extends Error {
  constructor(message, status, retryAfter = 0) {
    super(message);
    this.name = "ApiError";
    this.status = status; // 0 means the server could not be reached
    this.retryAfter = retryAfter;
  }
}

async function request(url, options) {
  try {
    return await fetch(url, options);
  } catch (error) {
    if (error.name === "AbortError") throw error;
    throw new ApiError("Could not reach the server.", 0);
  }
}

export function mergeResults(tickets, results = []) {
  const resultsById = new Map(results.map((result) => [result.id, result]));
  return tickets.map((ticket) => ({
    ...ticket,
    ...resultsById.get(ticket.id),
  }));
}

export async function fetchTickets(signal) {
  const ticketResponse = await request("/api/tickets", { signal });
  if (!ticketResponse.ok) {
    throw new ApiError(
      `Ticket request failed (${ticketResponse.status}).`,
      ticketResponse.status,
    );
  }
  const tickets = await ticketResponse.json();

  const analysisResponse = await request("/api/analysis", { signal });
  if (analysisResponse.status === 404) return tickets;
  if (!analysisResponse.ok) {
    throw new ApiError(
      `Analysis request failed (${analysisResponse.status}).`,
      analysisResponse.status,
    );
  }
  const analysis = await analysisResponse.json();
  return mergeResults(tickets, analysis.results);
}

export async function analyzeTickets(tickets) {
  const response = await request("/api/analyze", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      tickets: tickets.map(({ id, message }) => ({ id, message })),
    }),
  });
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    const retryAfter = Number(response.headers.get("Retry-After")) || 0;
    throw new ApiError(
      body.detail || `Analysis failed (${response.status}).`,
      response.status,
      retryAfter,
    );
  }
  const body = await response.json();
  return body.results || [];
}

// Only add a hint when it is actually likely to help.
export function describeError(error, serverHint = "") {
  if (error.status === 0) {
    return `${error.message} Check that the backend is running on port 8000.`;
  }
  if ([401, 403].includes(error.status) && serverHint) {
    return `${error.message} ${serverHint}`;
  }
  return error.message;
}
