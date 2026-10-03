# Ticket Support App walkthrough (about 2:30)

Use the running app at `http://localhost:5173`. The sample cache is already present; avoid clicking **Analyze with AI** during the recording unless a valid Gemini key and quota are available. Read the narration at a relaxed pace and follow the shot notes. Times are targets, not hard cuts.

## 0:00–0:20 — Introduce the app

**Show:** Open the support inbox and hold on the page header and ticket list.

**Say:** “This is a support inbox for a health and caregiver app. The goal is to help an agent see which messages need attention first, understand why they were flagged, and prepare a safe reply. The inbox keeps the agent in control: AI suggestions support review rather than sending messages automatically.”

## 0:20–0:50 — Show the inbox and insights

**Show:** Point out the ticket rows, then the overview cards and category, urgency, and sentiment breakdowns. Click one breakdown if convenient to demonstrate filtering, then clear it.

**Say:** “Each analyzed ticket has a category, urgency, sentiment, confidence, a short evidence-based reason, and a suggested response. The overview summarizes the batch. These breakdowns are interactive, so selecting a value narrows the ticket list to the matching cases. The review count helps an agent focus on items that still need a human decision.”

## 0:50–1:20 — Inspect a ticket

**Show:** Open a ticket marked for review. Point to its message and analysis, then the draft/review controls. Do not mark it reviewed unless you want that state changed in the demo data.

**Say:** “Opening a ticket keeps the original message alongside the model’s reasoning and reply draft. The prompt tells Gemini to ground the explanation and reply in the ticket, avoid inventing account details or promises, and direct emergencies to qualified help. A human agent can inspect and edit the draft before using it.”

## 1:20–1:55 — Explain the implementation

**Show:** Briefly show the repository tree or README sections for stack and prompt; optionally show `backend/prompts.py` and `backend/app/analysis_routes.py`.

**Say:** “The frontend is React with Vite. The backend is FastAPI with Pydantic schemas, and Gemini provides the structured triage. I chose this split to keep the inbox responsive while making the API’s inputs and model results explicit and validated. Sample tickets and successful analyses live in JSON files, which keeps the demo simple to set up.”

## 1:55–2:25 — Challenge and ending

**Show:** Show the prompt’s safety rules or the README’s challenge section, then return to the inbox.

**Say:** “One challenge is handling model output and provider limits reliably. The backend checks that each requested ticket has exactly one result with the right ID, caches successful results by message content, and batches only uncached unique messages. It retries a temporary service-unavailable response once, but it does not keep retrying quota or authentication failures. With more time, I’d persist review state for a whole team and evaluate borderline safety decisions against a labeled dataset. That’s the Ticket Support App.”

This narration is approximately 280 words, which takes about 2 to 2½ minutes at a clear speaking pace, plus a few seconds to move between screens.
