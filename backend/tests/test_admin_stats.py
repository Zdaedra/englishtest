"""Stats cabinet (/admin) — access gate + endpoint shape.

Covers the security-critical invariant (testing rule §2: access / admin-only
routes): the cabinet is fail-closed when unconfigured, demands the right Basic
credentials, and — because it lives OUTSIDE /api — is NOT subject to the per-user
session gate (so it must serve with only its own Basic auth).
"""
import base64

from app.config import get_settings


def _basic(u: str, p: str) -> dict:
    return {"Authorization": "Basic " + base64.b64encode(f"{u}:{p}".encode()).decode()}


def _enable(monkeypatch, user="boss", pw="s3cret"):
    s = get_settings()
    monkeypatch.setattr(s, "stats_user", user)
    monkeypatch.setattr(s, "stats_password", pw)


def test_disabled_when_unconfigured(client, monkeypatch):
    s = get_settings()
    monkeypatch.setattr(s, "stats_user", "")
    monkeypatch.setattr(s, "stats_password", "")
    assert client.get("/admin").status_code == 404
    assert client.get("/admin/api/overview").status_code == 404


def test_requires_correct_basic_auth(client, monkeypatch):
    _enable(monkeypatch)
    r = client.get("/admin/api/overview")  # no credentials
    assert r.status_code == 401
    assert "basic" in r.headers.get("www-authenticate", "").lower()
    assert client.get("/admin/api/overview", headers=_basic("boss", "wrong")).status_code == 401
    assert client.get("/admin/api/overview", headers=_basic("nope", "s3cret")).status_code == 401


def test_dashboard_html_served_with_auth(client, monkeypatch):
    # /admin is not under /api, so the per-user auth gate must not block it; the
    # cabinet's own Basic auth is the only gate.
    _enable(monkeypatch)
    r = client.get("/admin", headers=_basic("boss", "s3cret"))
    assert r.status_code == 200
    assert "text/html" in r.headers["content-type"]


def test_all_endpoints_respond_with_auth(client, make_user, monkeypatch):
    _enable(monkeypatch)
    make_user()  # at least one user so aggregates have data
    h = _basic("boss", "s3cret")
    ov = client.get("/admin/api/overview", headers=h)
    assert ov.status_code == 200
    assert ov.json()["total_users"] >= 1
    for path in ("/admin/api/funnel", "/admin/api/timeseries?days=30",
                 "/admin/api/plans", "/admin/api/quality",
                 "/admin/api/retention", "/admin/api/content"):
        assert client.get(path, headers=h).status_code == 200, path
