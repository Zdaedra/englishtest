"""Billing: Apple StoreKit 2 receipt verification via app-store-server-library.

Real Apple-signed transactions can only be produced in a sandbox/device, so here
we assert the security contract (auth required, garbage rejected, never granted
without verification) and stub the verifier for the happy path."""


def test_verify_requires_auth(client):
    r = client.post("/api/billing/verify", json={"signed_transaction": "x"})
    assert r.status_code == 401


def test_verify_rejects_invalid_transaction(make_user):
    """A garbage JWS fails Apple signature verification -> 400, never grants a plan."""
    c = make_user(plan="free")
    r = c.post("/api/billing/verify", json={"signed_transaction": "eyJ.eyJ.sig"})
    assert r.status_code == 400
    assert r.json()["detail"]["code"] == "invalid_transaction"


def test_verify_applies_plan_on_valid_transaction(make_user, monkeypatch):
    """With verification stubbed to a known product, the plan is applied."""
    import app.routers.billing as billing
    product = next(iter(billing.PRODUCT_PLAN))

    class _Tx:
        productId = product
        expiresDate = 1893456000000  # 2030-01-01, ms epoch
        originalTransactionId = "orig-123"

    class _Verifier:
        def verify_and_decode_signed_transaction(self, jws):
            return _Tx()

    monkeypatch.setattr(billing, "_build_verifier", lambda: _Verifier())
    c = make_user(plan="free")
    r = c.post("/api/billing/verify", json={"signed_transaction": "eyJ.eyJ.sig"})
    assert r.status_code == 200, r.text
    assert r.json()["plan"] == billing.PRODUCT_PLAN[product]


def test_verify_unknown_product_rejected(make_user, monkeypatch):
    import app.routers.billing as billing

    class _Tx:
        productId = "net.executiveenglish.bogus"
        expiresDate = None
        originalTransactionId = "x"

    class _Verifier:
        def verify_and_decode_signed_transaction(self, jws):
            return _Tx()

    monkeypatch.setattr(billing, "_build_verifier", lambda: _Verifier())
    c = make_user(plan="free")
    r = c.post("/api/billing/verify", json={"signed_transaction": "eyJ.eyJ.sig"})
    assert r.status_code == 400
    assert r.json()["detail"]["code"] == "unknown_product"


def test_verify_not_configured_returns_503(make_user, monkeypatch):
    import app.routers.billing as billing
    monkeypatch.setattr(billing, "_build_verifier", lambda: None)
    c = make_user(plan="free")
    r = c.post("/api/billing/verify", json={"signed_transaction": "x"})
    assert r.status_code == 503
    assert r.json()["detail"]["code"] == "billing_not_configured"


def test_apple_notifications_public_and_ok(client):
    """Webhook is public and always 200 (so Apple stops retrying); unverified
    payloads are ignored."""
    r = client.post("/api/billing/apple-notifications", json={"signedPayload": "x"})
    assert r.status_code == 200
    assert r.json() == {"ok": True}


def test_product_plan_covers_all_four(make_user):
    import app.routers.billing as billing
    assert set(billing.PRODUCT_PLAN) == {
        "net.executiveenglish.core.monthly", "net.executiveenglish.core.yearly",
        "net.executiveenglish.ai.monthly", "net.executiveenglish.ai.yearly",
    }
    assert set(billing.PRODUCT_PLAN.values()) == {"core", "ai"}
