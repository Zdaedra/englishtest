"""Load all authored batches from backend/content/ into the DB.

Idempotent: each file upserts by slug, so re-running syncs edits without creating
duplicates. This replaces ad-hoc one-off scripts for fixing batch content.

    python -m app.seed
"""
from sqlmodel import Session

from .content import content_dir, load_all
from .db import engine, init_db


def main() -> None:
    init_db()
    with Session(engine()) as session:
        rows = [
            (batch.id, batch.slug, batch.title, created, warnings)
            for batch, created, warnings in load_all(session)
        ]

    if not rows:
        print(f"No content files found in {content_dir()}")
        return

    for bid, slug, title, created, warnings in rows:
        verb = "created" if created else "updated"
        print(f"  {verb}: #{bid} {slug} — «{title}»")
        for w in warnings:
            print(f"      ⚠ {w}")
    print(f"DONE: {len(rows)} batch(es) from {content_dir()}")


if __name__ == "__main__":
    main()
