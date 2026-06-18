"""Billing endpoints. Apple receipt verification is intentionally inert
(_verify_signed_jws hardcoded False) until StoreKit keys are wired, so the
authenticated path currently returns 501 — we assert that contract."""


def test_verify_requires_auth(client):
    r = client.post("/api/billing/verify", json={"signed_transaction": "x"})
    assert r.status_code == 401


def test_verify_not_configured_returns_501(make_user):
    c = make_user(plan="free")
    r = c.post("/api/billing/verify", json={"signed_transaction": "eyJ.eyJ.sig"})
    assert r.status_code == 501
    assert r.json()["detail"]["code"] == "verification_not_configured"


def test_verify_applies_plan_when_verification_passes(make_user, monkeypatch):
    """With verification + decode stubbed to a known product, the purchase is
    applied and the user's plan is upgraded."""
    monkeypatch.setattr("app.routers.billing._verify_signed_jws", lambda jws: True)
    # decode to a product that maps to a plan
    import app.routers.billing as billing
    product = next(iter(billing.PRODUCT_PLAN))
    monkeypatch.setattr(billing, "_decode_jws_payload",
                        lambda jws: {"productId": product})
    c = make_user(plan="free")
    r = c.post("/api/billing/verify", json={"signed_transaction": "eyJ.eyJ.sig"})
    assert r.status_code == 200, r.text
    assert r.json()["plan"] == billing.PRODUCT_PLAN[product]


def test_apple_notifications_is_public_and_ok(client):
    r = client.post("/api/billing/apple-notifications", json={"signedPayload": "x"})
    assert r.status_code == 200
    assert r.json() == {"ok": True}
