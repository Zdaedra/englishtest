"""Re-sync mnemo stories from content/*.json into existing DB batches.

`upsert()` is create-or-replace: it wipes and recreates the batch's children,
which breaks phrase ids referenced by user SRS state. When the `mnemo` text of a
content file changed — or the anchors did (run AFTER `app.rephrase`) — run this
instead: it updates MnemoStory in place (story_ru + recomputed spans) and never
touches phrases or zones.

Spans are recomputed even when the story TEXT is unchanged: after an anchor
rename the old spans still point at the old words, so tap-to-reveal and the
anchors/shuffle audio drills would highlight/speak the wrong word. i18n handling
follows the change: a rewritten story drops story_i18n/spans_i18n entirely
(translations must regenerate), while a span-only change keeps each language
whose translation still contains every anchor verbatim (spans recomputed
mechanically, no LLM) and drops only the stale ones.

    python -m app.restory              # all content files whose story/spans differ
    python -m app.restory slug1 slug2  # only these slugs
"""
import json
import sys

from sqlmodel import Session, select

from . import models
from .content import content_dir
from .db import engine, init_db
from .i18n_content import recompute_spans
from .importer import _compute_spans
from .schemas import PhraseIn


def _anchors_word_bounded(text: str, spans: list[dict]) -> bool:
    """True when every span sits on word boundaries (not flanked by ASCII
    letters). recompute_spans is a raw substring search, so a short anchor like
    'art' can coincidentally match inside 'partir' in a STALE translation that
    semantically still carries the OLD anchor — keeping it would highlight a
    mid-word fragment. Dropping on doubt is safe: the language just retranslates."""
    for sp in spans:
        s, e = sp["start"], sp["end"]
        before = text[s - 1] if s > 0 else " "
        after = text[e] if e < len(text) else " "
        if ((before.isascii() and before.isalpha())
                or (after.isascii() and after.isalpha())):
            return False
    return True


def resync(session: Session, slugs: list[str] | None = None) -> None:
    wanted = set(slugs) if slugs else None
    for path in sorted(content_dir().glob("*.json")):
        if path.name.startswith("."):
            continue  # skip macOS AppleDouble (._*) and other dotfiles
        data = json.loads(path.read_text(encoding="utf-8"))
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
        phrases = session.exec(
            select(models.Phrase).where(models.Phrase.batch_id == batch.id)
            .order_by(models.Phrase.order_index)
        ).all()
        spans, warnings = _compute_spans(story, [
            PhraseIn(order_index=p.order_index, anchor=p.anchor, phrase_en=p.phrase_en)
            for p in phrases
        ])
        new_spans = [s.model_dump() for s in spans]
        story_changed = not mnemo or mnemo.story_ru != story
        spans_changed = not mnemo or (mnemo.spans or []) != new_spans
        if not story_changed and not spans_changed:
            continue
        for w in warnings:
            print(f"  {slug:16s} WARN: {w}")
        if not mnemo:
            mnemo = models.MnemoStory(batch_id=batch.id, story_ru=story, spans=[])
            session.add(mnemo)
        mnemo.story_ru = story
        mnemo.spans = new_spans
        if story_changed:
            # stale translations would show the OLD story to es/de/fr users
            mnemo.story_i18n = None
            mnemo.spans_i18n = None
            what = "story+spans"
        else:
            # Anchor rename under an unchanged story: a translation is still valid
            # only if it contains every (new) anchor verbatim — then its spans are
            # recomputed mechanically (no LLM). A language still carrying the OLD
            # anchor word is stale content and is dropped for retranslation.
            kept_stories: dict = {}
            kept_spans: dict = {}
            for lang, tr_story in (mnemo.story_i18n or {}).items():
                tr_spans = recompute_spans(story, new_spans, tr_story)
                if (tr_spans is not None
                        and _anchors_word_bounded(tr_story, tr_spans)):
                    kept_stories[lang] = tr_story
                    kept_spans[lang] = tr_spans
                else:
                    print(f"  {slug:16s} i18n[{lang}] dropped (translation no "
                          f"longer contains every anchor as a whole word)")
            mnemo.story_i18n = kept_stories or None
            mnemo.spans_i18n = kept_spans or None
            what = "spans-only"
        session.add(mnemo)
        session.commit()
        print(f"  {slug:16s} updated {what} (batch #{batch.id}, "
              f"{len(spans)}/{len(phrases)} spans)")


def main() -> None:
    init_db()
    with Session(engine()) as s:
        resync(s, sys.argv[1:] or None)
    print("DONE")


if __name__ == "__main__":
    main()
