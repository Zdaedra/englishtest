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
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlmodel import Session, select

from .. import models
from ..config import get_settings
from ..db import get_session

router = APIRouter(prefix="/api/billing", tags=["billing"])

# App Store Connect product ids → our plan tier. Must match the products created
# in App Store Connect → Subscriptions for bundle net.executiveenglish.app.
PRODUCT_PLAN: dict[str, str] = {
    "net.executiveenglish.core.monthly": "core",
    "net.executiveenglish.core.yearly": "core",
    "net.executiveenglish.ai.monthly": "ai",
    "net.executiveenglish.ai.yearly": "ai",
}

_CERT_DIR = Path(__file__).resolve().parent.parent / "apple_certs"
_verifier = None  # lazily built SignedDataVerifier (cached)
_verifier_built = False


def _build_verifier():
    """Build the SignedDataVerifier from bundled Apple root CAs + config. Returns
    None (and stays inert) if billing isn't configured or the lib is unavailable."""
    global _verifier, _verifier_built
    if _verifier_built:
        return _verifier
    _verifier_built = True
    s = get_settings()
    roots = [p.read_bytes() for p in sorted(_CERT_DIR.glob("*.cer"))]
    if not roots or not s.apple_bundle_id:
        return None
    try:
        from appstoreserverlibrary.signed_data_verifier import SignedDataVerifier
        from appstoreserverlibrary.models.Environment import Environment
        env = Environment.PRODUCTION if s.apple_environment == "production" else Environment.SANDBOX
        _verifier = SignedDataVerifier(
            roots, True, env, s.apple_bundle_id, s.apple_app_apple_id or None)
    except Exception:
        _verifier = None
    return _verifier


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
    verifier = _build_verifier()
    if verifier is None:
        raise HTTPException(503, {"code": "billing_not_configured"})
    from appstoreserverlibrary.signed_data_verifier import VerificationException
    try:
        tx = verifier.verify_and_decode_signed_transaction(body.signed_transaction)
    except VerificationException:
        raise HTTPException(400, {"code": "invalid_transaction"})
    plan = _apply_plan(session, u, tx.productId or "", tx.expiresDate, tx.originalTransactionId)
    return {"ok": True, "plan": plan,
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
    verifier = _build_verifier()
    try:
        body = await request.json()
    except Exception:
        return {"ok": True}
    signed = (body or {}).get("signedPayload")
    if verifier is None or not signed:
        return {"ok": True}
    from appstoreserverlibrary.signed_data_verifier import VerificationException
    try:
        notif = verifier.verify_and_decode_notification(signed)
        info = notif.data.signedTransactionInfo if notif.data else None
        tx = verifier.verify_and_decode_signed_transaction(info) if info else None
    except VerificationException:
        return {"ok": True}
    if not tx or not tx.originalTransactionId:
        return {"ok": True}

    ntype = (notif.notificationType.name if notif.notificationType else (notif.rawNotificationType or "")).upper()
    u = session.exec(select(models.User).where(
        models.User.apple_original_tx_id == tx.originalTransactionId)).first()
    if not u:
        return {"ok": True}  # unknown subscriber (e.g. before first /verify)

    if ntype in _EXPIRE_TYPES:
        u.plan = "free"
        u.plan_expires_at = _ms_to_dt(tx.expiresDate)
        session.add(u)
        session.commit()
    elif ntype in _GRANT_TYPES:
        try:
            _apply_plan(session, u, tx.productId or "", tx.expiresDate, tx.originalTransactionId)
        except HTTPException:
            pass  # unknown product — leave plan untouched
    # other types (DID_CHANGE_RENEWAL_*, PRICE_*, TEST, …) need no plan change.
    return {"ok": True}
