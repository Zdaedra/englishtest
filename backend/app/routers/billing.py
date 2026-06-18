"""Apple In-App Purchase (StoreKit 2) — server side.

Flow: the native client buys a subscription via StoreKit 2 and sends us the
`Transaction.jwsRepresentation` (a JWS signed by Apple). We verify the signature
against Apple's root, read {productId, expiresDate, originalTransactionId}, map
the product to a plan, and set it on the user. Apple also POSTs App Store Server
Notifications V2 (also JWS) for renewals / expirations / refunds → the webhook.

STATUS (2026-06-17): structure + product mapping + plan application are done and
testable. The JWS **signature verification** (`_verify_signed_jws`) is stubbed —
it requires the Apple Developer account (sandbox transactions to test against) and
Apple Root CA G3. Until it's wired + sandbox-validated, `/verify` returns 501 so
we NEVER grant a plan from an unverified payload. No security hole, just inert.
"""
import base64
import json

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlmodel import Session

from .. import models
from ..db import get_session

router = APIRouter(prefix="/api/billing", tags=["billing"])

# App Store Connect product ids → our plan tier.
PRODUCT_PLAN: dict[str, str] = {
    "core_monthly": "core", "core_yearly": "core",
    "ai_monthly": "ai", "ai_yearly": "ai",
}


def _decode_jws_payload(jws: str) -> dict:
    """Base64url-decode the middle (payload) segment of a JWS — WITHOUT verifying
    the signature. Used to read the transaction fields; never trust this until
    `_verify_signed_jws` has confirmed the signature."""
    try:
        seg = jws.split(".")[1]
        seg += "=" * (-len(seg) % 4)
        return json.loads(base64.urlsafe_b64decode(seg))
    except Exception:
        raise HTTPException(400, {"code": "bad_transaction"})


def _verify_signed_jws(jws: str) -> bool:
    """Verify the JWS is signed by Apple (StoreKit 2): ES256 signature by the leaf
    cert in the `x5c` header, chain leaf→intermediate→Apple Root CA G3.

    TODO (sandbox phase, needs Apple Developer account): implement with
    pyjwt[crypto] + the bundled AppleRootCA-G3 cert, then validate end-to-end
    against a sandbox purchase. Returns False until then so /verify stays inert."""
    return False


def _apply_purchase(session: Session, user: models.User, product_id: str,
                    expires_ms: int | None, original_tx_id: str | None) -> str:
    plan = PRODUCT_PLAN.get(product_id)
    if not plan:
        raise HTTPException(400, {"code": "unknown_product", "product": product_id})
    from datetime import datetime, timezone
    user.plan = plan
    user.plan_source = "apple"
    user.plan_expires_at = (
        datetime.fromtimestamp(expires_ms / 1000, tz=timezone.utc) if expires_ms else None
    )
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
    if not _verify_signed_jws(body.signed_transaction):
        # Inert until signature verification is wired + sandbox-validated.
        raise HTTPException(501, {"code": "verification_not_configured"})
    p = _decode_jws_payload(body.signed_transaction)
    plan = _apply_purchase(session, u, p.get("productId", ""),
                           p.get("expiresDate"), p.get("originalTransactionId"))
    return {"ok": True, "plan": plan, "plan_expires_at": u.plan_expires_at}


@router.post("/apple-notifications")
async def apple_notifications(request: Request, session: Session = Depends(get_session)):
    """App Store Server Notifications V2 webhook (renew / expire / refund / etc).
    Apple posts {signedPayload}. TODO: verify + decode, find the user by
    originalTransactionId, update plan/expiry. Returns 200 so Apple stops retrying
    once wired; inert until then."""
    return {"ok": True}
