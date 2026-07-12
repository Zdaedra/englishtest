"""AUDIT-1: per-user rows are UNIQUE per target. The get-or-create endpoints used
to race (two simultaneous first writes both inserted, doubling the freemium cap
and mastery stats). Contract now: the DB refuses twin rows (unique indexes from
db._migrate), racing losers are retried onto the winner's row, the migration
dedups pre-existing twins, and doctor reports/fixes any that sneak in sideways.
"""
from datetime import datetime, timezone

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from app import doctor, models
from app.db import _migrate, engine


def _seed_batch(slug: str) -> tuple[int, int]:
    with Session(engine()) as s:
        b = models.Batch(title=f"T-{slug}", slug=slug, status="approved")
        s.add(b)
        s.commit()
        s.refresh(b)
        p = models.Phrase(batch_id=b.id, order_index=1, anchor="a",
                          phrase_en=f"Phrase {slug}.", situation_ru="s", task_ru="t")
        s.add(p)
        s.commit()
        s.refresh(p)
        return b.id, p.id


# ---- the DB-level guarantee ----------------------------------------------------

def test_duplicate_progress_row_is_rejected(make_user):
    c = make_user(plan="ai", is_admin=True)
    uid = c.user["id"]  # type: ignore[attr-defined]
    bid, _pid = _seed_batch("ux-bp")
    with Session(engine()) as s:
        s.add(models.BatchProgress(user_id=uid, batch_id=bid, activated=True, on_path=True))
        s.commit()
        s.add(models.BatchProgress(user_id=uid, batch_id=bid, activated=True, on_path=True))
        with pytest.raises(IntegrityError):
            s.commit()


def test_duplicate_stat_row_is_rejected(make_user):
    c = make_user(plan="ai", is_admin=True)
    uid = c.user["id"]  # type: ignore[attr-defined]
    bid, pid = _seed_batch("ux-st")
    with Session(engine()) as s:
        s.add(models.UserPhraseStat(user_id=uid, phrase_id=pid, batch_id=bid))
        s.commit()
        s.add(models.UserPhraseStat(user_id=uid, phrase_id=pid, batch_id=bid))
        with pytest.raises(IntegrityError):
            s.commit()


# ---- the racing loser lands on the winner's row --------------------------------

def test_put_progress_retries_race_loser_onto_winner_row(make_user, monkeypatch):
    """Simulate the exact race: the loser's SELECT sees nothing, then its INSERT
    hits the unique index because the winner committed in between. The endpoint
    must retry on a fresh snapshot and apply the patch to the winner's row."""
    c = make_user(plan="ai", is_admin=True)
    uid = c.user["id"]  # type: ignore[attr-defined]
    bid, _pid = _seed_batch("race-bp")

    from app.routers import progress as prog_mod
    real = prog_mod._put_progress
    state = {"raced": False}

    def racing(batch_id, patch, user_id, session):
        if not state["raced"]:
            state["raced"] = True
            # the "winner" commits its row mid-flight, then the real handler
            # (whose get-or-create path inserts) collides with it
            with Session(engine()) as other:
                other.add(models.BatchProgress(user_id=user_id, batch_id=batch_id))
                other.commit()
        return real(batch_id, patch, user_id, session)

    monkeypatch.setattr(prog_mod, "_put_progress", racing)
    r = c.put(f"/api/progress/{bid}", json={"activated": True})
    assert r.status_code == 200, r.text
    assert r.json()["activated"] is True
    with Session(engine()) as s:
        rows = s.exec(select(models.BatchProgress).where(
            models.BatchProgress.user_id == uid,
            models.BatchProgress.batch_id == bid)).all()
    assert len(rows) == 1 and rows[0].activated   # one row, patch applied


def test_swipe_retries_race_loser_onto_winner_row(make_user, monkeypatch):
    c = make_user(plan="ai", is_admin=True)
    uid = c.user["id"]  # type: ignore[attr-defined]
    bid, pid = _seed_batch("race-st")

    from app.routers import training as tr_mod
    real = tr_mod._swipe
    state = {"raced": False}

    def racing(body, user_id, session):
        if not state["raced"]:
            state["raced"] = True
            with Session(engine()) as other:
                other.add(models.UserPhraseStat(user_id=user_id, phrase_id=body.phrase_id,
                                                batch_id=bid))
                other.commit()
        return real(body, user_id, session)

    monkeypatch.setattr(tr_mod, "_swipe", racing)
    r = c.post("/api/training/swipe", json={
        "session_id": "race", "phrase_id": pid, "swipe_direction": "right"})
    assert r.status_code == 200, r.text
    with Session(engine()) as s:
        rows = s.exec(select(models.UserPhraseStat).where(
            models.UserPhraseStat.user_id == uid,
            models.UserPhraseStat.phrase_id == pid)).all()
    assert len(rows) == 1
    assert rows[0].self_ewma == 1.0               # the swipe landed on the winner's row


# ---- migration dedups pre-existing twins ---------------------------------------

def test_migrate_dedups_existing_twins_keeping_most_progressed(make_user):
    c = make_user(plan="ai", is_admin=True)
    uid = c.user["id"]  # type: ignore[attr-defined]
    bid, pid = _seed_batch("mig-dd")
    with Session(engine()) as s:
        # sneak twins in past the index (drop it like a pre-migration DB would be)
        s.execute(text("DROP INDEX IF EXISTS ux_stat_user_phrase"))
        s.execute(text("DROP INDEX IF EXISTS ux_progress_user_batch"))
        s.add(models.UserPhraseStat(user_id=uid, phrase_id=pid, batch_id=bid, attempts=1))
        s.add(models.UserPhraseStat(user_id=uid, phrase_id=pid, batch_id=bid, attempts=5))
        s.add(models.BatchProgress(user_id=uid, batch_id=bid, activated=False))
        s.add(models.BatchProgress(user_id=uid, batch_id=bid, activated=True,
                                   updated_at=datetime.now(timezone.utc)))
        s.commit()
        _migrate(s)                                # dedup + recreate the indexes
        stats = s.exec(select(models.UserPhraseStat).where(
            models.UserPhraseStat.user_id == uid,
            models.UserPhraseStat.phrase_id == pid)).all()
        prog = s.exec(select(models.BatchProgress).where(
            models.BatchProgress.user_id == uid,
            models.BatchProgress.batch_id == bid)).all()
    assert len(stats) == 1 and stats[0].attempts == 5      # most-progressed kept
    assert len(prog) == 1 and prog[0].activated is True


# ---- doctor: twin progress rows are seen and fixable ---------------------------

def test_doctor_reports_and_fixes_duplicate_progress(make_user, tmp_path, monkeypatch):
    monkeypatch.setattr(doctor, "content_dir", lambda: tmp_path)
    c = make_user(plan="ai", is_admin=True)
    uid = c.user["id"]  # type: ignore[attr-defined]
    bid, _pid = _seed_batch("dr-bp")
    with Session(engine()) as s:
        s.execute(text("DROP INDEX IF EXISTS ux_progress_user_batch"))
        s.add(models.BatchProgress(user_id=uid, batch_id=bid, activated=False))
        s.add(models.BatchProgress(user_id=uid, batch_id=bid, activated=True, l3_passed=True))
        s.commit()
    assert doctor.run(fix=False).get("duplicate_progress") == 1
    doctor.run(fix=True)
    with Session(engine()) as s:
        rows = s.exec(select(models.BatchProgress).where(
            models.BatchProgress.user_id == uid,
            models.BatchProgress.batch_id == bid)).all()
    assert len(rows) == 1 and rows[0].l3_passed            # most-progressed kept
