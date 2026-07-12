"""app.restory — SRS-safe in-place story resync.

Spans must be recomputed even when the story TEXT is unchanged (an anchor rename
via app.rephrase leaves the old spans pointing at the old words — tap-to-reveal
and the anchors/shuffle drills would highlight/speak the wrong word). i18n
follows the change: a rewritten story drops translations entirely; a span-only
change keeps each language whose translation still contains every anchor
verbatim (spans recomputed mechanically) and drops only the stale ones.
"""
import json

from sqlmodel import Session, select

from app import models, restory
from app.db import engine


def _seed(slug, phrases, story, spans=None, story_i18n=None, spans_i18n=None):
    with Session(engine()) as s:
        b = models.Batch(title="T", slug=slug, status="approved")
        s.add(b)
        s.commit()
        s.refresh(b)
        pids = []
        for i, (anchor, en) in enumerate(phrases, start=1):
            p = models.Phrase(batch_id=b.id, order_index=i, anchor=anchor,
                              phrase_en=en)
            s.add(p)
            s.commit()
            s.refresh(p)
            pids.append(p.id)
        s.add(models.MnemoStory(batch_id=b.id, story_ru=story,
                                spans=spans or [],
                                story_i18n=story_i18n or {},
                                spans_i18n=spans_i18n or {}))
        s.commit()
        return b.id, pids


def _write_content(tmp_path, monkeypatch, files: dict):
    d = tmp_path / "content"
    d.mkdir()
    for name, payload in files.items():
        (d / name).write_text(json.dumps(payload, ensure_ascii=False))
    monkeypatch.setattr(restory, "content_dir", lambda: d)
    return d


def _mnemo(batch_id):
    with Session(engine()) as s:
        return s.exec(select(models.MnemoStory)
                      .where(models.MnemoStory.batch_id == batch_id)).first()


def test_story_change_recomputes_spans_and_resets_i18n(tmp_path, monkeypatch):
    bid, _ = _seed("rs-1", [("alpha", "Alpha.")], "старая alpha история",
                   spans=[{"anchor_id": "a1", "phrase_id": 1, "start": 7,
                           "end": 12}],
                   story_i18n={"es": "vieja alpha historia"},
                   spans_i18n={"es": [{"anchor_id": "a1", "phrase_id": 1,
                                       "start": 6, "end": 11}]})
    _write_content(tmp_path, monkeypatch,
                   {"rs-1.json": {"slug": "rs-1", "mnemo": "новая alpha сказка"}})
    with Session(engine()) as s:
        restory.resync(s)
    m = _mnemo(bid)
    assert m.story_ru == "новая alpha сказка"
    assert len(m.spans) == 1
    sp = m.spans[0]
    assert m.story_ru[sp["start"]:sp["end"]].lower() == "alpha"
    # a rewritten story invalidates ALL translations
    assert not m.story_i18n and not m.spans_i18n


def test_anchor_rename_recomputes_spans_and_keeps_valid_langs(tmp_path, monkeypatch):
    """The app.rephrase → app.restory flow: anchors already renamed in the DB,
    story text in the file unchanged. Spans must still be recomputed, valid
    translations kept (mechanical span recompute), stale ones dropped."""
    story = "ты видишь beta в лесу"
    bid, _ = _seed(
        "rs-2", [("beta", "Beta.")], story,
        spans=[{"anchor_id": "a1", "phrase_id": 1, "start": 0, "end": 2}],  # stale
        story_i18n={"es": "ves beta en el bosque",       # contains the new anchor
                    "de": "du siehst alt im Wald",       # still has the OLD word
                    "fr": "il voit betamax ici"},        # 'beta' only MID-WORD
        spans_i18n={"es": [{"anchor_id": "a1", "phrase_id": 1, "start": 0,
                            "end": 3}],
                    "de": [{"anchor_id": "a1", "phrase_id": 1, "start": 10,
                            "end": 13}],
                    "fr": [{"anchor_id": "a1", "phrase_id": 1, "start": 8,
                            "end": 12}]})
    _write_content(tmp_path, monkeypatch,
                   {"rs-2.json": {"slug": "rs-2", "mnemo": story}})
    with Session(engine()) as s:
        restory.resync(s)
    m = _mnemo(bid)
    assert m.story_ru == story
    sp = m.spans[0]
    assert story[sp["start"]:sp["end"]] == "beta"  # spans now point at the anchor
    # es still contains "beta" verbatim → kept, spans recomputed mechanically
    assert list(m.story_i18n.keys()) == ["es"]
    es_sp = m.spans_i18n["es"][0]
    assert m.story_i18n["es"][es_sp["start"]:es_sp["end"]] == "beta"
    # de no longer contains the anchor → stale translation dropped
    assert "de" not in (m.spans_i18n or {})
    # fr contains it only inside 'betamax' → coincidental substring, dropped too
    assert "fr" not in (m.spans_i18n or {})


def test_second_run_is_a_noop_and_keeps_i18n(tmp_path, monkeypatch):
    story = "ты видишь beta в лесу"
    bid, _ = _seed("rs-3", [("beta", "Beta.")], story,
                   spans=[],  # stale → first run fixes
                   story_i18n={"es": "ves beta en el bosque"},
                   spans_i18n={"es": [{"anchor_id": "a1", "phrase_id": 1,
                                       "start": 0, "end": 3}]})
    _write_content(tmp_path, monkeypatch,
                   {"rs-3.json": {"slug": "rs-3", "mnemo": story}})
    with Session(engine()) as s:
        restory.resync(s)
    first = _mnemo(bid)
    assert first.spans and first.story_i18n.get("es")
    with Session(engine()) as s:
        restory.resync(s)  # nothing changed → must not touch i18n again
    second = _mnemo(bid)
    assert second.spans == first.spans
    assert second.story_i18n == first.story_i18n
    assert second.spans_i18n == first.spans_i18n
