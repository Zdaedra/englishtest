# Contributing

## Testing norm (the one rule that keeps the suite from rotting)

> **When you add or change behaviour that touches money, privacy, or access —
> add or update a test in the _same_ change.** Not in a later "testing phase".

Concretely, bundle a test with the change whenever you touch:

- **Access / isolation** — who can see or mutate whose data (batch ownership,
  the auth gate, admin-only endpoints).
- **Entitlements / billing** — the free / core / ai matrix, plan gates, daily
  limits, Apple purchase handling.
- **Core invariants** — the SRS engine, the import parse→commit contract, the
  data model's required fields.

If you change existing behaviour on purpose and a test goes red, that's the
test doing its job: update it to match the new intent (usually a one-line edit).

### What we deliberately do *not* test

Rapidly-changing or throwaway surface: exact UI layout/wording, experimental
screens you might rip out. Tests there would be friction, not safety. Test by
**risk × stability**, not by development phase.

## Running the suite

```bash
make test                      # full backend suite (offline, ~2.4s, no API spend)
make -C backend test-v         # verbose
make -C backend smoke          # standalone parse→render→commit→review check
```

The suite stubs every paid/network call (TTS, STT, AI scorers, cover art, LLM),
so it needs no API keys and spends nothing. Details + coverage map:
[backend/tests/README.md](backend/tests/README.md).

## Automation

- **Local pre-push hook** — runs the suite before every `git push`. Enable once
  per machine with `scripts/setup-dev.sh` (installs dev deps + sets
  `core.hooksPath`). Override a run with `git push --no-verify`.
- **CI** — `.github/workflows/tests.yml` runs the suite on push / PR. Active
  once the repo has a GitHub remote.

New feature → add its tests → `make test` green → commit. That keeps the suite
moving with the code instead of drifting behind it.
