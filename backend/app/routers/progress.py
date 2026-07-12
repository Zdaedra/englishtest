"""Server-side per-batch learning state (single-user). Source of truth for the
swipe-trainer's 'active in-progress batches' and the learning path. Mirrors what
used to live in client localStorage (ee-progress-*); PUT upserts partial fields.
"""
from datetime import date, datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from .. import access, models
from ..auth import current_user_id
from ..db import get_session
from ..entitlements import FOCUS_CAP, user_entitlements

router = APIRouter(prefix="/api/progress", tags=["progress"])


def _serialize(bp: models.BatchProgress) -> dict:
    return {
        "batch_id": bp.batch_id,
        "on_path": bp.on_path,
        "on_path_at": bp.on_path_at.isoformat() if bp.on_path_at else None,
        "path_rank": bp.path_rank,
        "activated": bp.activated,
        "activated_at": bp.activated_at.isoformat() if bp.activated_at else None,
        "l1_listened": bp.l1_listened,
        "l1_retold": bp.l1_retold,
        "l1_best_seq": bp.l1_best_seq,
        "l3_s1": bp.l3_s1,
        "l3_s2": bp.l3_s2,
        "l3_passed": bp.l3_passed,
        "completed_at": bp.completed_at.isoformat() if bp.completed_at else None,
    }


def _empty(batch_id: int) -> dict:
    return {"batch_id": batch_id, "on_path": False, "on_path_at": None,
            "path_rank": None, "activated": False, "activated_at": None,
            "l1_listened": False, "l1_retold": False, "l1_best_seq": None,
            "l3_s1": False, "l3_s2": False, "l3_passed": False, "completed_at": None}


class ProgressPatch(BaseModel):
    on_path: bool | None = None
    # Explicit null clears the manual order (falls back to the computed plan);
    # "not sent" leaves it untouched (exclude_unset distinguishes the two).
    path_rank: int | None = None
    activated: bool | None = None
    l1_listened: bool | None = None
    l1_retold: bool | None = None
    l1_best_seq: float | None = None
    l3_s1: bool | None = None
    l3_s2: bool | None = None
    l3_passed: bool | None = None


@router.get("")
def list_progress(user_id: int = Depends(current_user_id), session: Session = Depends(get_session)):
    return [_serialize(bp) for bp in session.exec(select(models.BatchProgress)
            .where(models.BatchProgress.user_id == user_id)).all()]


# --- Work-based day streak ----------------------------------------------------
# A day counts only if the user actually trained (any TrainingEvent: swipe or a
# scored spoken answer) — opening the app is not work. One single-day gap can be
# bridged by an automatic "freeze", re-earned after FREEZE_EARN_DAYS active days,
# so a busy professional's one missed day doesn't zero the habit.
FREEZE_EARN_DAYS = 7


def compute_streak(active_days: set[date], today: date) -> dict:
    """Walk the activity history and return the CURRENT streak state.

    Freeze rule: a gap of exactly one day extends the run iff at least
    FREEZE_EARN_DAYS active days passed since the previous bridge (the first
    bridge of a run is free). Longer gaps always break the run.
    """
    if not active_days:
        return {"streak": 0, "today_done": False, "freeze_available": True,
                "last_active": None}
    streak = 0
    since_freeze = FREEZE_EARN_DAYS  # first freeze of a run is available
    last: date | None = None
    for d in sorted(active_days):
        gap = (d - last).days if last else 1
        if last is None or gap == 1:
            streak += 1
            since_freeze += 1
        elif gap == 2 and since_freeze >= FREEZE_EARN_DAYS:
            streak += 1
            since_freeze = 0
        else:
            streak = 1
            since_freeze = FREEZE_EARN_DAYS
        last = d
    freeze_available = since_freeze >= FREEZE_EARN_DAYS
    # Is the run still alive today? Alive if the last active day is today or
    # yesterday; a 2-day-old run survives (pending today's work) only on a freeze.
    age = (today - last).days
    alive = age <= 1 or (age == 2 and freeze_available)
    return {"streak": streak if alive else 0,
            "today_done": last == today,
            "freeze_available": freeze_available,
            "last_active": last.isoformat()}


@router.get("/streak")
def get_streak(tz_offset: int = Query(0, ge=-14 * 60, le=14 * 60),
               user_id: int = Depends(current_user_id),
               session: Session = Depends(get_session)):
    """Current work streak. `tz_offset` is JS Date.getTimezoneOffset() (minutes,
    UTC minus local) so days roll over at the learner's local midnight."""
    rows = session.exec(select(models.TrainingEvent.created_at).where(
        models.TrainingEvent.user_id == user_id)).all()
    local = lambda dt: (dt - timedelta(minutes=tz_offset)).date()  # noqa: E731
    today = local(datetime.now(timezone.utc).replace(tzinfo=None))
    return compute_streak({local(dt) for dt in rows if dt}, today)


@router.get("/{batch_id}")
def get_progress(batch_id: int, user_id: int = Depends(current_user_id),
                 session: Session = Depends(get_session)):
    """Single-row progress with an empty-stub fallback (not 404). No app screen
    hydrates through this — the client uses GET "" (listProgress) — but it's a
    reasonable REST read and part of a tested contract (empty stub for an
    untouched batch), so it stays."""
    bp = session.exec(select(models.BatchProgress).where(
        models.BatchProgress.user_id == user_id,
        models.BatchProgress.batch_id == batch_id)).first()
    return _serialize(bp) if bp else _empty(batch_id)


@router.put("/{batch_id}")
def put_progress(batch_id: int, patch: ProgressPatch,
                 user_id: int = Depends(current_user_id),
                 session: Session = Depends(get_session)):
    """AUDIT-1: two simultaneous FIRST writes for a (user, batch) both used to
    insert (get-or-create raced) — the unique index now rejects the loser, and
    we retry its patch once on a fresh snapshot, landing it on the winner's row."""
    try:
        return _put_progress(batch_id, patch, user_id, session)
    except IntegrityError:
        session.rollback()
        return _put_progress(batch_id, patch, user_id, session)


def _put_progress(batch_id: int, patch: ProgressPatch, user_id: int,
                  session: Session):
    batch = session.get(models.Batch, batch_id)
    if not batch:
        raise HTTPException(404, "Batch not found")
    bp = session.exec(select(models.BatchProgress).where(
        models.BatchProgress.user_id == user_id,
        models.BatchProgress.batch_id == batch_id)).first()
    if not bp:
        bp = models.BatchProgress(user_id=user_id, batch_id=batch_id)
    now = datetime.now(timezone.utc)
    data = patch.model_dump(exclude_unset=True)

    # The exam verdict must be EARNED: the client computes its L3 gate locally, but
    # a bare "l3_passed: true" with no spoken exam attempts on record is tampering
    # (or a broken client) — reject it. Any real pass leaves SequenceAttempt rows.
    if data.get("l3_passed") and not bp.l3_passed:
        proof = session.exec(select(models.SequenceAttempt).where(
            models.SequenceAttempt.user_id == user_id,
            models.SequenceAttempt.batch_id == batch_id,
            models.SequenceAttempt.score >= 7)).first()
        if not proof:
            raise HTTPException(409, "l3_unproven")

    # Resolve the two axes with the invariant activated ⊆ on_path. Engaging a lesson
    # keeps the batch on-path AND active (so starting a lesson never drops it from
    # the deck). Leaving the path drops it from the deck.
    LESSON_FLAGS = ("l1_listened", "l1_retold", "l3_s1", "l3_s2", "l3_passed")
    lesson_engaged = any(data.get(k) for k in LESSON_FLAGS)
    removing_from_path = data.get("on_path") is False   # explicit "Remove from path"
    next_activated = data.get("activated", bp.activated)
    next_on_path = data.get("on_path", bp.on_path)
    if lesson_engaged:
        next_activated = True
        next_on_path = True
    # Activating implies on-path — UNLESS the patch is explicitly removing from path
    # (then activated must drop too). Explicit removal wins over a stale activated.
    if next_activated and not removing_from_path:
        next_on_path = True
    if not next_on_path:
        next_activated = False

    # "Active focus" = the metered set {activated && !l3_passed}. A write ENTERS that
    # set iff the batch will be in it and wasn't already (so passing the exam in this
    # same write — which leaves it activated&&passed — never counts as entering).
    next_l3 = bool(data.get("l3_passed", bp.l3_passed))
    was_in_focus = bool(bp.activated) and not bool(bp.l3_passed)
    will_be_in_focus = bool(next_activated) and not next_l3
    entering_focus = will_be_in_focus and not was_in_focus
    explicit_activation = entering_focus and not lesson_engaged

    # (a) Paywall — walls ONLY an explicit "Activate" on locked (paid) content. The
    # lesson flow gates its own access, so never re-wall content mid-lesson.
    if explicit_activation:
        u = session.get(models.User, user_id)
        if not access.batch_usable(u.plan if u else "free", batch, user_id):
            raise HTTPException(403, "locked")

    # (b) Focus cap — a PEDAGOGICAL limit that applies to EVERY learner (free & paid)
    # and EVERY path INTO focus (the menu OR starting a lesson on a new batch): you
    # can't hold more than FOCUS_CAP batches in active focus at once, so you finish
    # and pass exams instead of piling up. De-activation and continuing/​passing the
    # ones already in focus are never blocked (they don't enter the set). Passing an
    # exam frees a slot. The plan's max_active_batches can only make this stricter.
    if entering_focus:
        plan_cap = user_entitlements(session, user_id)["max_active_batches"]
        cap = FOCUS_CAP if plan_cap is None else min(plan_cap, FOCUS_CAP)
        active = len(session.exec(select(models.BatchProgress).where(
            models.BatchProgress.user_id == user_id,
            models.BatchProgress.activated == True,   # noqa: E712
            models.BatchProgress.l3_passed == False)).all())  # noqa: E712
        if active >= cap:
            raise HTTPException(403, "limit_active")

    if next_activated and not bp.activated:
        bp.activated_at = now
    if next_on_path and not bp.on_path:
        bp.on_path_at = now
    if data.get("l3_passed") and not bp.l3_passed:
        bp.completed_at = now
    for k, v in data.items():
        if k in ("activated", "on_path"):
            continue
        setattr(bp, k, v)
    bp.activated = next_activated
    bp.on_path = next_on_path
    bp.updated_at = now
    session.add(bp)
    session.commit()
    return _serialize(bp)
