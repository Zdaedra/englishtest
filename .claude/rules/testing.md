---
description: Bundle a test with any backend change that touches money, privacy, or access; run pytest before finishing.
globs:
  - "backend/**"
---

# Backend testing rule

When working in `backend/`:

1. **After changing backend behaviour, run the suite before you finish:**
   `cd backend && python -m pytest` (offline; ~2.4s; stubs all paid/network
   calls — no API keys, no spend). Report the result honestly.

2. **Bundle a test with the change — in the same commit — whenever you add or
   modify behaviour that touches:**
   - access / isolation (batch ownership, the auth gate, admin-only routes),
   - entitlements / billing (free·core·ai matrix, plan gates, daily limits, Apple purchases),
   - core invariants (the SRS engine, the import parse→commit contract, model required fields).

3. **A red test on a deliberate behaviour change is correct** — update it to
   match the new intent (usually a one-liner), don't delete it.

4. **Do NOT add tests for volatile surface** — exact UI layout/wording or
   experimental screens. Test by risk × stability, not by development phase.

Conventions and the coverage map live in `backend/tests/README.md`; the
human-facing version of this rule is `CONTRIBUTING.md`. New routers/endpoints
get a matching `backend/tests/test_<area>.py`.
