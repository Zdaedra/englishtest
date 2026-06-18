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
    assert ents("free")["max_active_batches"] == 3
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
