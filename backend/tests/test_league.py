"""League placement 2.0: production answers scored by rubric.

Open to every plan (pre-paywall test), bounded by a per-user daily run cap;
503 when the LLM is down so the client can fall back to the choice quiz.
"""
import pytest

from app.routers import league as league_router

_ANSWERS = [
    {"id": "pushback", "situation": "A colleague presents a risky plan.",
     "text": "Let me play devil's advocate here."},
    {"id": "deadline", "situation": "CEO asks if it ships Friday. It won't.",
     "text": "We're not going to make Friday — here's where we are."},
    {"id": "circles", "situation": "Meeting circles for 20 minutes.", "text": ""},
]


@pytest.fixture(autouse=True)
def _fresh_runs():
    league_router._runs.clear()
    yield
    league_router._runs.clear()


def test_score_open_to_free_plan(make_user):
    make_user(plan="ai", is_admin=True)  # burn the first-user auto-admin slot
    c = make_user(plan="free")
    r = c.post("/api/league/score", json={"answers": _ANSWERS})
    assert r.status_code == 200, r.text
    body = r.json()
    # stub: non-empty answers score 7, empty 0 → avg (7+7+0)/3 ≈ 4.7 → confident
    assert body["tier"] == "confident"
    assert len(body["results"]) == 3
    assert body["results"][0]["better"]
    assert body["results"][2]["score"] == 0


def test_all_empty_answers_is_400(make_user):
    c = make_user(plan="ai", is_admin=True)
    r = c.post("/api/league/score", json={"answers": [
        {"id": "a", "situation": "s", "text": "  "}]})
    assert r.status_code == 400


def test_daily_run_cap_is_429(make_user):
    c = make_user(plan="ai", is_admin=True)
    for _ in range(league_router._DAILY_RUNS):
        assert c.post("/api/league/score", json={"answers": _ANSWERS}).status_code == 200
    r = c.post("/api/league/score", json={"answers": _ANSWERS})
    assert r.status_code == 429


def test_llm_down_is_503(make_user, monkeypatch):
    monkeypatch.setattr("app.scoring.league_score",
                        lambda answers: {"results": [], "via": "fallback"})
    c = make_user(plan="ai", is_admin=True)
    r = c.post("/api/league/score", json={"answers": _ANSWERS})
    assert r.status_code == 503


def test_tier_mapping():
    t = league_router._tier
    assert t(3.9) == "functional"
    assert t(4.0) == "confident"
    assert t(6.5) == "sharp"
    assert t(8.5) == "native"


def test_league_is_stopped_by_the_monthly_cost_ceiling(make_user):
    """League accrued cost to the monthly ledger but never checked it, so the
    only guard was an in-process daily counter that every redeploy reset. The
    ceiling is the durable one: it survives restarts."""
    from sqlmodel import Session
    from app.db import engine
    from app import models
    from app.entitlements import ENTITLEMENTS
    from app.usage import _period

    c = make_user(plan="free")
    cap = ENTITLEMENTS["free"]["monthly_ai_cost_cap_usd"]
    with Session(engine()) as s:
        s.add(models.UsageLedger(user_id=c.user["id"],  # type: ignore[attr-defined]
                                 period=_period(),
                                 micros=int(cap * 1_000_000) + 1))
        s.commit()

    r = c.post("/api/league/score", json={"answers": [
        {"id": "a1", "situation": "Your manager asks for an update.",
         "text": "Here is where we landed."}]})
    assert r.status_code == 429, f"league ran past the monthly ceiling: {r.status_code}"
