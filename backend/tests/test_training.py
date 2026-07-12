"""Training router: scoring (AI-stubbed), rate limits, AI-plan gating, swipe,
confirm, mastery/rotation/deck/summary reads."""
from sqlmodel import Session

from app import models
from app.db import engine
from conftest import commit_sample_batch, phrase_ids

_AUDIO = {"audio": ("clip.webm", b"\x00\x00\x00\x00", "audio/webm")}


def test_score_phrase_happy(make_user):
    admin = make_user(plan="ai", is_admin=True)
    bid = commit_sample_batch(admin)
    pid = phrase_ids(admin, bid)[0]
    r = admin.post("/api/training/score-phrase", files=_AUDIO,
                   data={"phrase_id": pid})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["score"] == 9
    assert body["via"] == "gate"
    assert body["attempts"] == 1


def test_score_phrase_missing_phrase_is_404(make_user):
    admin = make_user(plan="ai", is_admin=True)
    r = admin.post("/api/training/score-phrase", files=_AUDIO,
                   data={"phrase_id": 999999})
    assert r.status_code == 404


def test_score_phrase_oversize_audio_is_413(make_user):
    admin = make_user(plan="ai", is_admin=True)
    bid = commit_sample_batch(admin)
    pid = phrase_ids(admin, bid)[0]
    big = {"audio": ("clip.webm", b"\x00" * (8 * 1024 * 1024 + 1), "audio/webm")}
    r = admin.post("/api/training/score-phrase", files=big, data={"phrase_id": pid})
    assert r.status_code == 413


def test_score_phrase_daily_limit_is_429(make_user):
    admin = make_user(plan="ai", is_admin=True)
    bid = commit_sample_batch(admin)
    pid = phrase_ids(admin, bid)[0]
    free = make_user(plan="free")             # scored_per_day == 30
    uid = free.user["id"]  # type: ignore[attr-defined]
    with Session(engine()) as s:
        for _ in range(30):
            s.add(models.PhraseAttempt(user_id=uid, phrase_id=pid, score=5))
        s.commit()
    r = free.post("/api/training/score-phrase", files=_AUDIO, data={"phrase_id": pid})
    assert r.status_code == 429


def test_score_anchor_happy(make_user):
    admin = make_user(plan="ai", is_admin=True)
    bid = commit_sample_batch(admin)
    pid = phrase_ids(admin, bid)[0]
    r = admin.post("/api/training/score-anchor", files=_AUDIO, data={"phrase_id": pid})
    assert r.status_code == 200, r.text
    assert r.json()["score"] == 10


def test_score_sequence_happy(make_user):
    admin = make_user(plan="ai", is_admin=True)
    bid = commit_sample_batch(admin)
    r = admin.post("/api/training/score-sequence", files=_AUDIO, data={"batch_id": bid})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["score"] == 8
    assert body["passed"] is True


def test_mastery_returns_list(make_user):
    admin = make_user(plan="ai", is_admin=True)
    commit_sample_batch(admin)
    r = admin.get("/api/training/mastery")
    assert r.status_code == 200, r.text
    assert isinstance(r.json(), list)


def test_rotation_happy_and_missing(make_user):
    admin = make_user(plan="ai", is_admin=True)
    bid = commit_sample_batch(admin)
    ok = admin.get(f"/api/training/rotation/{bid}")
    assert ok.status_code == 200
    assert len(ok.json()) == 5
    assert admin.get("/api/training/rotation/999999").status_code == 404


def test_deck_returns_list(make_user):
    admin = make_user(plan="ai", is_admin=True)
    bid = commit_sample_batch(admin)
    r = admin.get("/api/training/deck", params={"batch_ids": str(bid)})
    assert r.status_code == 200, r.text
    assert isinstance(r.json(), list)


def test_swipe_updates_and_missing(make_user):
    admin = make_user(plan="ai", is_admin=True)
    bid = commit_sample_batch(admin)
    pid = phrase_ids(admin, bid)[0]
    ok = admin.post("/api/training/swipe", json={
        "session_id": "s1", "phrase_id": pid, "swipe_direction": "right"})
    assert ok.status_code == 200, ok.text
    assert ok.json()["ok"] is True
    missing = admin.post("/api/training/swipe", json={
        "session_id": "s1", "phrase_id": 999999, "swipe_direction": "right"})
    assert missing.status_code == 404


def test_answer_blocked_for_free_on_paid_batch(make_user):
    admin = make_user(plan="ai", is_admin=True)
    bid = commit_sample_batch(admin)
    pid = phrase_ids(admin, bid)[0]
    free = make_user(plan="free")
    r = free.post("/api/training/answer", files=_AUDIO,
                  data={"phrase_id": pid, "session_id": "s1"})
    assert r.status_code == 403
    assert r.json()["detail"] == "ai_required"


def test_answer_text_then_confirm(make_user):
    admin = make_user(plan="ai", is_admin=True)
    bid = commit_sample_batch(admin)
    pid = phrase_ids(admin, bid)[0]
    r = admin.post("/api/training/answer-text", json={
        "session_id": "s1", "phrase_id": pid, "transcript": "hello there"})
    assert r.status_code == 200, r.text
    eid = r.json()["event_id"]
    conf = admin.post("/api/training/answer/confirm",
                      json={"event_id": eid, "manual_success": True})
    assert conf.status_code == 200, conf.text


def test_answer_text_returns_hybrid_feedback(make_user):
    """F5: the answer endpoint surfaces the honest coaching fields (fits_task /
    natural / note) alongside the score, from the score_answer result."""
    admin = make_user(plan="ai", is_admin=True)
    bid = commit_sample_batch(admin)
    pid = phrase_ids(admin, bid)[0]
    r = admin.post("/api/training/answer-text", json={
        "session_id": "s1", "phrase_id": pid, "transcript": "hello there"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["fits_task"] is True     # from the stubbed score_answer
    assert body["natural"] == 8
    assert body["note"] == "стаб"
    assert body["correct_phrase"]


def test_confirm_foreign_event_is_404(make_user):
    admin = make_user(plan="ai", is_admin=True)
    bid = commit_sample_batch(admin)
    pid = phrase_ids(admin, bid)[0]
    r = admin.post("/api/training/answer-text", json={
        "session_id": "s1", "phrase_id": pid, "transcript": "hi"})
    eid = r.json()["event_id"]
    other = make_user(plan="ai")
    conf = other.post("/api/training/answer/confirm",
                      json={"event_id": eid, "manual_success": True})
    assert conf.status_code == 404


def test_coach_blocked_for_free(make_user):
    admin = make_user(plan="ai", is_admin=True)
    bid = commit_sample_batch(admin)
    pid = phrase_ids(admin, bid)[0]
    free = make_user(plan="free")
    r = free.post("/api/training/coach",
                  json={"phrase_id": pid, "transcript": "x", "score": 5})
    assert r.status_code == 403
    assert r.json()["detail"] == "ai_plan_required"


def test_coach_happy_for_ai(make_user):
    admin = make_user(plan="ai", is_admin=True)
    bid = commit_sample_batch(admin)
    pid = phrase_ids(admin, bid)[0]
    r = admin.post("/api/training/coach",
                   json={"phrase_id": pid, "transcript": "x", "score": 5})
    assert r.status_code == 200, r.text
    assert r.json()["feedback"] == "fb"


def test_session_summary(make_user):
    admin = make_user(plan="ai", is_admin=True)
    r = admin.get("/api/training/session/s1/summary")
    assert r.status_code == 200, r.text
    assert r.json()["session_id"] == "s1"


# --- Weekly rollup (/api/training/weekly) ------------------------------------
from datetime import datetime, timedelta, timezone  # noqa: E402


def _event(uid, bid, pid, *, score=None, mode="swipe", days_ago=0):
    return models.TrainingEvent(
        user_id=uid, session_id="w", batch_id=bid, phrase_id=pid,
        training_mode=mode, ai_score=score, attempt_number=1,
        created_at=datetime.now(timezone.utc).replace(tzinfo=None, hour=12)
        - timedelta(days=days_ago))


def test_weekly_empty(make_user):
    c = make_user(plan="ai", is_admin=True)
    body = c.get("/api/training/weekly").json()
    assert body["attempts"] == 0 and body["best"] == [] and body["focus"] == []


def test_weekly_rolls_up_best_and_focus(make_user):
    admin = make_user(plan="ai", is_admin=True)
    bid = commit_sample_batch(admin)
    pids = phrase_ids(admin, bid)
    uid = admin.user["id"]  # type: ignore[attr-defined]
    with Session(engine()) as s:
        # strong phrase: two high spoken scores; weak phrase: two low ones
        s.add(_event(uid, bid, pids[0], score=9, days_ago=1))
        s.add(_event(uid, bid, pids[0], score=10, days_ago=2))
        s.add(_event(uid, bid, pids[1], score=3, days_ago=1))
        s.add(_event(uid, bid, pids[1], score=4, days_ago=0))
        s.add(_event(uid, bid, pids[2], days_ago=10))  # outside the window
        s.commit()
    body = admin.get("/api/training/weekly").json()
    assert body["attempts"] == 4
    assert body["days_active"] == 3
    assert body["phrases"] == 2
    assert [b["phrase_id"] for b in body["best"]] == [pids[0]]
    assert body["best"][0]["avg_score"] == 9.5
    assert [f["phrase_id"] for f in body["focus"]] == [pids[1]]
    assert body["focus"][0]["phrase_en"]


def test_weekly_swipes_count_as_work_not_quality(make_user):
    admin = make_user(plan="ai", is_admin=True)
    bid = commit_sample_batch(admin)
    pid = phrase_ids(admin, bid)[0]
    uid = admin.user["id"]  # type: ignore[attr-defined]
    with Session(engine()) as s:
        s.add(_event(uid, bid, pid))  # swipe, no ai_score
        s.commit()
    body = admin.get("/api/training/weekly").json()
    assert body["attempts"] == 1 and body["avg_score"] is None
    assert body["best"] == [] and body["focus"] == []
