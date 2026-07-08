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
                             re-run `python -m app.i18n_content --refill`.
  - CheckPhrase rows        (curated situational cues) → DELETED: they were
                             authored against the OLD phrase text, and a stale cue
                             sets up the old line while scoring compares against
                             the new one — systematically failing correct recalls.
                             The deck falls back to situation_ru until re-curated.
A gloss_ru provided in the content file is synced too (empty/missing gloss in the
file means "keep the DB value" — files historically omit glosses).
Mnemo spans are NOT touched here — run `python -m app.restory` AFTER this so it
recomputes spans against the now-updated anchors. TTS (AudioAsset) is keyed by
text and regenerates on demand for the new phrase_en.

Structural safety: a batch whose content phrase count no longer matches the DB
(added/removed phrases) is SKIPPED with a warning — that case needs a real
re-author (upsert), not an in-place field update. A same-count REORDER is also
detected and SKIPPED: phrases are matched positionally by order_index, so
applying a reordered file would rewrite texts in place under existing
UserPhraseStat rows — every user's mastery would silently re-attach to a
different phrase. (Detected when a changed slot's new anchor equals another
slot's current anchor, case-insensitively.)

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
             "glosses_changed": 0, "checkphrases_dropped": 0,
             "batches_skipped": 0}
    for path in sorted(content_dir().glob("*.json")):
        if path.name.startswith("."):
            continue  # skip macOS AppleDouble (._*) and other dotfiles
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

        # Reorder guard: matching is positional, so a file whose rows MOVED would
        # swap texts under users' SRS stats. A changed slot is suspicious when its
        # new anchor is another slot's CURRENT anchor and either (a) the English
        # text moved with it (a true row move) or (b) that other slot is not
        # renaming away its anchor in the same file (which would end in duplicate
        # anchors within the batch). A chain rename — slot 5 delta→beta while
        # slot 2 vacates beta→gamma, each with its own new text — is a legitimate
        # bulk replacement (the v7.5.1 rollout shape) and passes.
        canchors = [(cp.get("anchor") or dp.anchor)
                    for cp, dp in zip(cphrases, db_phrases)]
        slot_of_db_anchor = {dp.anchor.lower(): i
                             for i, dp in enumerate(db_phrases)}
        suspicious = []
        for i, (cp, dp) in enumerate(zip(cphrases, db_phrases)):
            na = canchors[i]
            if na.lower() == dp.anchor.lower():
                continue
            j = slot_of_db_anchor.get(na.lower())
            if j is None or j == i:
                continue
            other = db_phrases[j]
            moved_row = cp.get("en", dp.phrase_en) == other.phrase_en
            vacating = canchors[j].lower() != other.anchor.lower()
            if moved_row or not vacating:
                suspicious.append(
                    f"#{dp.order_index} {na!r} is slot #{other.order_index}'s "
                    f"current anchor" + (" (text moved too)" if moved_row else ""))
        if suspicious:
            print(f"  {slug:20s} SKIP: reorder suspected ({'; '.join(suspicious)}) "
                  f"— in-place update would re-attach users' SRS stats to "
                  f"different phrases; re-author instead")
            stats["batches_skipped"] += 1
            continue

        batch_changed = 0
        # content is in order_index order (1..N); align positionally.
        for cp, dp in zip(cphrases, db_phrases):
            new_anchor = cp.get("anchor", dp.anchor)
            new_en = cp.get("en", dp.phrase_en)
            # empty/missing gloss in the file means "keep the DB value"
            new_gloss = (cp.get("gloss_ru") or "").strip()
            text_changed = dp.anchor != new_anchor or dp.phrase_en != new_en
            gloss_changed = bool(new_gloss) and new_gloss != dp.gloss_ru
            if not text_changed and not gloss_changed:
                continue
            anchor_changed = dp.anchor != new_anchor
            kind = " [anchor]" if anchor_changed else (
                " [en]" if text_changed else " [gloss]")
            print(f"  {slug:20s} #{dp.order_index} id={dp.id} "
                  f"{dp.anchor!r}->{new_anchor!r}{kind}")
            stale_cues = session.exec(select(models.CheckPhrase).where(
                models.CheckPhrase.phrase_id == dp.id)).all() if text_changed else []
            if not dry_run:
                if text_changed:
                    dp.anchor = new_anchor
                    dp.phrase_en = new_en
                if gloss_changed:
                    dp.gloss_ru = new_gloss
                # invalidate derived caches so they regenerate against the new text
                # (situation/task derive from anchor+en+gloss; gloss_i18n from gloss)
                dp.situation_ru = ""
                dp.task_ru = ""
                dp.gloss_i18n = {}
                session.add(dp)
                # curated cues were written against the OLD text — a stale cue sets
                # up the old line while scoring compares against the new one
                for cue in stale_cues:
                    session.delete(cue)
            stats["checkphrases_dropped"] += len(stale_cues)
            batch_changed += 1
            stats["phrases_changed"] += 1
            if anchor_changed:
                stats["anchors_changed"] += 1
            if gloss_changed:
                stats["glosses_changed"] += 1
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
          f"glosses_changed={stats['glosses_changed']} "
          f"checkphrases_dropped={stats['checkphrases_dropped']} "
          f"batches_skipped={stats['batches_skipped']}")
    if not args.dry_run and stats["phrases_changed"]:
        print("NEXT: python -m app.restory   (recompute spans against new anchors)")
        print("      python -m app.gen_context   (rebuild cleared situation/task prompts)")
        print("      python -m app.i18n_content --refill   (refill cleared translations)")
        if stats["checkphrases_dropped"]:
            print(f"      re-author {stats['checkphrases_dropped']} dropped "
                  f"CheckPhrase cue(s) for the changed phrases and show them to "
                  f"the user for review (see CONTENT-GRAPH.md) — app.doctor "
                  f"stays red until the holes are refilled")
    if not args.dry_run:
        from .doctor import verdict
        verdict("after rephrase")
    print("DONE")


if __name__ == "__main__":
    main()
