"""Re-sync mnemo stories from content/*.json into existing DB batches.

`upsert()` is create-or-replace: it wipes and recreates the batch's children,
which breaks phrase ids referenced by user SRS state. When only the `mnemo`
text of a content file changed, run this instead — it updates MnemoStory
in place (story_ru + recomputed spans), resets the story's i18n cache so
translations regenerate, and never touches phrases or zones.

    python -m app.restory              # all content files whose story differs
    python -m app.restory slug1 slug2  # only these slugs
"""
import json
import sys

from sqlmodel import Session, select

from . import models
from .content import content_dir
from .db import engine, init_db
from .importer import _compute_spans
from .schemas import PhraseIn


def resync(session: Session, slugs: list[str] | None = None) -> None:
    wanted = set(slugs) if slugs else None
    for path in sorted(content_dir().glob("*.json")):
        data = json.loads(path.read_text())
        slug = data.get("slug", "")
        story = (data.get("mnemo") or "").strip()
        if not slug or not story or (wanted and slug not in wanted):
            continue
        batch = session.exec(select(models.Batch).where(
            models.Batch.slug == slug, models.Batch.deleted_at == None  # noqa: E711
        )).first()
        if not batch:
            print(f"  {slug:16s} SKIP: no batch in DB")
            continue
        mnemo = session.exec(select(models.MnemoStory).where(
            models.MnemoStory.batch_id == batch.id
        )).first()
        if mnemo and mnemo.story_ru == story:
            continue
        phrases = session.exec(
            select(models.Phrase).where(models.Phrase.batch_id == batch.id)
            .order_by(models.Phrase.order_index)
        ).all()
        spans, warnings = _compute_spans(story, [
            PhraseIn(order_index=p.order_index, anchor=p.anchor, phrase_en=p.phrase_en)
            for p in phrases
        ])
        for w in warnings:
            print(f"  {slug:16s} WARN: {w}")
        if not mnemo:
            mnemo = models.MnemoStory(batch_id=batch.id, story_ru=story, spans=[])
            session.add(mnemo)
        mnemo.story_ru = story
        mnemo.spans = [s.model_dump() for s in spans]
        # stale translations would show the OLD story to es/de/fr users
        mnemo.story_i18n = None
        mnemo.spans_i18n = None
        session.add(mnemo)
        session.commit()
        print(f"  {slug:16s} updated (batch #{batch.id}, {len(spans)}/{len(phrases)} spans)")


def main() -> None:
    init_db()
    with Session(engine()) as s:
        resync(s, sys.argv[1:] or None)
    print("DONE")


if __name__ == "__main__":
    main()
