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

    monkeypatch.setattr(billing, "_build_verifiers", lambda: [_Verifier()])
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

    monkeypatch.setattr(billing, "_build_verifiers", lambda: [_Verifier()])
    c = make_user(plan="free")
    r = c.post("/api/billing/verify", json={"signed_transaction": "eyJ.eyJ.sig"})
    assert r.status_code == 400
    assert r.json()["detail"]["code"] == "unknown_product"


def test_verify_not_configured_returns_503(make_user, monkeypatch):
    import app.routers.billing as billing
    monkeypatch.setattr(billing, "_build_verifiers", list)
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


# --- Two Apple environments at once ------------------------------------------
# Real customers buy in production; App Review and TestFlight buy in sandbox. A
# single-environment verifier breaks one of the two whatever it is set to, so
# /verify must try each. Regression for the launch-day trap: the deploy file set
# ENGLISH_APPLE_ENV, which config never read (prefix ENGLISH_ + field
# apple_environment = ENGLISH_APPLE_ENVIRONMENT), so "flip it at launch" would
# silently have left live purchases verified as sandbox.

class _Rejecting:
    """Stands in for the verifier of the OTHER environment: refuses everything."""
    def verify_and_decode_signed_transaction(self, jws):
        from appstoreserverlibrary.signed_data_verifier import (
            VerificationException, VerificationStatus)
        # INVALID_ENVIRONMENT is exactly what the wrong-environment verifier raises.
        raise VerificationException(VerificationStatus.INVALID_ENVIRONMENT)


def test_verify_falls_back_to_the_other_environment(make_user, monkeypatch):
    """A transaction the first environment rejects is still accepted by the second."""
    import app.routers.billing as billing
    product = next(iter(billing.PRODUCT_PLAN))

    class _Tx:
        productId = product
        expiresDate = 1893456000000
        originalTransactionId = "orig-env-2"

    class _Accepting:
        def verify_and_decode_signed_transaction(self, jws):
            return _Tx()

    monkeypatch.setattr(billing, "_build_verifiers", lambda: [_Rejecting(), _Accepting()])
    c = make_user(plan="free")
    r = c.post("/api/billing/verify", json={"signed_transaction": "eyJ.eyJ.sig"})
    assert r.status_code == 200, r.text
    assert r.json()["plan"] == billing.PRODUCT_PLAN[product]


def test_verify_rejected_by_every_environment_is_400(make_user, monkeypatch):
    """Rejected everywhere means rejected — never grant on a fallback miss."""
    import app.routers.billing as billing
    monkeypatch.setattr(billing, "_build_verifiers", lambda: [_Rejecting(), _Rejecting()])
    c = make_user(plan="free")
    r = c.post("/api/billing/verify", json={"signed_transaction": "eyJ.eyJ.sig"})
    assert r.status_code == 400
    assert r.json()["detail"]["code"] == "invalid_transaction"


def test_env_var_name_matches_the_settings_field():
    """The deploy file must spell the variable the way pydantic-settings reads it."""
    import pathlib as _pl
    from app.config import Settings
    prefix = Settings.model_config["env_prefix"]
    expected = f"{prefix}apple_environment".upper()
    compose = (_pl.Path(__file__).resolve().parents[2] / "docker-compose.deploy.yml").read_text()
    assert f"- {expected}=" in compose, f"{expected} missing from docker-compose.deploy.yml"
    assert "- ENGLISH_APPLE_ENV=" not in compose, "the ignored ENGLISH_APPLE_ENV is back"


# --- Webhook: the events that move money -------------------------------------
# Previously only "returns 200" was covered. Renewal, expiry and refund all
# change what the learner may use, so they are cheaper to pin here than to chase
# by hand in the sandbox.

def _notif(ntype, product, expires, orig):
    class _Tx:
        productId = product
        expiresDate = expires
        originalTransactionId = orig

    class _NType:
        name = ntype

    class _Data:
        signedTransactionInfo = "signed"

    class _Notif:
        notificationType = _NType()
        rawNotificationType = ntype
        data = _Data()

    return _Notif(), _Tx()


def _subscriber(make_user, orig="orig-hook"):
    """A user already tied to an App Store subscription (as /verify leaves them)."""
    from sqlmodel import Session, select
    from app.db import engine
    from app import models
    c = make_user(plan="ai")
    with Session(engine()) as s:
        u = s.get(models.User, c.user["id"])
        u.apple_original_tx_id = orig
        u.plan_source = "apple"
        s.add(u)
        s.commit()
    return c


def _plan_of(uid):
    from sqlmodel import Session
    from app.db import engine
    from app import models
    with Session(engine()) as s:
        u = s.get(models.User, uid)
        return u.plan, u.plan_expires_at


def test_webhook_renewal_extends_the_plan(make_user, monkeypatch, client):
    import app.routers.billing as billing
    c = _subscriber(make_user)
    pair = _notif("DID_RENEW", "net.executiveenglish.ai.monthly", 1893456000000, "orig-hook")
    monkeypatch.setattr(billing, "_decode_notification", lambda signed: pair)
    monkeypatch.setattr(billing, "_build_verifiers", lambda: ["stub"])
    r = client.post("/api/billing/apple-notifications", json={"signedPayload": "x"})
    assert r.status_code == 200
    plan, expires = _plan_of(c.user["id"])
    assert plan == "ai"
    assert expires is not None and expires.year == 2030


def test_webhook_expiry_drops_to_free(make_user, monkeypatch, client):
    import app.routers.billing as billing
    c = _subscriber(make_user, "orig-exp")
    pair = _notif("EXPIRED", "net.executiveenglish.ai.monthly", 1600000000000, "orig-exp")
    monkeypatch.setattr(billing, "_decode_notification", lambda signed: pair)
    monkeypatch.setattr(billing, "_build_verifiers", lambda: ["stub"])
    client.post("/api/billing/apple-notifications", json={"signedPayload": "x"})
    assert _plan_of(c.user["id"])[0] == "free"


def test_webhook_refund_drops_to_free(make_user, monkeypatch, client):
    """Apple calls it REFUND, not REFUNDED — a typo here silently keeps access."""
    import app.routers.billing as billing
    assert "REFUND" in billing._EXPIRE_TYPES
    c = _subscriber(make_user, "orig-ref")
    pair = _notif("REFUND", "net.executiveenglish.ai.monthly", 1600000000000, "orig-ref")
    monkeypatch.setattr(billing, "_decode_notification", lambda signed: pair)
    monkeypatch.setattr(billing, "_build_verifiers", lambda: ["stub"])
    client.post("/api/billing/apple-notifications", json={"signedPayload": "x"})
    assert _plan_of(c.user["id"])[0] == "free"


def test_webhook_ignores_an_unknown_subscriber(make_user, monkeypatch, client):
    """A notification for someone we never verified must not touch anyone."""
    import app.routers.billing as billing
    c = _subscriber(make_user, "orig-mine")
    pair = _notif("EXPIRED", "net.executiveenglish.ai.monthly", 1600000000000, "someone-else")
    monkeypatch.setattr(billing, "_decode_notification", lambda signed: pair)
    monkeypatch.setattr(billing, "_build_verifiers", lambda: ["stub"])
    client.post("/api/billing/apple-notifications", json={"signedPayload": "x"})
    assert _plan_of(c.user["id"])[0] == "ai"


# --- Reconciliation against Apple's live subscription status -----------------
# A webhook can be lost, duplicated or delivered out of order, and until now the
# server had no way to find out: the plan only moved when a receipt was posted or
# a notification arrived. Apple's own guidance is that a notification is a nudge
# and the status endpoint is the truth. These pin the repair path.

def test_refresh_requires_auth(client):
    assert client.post("/api/billing/refresh").status_code == 401


def test_refresh_reports_honestly_when_it_cannot_ask(make_user):
    """No linked subscription (or no API credentials) => checked is false, and
    nothing is silently 'confirmed'. The client needs to tell 'unchanged' from
    'never looked'."""
    c = make_user(plan="free")
    r = c.post("/api/billing/refresh")
    assert r.status_code == 200, r.text
    assert r.json()["checked"] is False
    assert r.json()["plan"] == "free"


def _linked(make_user, orig="orig-reconcile", plan="ai"):
    from sqlmodel import Session
    from app.db import engine
    from app import models
    c = make_user(plan=plan)
    with Session(engine()) as s:
        u = s.get(models.User, c.user["id"])  # type: ignore[attr-defined]
        u.apple_original_tx_id = orig
        u.plan_source = "apple"
        s.add(u); s.commit()
    return c


def _status_client(status, product, expires, orig):
    """Stand-in for Apple's status endpoint."""
    class _Item:
        originalTransactionId = orig
        signedTransactionInfo = "signed"
        def __init__(self): self.status = status

    class _Group:
        lastTransactions = [_Item()]

    class _Resp:
        data = [_Group()]

    class _Tx:
        productId = product
        expiresDate = expires
        originalTransactionId = orig

    class _Client:
        def get_all_subscription_statuses(self, tx_id):
            return _Resp()

    return _Client(), _Tx()


def test_refresh_downgrades_when_apple_says_expired(make_user, monkeypatch):
    import app.routers.billing as billing
    c = _linked(make_user, "orig-exp-api")
    cl, tx = _status_client(2, "net.executiveenglish.ai.monthly", 1600000000000, "orig-exp-api")
    monkeypatch.setattr(billing, "_build_api_clients", lambda: [cl])
    monkeypatch.setattr(billing, "_decode_tx", lambda signed: tx)
    r = c.post("/api/billing/refresh")
    assert r.status_code == 200, r.text
    assert r.json()["checked"] is True
    assert r.json()["plan"] == "free", "Apple said expired and we kept the plan"


def test_refresh_restores_when_apple_says_active(make_user, monkeypatch):
    """The other direction matters just as much: a lost renewal left a paying
    customer on free, and only this can give the plan back."""
    import app.routers.billing as billing
    c = _linked(make_user, "orig-act-api", plan="free")
    cl, tx = _status_client(1, "net.executiveenglish.ai.yearly", 1893456000000, "orig-act-api")
    monkeypatch.setattr(billing, "_build_api_clients", lambda: [cl])
    monkeypatch.setattr(billing, "_decode_tx", lambda signed: tx)
    r = c.post("/api/billing/refresh")
    assert r.json()["checked"] is True
    assert r.json()["plan"] == "ai", "Apple said active and the customer stayed on free"


# --- Lazy self-repair on /me ------------------------------------------------
# Proven necessary on 2026-11-27: a sandbox subscription renewed three times,
# Apple sent no notification for any of them, and the server locked a live
# subscriber out of content they were still paying for. Waiting for the user to
# find the "Restore purchases" button is not a fix.

def _lapsed(make_user, orig="orig-lazy"):
    """Looks expired in our DB, still linked to an App Store subscription."""
    from datetime import datetime, timedelta, timezone
    from sqlmodel import Session
    from app.db import engine
    from app import models
    c = make_user(plan="ai")
    with Session(engine()) as s:
        u = s.get(models.User, c.user["id"])  # type: ignore[attr-defined]
        u.apple_original_tx_id = orig
        u.plan_source = "apple"
        u.plan_expires_at = datetime.now(timezone.utc) - timedelta(minutes=5)
        s.add(u); s.commit()
    return c


def test_me_repairs_an_account_apple_says_is_still_active(make_user, monkeypatch):
    import app.routers.billing as billing
    billing._next_try.clear()
    c = _lapsed(make_user, "orig-lazy-live")
    cl, tx = _status_client(1, "net.executiveenglish.ai.yearly", 1893456000000, "orig-lazy-live")
    monkeypatch.setattr(billing, "_build_api_clients", lambda: [cl])
    monkeypatch.setattr(billing, "_decode_tx", lambda signed: tx)
    assert c.get("/api/auth/me").json()["plan"] == "ai", \
        "a live subscriber stayed locked out after /me"


def test_me_does_not_call_apple_for_an_account_inside_its_paid_period(make_user, monkeypatch):
    """One call per lapse, not one per request."""
    import app.routers.billing as billing
    billing._next_try.clear()
    calls = []
    monkeypatch.setattr(billing, "_build_api_clients", lambda: calls.append(1) or [])
    c = make_user(plan="ai")          # no expiry, no linked subscription
    c.get("/api/auth/me")
    assert not calls, "asked Apple about an account that had nothing to check"


def test_me_retries_soon_when_the_renewal_is_not_visible_yet(make_user, monkeypatch):
    """Seen live on 2026-11-27: Apple renewed at 04:28:11, the app opened 23 s
    later, Apple's status endpoint still showed the old (just-ended) period, and
    the 15-minute throttle then kept a paying subscriber locked out. When Apple
    answers but the account still looks lapsed, ask again within a minute."""
    import time as _time
    import app.routers.billing as billing
    billing._next_try.clear()
    c = _lapsed(make_user, "orig-lazy-race")
    past = int((_time.time() - 30) * 1000)
    future = 1893456000000
    answers = [past, future]
    cl, tx = _status_client(1, "net.executiveenglish.ai.monthly", past, "orig-lazy-race")
    def _decode(signed):
        tx.expiresDate = answers[0]
        return tx
    monkeypatch.setattr(billing, "_build_api_clients", lambda: [cl])
    monkeypatch.setattr(billing, "_decode_tx", _decode)
    clock = [1000.0]
    monkeypatch.setattr(billing, "monotonic", lambda: clock[0])

    assert c.get("/api/auth/me").json()["plan"] == "free"   # renewal not visible yet
    answers.pop(0)                                           # Apple catches up
    clock[0] += 90
    assert c.get("/api/auth/me").json()["plan"] == "ai", \
        "a subscriber stayed locked out because the retry waited 15 minutes"


def test_me_backs_off_when_apple_cannot_be_reached(make_user, monkeypatch):
    """The long pause is for Apple being down — not one call per request."""
    import app.routers.billing as billing
    billing._next_try.clear()
    c = _lapsed(make_user, "orig-lazy-down")
    calls = []
    monkeypatch.setattr(billing, "_build_api_clients", lambda: calls.append(1) or [])
    clock = [1000.0]
    monkeypatch.setattr(billing, "monotonic", lambda: clock[0])
    c.get("/api/auth/me")
    clock[0] += 120
    c.get("/api/auth/me")
    assert len(calls) == 1, "kept calling an unreachable Apple on every request"


# --- Silent sign-in sync must not move subscriptions between accounts ---------
# Found 2026-11-27 (Apple-rules audit): on every sign-in the app re-posts the
# device's active purchases and the server applied them to whoever was signed in.
# A reviewer who buys on the free demo account and then signs into the full
# demo account would turn it into "core" — and free once the sandbox sub ends.

def _verify_stub(monkeypatch, orig, product=None, expires=1893456000000, revoked=None):
    import app.routers.billing as billing
    product = product or "net.executiveenglish.core.monthly"

    class _Tx:
        productId = product
        expiresDate = expires
        originalTransactionId = orig
        revocationDate = revoked

    class _Verifier:
        def verify_and_decode_signed_transaction(self, jws):
            return _Tx()

    monkeypatch.setattr(billing, "_build_verifiers", lambda: [_Verifier()])


def test_sync_does_not_rebind_a_subscription_owned_by_another_account(make_user, monkeypatch):
    owner = _linked(make_user, "orig-owned", plan="core")
    other = make_user(plan="free")
    _verify_stub(monkeypatch, "orig-owned")
    r = other.post("/api/billing/verify", json={"signed_transaction": "j", "source": "sync"})
    assert r.status_code == 200, r.text
    assert r.json()["plan"] == "free", "a sign-in on another account stole the subscription"
    assert owner.get("/api/auth/me").json()["plan"] == "core"


def test_sync_does_not_overwrite_a_manually_granted_plan(make_user, monkeypatch):
    c = make_user(plan="ai")                      # plan_source stays "manual"
    _verify_stub(monkeypatch, "orig-device")
    r = c.post("/api/billing/verify", json={"signed_transaction": "j", "source": "sync"})
    assert r.json()["plan"] == "ai", "the full-access demo account was downgraded by a device purchase"


def test_sync_still_recovers_an_unlinked_purchase(make_user, monkeypatch):
    """The reason sync exists: a purchase whose /verify never reached us."""
    c = make_user(plan="free")
    _verify_stub(monkeypatch, "orig-lost")
    r = c.post("/api/billing/verify", json={"signed_transaction": "j", "source": "sync"})
    assert r.json()["plan"] == "core"


def test_revoked_transaction_never_grants(make_user, monkeypatch):
    c = make_user(plan="free")
    _verify_stub(monkeypatch, "orig-refunded", revoked=1700000000000)
    for source in ("purchase", "restore", "sync"):
        r = c.post("/api/billing/verify", json={"signed_transaction": "j", "source": source})
        assert r.status_code == 200, r.text
        assert r.json()["plan"] == "free", f"{source}: a refunded purchase granted a plan"
