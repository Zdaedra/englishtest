"""Account auth primitives — dependency-free (stdlib only).

Passwords: PBKDF2-HMAC-SHA256 (Django-style format), salted, ~200k iterations.
Sessions: a stateless signed cookie token `<user_id>.<exp>.<hmac>` (HMAC-SHA256
over cookie_secret). No session table for the MVP; logout clears the cookie.
"""
import base64
import functools
import hashlib
import hmac
import secrets
import time

from fastapi import Depends, HTTPException, Request
from sqlmodel import Session

from . import models
from .config import get_settings
from .db import get_session

_ITERATIONS = 200_000
_SESSION_TTL = 60 * 60 * 24 * 60  # 60 days


@functools.lru_cache(maxsize=1)
def _signing_secret() -> str:
    """The HMAC key for session cookies. Prefer an explicit ENGLISH_COOKIE_SECRET;
    otherwise generate a strong random secret and persist it on the data volume so
    sessions survive restarts. This makes the gate secure-by-default even if ops
    forgets to set the env var (the old "change-me" default was forgeable)."""
    s = get_settings()
    configured = (s.cookie_secret or "").strip()
    if configured and configured != "change-me":
        return configured
    path = s.data_dir / ".cookie_secret"
    try:
        if path.exists():
            val = path.read_text().strip()
            if val:
                return val
        val = secrets.token_hex(32)
        path.write_text(val)
        try:
            path.chmod(0o600)
        except Exception:
            pass
        return val
    except Exception:
        # Read-only FS fallback: ephemeral per-process secret (sessions reset on
        # restart, but never forgeable with a known key).
        return secrets.token_hex(32)


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
    sig = hmac.new(_signing_secret().encode(), msg.encode(), hashlib.sha256).hexdigest()
    return f"{msg}.{sig}"


def parse_session(token: str) -> int | None:
    """Return the user_id from a valid, unexpired token, else None."""
    try:
        uid, exp, sig = token.split(".")
        msg = f"{uid}.{exp}"
        good = hmac.new(_signing_secret().encode(), msg.encode(), hashlib.sha256).hexdigest()
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


def is_admin(session: Session, user_id: int) -> bool:
    u = session.get(models.User, user_id)
    return bool(u and u.is_admin)


def require_admin(user_id: int = Depends(current_user_id),
                  session: Session = Depends(get_session)) -> int:
    """Dependency for owner/admin-only endpoints (curated-catalog mutations,
    global settings). Regular clients get 403."""
    if not is_admin(session, user_id):
        raise HTTPException(403, "admin_required")
    return user_id
