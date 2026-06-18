"""SM-2-lite spaced repetition over UserPhraseStat.

The app already keeps a per-phrase EWMA (avg_score). This module adds the missing
half: a real schedule. Each scored spoken attempt advances an interval/ease and
stamps `next_review_at`, so the deck can surface a phrase *when it is due* instead
of only by static weakness — the actual point of an SRS (the spacing effect).

The schedule is SEEDED from the pre-existing avg_score the first time a phrase is
scheduled, so a phrase already practiced (e.g. through L1/L2 before scheduling
existed) warm-starts at a sensible interval instead of resetting to day one.

Deliberately NOT full FSRS: a sprint-limited, 9-phrase-per-batch corpus has too
little review history to fit per-item half-lives yet. Ship SM-2-lite first; revisit
FSRS once there's data. See TZ-learning-audit.md.
"""
from datetime import datetime, timedelta, timezone

# Qualitative SRS-lite state, advanced alongside the numeric schedule. The deck
# and any competence map read srs_status; the scheduler reads next_review_at.
SRS_NEXT = {
    ("new", "easy"): "familiar", ("new", "slow"): "shaky", ("new", "failed"): "shaky",
    ("shaky", "easy"): "familiar", ("shaky", "slow"): "shaky", ("shaky", "failed"): "shaky",
    ("familiar", "easy"): "automatic", ("familiar", "slow"): "familiar", ("familiar", "failed"): "shaky",
    ("automatic", "easy"): "automatic", ("automatic", "slow"): "familiar", ("automatic", "failed"): "shaky",
}

EASE_DEFAULT = 2.3
EASE_MIN = 1.3
EASE_MAX = 2.7
INTERVAL_MAX_DAYS = 180.0
# A fresh lapse is "due now" — re-drilled this or the next session, not in days.
LAPSE_DELAY = timedelta(minutes=10)


def band_from_score(score: float) -> str:
    """Map a 0..10 spoken-recall score to an SRS grade.

    >=8 mirrors the app's auto-success bar; <5 is a lapse; the middle is 'slow'."""
    if score < 5:
        return "failed"
    if score < 8:
        return "slow"
    return "easy"


def _seed(st) -> None:
    """Warm-start the schedule from the existing EWMA, once, so a long-practiced
    phrase isn't reset to interval 1. No-op once a phrase has been scheduled."""
    if st.next_review_at is not None or (st.interval_days or 0) > 0:
        return
    avg = st.avg_score
    attempts = st.attempts or 0
    if avg is not None and avg >= 8 and attempts >= 3:
        st.reps, st.interval_days, st.ease = 2, 3.0, EASE_DEFAULT
    elif avg is not None and avg >= 5:
        st.reps, st.interval_days, st.ease = 1, 1.0, 2.1
    else:
        st.reps, st.interval_days, st.ease = 0, 0.0, EASE_DEFAULT


def advance(st, band: str, now: datetime | None = None) -> None:
    """Advance the schedule (interval / ease / reps / next_review_at) and srs_status
    for one graded review. `band` is 'easy' | 'slow' | 'failed'. Mutates `st`."""
    now = now or datetime.now(timezone.utc)
    _seed(st)
    ease = st.ease or EASE_DEFAULT
    interval = st.interval_days or 0.0
    reps = st.reps or 0

    if band == "failed":
        reps = 0
        interval = 0.0
        ease = max(EASE_MIN, ease - 0.20)
    elif band == "slow":
        reps = max(1, reps)
        interval = max(0.5, interval * 1.2) if interval > 0 else 0.5
        ease = max(EASE_MIN, ease - 0.15)
    else:  # easy
        reps += 1
        if reps <= 1:
            interval = 1.0
        elif reps == 2:
            interval = 3.0
        else:
            interval = (interval or 1.0) * ease
        ease = min(EASE_MAX, ease + 0.05)

    interval = min(INTERVAL_MAX_DAYS, round(interval, 1))
    st.reps = reps
    st.ease = round(ease, 3)
    st.interval_days = interval
    st.next_review_at = now + (timedelta(days=interval) if interval > 0 else LAPSE_DELAY)
    st.srs_status = SRS_NEXT.get((st.srs_status or "new", band), st.srs_status or "new")
