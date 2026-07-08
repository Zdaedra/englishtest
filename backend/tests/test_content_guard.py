"""content.upsert progress-preservation guard.

Replacing a batch's children mints new phrase ids, destroying per-user SRS state
(UserPhraseStat is keyed by phrase_id). The contract: upsert BLOCKS when live
progress exists (LiveProgressError / HTTP 409) BEFORE writing anything, and the
explicit force path deletes the dependent user rows first — so nothing orphans,
FK enforcement never explodes mid-write, and PlaybackSession listening history
(keyed by the surviving batch_id) is not collateral damage.
"""
import json

import pytest
from sqlmodel import Session, select

from app import content, models
from app.content import BatchAuthor, LiveProgressError, PhraseAuthor
from app.db import engine


def _author(slug, title="T", phrases=(("A", "Alpha line."), ("B", "Beta line."))):
    return BatchAuthor(slug=slug, title=title, zones=["z"],
                       phrases=[PhraseAuthor(anchor=a, en=e, zone="z")
                                for a, e in phrases],
                       mnemo="")


def _upsert(session, author, **kw):
    batch_in, _ = content.to_batch_in(author)
    return content.upsert(session, batch_in, slug=author.slug, **kw)


def _phrase_rows(session, batch_id):
    return session.exec(select(models.Phrase)
                        .where(models.Phrase.batch_id == batch_id)
                        .order_by(models.Phrase.order_index)).all()


def _add_user_with_stat(session, batch_id, phrase_id):
    u = models.User(email=f"cg{batch_id}@t.co", password_hash="x")
    session.add(u)
    session.commit()
    session.refresh(u)
    session.add(models.UserPhraseStat(user_id=u.id, phrase_id=phrase_id,
                                      batch_id=batch_id, srs_status="familiar"))
    session.commit()
    return u


def test_blocked_when_users_have_progress():
    with Session(engine()) as s:
        batch, created = _upsert(s, _author("cg-1"))
        assert created
        old_ids = [p.id for p in _phrase_rows(s, batch.id)]
        _add_user_with_stat(s, batch.id, old_ids[0])

    with Session(engine()) as s:
        with pytest.raises(LiveProgressError) as ei:
            _upsert(s, _author("cg-1", title="NEW TITLE"))
        assert "userphrasestat" in str(ei.value)

    with Session(engine()) as s:
        b = s.exec(select(models.Batch).where(models.Batch.slug == "cg-1")).first()
        # guard fired BEFORE any write: metadata AND children untouched
        assert b.title == "T"
        assert [p.id for p in _phrase_rows(s, b.id)] == old_ids
        stat = s.exec(select(models.UserPhraseStat)).first()
        assert stat is not None and stat.srs_status == "familiar"


def test_force_wipe_deletes_dependents_cleanly():
    with Session(engine()) as s:
        batch, _ = _upsert(s, _author("cg-2"))
        pid0 = _phrase_rows(s, batch.id)[0].id
        u = _add_user_with_stat(s, batch.id, pid0)
        s.add(models.TrainingEvent(user_id=u.id, session_id="s1",
                                   batch_id=batch.id, phrase_id=pid0,
                                   training_mode="swipe"))
        s.add(models.PhraseAttempt(user_id=u.id, phrase_id=pid0, score=7))
        s.add(models.ReviewEvent(user_id=u.id, phrase_id=pid0))
        s.add(models.PlaybackSession(user_id=u.id, batch_id=batch.id))
        s.add(models.CheckPhrase(phrase_id=pid0, batch_id=batch.id, text="cue"))
        s.add(models.ContextExample(phrase_id=pid0))
        s.commit()

    with Session(engine()) as s:
        batch2, created = _upsert(s, _author("cg-2", title="T2"),
                                  on_live_progress="wipe")
        assert not created and batch2.title == "T2"

    with Session(engine()) as s:
        b = s.exec(select(models.Batch).where(models.Batch.slug == "cg-2")).first()
        # dependents were deleted FIRST — nothing orphaned anywhere
        assert content.progress_census(s, b.id) == {}
        assert s.exec(select(models.UserPhraseStat)).all() == []
        assert s.exec(select(models.TrainingEvent)).all() == []
        assert s.exec(select(models.PhraseAttempt)).all() == []
        assert s.exec(select(models.ReviewEvent)).all() == []
        # content-side children keyed by phrase_id died with their phrases
        assert s.exec(select(models.CheckPhrase)).all() == []
        assert s.exec(select(models.ContextExample)).all() == []
        # listening history SURVIVES: batch_id is stable, plan is never re-read
        assert len(s.exec(select(models.PlaybackSession)).all()) == 1


def test_replace_without_progress_needs_no_force():
    with Session(engine()) as s:
        batch, _ = _upsert(s, _author("cg-3"))
    with Session(engine()) as s:
        batch2, created = _upsert(s, _author(
            "cg-3", phrases=(("C", "Gamma line."), ("D", "Delta line."))))
        assert not created
        rows = _phrase_rows(s, batch2.id)
        # replaced without error — no progress, nothing to guard. (NB: SQLite may
        # legally REUSE the freed rowids here — which is exactly why orphaned
        # stats re-attaching to recycled ids is dangerous, see app.doctor.)
        assert [p.anchor for p in rows] == ["C", "D"]


def test_load_all_reports_blocked_and_continues(tmp_path, monkeypatch):
    with Session(engine()) as s:
        batch, _ = _upsert(s, _author("cg-a"))
        _add_user_with_stat(s, batch.id, _phrase_rows(s, batch.id)[0].id)

    d = tmp_path / "content"
    d.mkdir()
    for slug in ("cg-a", "cg-b"):
        (d / f"{slug}.json").write_text(json.dumps({
            "slug": slug, "title": "T", "zones": ["z"],
            "phrases": [{"anchor": "A", "en": "Alpha line.", "zone": "z"}],
            "mnemo": "",
        }, ensure_ascii=False))
    monkeypatch.setattr(content, "content_dir", lambda: d)

    with Session(engine()) as s:
        results = content.load_all(s)
    # the trained batch is blocked+reported; the seed run continues past it
    assert [r["blocked"] for r in results] == [True, False]
    assert results[0]["batch"] is None and results[0]["slug"] == "cg-a"
    assert results[1]["batch"].slug == "cg-b"


def test_unchanged_file_is_skipped_even_with_progress_and_force(tmp_path, monkeypatch):
    """The catalog-wide-force footgun: `seed --force-progress-loss` must only
    touch EDITED batches. An unchanged file is a no-op — ids and stats survive."""
    with Session(engine()) as s:
        batch, _ = _upsert(s, _author("cg-u"))
        old_ids = [p.id for p in _phrase_rows(s, batch.id)]
        _add_user_with_stat(s, batch.id, old_ids[0])
        exported = content.to_authoring(s, batch)  # byte-identical authoring

    d = tmp_path / "content"
    d.mkdir()
    (d / "cg-u.json").write_text(json.dumps(exported, ensure_ascii=False))
    monkeypatch.setattr(content, "content_dir", lambda: d)

    with Session(engine()) as s:
        results = content.load_all(s, on_live_progress="wipe")  # force mode!
    assert results[0]["unchanged"] is True and results[0]["blocked"] is False

    with Session(engine()) as s:
        b = s.exec(select(models.Batch).where(models.Batch.slug == "cg-u")).first()
        assert [p.id for p in _phrase_rows(s, b.id)] == old_ids  # untouched
        stat = s.exec(select(models.UserPhraseStat)).first()
        assert stat is not None and stat.srs_status == "familiar"


def test_force_wipe_is_atomic_when_replacement_fails(monkeypatch):
    """If anything fails mid-replace, the progress wipe must roll back too — no
    window where progress is destroyed but the batch is stale/childless."""
    with Session(engine()) as s:
        batch, _ = _upsert(s, _author("cg-x"))
        old_ids = [p.id for p in _phrase_rows(s, batch.id)]
        _add_user_with_stat(s, batch.id, old_ids[0])

    def _boom(session, batch, batch_in):
        raise RuntimeError("simulated failure during child write")

    monkeypatch.setattr(content, "_write_children", _boom)
    with Session(engine()) as s:
        with pytest.raises(RuntimeError):
            _upsert(s, _author("cg-x", title="T2"), on_live_progress="wipe")
    # rollback: progress, children and metadata all intact
    with Session(engine()) as s:
        b = s.exec(select(models.Batch).where(models.Batch.slug == "cg-x")).first()
        assert b.title == "T"
        assert [p.id for p in _phrase_rows(s, b.id)] == old_ids
        assert len(s.exec(select(models.UserPhraseStat)).all()) == 1


def test_force_reauthor_preserves_curated_glosses():
    """Content files historically omit gloss_ru; a re-author must not zero the
    curated DB glosses (recall-mode audio and gloss_i18n depend on them)."""
    with Session(engine()) as s:
        batch, _ = _upsert(s, _author("cg-g"))
        p0 = _phrase_rows(s, batch.id)[0]
        p0.gloss_ru = "куратор писал"
        s.add(p0)
        s.commit()
    with Session(engine()) as s:
        # same anchors, edited text, NO glosses in the incoming payload
        _upsert(s, _author("cg-g", phrases=(("A", "Alpha rewritten."),
                                            ("B", "Beta line."))))
    with Session(engine()) as s:
        b = s.exec(select(models.Batch).where(models.Batch.slug == "cg-g")).first()
        rows = _phrase_rows(s, b.id)
        assert rows[0].gloss_ru == "куратор писал"  # backfilled by anchor


def test_replace_invalidates_batch_i18n_only_when_field_changed():
    with Session(engine()) as s:
        batch, _ = _upsert(s, _author("cg-i"))
        batch.title_i18n = {"es": "Título"}
        batch.theme_i18n = {"es": "Tema"}
        s.add(batch)
        s.commit()
    with Session(engine()) as s:
        # same title → its translation survives; theme changes → cache cleared
        author = _author("cg-i")
        author.theme = "новая тема"
        _upsert(s, author)
    with Session(engine()) as s:
        b = s.exec(select(models.Batch).where(models.Batch.slug == "cg-i")).first()
        assert b.title_i18n == {"es": "Título"}
        assert b.theme_i18n == {}


def test_route_upsert_409_then_force(make_user):
    admin = make_user(plan="ai", is_admin=True)
    author = {"slug": "cg-r", "title": "T", "zones": ["z"],
              "phrases": [{"anchor": "A", "en": "Alpha line.", "zone": "z"}],
              "mnemo": ""}
    r = admin.post("/api/imports/upsert", json=author)
    assert r.status_code == 200, r.text
    bid = r.json()["id"]

    with Session(engine()) as s:
        pid = _phrase_rows(s, bid)[0].id
        s.add(models.UserPhraseStat(user_id=admin.user["id"], phrase_id=pid,
                                    batch_id=bid))
        s.commit()

    r = admin.post("/api/imports/upsert", json=author)
    assert r.status_code == 409, r.text
    detail = r.json()["detail"]
    assert detail["error"] == "live_progress" and detail["slug"] == "cg-r"

    r = admin.post("/api/imports/upsert?force=true", json=author)
    assert r.status_code == 200, r.text
