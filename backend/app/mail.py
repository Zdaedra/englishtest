"""Email verification — magic-link tokens + Resend delivery.

The token is a stateless signed string ``verify.<uid>.<exp>.<sig>`` where the
signature is an HMAC over the uid, the email *at issue time*, and the expiry.
Binding the email means changing it (or a re-verify) invalidates older links.
There is no DB table: the auth router loads the user and recomputes the signature
against the user's current email. Delivery is via Resend; with no API key
configured (local dev / pre-DNS) the link is logged instead, so the whole flow
stays testable offline.
"""
import hashlib
import hmac
import json
import logging
import time
import urllib.error
import urllib.request

from .auth import _signing_secret
from .config import get_secrets, get_settings

log = logging.getLogger("uvicorn.error")

_VERIFY_TTL = 60 * 60 * 24 * 3  # 3 days


def is_configured() -> bool:
    """True once a Resend key is set. Until then the verification feature stays
    dormant (registration auto-verifies) so a deploy can't lock anyone out for
    lack of a way to receive the email."""
    return bool(get_secrets().resend_api_key.strip())


def _sig(uid: int, email: str, exp: int) -> str:
    msg = f"verify.{uid}.{email}.{exp}"
    return hmac.new(_signing_secret().encode(), msg.encode(), hashlib.sha256).hexdigest()


def make_verify_token(uid: int, email: str, ttl: int = _VERIFY_TTL) -> str:
    exp = int(time.time()) + ttl
    return f"verify.{uid}.{exp}.{_sig(uid, email, exp)}"


def token_uid(token: str) -> int | None:
    """The uid encoded in a token (signature NOT yet checked) so the caller can
    load the user; confirm with check_verify_token against that user's email."""
    try:
        kind, uid, _exp, _sig_v = token.split(".")
        return int(uid) if kind == "verify" else None
    except Exception:
        return None


def check_verify_token(token: str, email: str) -> bool:
    try:
        kind, uid, exp, sig_v = token.split(".")
        if kind != "verify" or int(exp) < int(time.time()):
            return False
        return hmac.compare_digest(sig_v, _sig(int(uid), email, int(exp)))
    except Exception:
        return False


def verification_link(token: str) -> str:
    base = get_settings().public_base_url.rstrip("/")
    return f"{base}/api/auth/verify-email?token={token}"


def send_verification_email(to_email: str, link: str) -> bool:
    """Send the verification email via Resend. Returns True if mailed. With no API
    key (dev / pre-DNS) the link is logged and we return False — registration still
    succeeds and the user can hit "resend" once mail is live."""
    key = get_secrets().resend_api_key.strip()
    if not key:
        log.warning("RESEND not configured — verification link for %s: %s", to_email, link)
        return False
    payload = {
        "from": get_settings().mail_from,
        "to": [to_email],
        "subject": "Confirm your email — Executive English",
        "html": _email_html(link),
    }
    req = urllib.request.Request(
        "https://api.resend.com/emails",
        data=json.dumps(payload).encode(),
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            r.read()
        return True
    except urllib.error.HTTPError as e:
        log.error("Resend send failed (%s): %s", e.code, e.read()[:300])
    except Exception as e:  # network etc. — best effort, user can resend
        log.error("Resend send error: %r", e)
    return False


# --- minimal branded HTML (inline styles; email clients ignore <style>) --------
def _email_html(link: str) -> str:
    return f"""\
<div style="font-family:-apple-system,Segoe UI,Roboto,sans-serif;max-width:480px;margin:0 auto;padding:32px 24px;color:#1c1c1e">
  <h1 style="font-size:22px;margin:0 0 8px">Executive English</h1>
  <p style="font-size:16px;line-height:1.5;color:#3a3a3c">Confirm your email to activate your account.</p>
  <p style="margin:28px 0">
    <a href="{link}" style="background:#1f6f54;color:#fff;text-decoration:none;padding:14px 28px;border-radius:12px;font-size:16px;font-weight:600;display:inline-block">Confirm email</a>
  </p>
  <p style="font-size:13px;color:#8e8e93;line-height:1.5">Or paste this link into your browser:<br><span style="color:#1f6f54;word-break:break-all">{link}</span></p>
  <p style="font-size:13px;color:#8e8e93">The link expires in 3 days. If you didn't create an account, ignore this email.</p>
</div>"""


def _page(title: str, body: str) -> str:
    return f"""\
<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title} — Executive English</title></head>
<body style="font-family:-apple-system,Segoe UI,Roboto,sans-serif;background:#f5f5f4;margin:0;
display:flex;min-height:100vh;align-items:center;justify-content:center;padding:24px">
<div style="background:#fff;border-radius:20px;padding:40px 32px;max-width:420px;text-align:center;
box-shadow:0 8px 30px rgba(0,0,0,.08)">
<div style="font-size:44px;margin-bottom:8px">{'✅' if title=='Email confirmed' else '⚠️'}</div>
<h1 style="font-size:22px;margin:0 0 10px;color:#1c1c1e">{title}</h1>
<p style="font-size:16px;line-height:1.5;color:#3a3a3c;margin:0">{body}</p>
</div></body></html>"""


def success_page() -> str:
    return _page("Email confirmed",
                 "Your email is verified. Return to the Executive English app to continue.")


def error_page() -> str:
    return _page("Link expired",
                 "This confirmation link is invalid or has expired. Open the app and request a new one.")
