"""app.rephrase — SRS-safe in-place phrase updates.

The whole point of this tool (vs content.upsert) is that user SRS state, keyed by
phrase_id, must SURVIVE a content edit. These tests lock that guarantee.
"""
import json

from sqlmodel import Session, select

from app import models, rephrase
from app.db import engine


def _seed_batch(slug: str, phrases: list[tuple[str, str]]) -> tuple[int, list[int]]:
    """One batch + phrases + a mnemo. Returns (batch_id, [phrase_id...])."""
    with Session(engine()) as s:
        b = models.Batch(title="T", slug=slug, status="approved", is_free=True)
        s.add(b); s.commit(); s.refresh(b)
        pids = []
        for i, (anchor, en) in enumerate(phrases, start=1):
            p = models.Phrase(batch_id=b.id, order_index=i, anchor=anchor,
                              phrase_en=en, situation_ru="OLD sit", task_ru="OLD task",
                              gloss_i18n={"es": "viejo"})
            s.add(p); s.commit(); s.refresh(p)
            pids.append(p.id)
        s.add(models.MnemoStory(batch_id=b.id, story_ru="старый", spans=[]))
        s.commit()
        return b.id, pids


def _write_content(tmp_path, monkeypatch, files: dict):
    d = tmp_path / "content"
    d.mkdir()
    for name, payload in files.items():
        (d / name).write_text(json.dumps(payload, ensure_ascii=False))
    monkeypatch.setattr(rephrase, "content_dir", lambda: d)
    return d


def test_inplace_update_preserves_phrase_id_and_srs(tmp_path, monkeypatch):
    bid, pids = _seed_batch("rp-1", [("Old", "Old phrase here."), ("Keep", "Keep me.")])
    # a user has SRS progress on the FIRST phrase — this must survive the edit
    with Session(engine()) as s:
        u = models.User(email="rp@t.co", password_hash="x")
        s.add(u); s.commit(); s.refresh(u)
        s.add(models.UserPhraseStat(user_id=u.id, phrase_id=pids[0], batch_id=bid,
                                    srs_status="familiar"))
        s.commit()

    _write_content(tmp_path, monkeypatch, {"rp-1.json": {
        "slug": "rp-1",
        "phrases": [
            {"anchor": "New", "zone": "z", "en": "Something new entirely."},  # changed
            {"anchor": "Keep", "zone": "z", "en": "Keep me."},                # unchanged
        ],
    }})

    with Session(engine()) as s:
        stats = rephrase.resync_phrases(s)
    assert stats["phrases_changed"] == 1
    assert stats["anchors_changed"] == 1

    with Session(engine()) as s:
        p0 = s.get(models.Phrase, pids[0])
        # id preserved → the update was in place, not a wipe-and-recreate
        assert p0.id == pids[0]
        assert p0.anchor == "New"
        assert p0.phrase_en == "Something new entirely."
        # derived caches invalidated so they regenerate against the new text
        assert p0.situation_ru == "" and p0.task_ru == ""
        assert p0.gloss_i18n == {}
        # untouched phrase keeps its caches
        p1 = s.get(models.Phrase, pids[1])
        assert p1.anchor == "Keep" and p1.situation_ru == "OLD sit"
        # the SRS row still points at a live phrase — user progress survived
        stat = s.exec(select(models.UserPhraseStat)
                      .where(models.UserPhraseStat.phrase_id == pids[0])).first()
        assert stat is not None and stat.srs_status == "familiar"


def test_structural_mismatch_is_skipped_not_corrupted(tmp_path, monkeypatch):
    bid, pids = _seed_batch("rp-2", [("A", "Phrase A."), ("B", "Phrase B.")])
    # content now has a DIFFERENT number of phrases → must be skipped, DB untouched
    _write_content(tmp_path, monkeypatch, {"rp-2.json": {
        "slug": "rp-2",
        "phrases": [{"anchor": "A", "zone": "z", "en": "Only one now."}],
    }})
    with Session(engine()) as s:
        stats = rephrase.resync_phrases(s)
    assert stats["batches_skipped"] == 1
    assert stats["phrases_changed"] == 0
    with Session(engine()) as s:
        p0 = s.get(models.Phrase, pids[0])
        assert p0.anchor == "A" and p0.phrase_en == "Phrase A."  # untouched


def test_dry_run_touches_nothing(tmp_path, monkeypatch):
    bid, pids = _seed_batch("rp-3", [("X", "Ex phrase.")])
    _write_content(tmp_path, monkeypatch, {"rp-3.json": {
        "slug": "rp-3",
        "phrases": [{"anchor": "Y", "zone": "z", "en": "Why phrase."}],
    }})
    with Session(engine()) as s:
        stats = rephrase.resync_phrases(s, dry_run=True)
    assert stats["phrases_changed"] == 1  # reported
    with Session(engine()) as s:
        p0 = s.get(models.Phrase, pids[0])
        assert p0.anchor == "X" and p0.phrase_en == "Ex phrase."  # but NOT written


def test_reorder_is_skipped_not_swapped(tmp_path, monkeypatch):
    """Positional matching means applying a reordered file would rewrite texts in
    place under existing UserPhraseStat rows — every user's mastery would silently
    re-attach to a different phrase. Must be detected and skipped."""
    bid, pids = _seed_batch("rp-4", [("Alpha", "Phrase A."), ("Beta", "Phrase B.")])
    _write_content(tmp_path, monkeypatch, {"rp-4.json": {
        "slug": "rp-4",
        "phrases": [
            {"anchor": "Beta", "zone": "z", "en": "Phrase B."},   # swapped
            {"anchor": "Alpha", "zone": "z", "en": "Phrase A."},
        ],
    }})
    with Session(engine()) as s:
        stats = rephrase.resync_phrases(s)
    assert stats["batches_skipped"] == 1
    assert stats["phrases_changed"] == 0
    with Session(engine()) as s:
        p0 = s.get(models.Phrase, pids[0])
        assert p0.anchor == "Alpha" and p0.phrase_en == "Phrase A."  # untouched


def test_chain_rename_is_not_a_reorder(tmp_path, monkeypatch):
    """A bulk replacement may legitimately reuse a vacated anchor: slot 1 renames
    Alpha→Gamma while slot 2 renames Beta→Alpha, each with its own NEW text (the
    v7.5.1 rollout shape). That is not a move — it must be applied, not skipped."""
    bid, pids = _seed_batch("rp-8", [("Alpha", "A text."), ("Beta", "B text.")])
    _write_content(tmp_path, monkeypatch, {"rp-8.json": {
        "slug": "rp-8",
        "phrases": [
            {"anchor": "Gamma", "zone": "z", "en": "G new text."},
            {"anchor": "Alpha", "zone": "z", "en": "A new text."},
        ],
    }})
    with Session(engine()) as s:
        stats = rephrase.resync_phrases(s)
    assert stats["batches_skipped"] == 0
    assert stats["phrases_changed"] == 2
    with Session(engine()) as s:
        p0, p1 = (s.get(models.Phrase, pid) for pid in pids)
        assert (p0.anchor, p0.phrase_en) == ("Gamma", "G new text.")
        assert (p1.anchor, p1.phrase_en) == ("Alpha", "A new text.")


def test_gloss_sync_and_empty_gloss_keeps_db_value(tmp_path, monkeypatch):
    bid, pids = _seed_batch("rp-5", [("A", "Phrase A."), ("B", "Phrase B.")])
    with Session(engine()) as s:
        for pid, g in zip(pids, ["старый А", "старый Б"]):
            p = s.get(models.Phrase, pid)
            p.gloss_ru = g
            s.add(p)
        s.commit()
    _write_content(tmp_path, monkeypatch, {"rp-5.json": {
        "slug": "rp-5",
        "phrases": [
            {"anchor": "A", "zone": "z", "en": "Phrase A.", "gloss_ru": "новый А"},
            {"anchor": "B", "zone": "z", "en": "Phrase B."},  # no gloss in file
        ],
    }})
    with Session(engine()) as s:
        stats = rephrase.resync_phrases(s)
    assert stats["phrases_changed"] == 1
    assert stats["glosses_changed"] == 1
    assert stats["anchors_changed"] == 0
    with Session(engine()) as s:
        p0 = s.get(models.Phrase, pids[0])
        assert p0.gloss_ru == "новый А"
        # gloss feeds situation/task + gloss_i18n → caches invalidated
        assert p0.situation_ru == "" and p0.gloss_i18n == {}
        # file without gloss means "keep the DB value" — and caches stay
        p1 = s.get(models.Phrase, pids[1])
        assert p1.gloss_ru == "старый Б" and p1.situation_ru == "OLD sit"


def test_checkphrase_dropped_only_for_changed_text(tmp_path, monkeypatch):
    """Curated cues are authored against a specific phrase_en; after a text change
    a stale cue sets up the OLD line while scoring compares against the NEW one."""
    bid, pids = _seed_batch("rp-6", [("A", "Phrase A."), ("B", "Phrase B.")])
    with Session(engine()) as s:
        s.add(models.CheckPhrase(phrase_id=pids[0], batch_id=bid, text="cue A"))
        s.add(models.CheckPhrase(phrase_id=pids[1], batch_id=bid, text="cue B"))
        s.commit()
    _write_content(tmp_path, monkeypatch, {"rp-6.json": {
        "slug": "rp-6",
        "phrases": [
            {"anchor": "A", "zone": "z", "en": "Phrase A rewritten."},  # changed
            {"anchor": "B", "zone": "z", "en": "Phrase B."},            # unchanged
        ],
    }})
    with Session(engine()) as s:
        stats = rephrase.resync_phrases(s)
    assert stats["checkphrases_dropped"] == 1
    with Session(engine()) as s:
        cues = s.exec(select(models.CheckPhrase)).all()
        assert [c.phrase_id for c in cues] == [pids[1]]  # only the stale one died


def test_dry_run_counts_but_keeps_checkphrases(tmp_path, monkeypatch):
    bid, pids = _seed_batch("rp-7", [("A", "Phrase A.")])
    with Session(engine()) as s:
        s.add(models.CheckPhrase(phrase_id=pids[0], batch_id=bid, text="cue"))
        s.commit()
    _write_content(tmp_path, monkeypatch, {"rp-7.json": {
        "slug": "rp-7",
        "phrases": [{"anchor": "A", "zone": "z", "en": "Phrase A rewritten."}],
    }})
    with Session(engine()) as s:
        stats = rephrase.resync_phrases(s, dry_run=True)
    assert stats["checkphrases_dropped"] == 1  # reported
    with Session(engine()) as s:
        assert len(s.exec(select(models.CheckPhrase)).all()) == 1  # but kept
