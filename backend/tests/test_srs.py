"""Unit tests for the SM-2-lite SRS engine (app/srs.py).

These hit the pure functions directly with a UserPhraseStat instance as the
mutable state object — no DB, no network.
"""
from datetime import datetime, timedelta, timezone

import pytest

from app import models, srs

NOW = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)


def _stat(**kw):
    return models.UserPhraseStat(user_id=1, phrase_id=1, batch_id=1, **kw)


@pytest.mark.parametrize("score,band", [
    (0, "failed"), (4.99, "failed"),
    (5, "slow"), (7.99, "slow"),
    (8, "easy"), (10, "easy"),
])
def test_band_from_score_thresholds(score, band):
    assert srs.band_from_score(score) == band


def test_new_easy_promotes_to_familiar():
    st = _stat()  # srs_status "new", reps 0, interval 0.0
    srs.advance(st, "easy", NOW)
    assert st.srs_status == "familiar"
    assert st.reps == 1
    assert st.interval_days == 1.0
    assert st.next_review_at == NOW + timedelta(days=1.0)


def test_easy_ladder_reaches_automatic():
    st = _stat()
    srs.advance(st, "easy", NOW)          # new -> familiar
    assert st.srs_status == "familiar"
    srs.advance(st, "easy", NOW)          # familiar -> automatic
    assert st.srs_status == "automatic"
    assert st.reps == 2
    # reps==2 rung of the interval ladder
    assert st.interval_days == 3.0


def test_failed_is_a_lapse_short_relearn_delay():
    st = _stat(srs_status="familiar", reps=3, interval_days=10.0, ease=2.3)
    srs.advance(st, "failed", NOW)
    assert st.srs_status == "shaky"
    assert st.reps == 0
    assert st.interval_days == 0.0
    # interval 0 -> relearn after LAPSE_DELAY (10 min), not days
    assert st.next_review_at == NOW + srs.LAPSE_DELAY
    # ease is penalised but floored
    assert st.ease == pytest.approx(2.1, abs=1e-6)
    assert st.ease >= srs.EASE_MIN


def test_slow_keeps_shaky_and_small_interval():
    st = _stat()
    srs.advance(st, "slow", NOW)
    assert st.srs_status == "shaky"
    assert st.interval_days == 0.5
    assert st.next_review_at == NOW + timedelta(days=0.5)


def test_ease_is_capped_on_repeated_easy():
    st = _stat(ease=2.69)
    for _ in range(5):
        srs.advance(st, "easy", NOW)
    assert st.ease <= srs.EASE_MAX


def test_interval_capped_at_max_days():
    st = _stat(srs_status="automatic", reps=8, interval_days=170.0, ease=2.7)
    srs.advance(st, "easy", NOW)
    assert st.interval_days <= srs.INTERVAL_MAX_DAYS


def test_srs_next_table_is_total_over_known_states():
    states = ["new", "shaky", "familiar", "automatic"]
    bands = ["easy", "slow", "failed"]
    for s in states:
        for b in bands:
            assert (s, b) in srs.SRS_NEXT, f"missing transition ({s},{b})"


# --- Self-report (swipe) scheduling — the mic-less due loop ------------------
from conftest import commit_sample_batch, phrase_ids  # noqa: E402
from sqlmodel import Session  # noqa: E402

from app.db import engine  # noqa: E402


def _stat_row(uid, pid):
    with Session(engine()) as s:
        return s.exec(models.UserPhraseStat.__table__.select().where(
            models.UserPhraseStat.user_id == uid,
            models.UserPhraseStat.phrase_id == pid)).first()


def test_swipe_right_schedules_unspoken_phrase(make_user):
    """A free/core learner (no mic) still gets a real SM-2 schedule from swipes."""
    admin = make_user(plan="ai", is_admin=True)
    bid = commit_sample_batch(admin)
    pid = phrase_ids(admin, bid)[0]
    free = make_user(plan="free")
    r = free.post("/api/training/swipe",
                  json={"session_id": "s", "phrase_id": pid, "swipe_direction": "right"})
    assert r.status_code == 200, r.text
    st = _stat_row(free.user["id"], pid)
    assert st.next_review_at is not None
    # fast=False caps self-reported knowledge below "automatic"
    assert st.srs_status == "familiar"
    assert st.avg_score is None  # spoken mastery untouched by swipes


def test_swipe_left_lapses_unspoken_phrase(make_user):
    admin = make_user(plan="ai", is_admin=True)
    bid = commit_sample_batch(admin)
    pid = phrase_ids(admin, bid)[0]
    free = make_user(plan="free")
    free.post("/api/training/swipe",
              json={"session_id": "s", "phrase_id": pid, "swipe_direction": "left"})
    st = _stat_row(free.user["id"], pid)
    assert st.srs_status == "shaky" and st.next_review_at is not None


def test_swipe_never_reschedules_a_spoken_phrase(make_user):
    """One scored spoken attempt makes the objective signal the sole scheduler."""
    admin = make_user(plan="ai", is_admin=True)
    bid = commit_sample_batch(admin)
    pid = phrase_ids(admin, bid)[0]
    admin.post("/api/training/answer-text",
               json={"session_id": "s", "phrase_id": pid, "transcript": "whatever"})
    before = _stat_row(admin.user["id"], pid).next_review_at
    assert before is not None
    admin.post("/api/training/swipe",
               json={"session_id": "s", "phrase_id": pid, "swipe_direction": "right"})
    assert _stat_row(admin.user["id"], pid).next_review_at == before


def test_confirm_fail_override_lapses_high_score(make_user):
    """AI said pass (9) → schedule extended; learner overrides to fail → due soon."""
    admin = make_user(plan="ai", is_admin=True)
    bid = commit_sample_batch(admin)
    pid = phrase_ids(admin, bid)[0]
    r = admin.post("/api/training/answer-text",
                   json={"session_id": "s", "phrase_id": pid, "transcript": "x"})
    ev = r.json()
    assert ev["score"] >= 8  # stubbed scorer passes
    long_interval = _stat_row(admin.user["id"], pid).interval_days
    assert long_interval >= 1.0
    admin.post("/api/training/answer/confirm",
               json={"event_id": ev["event_id"], "manual_success": False})
    st = _stat_row(admin.user["id"], pid)
    assert st.interval_days == 0.0 and st.srs_status == "shaky"
