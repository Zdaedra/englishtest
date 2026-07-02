"""Mandatory email verification (magic link) + the auth gate that enforces it.

Risk × stability: this is an access gate (who may use the API) — exactly the kind
of invariant the testing rule says to cover. Mail delivery itself is a no-op here
(no RESEND key in the test env), so we drive the signed token directly.
"""
import pytest
from fastapi.testclient import TestClient

from app import mail
from app.main import app


@pytest.fixture(autouse=True)
def _mail_on(monkeypatch):
    """Pretend Resend is configured so signups start UNVERIFIED (the gate's whole
    point). Delivery is stubbed to a no-op — we drive the signed token directly."""
    monkeypatch.setattr("app.mail.is_configured", lambda: True)
    monkeypatch.setattr("app.mail.send_verification_email", lambda *a, **k: True)


def _register(email: str) -> TestClient:
    c = TestClient(app)
    r = c.post("/api/auth/register", json={"email": email, "password": "password123"})
    assert r.status_code == 200, r.text
    c.user = r.json()  # type: ignore[attr-defined]
    c.headers.update({"Authorization": f"Bearer {r.json()['token']}"})
    return c


def _content(c: TestClient):
    # A gated, non-exempt content endpoint (lists the catalog).
    return c.get("/api/batches")


def test_owner_is_auto_verified(client):
    """The bootstrap owner (first account) skips verification — never self-lock."""
    r = client.post("/api/auth/register",
                    json={"email": "owner@x.com", "password": "password123"})
    assert r.json()["email_verified"] is True
    client.headers.update({"Authorization": f"Bearer {r.json()['token']}"})
    assert _content(client).status_code == 200


def test_new_signup_unverified_and_gated():
    _register("owner@x.com")          # owner (auto-verified)
    u = _register("late@x.com")       # second account → must verify
    assert u.user["email_verified"] is False
    # Content is blocked with a machine-readable code...
    r = _content(u)
    assert r.status_code == 403
    assert r.json()["code"] == "email_unverified"
    # ...but account-management endpoints stay reachable so they can recover.
    assert u.get("/api/auth/me").status_code == 200
    assert u.post("/api/auth/resend-verification").status_code == 200


def test_magic_link_verifies_and_unblocks():
    _register("owner@x.com")
    u = _register("confirm@x.com")
    token = mail.make_verify_token(u.user["id"], "confirm@x.com")
    r = u.get(f"/api/auth/verify-email?token={token}")
    assert r.status_code == 200 and "confirmed" in r.text.lower()
    # Re-fetching /me now reflects verified, and content opens up.
    assert u.get("/api/auth/me").json()["email_verified"] is True
    assert _content(u).status_code == 200


def test_bad_or_expired_token_rejected(client):
    _register("owner@x.com")
    u = _register("bad@x.com")
    assert u.get("/api/auth/verify-email?token=not-a-real-token").status_code == 400
    # A token signed for a different email must not verify this account.
    wrong = mail.make_verify_token(u.user["id"], "someone-else@x.com")
    assert u.get(f"/api/auth/verify-email?token={wrong}").status_code == 400
    assert _content(u).status_code == 403  # still gated


def test_change_email_requires_reverification():
    _register("owner@x.com")
    u = _register("first@x.com")
    u.get(f"/api/auth/verify-email?token={mail.make_verify_token(u.user['id'], 'first@x.com')}")
    assert _content(u).status_code == 200            # verified, working

    r = u.post("/api/auth/change-email", json={"email": "second@x.com"})
    assert r.status_code == 200
    assert r.json()["email"] == "second@x.com"
    assert r.json()["email_verified"] is False
    assert _content(u).status_code == 403            # gated again until re-confirmed
    # Old address's link no longer works; the new one does.
    assert u.get(f"/api/auth/verify-email?token={mail.make_verify_token(u.user['id'], 'first@x.com')}"
                 ).status_code == 400
    u.get(f"/api/auth/verify-email?token={mail.make_verify_token(u.user['id'], 'second@x.com')}")
    assert _content(u).status_code == 200


def test_change_email_rejects_taken_address():
    _register("owner@x.com")
    _register("taken@x.com")
    u = _register("mover@x.com")
    u.get(f"/api/auth/verify-email?token={mail.make_verify_token(u.user['id'], 'mover@x.com')}")
    r = u.post("/api/auth/change-email", json={"email": "taken@x.com"})
    assert r.status_code == 409
