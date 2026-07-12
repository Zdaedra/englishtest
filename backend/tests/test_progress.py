"""Per-user batch progress + activation gates (lock + max-active-batches cap)."""
from sqlmodel import Session

from app import models
from app.db import engine
from conftest import commit_sample_batch


def _free_batch(slug):
    with Session(engine()) as s:
        b = models.Batch(title="T", slug=slug, status="approved",
                         owner_id=None, is_free=True)
        s.add(b)
        s.commit()
        s.refresh(b)
        return b.id


def test_progress_list_empty(make_user):
    c = make_user(plan="ai", is_admin=True)
    assert c.get("/api/progress").json() == []


def test_progress_single_is_empty_stub_not_404(make_user):
    c = make_user(plan="ai", is_admin=True)
    r = c.get("/api/progress/123")
    assert r.status_code == 200
    assert r.json()["batch_id"] == 123
    assert r.json()["activated"] is False


def test_progress_patch_updates_fields(make_user):
    admin = make_user(plan="ai", is_admin=True)
    bid = commit_sample_batch(admin)
    r = admin.put(f"/api/progress/{bid}",
                  json={"l1_listened": True, "l1_best_seq": 8.5})
    assert r.status_code == 200, r.text
    assert r.json()["l1_listened"] is True
    assert r.json()["l1_best_seq"] == 8.5


def test_activate_locked_batch_is_403(make_user):
    admin = make_user(plan="ai", is_admin=True)
    bid = commit_sample_batch(admin)             # paid catalog batch
    free = make_user(plan="free")
    r = free.put(f"/api/progress/{bid}", json={"activated": True})
    assert r.status_code == 403
    assert r.json()["detail"] == "locked"


def test_activate_free_batch_succeeds(make_user):
    bid = _free_batch("free-1")
    free = make_user(plan="free")
    r = free.put(f"/api/progress/{bid}", json={"activated": True})
    assert r.status_code == 200, r.text
    assert r.json()["activated"] is True


def test_patch_missing_batch_is_404(make_user):
    c = make_user(plan="ai", is_admin=True)
    assert c.put("/api/progress/999999", json={"l1_listened": True}).status_code == 404


def test_active_batch_cap_for_free(make_user):
    """free max_active_batches == 3 -> activating a 4th is rejected."""
    ids = [_free_batch(f"free-{i}") for i in range(4)]
    free = make_user(plan="free")
    for bid in ids[:3]:
        assert free.put(f"/api/progress/{bid}",
                        json={"activated": True}).status_code == 200
    r = free.put(f"/api/progress/{ids[3]}", json={"activated": True})
    assert r.status_code == 403
    assert r.json()["detail"] == "limit_active"


# ── Two-axis batch management (on_path + activated), invariant activated ⊆ on_path ──

def test_activate_implies_on_path(make_user):
    """Invariant: activating a batch always puts it on the learning path."""
    bid = _free_batch("inv-1")
    free = make_user(plan="free")
    r = free.put(f"/api/progress/{bid}", json={"activated": True})
    assert r.status_code == 200, r.text
    assert r.json()["activated"] is True
    assert r.json()["on_path"] is True


def test_remove_from_path_clears_activated(make_user):
    """Invariant: leaving the path drops the batch from the deck too."""
    bid = _free_batch("inv-2")
    free = make_user(plan="free")
    free.put(f"/api/progress/{bid}", json={"activated": True})
    r = free.put(f"/api/progress/{bid}", json={"on_path": False})
    assert r.status_code == 200, r.text
    assert r.json()["on_path"] is False
    assert r.json()["activated"] is False


def test_on_path_not_capped(make_user):
    """Trajectory is planning, not the metered resource — never capped."""
    ids = [_free_batch(f"path-{i}") for i in range(5)]
    free = make_user(plan="free")
    for bid in ids:
        r = free.put(f"/api/progress/{bid}", json={"on_path": True})
        assert r.status_code == 200, r.text
        assert r.json()["on_path"] is True and r.json()["activated"] is False


def test_deactivate_always_allowed_and_frees_a_slot(make_user):
    """De-activation is never capped; it frees a slot so a new one can activate."""
    ids = [_free_batch(f"deact-{i}") for i in range(3)]
    free = make_user(plan="free")
    for bid in ids:
        free.put(f"/api/progress/{bid}", json={"activated": True})  # 3/3 (at cap)
    assert free.put(f"/api/progress/{ids[0]}",
                    json={"activated": False}).status_code == 200
    bid4 = _free_batch("deact-4")
    assert free.put(f"/api/progress/{bid4}",
                    json={"activated": True}).status_code == 200


def _seq_proof(uid, bid, score=8):
    """A real spoken exam attempt — the server-side evidence behind l3_passed."""
    with Session(engine()) as s:
        s.add(models.SequenceAttempt(user_id=uid, batch_id=bid, score=score,
                                     transcript="t", missed_anchors=[], order_ok=True,
                                     via="llm"))
        s.commit()


def test_completed_batch_does_not_count_toward_cap(make_user):
    """Cap counts active-practice (activated && !l3_passed); maintenance is free."""
    ids = [_free_batch(f"cap-{i}") for i in range(3)]
    free = make_user(plan="free")
    for bid in ids:
        free.put(f"/api/progress/{bid}", json={"activated": True})  # 3/3
    _seq_proof(free.user["id"], ids[0])
    free.put(f"/api/progress/{ids[0]}", json={"l3_passed": True})    # → maintenance
    bid4 = _free_batch("cap-4")
    r = free.put(f"/api/progress/{bid4}", json={"activated": True})
    assert r.status_code == 200, r.text                              # only 2 active-practice


def test_lesson_start_of_a_new_batch_is_capped(make_user):
    """The focus cap walls a NEW batch entering focus by ANY path — including
    starting a lesson. You can't pile up focus by opening lessons either."""
    ids = [_free_batch(f"les-{i}") for i in range(3)]
    free = make_user(plan="free")
    for bid in ids:
        free.put(f"/api/progress/{bid}", json={"activated": True})  # at cap
    bid4 = _free_batch("les-4")
    r = free.put(f"/api/progress/{bid4}", json={"l1_listened": True})
    assert r.status_code == 403
    assert r.json()["detail"] == "limit_active"


def test_lesson_progress_on_an_in_focus_batch_is_never_blocked(make_user):
    """Continuing the batches already in focus is always allowed — the cap only
    gates a NEW batch entering focus, never work on the ones you've opened."""
    ids = [_free_batch(f"cont-{i}") for i in range(3)]
    free = make_user(plan="free")
    for bid in ids:
        free.put(f"/api/progress/{bid}", json={"activated": True})  # at cap
    r = free.put(f"/api/progress/{ids[0]}", json={"l1_listened": True})
    assert r.status_code == 200, r.text
    assert r.json()["l1_listened"] is True and r.json()["activated"] is True


def test_focus_cap_applies_to_paid_unlimited_plans(make_user):
    """The pedagogical cap is plan-independent: even an 'ai' plan (whose
    max_active_batches is None/unlimited) can hold at most FOCUS_CAP=3 in focus."""
    ids = [_free_batch(f"paid-{i}") for i in range(4)]
    ai = make_user(plan="ai")
    for bid in ids[:3]:
        assert ai.put(f"/api/progress/{bid}",
                      json={"activated": True}).status_code == 200
    r = ai.put(f"/api/progress/{ids[3]}", json={"activated": True})
    assert r.status_code == 403
    assert r.json()["detail"] == "limit_active"


def test_paid_exam_pass_frees_a_focus_slot(make_user):
    """Passing an exam (l3_passed) drops a batch out of active focus, so a paid
    learner at the cap can then open a new one — the intended release valve."""
    ids = [_free_batch(f"free-slot-{i}") for i in range(3)]
    ai = make_user(plan="ai")
    for bid in ids:
        ai.put(f"/api/progress/{bid}", json={"activated": True})  # 3/3
    _seq_proof(ai.user["id"], ids[0])
    ai.put(f"/api/progress/{ids[0]}", json={"l3_passed": True})   # frees a slot
    bid4 = _free_batch("free-slot-4")
    assert ai.put(f"/api/progress/{bid4}",
                  json={"activated": True}).status_code == 200


# --- Work-based streak (/api/progress/streak) --------------------------------
from datetime import date, datetime, timedelta, timezone  # noqa: E402

from app.routers.progress import compute_streak  # noqa: E402

D = date(2026, 7, 1)  # fixed "today" for the pure-function tests


def _days(*offsets):
    """Set of dates at the given day-offsets back from D (0 = today)."""
    return {D - timedelta(days=o) for o in offsets}


def test_streak_empty_history():
    s = compute_streak(set(), D)
    assert s == {"streak": 0, "today_done": False, "freeze_available": True,
                 "last_active": None}


def test_streak_consecutive_days_counts():
    s = compute_streak(_days(2, 1, 0), D)
    assert s["streak"] == 3 and s["today_done"] is True


def test_streak_alive_when_last_active_yesterday():
    s = compute_streak(_days(3, 2, 1), D)
    assert s["streak"] == 3 and s["today_done"] is False


def test_streak_single_gap_bridged_by_freeze():
    # active t-4..t-2, missed t-1, trained today → freeze bridges the gap
    s = compute_streak(_days(4, 3, 2, 0), D)
    assert s["streak"] == 4 and s["freeze_available"] is False


def test_streak_second_gap_within_week_breaks():
    # two 1-day gaps close together: the 2nd has no freeze left → run restarts
    s = compute_streak(_days(6, 4, 2), D)
    assert s["streak"] == 1


def test_streak_long_gap_always_breaks():
    s = compute_streak(_days(5, 1, 0), D)
    assert s["streak"] == 2  # only t-1 and today


def test_streak_dead_after_two_idle_days_without_freeze():
    # freeze already spent inside the run → a 2-day-old tail is broken
    s = compute_streak(_days(6, 5, 3, 2), D)          # bridge used at t-4
    assert s["freeze_available"] is False
    assert s["streak"] == 0                            # last active t-2, no freeze


def test_streak_two_day_old_tail_survives_on_freeze():
    s = compute_streak(_days(4, 3, 2), D)              # untouched freeze
    assert s["streak"] == 3 and s["today_done"] is False


def test_streak_freeze_reearned_after_seven_active_days():
    # bridge, then 7 straight active days re-earn the freeze → 2nd bridge works
    offsets = [13, 12, 11] + [9, 8, 7, 6, 5, 4, 3, 2] + [0]
    s = compute_streak(_days(*offsets), D)
    assert s["streak"] == 12


def _seed_events(uid, *created_ats):
    """Insert minimal batch+phrase, then one swipe TrainingEvent per timestamp."""
    with Session(engine()) as s:
        b = models.Batch(title="S", slug=f"streak-{uid}", status="approved",
                         owner_id=None, is_free=True)
        s.add(b)
        s.commit()
        p = models.Phrase(batch_id=b.id, anchor="A", phrase_en="a b",
                          gloss_ru="г", order_index=0)
        s.add(p)
        s.commit()
        for ts in created_ats:
            s.add(models.TrainingEvent(
                user_id=uid, session_id="t", batch_id=b.id, phrase_id=p.id,
                training_mode="swipe", attempt_number=1, created_at=ts))
        s.commit()


def test_streak_endpoint_counts_training_events(make_user):
    c = make_user(plan="ai", is_admin=True)
    now = datetime.now(timezone.utc).replace(tzinfo=None, hour=12)
    _seed_events(c.user["id"], *[now - timedelta(days=d) for d in (2, 1, 0)])
    r = c.get("/api/progress/streak?tz_offset=0")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["streak"] == 3 and body["today_done"] is True


def test_streak_endpoint_no_work_is_zero(make_user):
    c = make_user(plan="ai", is_admin=True)  # app opens don't count
    assert c.get("/api/progress/streak").json()["streak"] == 0


def test_streak_endpoint_respects_timezone(make_user):
    """23:30 UTC yesterday is already 'today' at UTC+2 (tz_offset=-120)."""
    c = make_user(plan="ai", is_admin=True)
    utc_now = datetime.now(timezone.utc).replace(tzinfo=None)
    yesterday_2330 = (utc_now - timedelta(days=1)).replace(hour=23, minute=30)
    _seed_events(c.user["id"], yesterday_2330)
    utc = c.get("/api/progress/streak?tz_offset=0").json()
    plus2 = c.get("/api/progress/streak?tz_offset=-120").json()
    assert utc["today_done"] is False
    # at UTC+2 that event lands on the local "today" — unless we're within 2h of
    # local midnight rollover; both interpretations keep the streak alive
    assert plus2["streak"] == 1 and utc["streak"] == 1


# --- L3 verdict must be earned (anti-tamper) ----------------------------------
def test_l3_passed_without_exam_attempts_is_409(make_user):
    bid = _free_batch("l3-cheat")
    free = make_user(plan="free")
    r = free.put(f"/api/progress/{bid}", json={"l3_passed": True})
    assert r.status_code == 409
    assert r.json()["detail"] == "l3_unproven"
    assert free.get(f"/api/progress/{bid}").json()["l3_passed"] is False


def test_l3_passed_with_exam_proof_is_accepted(make_user):
    bid = _free_batch("l3-legit")
    free = make_user(plan="free")
    _seq_proof(free.user["id"], bid)
    r = free.put(f"/api/progress/{bid}", json={"l3_passed": True})
    assert r.status_code == 200, r.text
    assert r.json()["l3_passed"] is True and r.json()["completed_at"]


def test_l3_low_scores_are_not_proof(make_user):
    bid = _free_batch("l3-low")
    free = make_user(plan="free")
    _seq_proof(free.user["id"], bid, score=4)
    assert free.put(f"/api/progress/{bid}", json={"l3_passed": True}).status_code == 409


# --- Manual path order (path_rank), cross-device -------------------------------
def test_path_rank_roundtrip_and_clear(make_user):
    bid = _free_batch("rank-1")
    free = make_user(plan="free")
    r = free.put(f"/api/progress/{bid}", json={"path_rank": 4})
    assert r.status_code == 200 and r.json()["path_rank"] == 4
    assert free.get("/api/progress").json()[0]["path_rank"] == 4
    # explicit null clears the manual order (back to the computed plan)
    r = free.put(f"/api/progress/{bid}", json={"path_rank": None})
    assert r.status_code == 200 and r.json()["path_rank"] is None
