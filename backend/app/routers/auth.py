"""Account endpoints: register / login / logout / me. Sets a signed session
cookie (eng_auth). Public: register + login. The rest of the API requires a
valid session (enforced by the auth-gate middleware in main.py)."""
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel
from sqlmodel import Session, select

from .. import models
from ..auth import hash_password, verify_password, make_session
from ..db import get_session
from ..entitlements import ents, effective_plan

router = APIRouter(prefix="/api/auth", tags=["auth"])

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


def _serialize(u: models.User) -> dict:
    # `token` is the same signed session as the cookie; native (Capacitor) stores
    # it in the Keychain and sends it as a Bearer header. Web ignores it and uses
    # the httponly cookie. Safe over HTTPS.
    plan = effective_plan(u)
    return {"id": u.id, "email": u.email, "name": u.name, "plan": plan,
            "is_admin": u.is_admin, "ui_lang": u.ui_lang, "entitlements": ents(plan),
            "token": make_session(u.id)}


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
    u = models.User(email=email, password_hash=hash_password(body.password),
                    name=(body.name or "").strip(),
                    is_admin=first, plan=("ai" if first else "free"))
    session.add(u)
    session.commit()
    session.refresh(u)
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


@router.delete("/me")
def delete_account(request: Request, response: Response, session: Session = Depends(get_session)):
    """Delete the account and ALL its data (Apple App Store Guideline 5.1.1(v)):
    per-user state/events, the user's own private imports (+ their content), and
    the account row. The shared catalog (owner_id NULL) is untouched."""
    uid = getattr(request.state, "user_id", None)
    u = session.get(models.User, uid) if uid else None
    if not u:
        raise HTTPException(401, {"code": "unauthorized", "msg": "Не авторизован."})
    # Per-user state + event rows.
    for M in (models.UserPhraseStat, models.PlaybackSession, models.ReviewEvent,
              models.PhraseAttempt, models.SequenceAttempt, models.BatchProgress,
              models.TrainingEvent):
        for row in session.exec(select(M).where(M.user_id == uid)).all():
            session.delete(row)
    # The user's own private imports (+ their children). Shared catalog is NULL-owned.
    for b in session.exec(select(models.Batch).where(models.Batch.owner_id == uid)).all():
        ph_ids = [p.id for p in session.exec(
            select(models.Phrase).where(models.Phrase.batch_id == b.id)).all()]
        if ph_ids:
            for ce in session.exec(select(models.ContextExample).where(
                    models.ContextExample.phrase_id.in_(ph_ids))).all():
                session.delete(ce)
        for M in (models.Zone, models.Phrase, models.MnemoStory, models.CheckPhrase):
            for row in session.exec(select(M).where(M.batch_id == b.id)).all():
                session.delete(row)
        session.delete(b)
    session.delete(u)
    session.commit()
    response.delete_cookie(COOKIE, path="/")
    return {"ok": True}
