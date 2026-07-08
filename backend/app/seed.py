"""Load all authored batches from backend/content/ into the DB.

Idempotent: each file upserts by slug, so re-running syncs edits without creating
duplicates. This replaces ad-hoc one-off scripts for fixing batch content.

Batches with live user progress are BLOCKED (reported, not replaced): a re-seed
mints new phrase ids, which would destroy every user's SRS state for the batch.
Text-only edits belong in `app.rephrase` / `app.restory`. To consciously destroy
progress and replace anyway:

    python -m app.seed --force-progress-loss
"""
import argparse

from sqlmodel import Session

from .content import content_dir, load_all
from .db import engine, init_db


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--force-progress-loss", action="store_true",
                    help="replace EDITED batches even if users have SRS progress "
                         "on them (their progress rows are deleted first — "
                         "including training-event history, which can "
                         "retroactively shrink day-streaks). Unchanged batches "
                         "are always skipped untouched.")
    args = ap.parse_args()
    mode = "wipe" if args.force_progress_loss else "block"

    init_db()
    with Session(engine()) as session:
        results = load_all(session, on_live_progress=mode)
        rows = [
            (r["batch"].id if r["batch"] else None, r["slug"],
             r["batch"].title if r["batch"] else "", r["created"],
             r["warnings"], r["blocked"], r["unchanged"])
            for r in results
        ]

    if not rows:
        print(f"No content files found in {content_dir()}")
        return

    blocked = unchanged_n = 0
    for bid, slug, title, created, warnings, was_blocked, unchanged in rows:
        if was_blocked:
            blocked += 1
            print(f"  BLOCKED: {slug}")
        elif unchanged:
            unchanged_n += 1
        else:
            verb = "created" if created else "updated"
            print(f"  {verb}: #{bid} {slug} — «{title}»")
        for w in warnings:
            print(f"      ⚠ {w}")
    print(f"DONE: {len(rows)} batch(es) from {content_dir()}"
          + (f" — {unchanged_n} unchanged (skipped)" if unchanged_n else "")
          + (f" — {blocked} BLOCKED (live user progress; see app.rephrase, "
             f"or --force-progress-loss)" if blocked else ""))
    from .doctor import verdict
    verdict("after seed")


if __name__ == "__main__":
    main()
