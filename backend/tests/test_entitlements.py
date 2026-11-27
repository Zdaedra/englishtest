"""Unit tests for the plan/entitlement source of truth (app/entitlements.py)."""
from datetime import datetime, timedelta, timezone

from app import models
from app.entitlements import effective_plan, ents


def test_matrix_import_gate_per_plan():
    assert ents("free")["import"] is False
    assert ents("core")["import"] is True
    assert ents("ai")["import"] is True


def test_matrix_voice_and_coach_are_ai_only():
    assert ents("ai")["voice_answer"] is True
    assert ents("ai")["ai_coach"] is True
    assert ents("core")["voice_answer"] is False
    assert ents("free")["ai_coach"] is False


def test_matrix_daily_caps():
    assert ents("free")["scored_per_day"] == 30
    assert ents("core")["scored_per_day"] == 200
    assert ents("ai")["scored_per_day"] == 400
    assert ents("free")["max_active_batches"] == 10
    assert ents("core")["max_active_batches"] is None


def test_unknown_plan_falls_back_to_free():
    assert ents(None) == ents("free")
    assert ents("bogus") == ents("free")


def test_effective_plan_no_expiry_keeps_plan():
    u = models.User(email="a@b.co", password_hash="x", plan="core",
                    plan_expires_at=None)
    assert effective_plan(u) == "core"


def test_effective_plan_expired_subscription_falls_back_to_free():
    past = datetime.now(timezone.utc) - timedelta(days=1)
    u = models.User(email="a@b.co", password_hash="x", plan="ai",
                    plan_expires_at=past)
    assert effective_plan(u) == "free"


def test_effective_plan_future_expiry_still_active():
    future = datetime.now(timezone.utc) + timedelta(days=30)
    u = models.User(email="a@b.co", password_hash="x", plan="ai",
                    plan_expires_at=future)
    assert effective_plan(u) == "ai"


def test_effective_plan_none_user_is_free():
    assert effective_plan(None) == "free"


# --- An expired subscription must actually close the paid doors --------------
# The `user.plan` column still says "ai" after an Apple subscription lapses: it
# is only corrected when a webhook arrives, and a webhook can be lost, late or
# duplicated. Fifteen access checks in the routers read that raw column, so the
# profile screen said "free" (it uses effective_plan) while every paid topic
# stayed open. Fixed 2026-11-26 — these pin it.

def _expire(uid, days=2):
    """Leave plan='ai' in the column but put the expiry in the past."""
    from datetime import datetime, timedelta, timezone
    from sqlmodel import Session
    from app.db import engine
    from app import models
    with Session(engine()) as s:
        u = s.get(models.User, uid)
        u.plan = "ai"
        u.plan_source = "apple"
        u.plan_expires_at = datetime.now(timezone.utc) - timedelta(days=days)
        s.add(u); s.commit()


def test_expired_subscription_locks_paid_topics(make_user):
    from conftest import commit_sample_batch
    admin = make_user(plan="ai", is_admin=True)
    bid = commit_sample_batch(admin)
    lapsed = make_user(plan="ai")
    _expire(lapsed.user["id"])  # type: ignore[attr-defined]

    r = lapsed.get(f"/api/batches/{bid}")
    assert r.status_code == 200, r.text
    assert r.json()["locked"] is True, "a lapsed subscriber still saw a paid topic unlocked"
    assert not r.json().get("phrases"), "a lapsed subscriber was served paid content"


def test_expired_subscription_closes_the_phrase_index(make_user):
    from conftest import commit_sample_batch
    admin = make_user(plan="ai", is_admin=True)
    bid = commit_sample_batch(admin)
    lapsed = make_user(plan="ai")
    _expire(lapsed.user["id"])  # type: ignore[attr-defined]
    got = {r["batch_id"] for r in lapsed.get("/api/batches/phrases").json()}
    assert bid not in got, "paid phrases leaked to a lapsed subscriber"


def test_expired_subscription_closes_voice_scoring(make_user):
    """The mic costs us money per call, so it must shut with the subscription."""
    from conftest import commit_sample_batch, phrase_ids
    admin = make_user(plan="ai", is_admin=True)
    bid = commit_sample_batch(admin)
    pid = phrase_ids(admin, bid)[0]
    lapsed = make_user(plan="ai")
    _expire(lapsed.user["id"])  # type: ignore[attr-defined]
    audio = {"audio": ("clip.webm", b"\x00" * 2048, "audio/webm")}
    r = lapsed.post("/api/training/score-phrase", files=audio, data={"phrase_id": pid})
    assert r.status_code == 403, f"lapsed subscriber still got AI scoring: {r.status_code}"
