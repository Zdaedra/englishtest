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
