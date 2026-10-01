# Prompt evaluation notes

## Run status

Each saved version was attempted twice on 2026-10-01:

| Version | Runs | Result                  | What was wrong                                                             | Change made                                 | Fixed?            |
| ------- | ---: | ----------------------- | -------------------------------------------------------------------------- | ------------------------------------------- | ----------------- |
| v1      |    2 | Blocked before ticket 1 | `OPENAI_API_KEY` was not configured, so `AsyncOpenAI` could not initialize | None; environment configuration is required | No, not evaluated |
| v2      |    2 | Blocked before ticket 1 | `OPENAI_API_KEY` was not configured, so `AsyncOpenAI` could not initialize | None; environment configuration is required | No, not evaluated |
| v3      |    2 | Blocked before ticket 1 | `OPENAI_API_KEY` was not configured, so `AsyncOpenAI` could not initialize | None; environment configuration is required | No, not evaluated |

Because all attempts stopped before the first API request, there are no ticket-level findings such as an incorrect reply or unstable label. Label stability across repeated runs remains unverified.

## Version changes

- **v1:** Minimal triage instructions and label names.
- **v2:** Added explicit urgency, category, sentiment, grounding, safety, and human-review definitions.
- **v3:** Preserved v2 and added four synthetic few-shot examples.
