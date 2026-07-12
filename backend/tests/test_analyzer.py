"""Call Analyzer: AI-plan gate, input validation, monthly budget guardrail."""
from sqlmodel import Session

from app import models
from app.db import engine

_TEXT = "We discussed the deadline and I said I think this is not good for us. " * 2


def test_analyze_happy_on_ai_plan(make_user):
    c = make_user(plan="ai", is_admin=True)
    r = c.post("/api/analyzer/call", json={"text": _TEXT})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["via"] == "llm"
    assert body["upgrades"][0]["native"] == "Let me push back on that"


def test_analyze_locked_for_free_and_core(make_user):
    make_user(plan="ai", is_admin=True)  # burn the first-user auto-admin slot
    for plan in ("free", "core"):
        c = make_user(plan=plan)
        r = c.post("/api/analyzer/call", json={"text": _TEXT})
        assert r.status_code == 403, f"{plan}: {r.text}"
        assert r.json()["detail"] == "locked"


def test_analyze_too_short_is_400(make_user):
    c = make_user(plan="ai", is_admin=True)
    r = c.post("/api/analyzer/call", json={"text": "hi"})
    assert r.status_code == 400


def test_analyze_monthly_budget_is_429(make_user):
    c = make_user(plan="ai", is_admin=True)
    uid = c.user["id"]  # type: ignore[attr-defined]
    from app.usage import _period
    with Session(engine()) as s:
        s.add(models.UsageLedger(user_id=uid, period=_period(),
                                 micros=10_000_000))  # $10 — over any cap
        s.commit()
    r = c.post("/api/analyzer/call", json={"text": _TEXT})
    assert r.status_code == 429


def test_analyze_accrues_usage(make_user):
    c = make_user(plan="ai", is_admin=True)
    uid = c.user["id"]  # type: ignore[attr-defined]
    c.post("/api/analyzer/call", json={"text": _TEXT})
    from app.usage import _period
    with Session(engine()) as s:
        row = s.exec(models.UsageLedger.__table__.select().where(
            models.UsageLedger.user_id == uid,
            models.UsageLedger.period == _period())).first()
    assert row is not None and row.micros > 0
