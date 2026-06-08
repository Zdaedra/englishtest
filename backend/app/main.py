from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from fastapi.staticfiles import StaticFiles

from .config import get_settings
from .db import init_db
from .auth import parse_session
from .routers import auth, batches, imports, practice, progress, sessions, settings, training

app = FastAPI(title="English Executive")

# Dev: Vite runs on :5173 and proxies /api, but allow direct CORS too.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Per-user account auth gate ---------------------------------------------
# Commercial multi-user: a signed session cookie (eng_auth) carries the user id.
# Only the API + cost-bearing media are gated; the SPA shell/assets load freely
# and the frontend gates itself via /api/auth/me. Register + login are public.
_COOKIE = "eng_auth"
_PUBLIC = {"/api/auth/login", "/api/auth/register", "/api/health"}


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
    path = request.url.path
    if not (path.startswith("/api/") or path.startswith("/audio/") or path.startswith("/covers/")):
        return await call_next(request)
    if path in _PUBLIC:
        return await call_next(request)
    uid = parse_session(request.cookies.get(_COOKIE, ""))
    if uid is None:
        return Response(status_code=401)
    request.state.user_id = uid
    return await call_next(request)

app.include_router(auth.router)
app.include_router(imports.router)
app.include_router(batches.router)
app.include_router(sessions.router)
app.include_router(settings.router)
app.include_router(training.router)
app.include_router(practice.router)
app.include_router(progress.router)


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
