import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import App from "../App";

const json = (body, status = 200, extraHeaders = {}) =>
  new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json", ...extraHeaders },
  });

const TICKETS = [
  { id: 1, message: "I was charged twice" },
  { id: 2, message: "The app keeps crashing" },
];

const ANALYSIS = {
  results: [
    {
      id: 1,
      category: "Billing",
      urgency: "High",
      sentiment: "Angry",
      confidence: "High",
      status: "ok",
      needs_human_review: true,
      reasoning: "Double charge.",
      suggested_reply:
        "Thanks for contacting us. We can review the duplicate charge.",
    },
    {
      id: 2,
      category: "Technical",
      urgency: "Critical",
      sentiment: "Frustrated",
      confidence: "Medium",
      status: "ok",
      needs_human_review: false,
      reasoning: "Crash loop.",
      suggested_reply: "Please share when the crashes started.",
    },
  ],
};

function mockApi({ analysis = null, analyze } = {}) {
  global.fetch = vi.fn(async (url) => {
    if (url === "/api/tickets") return json(TICKETS);
    if (url === "/api/analysis")
      return analysis ? json(analysis) : new Response(null, { status: 404 });
    if (url === "/api/analyze") return analyze();
    throw new Error(`Unexpected request: ${url}`);
  });
}

const table = () => screen.getByRole("table");
const openTicket = (user, element) => user.click(element);

describe("App", () => {
  it("shows tickets as Pending before analysis", async () => {
    mockApi();
    render(<App />);
    expect(
      await within(table()).findByText("I was charged twice"),
    ).toBeInTheDocument();
    expect(within(table()).getAllByText("Not analyzed").length).toBeGreaterThan(
      0,
    );
  });

  it("merges stored analysis results on load", async () => {
    mockApi({ analysis: ANALYSIS });
    render(<App />);
    await within(table()).findByText("I was charged twice");
    expect(within(table()).getByText("Billing")).toBeInTheDocument();
  });

  it("shows batch analytics and applies a chart selection to the list", async () => {
    mockApi({ analysis: ANALYSIS });
    const user = userEvent.setup();
    render(<App />);
    await within(table()).findByText("I was charged twice");

    const analytics = screen.getByRole("region", { name: "Batch analytics" });
    expect(within(analytics).getByText("Total tickets")).toBeInTheDocument();
    expect(within(analytics).getByText("Critical + High")).toBeInTheDocument();
    expect(within(analytics).getByText("Needs review")).toBeInTheDocument();
    await user.click(
      within(
        screen.getByRole("region", { name: "Category breakdown" }),
      ).getByRole("button", { name: /Billing/ }),
    );
    expect(screen.getByLabelText("Filter by category")).toHaveValue("Billing");
    expect(screen.getByText("1 of 2 tickets")).toBeInTheDocument();
  });

  it("filters by search text", async () => {
    mockApi();
    const user = userEvent.setup();
    render(<App />);
    await within(table()).findByText("I was charged twice");
    await user.type(screen.getByLabelText("Search tickets"), "crashing");
    expect(
      within(table()).queryByText("I was charged twice"),
    ).not.toBeInTheDocument();
    expect(
      within(table()).getByText("The app keeps crashing"),
    ).toBeInTheDocument();
    await user.clear(screen.getByLabelText("Search tickets"));
    await user.type(screen.getByLabelText("Search tickets"), "zzz");
    expect(
      screen.getByText("No tickets match these filters."),
    ).toBeInTheDocument();
  });

  it("marks the active sort column with aria-sort and toggles direction", async () => {
    mockApi({ analysis: ANALYSIS });
    const user = userEvent.setup();
    render(<App />);
    await within(table()).findByText("I was charged twice");
    const urgencyHeader = screen.getByRole("columnheader", {
      name: /urgency/i,
    });
    expect(urgencyHeader).toHaveAttribute("aria-sort", "ascending");
    await user.click(within(urgencyHeader).getByRole("button"));
    expect(urgencyHeader).toHaveAttribute("aria-sort", "descending");
  });

  it("opens a ticket with Enter or Space and closes it with Escape", async () => {
    mockApi();
    const user = userEvent.setup();
    render(<App />);
    const cell = await within(table()).findByText("I was charged twice");
    const row = cell.closest("tr");
    row.focus();
    await user.keyboard(" ");
    expect(
      screen.getByRole("dialog", { name: "Ticket 1" }),
    ).toBeInTheDocument();
    await user.keyboard("{Escape}");
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(row).toHaveFocus();
    await user.keyboard("{Enter}");
    expect(screen.getByRole("dialog")).toBeInTheDocument();
  });

  it("navigates through the currently visible tickets in the detail panel", async () => {
    mockApi({ analysis: ANALYSIS });
    const user = userEvent.setup();
    render(<App />);
    await openTicket(
      user,
      await within(table()).findByText("I was charged twice"),
    );

    expect(
      screen.getByRole("button", { name: "Previous ticket" }),
    ).toBeDisabled();
    await user.click(screen.getByRole("button", { name: "Next ticket" }));
    expect(
      screen.getByRole("dialog", { name: "Ticket 2" }),
    ).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Previous ticket" }));
    expect(
      screen.getByRole("dialog", { name: "Ticket 1" }),
    ).toBeInTheDocument();
  });

  it("updates an open detail panel when analysis finishes", async () => {
    const writeText = vi.fn().mockResolvedValue(undefined);
    Object.defineProperty(navigator, "clipboard", {
      configurable: true,
      value: { writeText },
    });
    mockApi({ analyze: async () => json(ANALYSIS) });
    const user = userEvent.setup();
    render(<App />);
    await openTicket(
      user,
      await within(table()).findByText("I was charged twice"),
    );
    const dialog = screen.getByRole("dialog");
    expect(
      within(dialog).getByText("AI analysis is not available yet."),
    ).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Analyze with AI" }));

    expect(
      await within(dialog).findByText("Double charge."),
    ).toBeInTheDocument();
    expect(
      within(dialog).getByText(ANALYSIS.results[0].suggested_reply),
    ).toBeInTheDocument();
    await user.click(
      within(dialog).getByRole("button", { name: "Copy reply" }),
    );
    expect(writeText).toHaveBeenCalledWith(ANALYSIS.results[0].suggested_reply);
  });

  it("keeps reply edits across close/reopen and can reset to the AI draft", async () => {
    localStorage.removeItem("ticket-support-workflow-v1");
    mockApi({ analysis: ANALYSIS });
    const user = userEvent.setup();
    render(<App />);
    await openTicket(
      user,
      await within(table()).findByText("I was charged twice"),
    );
    let reply = within(screen.getByRole("dialog")).getByRole("textbox", {
      name: "Suggested reply",
    });
    await user.type(reply, " Edited locally.");
    await user.click(screen.getByRole("button", { name: "Close details" }));

    await openTicket(user, within(table()).getByText("I was charged twice"));
    reply = within(screen.getByRole("dialog")).getByRole("textbox", {
      name: "Suggested reply",
    });
    expect(reply).toHaveValue(
      `${ANALYSIS.results[0].suggested_reply} Edited locally.`,
    );
    await user.click(screen.getByRole("button", { name: "Reset to AI draft" }));
    expect(reply).toHaveValue(ANALYSIS.results[0].suggested_reply);
    expect(
      screen.queryByRole("button", { name: "Reset to AI draft" }),
    ).not.toBeInTheDocument();
  });

  it("marks a reply sent locally and supports undo", async () => {
    localStorage.removeItem("ticket-support-workflow-v1");
    mockApi({ analysis: ANALYSIS });
    const user = userEvent.setup();
    render(<App />);
    await openTicket(
      user,
      await within(table()).findByText("I was charged twice"),
    );
    await user.click(screen.getByRole("button", { name: "Mark as sent" }));
    expect(await within(table()).findByText("Sent")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Undo" }));
    expect(within(table()).queryByText("Sent")).not.toBeInTheDocument();
  });

  it("marks attention tickets reviewed from the list and supports undo in detail", async () => {
    localStorage.removeItem("ticket-support-workflow-v1");
    mockApi({ analysis: ANALYSIS });
    const user = userEvent.setup();
    render(<App />);
    const row = within(table()).getByText("I was charged twice").closest("tr");
    await user.click(
      within(row).getByRole("button", { name: "Mark reviewed" }),
    );
    expect(within(row).getByText("Reviewed")).toBeInTheDocument();

    await openTicket(user, within(row).getByText("I was charged twice"));
    expect(screen.getByText(/Reviewed at/)).toBeInTheDocument();
    await user.click(
      within(screen.getByRole("dialog")).getByRole("button", { name: "Undo" }),
    );
    expect(within(table()).getByText("Pending review")).toBeInTheDocument();
  });

  it("shows a visible message when copying the reply fails", async () => {
    Object.defineProperty(navigator, "clipboard", {
      configurable: true,
      value: { writeText: vi.fn().mockRejectedValue(new Error("denied")) },
    });
    mockApi({ analysis: ANALYSIS });
    const user = userEvent.setup();
    render(<App />);
    await openTicket(
      user,
      await within(table()).findByText("I was charged twice"),
    );
    await user.click(screen.getByRole("button", { name: "Copy reply" }));
    expect(
      await within(screen.getByRole("dialog")).findByRole("alert"),
    ).toHaveTextContent("Could not copy the reply");
  });

  it("keeps only one analyze request in flight", async () => {
    let finishAnalysis;
    const analyzeRequest = vi.fn(
      () =>
        new Promise((resolve) => {
          finishAnalysis = resolve;
        }),
    );
    mockApi({ analyze: analyzeRequest });
    const user = userEvent.setup();
    render(<App />);
    await within(table()).findByText("I was charged twice");
    const button = screen.getByRole("button", { name: "Analyze with AI" });

    await user.click(button);
    expect(button).toBeDisabled();
    await user.click(button);
    expect(analyzeRequest).toHaveBeenCalledTimes(1);

    finishAnalysis(json(ANALYSIS));
    expect(await within(table()).findByText("Billing")).toBeInTheDocument();
  });

  it("warns when some tickets were not analyzed", async () => {
    mockApi({ analyze: async () => json({ results: [ANALYSIS.results[0]] }) });
    const user = userEvent.setup();
    render(<App />);
    await within(table()).findByText("I was charged twice");
    await user.click(screen.getByRole("button", { name: "Analyze with AI" }));
    expect(await screen.findByRole("status")).toHaveTextContent(
      "1 ticket was not analyzed",
    );
  });

  it("starts a cooldown when the batch contains failed analyses", async () => {
    const failedResults = {
      results: [
        { ...ANALYSIS.results[0], status: "failed", error: "Timed out." },
        { ...ANALYSIS.results[1], status: "ok" },
      ],
    };
    mockApi({ analyze: async () => json(failedResults) });
    const user = userEvent.setup();
    render(<App />);
    await within(table()).findByText("I was charged twice");
    await user.click(screen.getByRole("button", { name: "Analyze with AI" }));

    expect(await screen.findByRole("status")).toHaveTextContent(
      "Analyze again in 30 seconds.",
    );
    expect(
      screen.getByRole("button", { name: "Analyze with AI" }),
    ).toBeDisabled();
  });

  it("only mentions the backend port when the server is unreachable", async () => {
    global.fetch = vi.fn(async () => {
      throw new TypeError("Failed to fetch");
    });
    render(<App />);
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Check that the backend is running on port 8000.",
    );
  });

  it("shows the API key hint for authentication errors during analysis", async () => {
    mockApi({ analyze: async () => json({ detail: "Upstream failed." }, 500) });
    const user = userEvent.setup();
    render(<App />);
    await within(table()).findByText("I was charged twice");
    await user.click(screen.getByRole("button", { name: "Analyze with AI" }));
    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("Upstream failed.");
    expect(alert).not.toHaveTextContent("GEMINI_API_KEY");
    expect(alert).not.toHaveTextContent("port 8000");
    expect(
      screen.getByRole("button", { name: "Analyze with AI" }),
    ).toBeDisabled();
    expect(await screen.findByRole("status")).toHaveTextContent("30 seconds");
  });

  it("mentions the API key for 401 and 403 errors only", async () => {
    for (const status of [401, 403]) {
      mockApi({
        analyze: async () => json({ detail: "Not authorized." }, status),
      });
      const user = userEvent.setup();
      const { unmount } = render(<App />);
      await within(table()).findByText("I was charged twice");
      await user.click(screen.getByRole("button", { name: "Analyze with AI" }));
      expect(await screen.findByRole("alert")).toHaveTextContent(
        "GEMINI_API_KEY",
      );
      unmount();
    }
  });

  it("shows quota errors without blaming the API key", async () => {
    mockApi({
      analyze: async () =>
        json(
          { detail: "AI rate limit reached. Try again in 45 seconds." },
          429,
          { "Retry-After": "45" },
        ),
    });
    const user = userEvent.setup();
    render(<App />);
    await within(table()).findByText("I was charged twice");
    await user.click(screen.getByRole("button", { name: "Analyze with AI" }));
    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent(
      "AI rate limit reached. Try again in 45 seconds.",
    );
    expect(alert).not.toHaveTextContent("GEMINI_API_KEY");
    expect(
      screen.getByRole("button", { name: "Analyze with AI" }),
    ).toBeDisabled();
    expect(await screen.findByRole("status")).toHaveTextContent("45 seconds");
  });

  it("labels failed tickets and shows their error in details", async () => {
    const failedAnalysis = {
      results: [
        {
          ...ANALYSIS.results[0],
          status: "failed",
          error: "Invalid response from Gemini.",
        },
      ],
    };
    mockApi({ analysis: failedAnalysis });
    const user = userEvent.setup();
    render(<App />);
    expect(await within(table()).findByText("Failed")).toBeInTheDocument();
    await openTicket(
      user,
      await within(table()).findByText("I was charged twice"),
    );
    expect(
      screen.getByText("Invalid response from Gemini."),
    ).toBeInTheDocument();
  });

  it("does not blame the API key for client errors", async () => {
    mockApi({ analyze: async () => json({ detail: "Bad request." }, 422) });
    const user = userEvent.setup();
    render(<App />);
    await within(table()).findByText("I was charged twice");
    await user.click(screen.getByRole("button", { name: "Analyze with AI" }));
    expect(await screen.findByRole("alert")).not.toHaveTextContent(
      "GEMINI_API_KEY",
    );
  });
});
