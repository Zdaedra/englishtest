"""Account-level learning profile (goals/strategy/plan/league blob): default {},
set→/me roundtrip, auth gate, and the size guard. The blob is client-owned —
the server only stores and echoes it, so the contract here is storage fidelity.
"""
from fastapi.testclient import TestClient

from app.main import app


def test_learn_profile_defaults_empty(make_user):
    c = make_user(plan="free")
    me = c.get("/api/auth/me").json()
    assert me["learn_profile"] == {}


def test_learn_profile_roundtrip(make_user):
    c = make_user(plan="free")
    blob = {"scenarios": ["charisma", "business"], "planMode": "manual",
            "manualIds": [3, 7], "onboardedAt": "2026-07-09T00:00:00Z",
            "league": {"tier": "sharp", "score": 5, "missed": [], "at": "2026-07-09"}}
    r = c.post("/api/auth/learn-profile", json={"profile": blob})
    assert r.status_code == 200, r.text
    assert c.get("/api/auth/me").json()["learn_profile"] == blob
    # last write wins — a second device overwrites wholesale
    r2 = c.post("/api/auth/learn-profile", json={"profile": {"scenarios": ["stage"]}})
    assert r2.status_code == 200
    assert c.get("/api/auth/me").json()["learn_profile"] == {"scenarios": ["stage"]}


def test_learn_profile_requires_auth():
    r = TestClient(app).post("/api/auth/learn-profile", json={"profile": {}})
    assert r.status_code == 401


def test_learn_profile_size_guard(make_user):
    c = make_user(plan="free")
    r = c.post("/api/auth/learn-profile",
               json={"profile": {"junk": "x" * 20_000}})
    assert r.status_code == 413


def test_learn_profile_isolated_per_user(make_user):
    a = make_user(plan="ai", is_admin=True)
    b = make_user(plan="free")
    a.post("/api/auth/learn-profile", json={"profile": {"scenarios": ["flirt"]}})
    assert b.get("/api/auth/me").json()["learn_profile"] == {}
