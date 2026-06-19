# Backend tests — `smoketest3`

This collection is codenamed **`smoketest3`** (the canonical backend suite). Run
it as a named group with `make smoketest3` or `pytest -m smoketest3` — that
selects exactly these tests.

Offline pytest suite for the FastAPI backend. Every paid/network boundary
(OpenAI TTS, STT, the AI scorers, cover-art generation, LLM) is stubbed in
`conftest.py`, so the whole suite runs in ~2–3s with **zero API spend** and no
network. Each test gets a fresh in-process SQLite DB (tables dropped + recreated
between tests), so the first user registered in a test always bootstraps as the
admin / "ai"-plan owner.

## Running

```bash
# from repo root
make test

# or directly
cd backend && python -m pytest          # uses pytest.ini (pythonpath, testpaths)
cd backend && python -m pytest -v       # list each test
make -C backend smoke                    # standalone parse→render→commit→review check
```

First time on a machine: `scripts/setup-dev.sh` installs the dev deps
(`requirements-dev.txt`) and enables a pre-push hook that runs the suite before
every `git push`.

## What's covered

| Area | File |
|---|---|
| Auth + the global 401 gate, register/login/me/ui-lang/delete | `test_auth.py` |
| Plan/entitlement matrix, expired-subscription fallback | `test_entitlements.py` |
| Import parse/commit, import + admin gates | `test_imports.py` |
| Catalog listing, freemium lock, **cross-user isolation (404)**, reviews, audio, export, delete, cover, free-flag | `test_batches.py` |
| Gapless session render, lock, empty-batch, **daily cap (429)** | `test_sessions.py` |
| Training loop: scoring, rate limits, AI-plan gates, swipe/confirm/coach, reads | `test_training.py` |
| Practice questions/prompt-audio/score | `test_practice.py` |
| Per-user progress, activation lock + max-active cap | `test_progress.py` |
| Global settings (admin-only write) | `test_settings.py` |
| Apple billing (verify 401/501/applied, public notifications) | `test_billing.py` |
| SRS engine units (bands, transition ladder, lapse) | `test_srs.py` |

## CI

`.github/workflows/tests.yml` runs this suite on push/PR (Python 3.12). It only
executes once the repo has a GitHub remote and is pushed there.
