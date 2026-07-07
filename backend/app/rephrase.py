"""SRS-safe in-place update of phrase content (anchor + phrase_en) from content/*.json.

Unlike `content.upsert()` — which wipes and recreates a batch's children, minting
new phrase ids and orphaning every `UserPhraseStat` row that referenced them — this
matches existing DB phrases to the content file by `order_index` and updates them
IN PLACE. `phrase.id` is preserved, so per-user SRS / mastery / swipe state survives.

When a phrase's English text or anchor actually changes, the derived per-phrase
caches are invalidated so they regenerate cleanly (never left stale):
  - situation_ru / task_ru  (the RU active-recall prompt) → cleared;
                             re-run `python -m app.gen_context` to rebuild only these.
  - gloss_i18n              (es/de/fr gloss translations) → cleared;
                             re-run the i18n backfill.
Mnemo spans are NOT touched here — run `python -m app.restory` AFTER this so it
recomputes spans against the now-updated anchors. TTS (AudioAsset) is keyed by
text and regenerates on demand for the new phrase_en.

Structural safety: a batch whose content phrase count no longer matches the DB
(added/removed/reordered phrases) is SKIPPED with a warning — that case needs a
real re-author (upsert), not an in-place field update.

    python -m app.rephrase              # every batch whose phrases differ
    python -m app.rephrase slug1 slug2  # only these slugs
    python -m app.rephrase --dry-run    # report what would change, touch nothing
"""
import argparse
import json

from sqlmodel import Session, select

from . import models
from .content import content_dir
from .db import engine, init_db


def resync_phrases(session: Session, slugs: list[str] | None = None,
                   dry_run: bool = False) -> dict:
    wanted = set(slugs) if slugs else None
    stats = {"batches_changed": 0, "phrases_changed": 0, "anchors_changed": 0,
             "batches_skipped": 0}
    for path in sorted(content_dir().glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        slug = data.get("slug", "")
        cphrases = data.get("phrases") or []
        if not slug or not cphrases or (wanted and slug not in wanted):
            continue
        batch = session.exec(select(models.Batch).where(
            models.Batch.slug == slug, models.Batch.deleted_at == None  # noqa: E711
        )).first()
        if not batch:
            print(f"  {slug:20s} SKIP: no batch in DB")
            continue
        db_phrases = session.exec(
            select(models.Phrase).where(models.Phrase.batch_id == batch.id)
            .order_by(models.Phrase.order_index)
        ).all()
        if len(db_phrases) != len(cphrases):
            print(f"  {slug:20s} SKIP: phrase count DB={len(db_phrases)} "
                  f"!= content={len(cphrases)} (needs re-author, not in-place)")
            stats["batches_skipped"] += 1
            continue

        batch_changed = 0
        # content is in order_index order (1..N); align positionally.
        for cp, dp in zip(cphrases, db_phrases):
            new_anchor = cp.get("anchor", dp.anchor)
            new_en = cp.get("en", dp.phrase_en)
            if dp.anchor == new_anchor and dp.phrase_en == new_en:
                continue
            anchor_changed = dp.anchor != new_anchor
            print(f"  {slug:20s} #{dp.order_index} id={dp.id} "
                  f"{dp.anchor!r}->{new_anchor!r}" + (" [anchor]" if anchor_changed else " [en]"))
            if not dry_run:
                dp.anchor = new_anchor
                dp.phrase_en = new_en
                # invalidate derived caches so they regenerate against the new text
                dp.situation_ru = ""
                dp.task_ru = ""
                dp.gloss_i18n = {}
                session.add(dp)
            batch_changed += 1
            stats["phrases_changed"] += 1
            if anchor_changed:
                stats["anchors_changed"] += 1
        if batch_changed:
            if not dry_run:
                session.commit()
            stats["batches_changed"] += 1
    return stats


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("slugs", nargs="*")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    init_db()
    with Session(engine()) as s:
        stats = resync_phrases(s, args.slugs or None, dry_run=args.dry_run)
    tag = "[dry-run] " if args.dry_run else ""
    print(f"\n{tag}batches_changed={stats['batches_changed']} "
          f"phrases_changed={stats['phrases_changed']} "
          f"anchors_changed={stats['anchors_changed']} "
          f"batches_skipped={stats['batches_skipped']}")
    if not args.dry_run and stats["phrases_changed"]:
        print("NEXT: python -m app.restory   (recompute spans against new anchors)")
        print("      python -m app.gen_context   (rebuild cleared situation/task prompts)")
    print("DONE")


if __name__ == "__main__":
    main()
