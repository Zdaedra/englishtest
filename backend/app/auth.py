"""Account auth primitives — dependency-free (stdlib only).

Passwords: PBKDF2-HMAC-SHA256 (Django-style format), salted, ~200k iterations.
Sessions: a stateless signed cookie token `<user_id>.<exp>.<hmac>` (HMAC-SHA256
over cookie_secret). No session table for the MVP; logout clears the cookie.
"""
import base64
import hashlib
import hmac
import secrets
import time

from fastapi import HTTPException, Request

from .config import get_settings

_ITERATIONS = 200_000
_SESSION_TTL = 60 * 60 * 24 * 60  # 60 days


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, _ITERATIONS)
    return "pbkdf2_sha256${}${}${}".format(
        _ITERATIONS, base64.b64encode(salt).decode(), base64.b64encode(dk).decode())


def verify_password(password: str, stored: str) -> bool:
    try:
        algo, iters, salt_b64, hash_b64 = stored.split("$")
        if algo != "pbkdf2_sha256":
            return False
        salt = base64.b64decode(salt_b64)
        expected = base64.b64decode(hash_b64)
        dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, int(iters))
        return hmac.compare_digest(dk, expected)
    except Exception:
        return False


def make_session(user_id: int) -> str:
    exp = int(time.time()) + _SESSION_TTL
    msg = f"{user_id}.{exp}"
    sig = hmac.new(get_settings().cookie_secret.encode(), msg.encode(), hashlib.sha256).hexdigest()
    return f"{msg}.{sig}"


def parse_session(token: str) -> int | None:
    """Return the user_id from a valid, unexpired token, else None."""
    try:
        uid, exp, sig = token.split(".")
        msg = f"{uid}.{exp}"
        good = hmac.new(get_settings().cookie_secret.encode(), msg.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(sig, good):
            return None
        if int(exp) < int(time.time()):
            return None
        return int(uid)
    except Exception:
        return None


def current_user_id(request: Request) -> int:
    """FastAPI dependency: the authenticated user's id (set by the auth-gate
    middleware). Raises 401 if missing (shouldn't happen on gated routes)."""
    uid = getattr(request.state, "user_id", None)
    if uid is None:
        raise HTTPException(401, "Не авторизован.")
    return uid
