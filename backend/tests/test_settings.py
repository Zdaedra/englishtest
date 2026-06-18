"""Global settings: readable by any user, writable by admins only."""


def test_get_settings_returns_defaults(make_user):
    c = make_user(plan="free")
    r = c.get("/api/settings")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["tts_voice"] == "alloy"
    assert "default_order_mode" in body


def test_put_settings_requires_admin(make_user):
    c = make_user(plan="ai", is_admin=False)
    r = c.put("/api/settings", json={"tts_speed": 1.5})
    assert r.status_code == 403


def test_put_settings_admin_updates(make_user):
    admin = make_user(plan="ai", is_admin=True)
    r = admin.put("/api/settings", json={"tts_speed": 1.25,
                                         "default_order_mode": "ordered"})
    assert r.status_code == 200, r.text
    assert r.json()["tts_speed"] == 1.25
    assert r.json()["default_order_mode"] == "ordered"


def test_put_settings_ignores_unknown_keys(make_user):
    admin = make_user(plan="ai", is_admin=True)
    r = admin.put("/api/settings", json={"bogus_key": 123, "tts_speed": 1.1})
    assert r.status_code == 200, r.text
    assert "bogus_key" not in r.json()
    assert r.json()["tts_speed"] == 1.1
