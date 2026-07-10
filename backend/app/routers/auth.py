"""Account endpoints: register / login / logout / me. Sets a signed session
cookie (eng_auth). Public: register + login. The rest of the API requires a
valid session (enforced by the auth-gate middleware in main.py)."""
import json

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from sqlmodel import Session, select

from .. import mail, models
from ..auth import hash_password, verify_password, make_session, current_user_id
from ..db import get_session
from ..entitlements import ents, effective_plan

router = APIRouter(prefix="/api/auth", tags=["auth"])

# Per-user tables that are BOTH wiped on account deletion AND included in the data
# export — one source of truth so the two can never drift (a row you can delete but
# not export, or vice-versa, would be a compliance bug).
_USER_TABLES = (
    models.UserPhraseStat, models.PlaybackSession, models.ReviewEvent,
    models.PhraseAttempt, models.SequenceAttempt, models.BatchProgress,
    models.TrainingEvent, models.ConsentRecord,
)
_TRANSCRIPT_TABLES = (models.PhraseAttempt, models.SequenceAttempt, models.TrainingEvent)

COOKIE = "eng_auth"
MAX_AGE = 60 * 60 * 24 * 60  # 60 days
MIN_PASSWORD = 8


class Credentials(BaseModel):
    email: str
    password: str
    name: str | None = None


def _norm(email: str) -> str:
    return (email or "").strip().lower()


SUPPORTED_LANGS = {"ru", "es", "de", "fr"}
HERO_GENDERS = {"male", "female", "mixed"}


def _serialize(u: models.User) -> dict:
    # `token` is the same signed session as the cookie; native (Capacitor) stores
    # it in the Keychain and sends it as a Bearer header. Web ignores it and uses
    # the httponly cookie. Safe over HTTPS.
    plan = effective_plan(u)
    return {"id": u.id, "email": u.email, "name": u.name, "plan": plan,
            "is_admin": u.is_admin, "ui_lang": u.ui_lang, "hero_gender": u.hero_gender,
            "learn_profile": u.learn_profile or {},
            "entitlements": ents(plan),
            "email_verified": u.email_verified, "token": make_session(u.id)}


def _send_verification(u: models.User) -> None:
    """Best-effort: email a fresh magic link to the user's current address."""
    link = mail.verification_link(mail.make_verify_token(u.id, u.email))
    mail.send_verification_email(u.email, link)


def _set_cookie(response: Response, user_id: int) -> None:
    response.set_cookie(COOKIE, make_session(user_id), max_age=MAX_AGE,
                        httponly=True, samesite="lax", path="/")


@router.post("/register")
def register(body: Credentials, response: Response, session: Session = Depends(get_session)):
    email = _norm(body.email)
    # Errors carry a machine `code` (+ params) so the client localizes them; `msg`
    # is a Russian fallback for non-localized callers.
    if "@" not in email or "." not in email.split("@")[-1]:
        raise HTTPException(400, {"code": "bad_email", "msg": "Введите корректный email."})
    if len(body.password) < MIN_PASSWORD:
        raise HTTPException(400, {"code": "weak_password", "min": MIN_PASSWORD,
                                  "msg": f"Пароль слишком короткий (минимум {MIN_PASSWORD} символов)."})
    if session.exec(select(models.User).where(models.User.email == email)).first():
        raise HTTPException(409, {"code": "email_taken", "msg": "Этот email уже зарегистрирован."})
    # Bootstrap: the very first account is the owner — admin (curates the shared
    # catalog) and full-access plan, so no manual SQL is needed post-deploy.
    first = session.exec(select(models.User).limit(1)).first() is None
    # The bootstrap owner is always auto-verified. Everyone else must confirm via
    # the magic link — UNLESS email isn't configured yet, in which case we
    # auto-verify too so the gate can't strand a signup with no way to confirm.
    verified = first or not mail.is_configured()
    u = models.User(email=email, password_hash=hash_password(body.password),
                    name=(body.name or "").strip(),
                    is_admin=first, plan=("ai" if first else "free"),
                    email_verified=verified)
    session.add(u)
    session.commit()
    session.refresh(u)
    if not u.email_verified:
        _send_verification(u)
    _set_cookie(response, u.id)
    return _serialize(u)


@router.post("/login")
def login(body: Credentials, response: Response, session: Session = Depends(get_session)):
    email = _norm(body.email)
    u = session.exec(select(models.User).where(models.User.email == email)).first()
    if not u or not verify_password(body.password, u.password_hash):
        raise HTTPException(401, {"code": "bad_credentials", "msg": "Неверный email или пароль."})
    _set_cookie(response, u.id)
    return _serialize(u)


@router.post("/logout")
def logout(response: Response):
    response.delete_cookie(COOKIE, path="/")
    return {"ok": True}


@router.get("/me")
def me(request: Request, session: Session = Depends(get_session)):
    uid = getattr(request.state, "user_id", None)
    u = session.get(models.User, uid) if uid else None
    if not u:
        raise HTTPException(401, {"code": "unauthorized", "msg": "Не авторизован."})
    return _serialize(u)


class UiLang(BaseModel):
    lang: str


@router.post("/ui-lang")
def set_ui_lang(body: UiLang, request: Request, session: Session = Depends(get_session)):
    """Persist the caller's UI language so it follows them across devices."""
    uid = getattr(request.state, "user_id", None)
    u = session.get(models.User, uid) if uid else None
    if not u:
        raise HTTPException(401, {"code": "unauthorized", "msg": "Не авторизован."})
    if body.lang not in SUPPORTED_LANGS:
        raise HTTPException(400, {"code": "bad_lang", "msg": "Unsupported language."})
    u.ui_lang = body.lang
    session.add(u)
    session.commit()
    return {"ok": True, "ui_lang": u.ui_lang}


class HeroGender(BaseModel):
    gender: str


@router.post("/hero-gender")
def set_hero_gender(body: HeroGender, request: Request, session: Session = Depends(get_session)):
    """Persist the cover-art protagonist preference (male | female | mixed) so a
    user's library shows itself back-to-camera in their gender across devices."""
    uid = getattr(request.state, "user_id", None)
    u = session.get(models.User, uid) if uid else None
    if not u:
        raise HTTPException(401, {"code": "unauthorized", "msg": "Не авторизован."})
    if body.gender not in HERO_GENDERS:
        raise HTTPException(400, {"code": "bad_gender", "msg": "Unsupported gender."})
    u.hero_gender = body.gender
    session.add(u)
    session.commit()
    return {"ok": True, "hero_gender": u.hero_gender}


class LearnProfile(BaseModel):
    profile: dict


_MAX_PROFILE_BYTES = 16 * 1024   # goals+strategy+manual ids+league ≈ 1 KB; 16 KB = abuse guard


@router.post("/learn-profile")
def set_learn_profile(body: LearnProfile, request: Request,
                      session: Session = Depends(get_session)):
    """Persist the learning profile (goals / strategy / plan mode / manual set /
    league result) so the trajectory follows the ACCOUNT across devices and
    reinstalls. Client-authoritative, last write wins — the server stores the
    blob and echoes it back in /me; lib/profile.ts owns the shape."""
    uid = getattr(request.state, "user_id", None)
    u = session.get(models.User, uid) if uid else None
    if not u:
        raise HTTPException(401, {"code": "unauthorized", "msg": "Не авторизован."})
    if len(json.dumps(body.profile, ensure_ascii=False)) > _MAX_PROFILE_BYTES:
        raise HTTPException(413, {"code": "profile_too_large", "msg": "Profile blob too large."})
    u.learn_profile = body.profile
    session.add(u)
    session.commit()
    return {"ok": True}


@router.delete("/me")
def delete_account(request: Request, response: Response, session: Session = Depends(get_session)):
    """Delete the account and ALL its data (Apple App Store Guideline 5.1.1(v)):
    per-user state/events, the user's own private imports (+ their content), and
    the account row. The shared catalog (owner_id NULL) is untouched."""
    uid = getattr(request.state, "user_id", None)
    u = session.get(models.User, uid) if uid else None
    if not u:
        raise HTTPException(401, {"code": "unauthorized", "msg": "Не авторизован."})
    # Count stored transcripts (for the non-PII deletion audit) before wiping.
    purged = 0
    for M in _TRANSCRIPT_TABLES:
        for row in session.exec(select(M).where(M.user_id == uid)).all():
            if getattr(row, "transcript", ""):
                purged += 1
    # Per-user state + event rows (incl. consent records).
    for M in _USER_TABLES:
        for row in session.exec(select(M).where(M.user_id == uid)).all():
            session.delete(row)
    # The user's own private imports (+ their children). Shared catalog is NULL-owned.
    for b in session.exec(select(models.Batch).where(models.Batch.owner_id == uid)).all():
        ph_ids = [p.id for p in session.exec(
            select(models.Phrase).where(models.Phrase.batch_id == b.id)).all()]
        if ph_ids:
            # Phrase-keyed children must die with the phrases — embeddings.seed
            # deliberately indexes private imports too, and orphaned vectors /
            # intent tags could mis-attach when SQLite recycles the phrase ids.
            for M in (models.ContextExample, models.PhraseIntent,
                      models.PhraseEmbedding):
                for row in session.exec(select(M).where(M.phrase_id.in_(ph_ids))).all():
                    session.delete(row)
        for M in (models.Zone, models.Phrase, models.MnemoStory, models.CheckPhrase,
                  models.BatchIntent):
            for row in session.exec(select(M).where(M.batch_id == b.id)).all():
                session.delete(row)
        # Children first: without ORM relationships the unit-of-work doesn't know
        # these tables depend on batch, so flush them before deleting the parent.
        session.flush()
        session.delete(b)
    session.delete(u)
    # Non-PII proof the account was deleted (keeps no personal data).
    session.add(models.DeletionLog(deleted_user_id=uid, transcripts_purged=purged))
    session.commit()
    response.delete_cookie(COOKIE, path="/")
    return {"ok": True}


# --- Data export (GDPR access/portability + CCPA right to know) --------------
@router.get("/export")
def export_data(uid: int = Depends(current_user_id), session: Session = Depends(get_session)):
    """Bundle everything tied to this account as JSON (the exact inverse of the
    deletion table list, so the two stay in lockstep). Excludes the password hash."""
    u = session.get(models.User, uid)
    if not u:
        raise HTTPException(401, {"code": "unauthorized", "msg": "Не авторизован."})
    acct = u.model_dump()
    acct.pop("password_hash", None)
    out: dict = {"format_version": 1, "account": acct}
    for M in _USER_TABLES:
        rows = session.exec(select(M).where(M.user_id == uid)).all()
        out[M.__name__] = [r.model_dump() for r in rows]
    out["OwnedBatches"] = [b.model_dump() for b in session.exec(
        select(models.Batch).where(models.Batch.owner_id == uid)).all()]
    return out


# --- Consent audit (append-only) --------------------------------------------
class ConsentIn(BaseModel):
    kind: str            # voice_ai | privacy_terms | withdraw_voice_ai
    granted: bool = True


@router.post("/consent")
def record_consent(body: ConsentIn, request: Request,
                   uid: int = Depends(current_user_id),
                   session: Session = Depends(get_session)):
    """Log a consent event (never updated — each is a new row) for audit."""
    from ..policy import PRIVACY_VERSION
    ver = PRIVACY_VERSION if body.kind == "privacy_terms" else ""
    session.add(models.ConsentRecord(
        user_id=uid, kind=body.kind, granted=body.granted, policy_version=ver,
        user_agent=request.headers.get("user-agent", "")[:300]))
    session.commit()
    return {"ok": True}


# --- Email verification (magic link) ----------------------------------------
@router.get("/verify-email", response_class=HTMLResponse)
def verify_email(token: str = "", session: Session = Depends(get_session)):
    """Public landing for the emailed magic link (opened in a browser). Confirms
    the signed token against the user's current email and flips email_verified."""
    uid = mail.token_uid(token)
    u = session.get(models.User, uid) if uid else None
    if not u or not mail.check_verify_token(token, u.email):
        return HTMLResponse(mail.error_page(), status_code=400)
    if not u.email_verified:
        u.email_verified = True
        session.add(u)
        session.commit()
    return HTMLResponse(mail.success_page())


@router.post("/resend-verification")
def resend_verification(uid: int = Depends(current_user_id),
                        session: Session = Depends(get_session)):
    """Re-send the magic link to the caller's email (no-op if already verified)."""
    u = session.get(models.User, uid)
    if not u:
        raise HTTPException(401, {"code": "unauthorized", "msg": "Не авторизован."})
    if u.email_verified:
        return {"ok": True, "already_verified": True}
    _send_verification(u)
    return {"ok": True}


class EmailChange(BaseModel):
    email: str


@router.post("/change-email")
def change_email(body: EmailChange, uid: int = Depends(current_user_id),
                 session: Session = Depends(get_session)):
    """Change the account email. The new address starts unverified and a fresh
    magic link is sent — the gate then requires confirming it (re-verification)."""
    u = session.get(models.User, uid)
    if not u:
        raise HTTPException(401, {"code": "unauthorized", "msg": "Не авторизован."})
    email = _norm(body.email)
    if "@" not in email or "." not in email.split("@")[-1]:
        raise HTTPException(400, {"code": "bad_email", "msg": "Введите корректный email."})
    if email == u.email:
        return _serialize(u)
    if session.exec(select(models.User).where(models.User.email == email)).first():
        raise HTTPException(409, {"code": "email_taken", "msg": "Этот email уже зарегистрирован."})
    u.email = email
    # Re-verify the new address only when email is actually configured; otherwise
    # leave the account usable (it can't receive a confirmation link anyway).
    u.email_verified = not mail.is_configured()
    session.add(u)
    session.commit()
    session.refresh(u)
    if not u.email_verified:
        _send_verification(u)
    return _serialize(u)
