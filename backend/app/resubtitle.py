"""(Re)assign short mnemonic-image subtitles to existing batches via the LLM.

Sibling of app.retitle: the standard pipeline auto-subtitles *new* batches
(content.upsert auto_subtitle); this one-off backfills batches that still carry a
hand-written or first-sentence-derived subtitle.

Usage:
    python -m app.resubtitle --all            # regenerate every live batch
    python -m app.resubtitle 2 3              # only batches #2 and #3
    python -m app.resubtitle --all --dry-run  # preview, change nothing
"""
import sys

from sqlmodel import Session, select

from . import models, titling
from .db import engine, init_db


def run(ids: list[int], *, all_: bool, dry: bool) -> list[tuple[int, str, str]]:
    init_db()
    rows: list[tuple[int, str, str]] = []
    with Session(engine()) as s:
        batches = s.exec(
            select(models.Batch).where(models.Batch.deleted_at == None)  # noqa: E711
            .order_by(models.Batch.id)
        ).all()
        if not all_:
            batches = [b for b in batches if b.id in ids]
        for b in batches:
            mnemo = s.exec(
                select(models.MnemoStory).where(models.MnemoStory.batch_id == b.id)
            ).first()
            old = b.subtitle
            try:
                new = titling.suggest_subtitle(mnemo.story_ru if mnemo else "")
            except Exception as e:  # noqa: BLE001
                rows.append((b.id, old, f"ERR {e}"))
                continue
            rows.append((b.id, old, new))
            if new and not dry and new != b.subtitle:
                b.subtitle = new
                # translations were of the OLD subtitle — clear so app.doctor
                # sees the hole and `i18n_content --refill` re-translates
                b.subtitle_i18n = {}
                s.add(b)
        if not dry:
            s.commit()
    return rows


def main(argv: list[str]) -> None:
    dry = "--dry-run" in argv
    all_ = "--all" in argv
    ids = [int(a) for a in argv if a.isdigit()]
    if not all_ and not ids:
        print("usage: python -m app.resubtitle [--all | <id>...] [--dry-run]")
        return
    rows = run(ids, all_=all_, dry=dry)
    for bid, old, new in rows:
        print(f"#{bid}: {old!r} -> {new!r}")
    print("DRY-RUN — no changes written" if dry else f"COMMITTED {len(rows)} batch(es)")


if __name__ == "__main__":
    main(sys.argv[1:])
