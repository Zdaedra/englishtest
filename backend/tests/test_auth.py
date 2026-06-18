"""Auth router + the global auth-gate middleware."""
from fastapi.testclient import TestClient

from app.main import app


def test_register_first_user_is_admin_ai(client):
    r = client.post("/api/auth/register",
                    json={"email": "owner@example.com", "password": "password123"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["is_admin"] is True
    assert body["plan"] == "ai"
    assert body["entitlements"]["import"] is True
    assert body["token"]


def test_second_user_is_free_non_admin(client):
    client.post("/api/auth/register",
                json={"email": "owner@example.com", "password": "password123"})
    r = client.post("/api/auth/register",
                    json={"email": "second@example.com", "password": "password123"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["is_admin"] is False
    assert body["plan"] == "free"
    assert body["entitlements"]["import"] is False


def test_register_rejects_bad_email(client):
    r = client.post("/api/auth/register",
                    json={"email": "notanemail", "password": "password123"})
    assert r.status_code == 400
    assert r.json()["detail"]["code"] == "bad_email"


def test_register_rejects_weak_password(client):
    r = client.post("/api/auth/register",
                    json={"email": "weak@example.com", "password": "short"})
    assert r.status_code == 400
    assert r.json()["detail"]["code"] == "weak_password"


def test_register_rejects_duplicate_email(client):
    payload = {"email": "dup@example.com", "password": "password123"}
    assert client.post("/api/auth/register", json=payload).status_code == 200
    r = client.post("/api/auth/register", json=payload)
    assert r.status_code == 409
    assert r.json()["detail"]["code"] == "email_taken"


def test_login_happy_path(client):
    client.post("/api/auth/register",
                json={"email": "log@example.com", "password": "password123"})
    r = client.post("/api/auth/login",
                    json={"email": "log@example.com", "password": "password123"})
    assert r.status_code == 200, r.text
    assert r.json()["token"]


def test_login_wrong_password_is_401(client):
    client.post("/api/auth/register",
                json={"email": "log@example.com", "password": "password123"})
    r = client.post("/api/auth/login",
                    json={"email": "log@example.com", "password": "wrongpass1"})
    assert r.status_code == 401
    assert r.json()["detail"]["code"] == "bad_credentials"


def test_login_unknown_email_is_401(client):
    r = client.post("/api/auth/login",
                    json={"email": "ghost@example.com", "password": "password123"})
    assert r.status_code == 401
    assert r.json()["detail"]["code"] == "bad_credentials"


def test_me_requires_auth(client):
    assert client.get("/api/auth/me").status_code == 401


def test_me_returns_profile(make_user):
    c = make_user(email="me@example.com")
    r = c.get("/api/auth/me")
    assert r.status_code == 200, r.text
    assert r.json()["email"] == "me@example.com"


def test_ui_lang_updates_and_validates(make_user):
    c = make_user()
    ok = c.post("/api/auth/ui-lang", json={"lang": "es"})
    assert ok.status_code == 200, ok.text
    assert ok.json()["ui_lang"] == "es"
    bad = c.post("/api/auth/ui-lang", json={"lang": "klingon"})
    assert bad.status_code == 400
    assert bad.json()["detail"]["code"] == "bad_lang"


def test_logout_requires_auth_but_succeeds_with_token(client, make_user):
    assert client.post("/api/auth/logout").status_code == 401
    c = make_user()
    assert c.post("/api/auth/logout").json() == {"ok": True}


def test_delete_account_removes_user(make_user):
    c = make_user(email="bye@example.com")
    assert c.request("DELETE", "/api/auth/me").json() == {"ok": True}
    # token still decodes, but the user row is gone -> router-level 401
    assert c.get("/api/auth/me").status_code == 401


def test_gated_endpoint_without_token_is_401(client):
    # /api/batches is not in the public set -> middleware rejects with 401
    assert client.get("/api/batches").status_code == 401


def test_health_is_public(client):
    assert client.get("/api/health").json() == {"ok": True}
