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
