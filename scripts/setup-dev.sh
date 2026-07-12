#!/bin/sh
# One-time dev setup: install test deps + enable the pre-push test hook.
set -e
root=$(git rev-parse --show-toplevel)
cd "$root"

echo "→ Installing backend dev/test dependencies…"
backend/.venv/bin/python -m pip install -r backend/requirements-dev.txt

echo "→ Enabling git hooks (core.hooksPath = scripts/git-hooks)…"
git config core.hooksPath scripts/git-hooks
chmod +x scripts/git-hooks/* 2>/dev/null || true

echo "✓ Done."
echo "  • Run the suite any time:   make test   (or: cd backend && python -m pytest)"
echo "  • Pushes now run the suite automatically (override with: git push --no-verify)"
