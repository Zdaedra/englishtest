"""Generate batch cover images and persist cover_path on each batch.

Mirrors app.resubtitle: the active prompt style is ENGLISH_COVER_PROMPT_VERSION
(default 2 = single-style scene photo). Files are keyed by version, so switching
versions and re-running reuses cached images instead of re-spending. Each
gpt-image-1 cover costs money — run deliberately.

Usage:
    python -m app.gencovers --all                 # every live batch (active version)
    python -m app.gencovers 2 3                    # only batches #2 and #3
    python -m app.gencovers --all --version 2      # force a specific prompt version
    python -m app.gencovers --all --force          # regenerate even if cached
"""
import sys

from sqlmodel import Session, select

from . import cover, models
from .db import engine, init_db


def run(ids: list[int], *, all_: bool, force: bool,
        version: int | None) -> list[tuple[int, str]]:
    init_db()
    out: list[tuple[int, str]] = []
    with Session(engine()) as s:
        batches = s.exec(
            select(models.Batch).where(models.Batch.deleted_at == None)  # noqa: E711
            .order_by(models.Batch.id)
        ).all()
        if not all_:
            batches = [b for b in batches if b.id in ids]
        for b in batches:
            try:
                url = cover.generate_cover(b.id, b.slug, b.title, b.theme, b.subtitle,
                                           force=force, version=version)
            except Exception as e:  # noqa: BLE001
                out.append((b.id, f"ERR {e}"))
                continue
            b.cover_path = url
            s.add(b)
            out.append((b.id, url))
        s.commit()
    return out


def main(argv: list[str]) -> None:
    all_ = "--all" in argv
    force = "--force" in argv
    version = None
    skip = set()
    if "--version" in argv:
        i = argv.index("--version")
        if i + 1 < len(argv):
            version = int(argv[i + 1])
            skip.add(i + 1)
    ids = [int(a) for i, a in enumerate(argv) if a.isdigit() and i not in skip]
    if not all_ and not ids:
        print("usage: python -m app.gencovers [--all | <id>...] [--version N] [--force]")
        return
    rows = run(ids, all_=all_, force=force, version=version)
    for bid, url in rows:
        print(f"#{bid}: {url}")
    print(f"DONE {len(rows)} batch(es)")


if __name__ == "__main__":
    main(sys.argv[1:])
