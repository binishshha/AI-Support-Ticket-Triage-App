# Ticket Support App

FastAPI backend and Vite frontend for classifying support tickets with Gemini.

## Quota & Rate-Limit Design

- One Analyze action sends all uncached, unique ticket messages in one structured Gemini request.
- Successful analyses are cached by SHA-256 of the ticket message. Repeated content reuses the analysis and maps it back to the caller's ticket ID; failed entries are retried, and legacy entries without a matchable hash are ignored.
- Only HTTP 503 receives one retry after a short backoff. Timeouts, 429 quota responses, authentication errors, and invalid structured output are not retried.
- Analysis requests are limited to 25 tickets and 25,000 combined message characters.
- Read endpoints use `RATE_LIMIT_PER_MINUTE` (default 60). Gemini analysis uses the separate `GEMINI_RATE_LIMIT_PER_MINUTE` (default 3). Both limits are tracked by the first `X-Forwarded-For` address when present, otherwise by the direct client address, and return `Retry-After` when limited.
- An in-process single-flight lock rechecks the cache before calling Gemini, preventing overlapping identical requests from duplicating work in one backend process.

### Seed the deployment cache

Cache seeding is opt-in and makes one real Gemini request. Set `GEMINI_API_KEY`, then run from the repository root:

```powershell
python -m backend.scripts.build_cache
```

The script leaves the existing cache unchanged unless every sample ticket receives a successful analysis. It is not run automatically. Tests use mocked Gemini clients and do not call the live API.
