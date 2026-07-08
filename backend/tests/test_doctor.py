"""app.doctor — the integrity checker for the content↔progress contract.

Orphans (stats pointing at dead phrase ids) are impossible through the app (FK
ON) but real on prod: sqlite3-CLI writes run with foreign_keys=OFF. The doctor
must SEE them, fix the safe ones, and never touch TrainingEvent history (its
timestamps feed the day-streak).
"""
from sqlmodel import Session, select

from app import doctor, models
from app.db import engine


def _fk_off(session):
    session.connection().exec_driver_sql("PRAGMA foreign_keys=OFF")


def _seed_batch_with_phrase(slug="dr"):
    with Session(engine()) as s:
        b = models.Batch(title="T", slug=slug, status="approved")
        s.add(b)
        s.commit()
        s.refresh(b)
        p = models.Phrase(batch_id=b.id, order_index=1, anchor="A",
                          phrase_en="Alpha.", situation_ru="s", task_ru="t")
        s.add(p)
        s.commit()
        s.refresh(p)
        u = models.User(email=f"{slug}@t.co", password_hash="x")
        s.add(u)
        s.commit()
        s.refresh(u)
        return b.id, p.id, u.id


def _isolate_content(tmp_path, monkeypatch):
    monkeypatch.setattr(doctor, "content_dir", lambda: tmp_path)


def test_orphan_stats_fixed_but_training_history_kept(tmp_path, monkeypatch):
    _isolate_content(tmp_path, monkeypatch)
    bid, pid, uid = _seed_batch_with_phrase("dr-1")
    with Session(engine()) as s:
        _fk_off(s)  # simulate the prod sqlite3-CLI path (foreign_keys defaults OFF)
        s.add(models.UserPhraseStat(user_id=uid, phrase_id=999999, batch_id=bid))
        s.add(models.TrainingEvent(user_id=uid, session_id="x", batch_id=bid,
                                   phrase_id=999999, training_mode="swipe"))
        s.add(models.CheckPhrase(phrase_id=999999, batch_id=bid, text="cue"))
        s.commit()

    problems = doctor.run(fix=False)
    assert problems["orphaned_user_phrase_stats"] == 1
    assert problems["orphaned_training_events"] == 1
    assert problems["orphaned_check_phrases"] == 1

    doctor.run(fix=True)
    with Session(engine()) as s:
        # orphaned SRS row + stale cue deleted…
        assert s.exec(select(models.UserPhraseStat)).all() == []
        assert s.exec(select(models.CheckPhrase)).all() == []
        # …but the raw training log survives (day-streak is computed from it)
        assert len(s.exec(select(models.TrainingEvent)).all()) == 1

    problems = doctor.run(fix=False)
    assert "orphaned_user_phrase_stats" not in problems
    assert "orphaned_check_phrases" not in problems


def test_duplicate_stats_deduped_keeping_most_progressed(tmp_path, monkeypatch):
    _isolate_content(tmp_path, monkeypatch)
    bid, pid, uid = _seed_batch_with_phrase("dr-2")
    with Session(engine()) as s:
        s.add(models.UserPhraseStat(user_id=uid, phrase_id=pid, batch_id=bid,
                                    attempts=5, srs_status="familiar"))
        s.add(models.UserPhraseStat(user_id=uid, phrase_id=pid, batch_id=bid,
                                    attempts=1, srs_status="new"))
        s.commit()

    problems = doctor.run(fix=False)
    assert problems["duplicate_stats"] == 1

    doctor.run(fix=True)
    with Session(engine()) as s:
        rows = s.exec(select(models.UserPhraseStat)).all()
        assert len(rows) == 1 and rows[0].attempts == 5


def test_cross_attached_stat_reported_not_deleted(tmp_path, monkeypatch):
    """stat.batch_id != phrase.batch_id is the rowid-reuse signature — flag it
    for human review, never auto-delete."""
    _isolate_content(tmp_path, monkeypatch)
    bid, pid, uid = _seed_batch_with_phrase("dr-3")
    with Session(engine()) as s:
        other = models.Batch(title="T2", slug="dr-3b", status="approved")
        s.add(other)
        s.commit()
        s.refresh(other)
        s.add(models.UserPhraseStat(user_id=uid, phrase_id=pid,
                                    batch_id=other.id))
        s.commit()

    problems = doctor.run(fix=False)
    assert problems["cross_attached_stats"] == 1
    doctor.run(fix=True)
    with Session(engine()) as s:
        assert len(s.exec(select(models.UserPhraseStat)).all()) == 1  # untouched


def test_clean_db_reports_no_problems(tmp_path, monkeypatch):
    _isolate_content(tmp_path, monkeypatch)
    _seed_batch_with_phrase("dr-4")
    assert doctor.run(fix=False) == {}


def test_private_imports_are_not_flagged(tmp_path, monkeypatch):
    """User private imports (owner_id set) legitimately lack gen_context/i18n —
    doctor must not stay permanently red (nor route paid LLM runs at private
    content) because a client imported a batch."""
    _isolate_content(tmp_path, monkeypatch)
    with Session(engine()) as s:
        u = models.User(email="dr5@t.co", password_hash="x")
        s.add(u)
        s.commit()
        s.refresh(u)
        b = models.Batch(title="T", slug="dr-5", status="approved", owner_id=u.id)
        s.add(b)
        s.commit()
        s.refresh(b)
        # empty situation_ru/task_ru — a cache hole on a CURATED batch,
        # legitimate on a private import
        s.add(models.Phrase(batch_id=b.id, order_index=1, anchor="A",
                            phrase_en="Alpha."))
        s.commit()
    assert doctor.run(fix=False) == {}


def test_missing_anchor_reported_separately_from_stale_spans(tmp_path, monkeypatch):
    """A story that legitimately lacks an anchor must not be reported as 'stale
    spans' (restory would be a no-op) — it needs a content fix, not a resync."""
    _isolate_content(tmp_path, monkeypatch)
    with Session(engine()) as s:
        b = models.Batch(title="T", slug="dr-6", status="approved")
        s.add(b)
        s.commit()
        s.refresh(b)
        s.add(models.Phrase(batch_id=b.id, order_index=1, anchor="beta",
                            phrase_en="Beta.", situation_ru="s", task_ru="t"))
        s.add(models.Phrase(batch_id=b.id, order_index=2, anchor="omega",
                            phrase_en="Omega.", situation_ru="s", task_ru="t"))
        s.commit()
        # story contains ONLY beta; spans already equal a fresh recompute
        s.add(models.MnemoStory(
            batch_id=b.id, story_ru="ты видишь beta в лесу",
            spans=[{"anchor_id": "a1", "phrase_id": 1, "start": 10, "end": 14}]))
        s.commit()
    problems = doctor.run(fix=False)
    assert "stale_spans" not in problems
    assert problems["missing_anchors"] == 1
