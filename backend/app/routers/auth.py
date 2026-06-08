"""Account endpoints: register / login / logout / me. Sets a signed session
cookie (eng_auth). Public: register + login. The rest of the API requires a
valid session (enforced by the auth-gate middleware in main.py)."""
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel
from sqlmodel import Session, select

from .. import models
from ..auth import hash_password, verify_password, make_session
from ..db import get_session
from ..entitlements import ents

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


def _serialize(u: models.User) -> dict:
    return {"id": u.id, "email": u.email, "name": u.name, "plan": u.plan,
            "is_admin": u.is_admin, "entitlements": ents(u.plan)}


def _set_cookie(response: Response, user_id: int) -> None:
    response.set_cookie(COOKIE, make_session(user_id), max_age=MAX_AGE,
                        httponly=True, samesite="lax", path="/")


@router.post("/register")
def register(body: Credentials, response: Response, session: Session = Depends(get_session)):
    email = _norm(body.email)
    if "@" not in email or "." not in email.split("@")[-1]:
        raise HTTPException(400, "Введите корректный email.")
    if len(body.password) < MIN_PASSWORD:
        raise HTTPException(400, f"Пароль слишком короткий (минимум {MIN_PASSWORD} символов).")
    if session.exec(select(models.User).where(models.User.email == email)).first():
        raise HTTPException(409, "Этот email уже зарегистрирован.")
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
        raise HTTPException(401, "Неверный email или пароль.")
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
        raise HTTPException(401, "Не авторизован.")
    return _serialize(u)
