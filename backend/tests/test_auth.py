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


def test_ui_lang_accepts_every_ui_locale(make_user):
    """SUPPORTED_LANGS must mirror LANGS in frontend/src/i18n/index.tsx — a locale
    shipped on the client but missing here gets a 400 and silently fails to sync
    across devices."""
    c = make_user()
    for code in ("ru", "en", "es", "de", "fr"):
        r = c.post("/api/auth/ui-lang", json={"lang": code})
        assert r.status_code == 200, f"{code}: {r.text}"
        assert r.json()["ui_lang"] == code
        assert c.get("/api/auth/me").json()["ui_lang"] == code


def test_ui_lang_en_leaves_content_axis_on_russian(make_user):
    """`en` is a UI-chrome-only locale: localize.SUPPORTED stays {ru,es,de,fr}, so
    an English UI must still resolve content (batch titles, glosses, stories) to
    the Russian base instead of raising."""
    from app import localize

    c = make_user()
    assert c.post("/api/auth/ui-lang", json={"lang": "en"}).status_code == 200
    assert "en" not in localize.SUPPORTED

    class U:
        ui_lang = "en"

    assert localize.resolve_lang(None, U()) == "ru"      # saved ui_lang collapses
    assert localize.resolve_lang("en", U()) == "ru"      # explicit ?lang=en collapses
    assert localize.pick({"es": "hola"}, "ru", "база") == "база"

    assert c.get("/api/batches").status_code == 200
    assert c.get("/api/batches?lang=en").status_code == 200


def test_logout_requires_auth_but_succeeds_with_token(client, make_user):
    assert client.post("/api/auth/logout").status_code == 401
    c = make_user()
    assert c.post("/api/auth/logout").json() == {"ok": True}


def test_delete_account_removes_user(make_user):
    c = make_user(email="bye@example.com")
    assert c.request("DELETE", "/api/auth/me").json() == {"ok": True}
    # token still decodes, but the user row is gone -> router-level 401
    assert c.get("/api/auth/me").status_code == 401


def test_delete_account_wipes_private_import_live_children(make_user):
    """A private import's phrase-keyed Live children (intent tags, semantic
    vectors, batch tags) must die with the account — orphans could mis-attach
    when SQLite recycles the phrase ids (audit census, 2026-07-10)."""
    from sqlmodel import Session, select
    from app import models
    from app.db import engine
    c = make_user(email="bye2@example.com", plan="ai")
    uid = c.user["id"]  # type: ignore[attr-defined]
    with Session(engine()) as s:
        b = models.Batch(title="Private", slug="priv-1", status="approved", owner_id=uid)
        s.add(b)
        s.commit()
        s.refresh(b)
        p = models.Phrase(batch_id=b.id, order_index=1, anchor="a", phrase_en="X.")
        s.add(p)
        s.commit()
        s.refresh(p)
        s.add(models.PhraseIntent(phrase_id=p.id, intent="warm"))
        s.add(models.PhraseEmbedding(phrase_id=p.id, model="m", dim=2,
                                     text_hash="h", vector=b"\x00" * 8))
        s.add(models.BatchIntent(batch_id=b.id, intent="warm"))
        s.commit()
    assert c.request("DELETE", "/api/auth/me").json() == {"ok": True}
    with Session(engine()) as s:
        assert s.exec(select(models.PhraseIntent)).all() == []
        assert s.exec(select(models.PhraseEmbedding)).all() == []
        assert s.exec(select(models.BatchIntent)).all() == []


def test_gated_endpoint_without_token_is_401(client):
    # /api/batches is not in the public set -> middleware rejects with 401
    assert client.get("/api/batches").status_code == 401


def test_health_is_public(client):
    assert client.get("/api/health").json() == {"ok": True}
