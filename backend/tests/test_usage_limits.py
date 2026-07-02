"""AI-cost ledger + the monthly-budget profitability guardrail. Covers the
testing-rule billing/entitlement invariants: cost accrues per billable call, and a
user over their plan's monthly cost cap is blocked (graceful self-grade)."""
import pytest
from fastapi import HTTPException
from sqlmodel import Session

from app import models, usage
from app.db import engine
from app.routers.training import _check_rate


def test_cost_keys_map_via():
    assert usage.score_key("llm") == "score"
    assert usage.score_key("llm:escalated") == "score_escalated"
    assert usage.score_key("gate") is None
    assert usage.score_key("cache") is None
    assert usage.score_key("fallback") is None
    assert usage.sequence_key("llm") == "sequence"
    assert usage.sequence_key("gate") is None
    assert usage.coach_key("llm") == "coach"
    assert usage.coach_key("fallback") is None


def test_accrue_accumulates(make_user):
    uid = make_user().user["id"]
    with Session(engine()) as s:
        usage.accrue(s, uid, "score", "stt"); s.commit()
        assert round(usage.month_cost_usd(s, uid), 9) == round(0.000076 + 0.000250, 9)
        usage.accrue(s, uid, "coach"); s.commit()
        assert round(usage.month_cost_usd(s, uid), 9) == round(0.000076 + 0.000250 + 0.000445, 9)


def test_accrue_ignores_free_paths(make_user):
    """gate/cache/fallback map to None => no cost added."""
    uid = make_user().user["id"]
    with Session(engine()) as s:
        usage.accrue(s, uid, usage.score_key("gate"), usage.coach_key("fallback")); s.commit()
        assert usage.month_cost_usd(s, uid) == 0.0


def test_over_budget_blocks(make_user):
    """An AI user past the $1.50 monthly cap gets 429 (continue self-graded)."""
    uid = make_user(plan="ai").user["id"]
    with Session(engine()) as s:
        s.add(models.UsageLedger(user_id=uid, period=usage._period(), micros=1_600_000))
        s.commit()
        with pytest.raises(HTTPException) as ei:
            _check_rate(s, uid)
        assert ei.value.status_code == 429


def test_under_budget_ok(make_user):
    uid = make_user(plan="ai").user["id"]
    with Session(engine()) as s:
        s.add(models.UsageLedger(user_id=uid, period=usage._period(), micros=100_000))  # $0.10
        s.commit()
        _check_rate(s, uid)  # must not raise
