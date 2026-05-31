import hashlib
import hmac
from pathlib import Path
from urllib.parse import parse_qs

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles

from .config import get_settings
from .db import init_db
from .routers import batches, imports, sessions, settings, training

app = FastAPI(title="English Executive")

# Dev: Vite runs on :5173 and proxies /api, but allow direct CORS too.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Single-user cookie auth gate -------------------------------------------
# Replaces HTTP basic-auth so iOS Safari (and the home-screen PWA) remember the
# login: one password entry sets a signed, year-long cookie. Cost-bearing TTS
# stays protected. Disabled when ENGLISH_APP_PASSWORD is empty (local dev).
_COOKIE = "eng_auth"
_COOKIE_MAX_AGE = 31536000  # 1 year


def _auth_token() -> str:
    s = get_settings()
    return hmac.new(s.cookie_secret.encode(), b"eng-auth-v1", hashlib.sha256).hexdigest()


def _login_page(error: str = "") -> HTMLResponse:
    err = f'<p class="err">{error}</p>' if error else ""
    html = f"""<!doctype html><html lang="ru"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="theme-color" content="#F8F8F6">
<title>English Executive — вход</title>
<style>
  body{{margin:0;min-height:100vh;display:flex;align-items:center;justify-content:center;
       background:#F8F8F6;color:#111111;
       font-family:-apple-system,"SF Pro Display","SF Pro Text",system-ui,sans-serif}}
  form{{width:min(360px,86vw);padding:32px 24px;background:#FFFFFF;border:1px solid #ECECEC;
       border-radius:26px;box-shadow:0 10px 40px rgba(17,17,17,.06)}}
  .brand{{font-size:24px;font-weight:800;letter-spacing:-.01em;margin:0 0 4px}}
  .tag{{font-size:13px;color:#6B6B6B;margin:0 0 22px}}
  input{{width:100%;box-sizing:border-box;padding:14px 16px;font-size:17px;border-radius:14px;
        border:1px solid #ECECEC;background:#F8F8F6;color:#111111;margin-bottom:14px;
        outline:none;transition:border-color .2s}}
  input:focus{{border-color:#6B6FCF;background:#FFFFFF}}
  button{{width:100%;padding:15px;font-size:17px;font-weight:700;border:0;border-radius:14px;
         background:#6B6FCF;color:#fff;cursor:pointer}}
  .err{{color:#C0564B;font-size:14px;margin:0 0 12px}}
</style></head><body>
<form method="post" action="/login">
  <h1 class="brand">English Executive</h1>
  <p class="tag">Executive communication. Built for real conversations.</p>{err}
  <input type="password" name="password" placeholder="Пароль" autofocus
         autocomplete="current-password">
  <button type="submit">Войти</button>
</form></body></html>"""
    return HTMLResponse(html)


@app.middleware("http")
async def _cache_control(request: Request, call_next):
    # Only Vite's content-hashed /assets/* are safe to cache forever (a new build
    # => a new filename). Covers/audio may be regenerated under the same name, so
    # revalidate. Everything else — the HTML shell, sw.js, the manifest, and ALL
    # /api JSON (e.g. the cover URLs the UI renders) — must never be served stale,
    # or a deploy ships an old shell or the old data behind a fresh one.
    resp = await call_next(request)
    path = request.url.path
    if path.startswith("/assets/"):
        resp.headers["Cache-Control"] = "public, max-age=31536000, immutable"
    elif path.startswith("/covers/") or path.startswith("/audio/"):
        resp.headers["Cache-Control"] = "no-cache"
    else:
        resp.headers["Cache-Control"] = "no-store, must-revalidate"
    return resp


@app.middleware("http")
async def _auth_gate(request: Request, call_next):
    s = get_settings()
    if not s.app_password:  # gate disabled
        return await call_next(request)

    token = _auth_token()
    path = request.url.path

    if path == "/login":
        if request.method == "POST":
            body = await request.body()
            pw = (parse_qs(body.decode()).get("password") or [""])[0]
            if hmac.compare_digest(pw, s.app_password):
                resp = RedirectResponse("/", status_code=303)
                resp.set_cookie(_COOKIE, token, max_age=_COOKIE_MAX_AGE,
                                httponly=True, samesite="lax", path="/")
                return resp
            return _login_page("Неверный пароль")
        return _login_page()

    if hmac.compare_digest(request.cookies.get(_COOKIE, ""), token):
        return await call_next(request)

    if path.startswith("/api/") or path.startswith("/audio/"):
        return Response(status_code=401)
    return RedirectResponse("/login", status_code=303)

app.include_router(imports.router)
app.include_router(batches.router)
app.include_router(sessions.router)
app.include_router(settings.router)
app.include_router(training.router)


@app.on_event("startup")
def _startup():
    init_db()


@app.get("/api/health")
def health():
    return {"ok": True}


# Static rendered audio (sessions + phrases)
_s = get_settings()
app.mount("/audio", StaticFiles(directory=str(_s.audio_dir)), name="audio")

# AI-generated batch cover art
app.mount("/covers", StaticFiles(directory=str(_s.covers_dir)), name="covers")

# Serve built frontend if present (production single-container).
_dist = Path(__file__).resolve().parent.parent.parent / "frontend" / "dist"
if _dist.exists():
    app.mount("/", StaticFiles(directory=str(_dist), html=True), name="frontend")
