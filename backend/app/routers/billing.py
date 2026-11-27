"""Apple In-App Purchase (StoreKit 2) — server side.

Flow: the native client buys a subscription via StoreKit 2 and sends us the
`Transaction.jwsRepresentation` (a JWS signed by Apple). We verify the signature
against Apple's root CAs (bundled in app/apple_certs), read
{productId, expiresDate, originalTransactionId}, map the product to a plan, and
set it on the user. Apple also POSTs App Store Server Notifications V2 (also JWS)
for renewals / expirations / refunds → the webhook keeps the plan in sync.

Verification uses Apple's official `app-store-server-library` (SignedDataVerifier).
If the Apple env isn't configured (no bundle id / certs), the verifier is None and
the endpoints stay inert (503) so we NEVER grant a plan from an unverified payload.
"""
import logging
from datetime import datetime, timezone
from time import monotonic
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlmodel import Session, select

from .. import models
from ..config import get_settings
from ..db import get_session
from ..entitlements import effective_plan

router = APIRouter(prefix="/api/billing", tags=["billing"])

# App Store notifications are the only thing that moves a plan between
# purchases, and when one goes missing there is nothing to look at afterwards:
# the HTTP line in the log says 200 and tells you nothing. 2026-11-26 we had a
# subscription expire, two notifications arrive, and the plan column stay "ai" —
# with no way to tell which events those were. One line per notification, no
# personal data, just the type and what we did with it.
_log = logging.getLogger("billing")
# Uvicorn wires up only its own loggers, so these lines were silently dropped —
# and they are the only record of which notification Apple actually sent and
# what self-repair decided. Print them next to the access log.
if not _log.handlers:
    _h = logging.StreamHandler()
    _h.setFormatter(logging.Formatter("billing %(levelname)s: %(message)s"))
    _log.addHandler(_h)
    _log.setLevel(logging.INFO)
    _log.propagate = False

# App Store Connect product ids → our plan tier. Must match the products created
# in App Store Connect → Subscriptions for bundle net.executiveenglish.app.
PRODUCT_PLAN: dict[str, str] = {
    "net.executiveenglish.core.monthly": "core",
    "net.executiveenglish.core.yearly": "core",
    "net.executiveenglish.ai.monthly": "ai",
    "net.executiveenglish.ai.yearly": "ai",
}

_CERT_DIR = Path(__file__).resolve().parent.parent / "apple_certs"
_verifiers: list = []  # one SignedDataVerifier per Apple environment (cached)
_verifiers_built = False


def _build_verifiers() -> list:
    """One SignedDataVerifier per Apple environment, preferred one first.

    BOTH are always built, because both are always in use at the same time: real
    customers buy in production, while every App Review pass and every TestFlight
    build buys in sandbox. A single-environment verifier therefore breaks one of
    those two no matter how it is set — flipping a flag at launch would break the
    review of the next update, and not flipping it would break live purchases. So
    we try the environments in turn instead. `apple_environment` only decides
    which one is tried FIRST (a cheap win on the hot path), never which exist.

    Returns [] (and billing stays inert) if it isn't configured or the library is
    unavailable.
    """
    global _verifiers, _verifiers_built
    if _verifiers_built:
        return _verifiers
    _verifiers_built = True
    s = get_settings()
    roots = [p.read_bytes() for p in sorted(_CERT_DIR.glob("*.cer"))]
    if not roots or not s.apple_bundle_id:
        return _verifiers
    try:
        from appstoreserverlibrary.signed_data_verifier import SignedDataVerifier
        from appstoreserverlibrary.models.Environment import Environment
    except Exception:
        return _verifiers
    order = ([Environment.PRODUCTION, Environment.SANDBOX]
             if s.apple_environment == "production"
             else [Environment.SANDBOX, Environment.PRODUCTION])
    for env in order:
        try:
            _verifiers.append(SignedDataVerifier(
                roots, True, env, s.apple_bundle_id, s.apple_app_apple_id or None))
        except Exception:
            pass  # one environment failing to build must not kill the other
    return _verifiers


def _decode_tx(signed: str):
    """Decode a signed transaction against each environment; None if none accept."""
    from appstoreserverlibrary.signed_data_verifier import VerificationException
    for v in _build_verifiers():
        try:
            return v.verify_and_decode_signed_transaction(signed)
        except VerificationException:
            continue
    return None


def _decode_notification(signed: str):
    """Decode a notification and its transaction against each environment."""
    from appstoreserverlibrary.signed_data_verifier import VerificationException
    for v in _build_verifiers():
        try:
            notif = v.verify_and_decode_notification(signed)
            info = notif.data.signedTransactionInfo if notif.data else None
            return notif, (v.verify_and_decode_signed_transaction(info) if info else None)
        except VerificationException:
            continue
    return None, None


_api_clients: list = []
_api_clients_built = False


def _build_api_clients() -> list:
    """App Store Server API clients, one per environment, preferred first.

    Same two-environment rule as the verifiers above: a sandbox subscription can
    only be asked about on the sandbox API. Returns [] when the credentials are
    not configured — reconciliation is then simply skipped, never an error.
    """
    global _api_clients, _api_clients_built
    if _api_clients_built:
        return _api_clients
    _api_clients_built = True
    s = get_settings()
    if not (s.apple_key_id and s.apple_issuer_id and s.apple_private_key_path
            and s.apple_bundle_id):
        return _api_clients
    try:
        key = Path(s.apple_private_key_path).read_bytes()
        from appstoreserverlibrary.api_client import AppStoreServerAPIClient
        from appstoreserverlibrary.models.Environment import Environment
    except Exception:
        return _api_clients
    order = ([Environment.PRODUCTION, Environment.SANDBOX]
             if s.apple_environment == "production"
             else [Environment.SANDBOX, Environment.PRODUCTION])
    for env in order:
        try:
            _api_clients.append(AppStoreServerAPIClient(
                key, s.apple_key_id, s.apple_issuer_id, s.apple_bundle_id, env))
        except Exception:
            pass  # one environment failing to build must not kill the other
    return _api_clients


# Apple's subscription status codes (get_all_subscription_statuses).
_STATUS_ACTIVE = {1, 4}       # active, or in a billing grace period -> keep access
_STATUS_ENDED = {2, 5}        # expired, revoked -> access is over
# 3 = in billing retry: Apple is still trying to charge. We leave the stored
# expiry alone and let it lapse on its own rather than cutting a paying customer
# off mid-retry.


def reconcile_with_apple(session: Session, user) -> bool:
    """Ask Apple what this subscription is RIGHT NOW, and apply the answer.

    Until this existed the stored plan only ever moved when the client posted a
    receipt or when a webhook arrived. A webhook can be lost, duplicated or
    delivered out of order, and the server then stayed wrong forever with nothing
    able to correct it. A notification is a nudge, not a source of truth; the
    status endpoint is. Wired into "restore purchases" so a learner can always
    put their own account right without writing to support.

    Returns True if Apple answered, False if we could not ask (no credentials, no
    linked subscription, network error) — in which case nothing is changed.
    """
    tx_id = getattr(user, "apple_original_tx_id", None)
    if not tx_id:
        return False
    for client in _build_api_clients():
        try:
            resp = client.get_all_subscription_statuses(tx_id)
        except Exception:
            continue                      # wrong environment or transient — try the next
        for group in (resp.data or []):
            for item in (group.lastTransactions or []):
                if item.originalTransactionId != tx_id:
                    continue
                tx = _decode_tx(item.signedTransactionInfo or "")
                status = item.status
                if status in _STATUS_ENDED:
                    user.plan = "free"
                    user.plan_expires_at = _ms_to_dt(tx.expiresDate) if tx else None
                    session.add(user)
                    session.commit()
                    return True
                if status in _STATUS_ACTIVE and tx:
                    try:
                        _apply_plan(session, user, tx.productId or "",
                                    tx.expiresDate, tx.originalTransactionId)
                    except HTTPException:
                        pass              # unknown product — leave the plan alone
                    return True
                return True               # billing retry: answered, nothing to change
    return False


def _ms_to_dt(ms: int | None) -> datetime | None:
    return datetime.fromtimestamp(ms / 1000, tz=timezone.utc) if ms else None


def _apply_plan(session: Session, user: models.User, product_id: str,
                expires_ms: int | None, original_tx_id: str | None) -> str:
    plan = PRODUCT_PLAN.get(product_id)
    if not plan:
        raise HTTPException(400, {"code": "unknown_product", "product": product_id})
    user.plan = plan
    user.plan_source = "apple"
    user.plan_expires_at = _ms_to_dt(expires_ms)
    if original_tx_id:
        user.apple_original_tx_id = original_tx_id
    session.add(user)
    session.commit()
    return plan


class VerifyIn(BaseModel):
    signed_transaction: str  # StoreKit2 Transaction.jwsRepresentation


@router.post("/verify")
def verify(body: VerifyIn, request: Request, session: Session = Depends(get_session)):
    """Client posts the signed StoreKit 2 transaction after a purchase/restore."""
    uid = getattr(request.state, "user_id", None)
    u = session.get(models.User, uid) if uid else None
    if not u:
        raise HTTPException(401, {"code": "unauthorized"})
    if not _build_verifiers():
        raise HTTPException(503, {"code": "billing_not_configured"})
    tx = _decode_tx(body.signed_transaction)
    if tx is None:
        raise HTTPException(400, {"code": "invalid_transaction"})
    plan = _apply_plan(session, u, tx.productId or "", tx.expiresDate, tx.originalTransactionId)
    return {"ok": True, "plan": plan,
            "plan_expires_at": u.plan_expires_at.isoformat() if u.plan_expires_at else None}


# Lazy self-repair throttle {user_id: monotonic time of the next allowed ask}.
# Apple unreachable -> wait long. Apple answered but the account still looks
# lapsed -> ask again soon: right after a renewal Apple's status endpoint can
# still show the period that just ended (seen live 2026-11-27: renewal 04:28:11,
# app opened 23 s later, old period returned, subscriber locked for 15 min).
# Billing retry also lands here — at most one call a minute while they use the app.
_next_try: dict[int, float] = {}
_RETRY_UNREACHABLE_S = 15 * 60
_RETRY_STILL_LAPSED_S = 60


def _looks_lapsed(user) -> bool:
    """Paid plan in the DB, linked to an App Store subscription, period over."""
    if not user or not getattr(user, "apple_original_tx_id", None):
        return False
    if (user.plan or "free") == "free":
        return False
    exp = getattr(user, "plan_expires_at", None)
    if exp is None:
        return False
    e = exp if exp.tzinfo else exp.replace(tzinfo=timezone.utc)
    return e < datetime.now(timezone.utc)


def maybe_reconcile(session: Session, user) -> None:
    """Quietly repair an account that LOOKS lapsed but may not be.

    Proven necessary on 2026-11-27: a sandbox subscription renewed three times
    and Apple sent us no notification for any of them, so the server believed it
    had expired and locked the account out — we were denying content to a live
    subscriber, the worst way round to get this wrong. Asking Apple fixed it in
    one call.

    Runs only when the stored state says "paid plan whose time has run out" and
    the account is linked to an App Store subscription, so it costs one API call
    per account per lapse, not one per request: whatever Apple answers (expired →
    plan goes free, still active → expiry moves forward) stops the condition from
    matching again. The throttle (see _next_try) covers Apple being unreachable
    and the minute right after a renewal when Apple still shows the old period.
    """
    if not _looks_lapsed(user):
        return                      # nothing to check (or still inside the paid period)
    now = monotonic()
    if now < _next_try.get(user.id, 0.0):
        return
    _next_try[user.id] = now + _RETRY_UNREACHABLE_S   # held while the call runs
    try:
        answered = reconcile_with_apple(session, user)
    except Exception:
        answered = False            # never let self-repair break the caller
    if not answered:
        _log.warning("self-repair for user %s: Apple not reachable, next try in %ss",
                     user.id, _RETRY_UNREACHABLE_S)
    elif _looks_lapsed(user):
        _next_try[user.id] = now + _RETRY_STILL_LAPSED_S
        _log.info("self-repair for user %s: Apple still shows the ended period, "
                  "next try in %ss", user.id, _RETRY_STILL_LAPSED_S)
    else:
        _next_try.pop(user.id, None)
        _log.info("self-repair for user %s: plan %s until %s",
                  user.id, user.plan, user.plan_expires_at)


@router.post("/refresh")
def refresh(request: Request, session: Session = Depends(get_session)):
    """Re-ask Apple for this account's real subscription status and apply it.

    The self-service repair for a lost or out-of-order webhook: the client calls
    this from "restore purchases", so a learner whose plan is wrong can fix it
    themselves. Honest about what happened — `checked` is false when we could not
    ask Apple at all (credentials not configured, or no linked subscription), so
    the client can tell "nothing changed" from "we never looked"."""
    uid = getattr(request.state, "user_id", None)
    u = session.get(models.User, uid) if uid else None
    if not u:
        raise HTTPException(401, {"code": "unauthorized"})
    checked = reconcile_with_apple(session, u)
    session.refresh(u)
    return {"ok": True, "checked": checked, "plan": effective_plan(u),
            "plan_expires_at": u.plan_expires_at.isoformat() if u.plan_expires_at else None}


# Notification types that END access (downgrade to free) once effective.
_EXPIRE_TYPES = {"EXPIRED", "REVOKE", "REFUND", "GRACE_PERIOD_EXPIRED"}
# Types that (re)grant / extend access.
_GRANT_TYPES = {"SUBSCRIBED", "DID_RENEW", "OFFER_REDEEMED", "RENEWAL_EXTENDED", "REFUND_REVERSED"}


@router.post("/apple-notifications")
async def apple_notifications(request: Request, session: Session = Depends(get_session)):
    """App Store Server Notifications V2 webhook (renew / expire / refund / etc).
    Apple posts {signedPayload}. We verify it, find the user by
    originalTransactionId, and update plan/expiry. Always 200 once configured so
    Apple stops retrying; ignores anything that doesn't verify."""
    try:
        body = await request.json()
    except Exception:
        return {"ok": True}
    signed = (body or {}).get("signedPayload")
    if not _build_verifiers() or not signed:
        return {"ok": True}
    notif, tx = _decode_notification(signed)
    if not notif or not tx or not tx.originalTransactionId:
        return {"ok": True}

    ntype = (notif.notificationType.name if notif.notificationType else (notif.rawNotificationType or "")).upper()
    subtype = getattr(getattr(notif, "subtype", None), "name", None) or ""
    u = session.exec(select(models.User).where(
        models.User.apple_original_tx_id == tx.originalTransactionId)).first()
    if not u:
        _log.info("apple notification %s/%s: no account linked to this subscription",
                  ntype, subtype or "-")
        return {"ok": True}  # unknown subscriber (e.g. before first /verify)

    if ntype in _EXPIRE_TYPES:
        u.plan = "free"
        u.plan_expires_at = _ms_to_dt(tx.expiresDate)
        session.add(u)
        session.commit()
        _log.info("apple notification %s/%s for user %s: plan -> free",
                  ntype, subtype or "-", u.id)
    elif ntype in _GRANT_TYPES:
        try:
            plan = _apply_plan(session, u, tx.productId or "", tx.expiresDate,
                               tx.originalTransactionId)
            _log.info("apple notification %s/%s for user %s: plan -> %s until %s",
                      ntype, subtype or "-", u.id, plan, u.plan_expires_at)
        except HTTPException:
            _log.warning("apple notification %s/%s for user %s: unknown product %s",
                         ntype, subtype or "-", u.id, tx.productId)
    else:
        _log.info("apple notification %s/%s for user %s: no plan change needed",
                  ntype, subtype or "-", u.id)
    return {"ok": True}
