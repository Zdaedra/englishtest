from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from sqlmodel import Session

from . import models
from .config import get_settings
from .db import engine, init_db
from .auth import parse_session
from .routers import admin_stats, analyzer, auth, batches, billing, imports, league, practice, progress, sessions, settings, training, tutorial

app = FastAPI(title="English Executive")

# Dev: Vite runs on :5173 and proxies /api, but allow direct CORS too.
# Native (Capacitor/iOS) loads from capacitor://localhost and calls the API
# cross-origin with a Bearer token (no cookie), so its origin must be allowed.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173", "http://127.0.0.1:5173",
        "capacitor://localhost", "ionic://localhost", "https://localhost",
    ],
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Per-user account auth gate ---------------------------------------------
# Commercial multi-user: a signed session cookie (eng_auth) carries the user id.
# Only the API + cost-bearing media are gated; the SPA shell/assets load freely
# and the frontend gates itself via /api/auth/me. Register + login are public.
_COOKIE = "eng_auth"
_PUBLIC = {"/api/auth/login", "/api/auth/register", "/api/health",
           "/api/auth/verify-email",  # magic link is opened in a browser, no session
           "/api/policy/versions",    # legal-doc versions (read before/at login)
           "/api/tutorial/manifest",  # which coach-mark steps have a video (read-only file listing)
           "/api/billing/apple-notifications"}  # Apple posts the webhook unauthenticated
# Authed endpoints an unverified account may still reach (account management) so it
# can confirm/resend/change its email, switch UI language, or delete itself. Every
# other /api path is blocked with 403 email_unverified until the email is confirmed.
_VERIFY_EXEMPT = {"/api/auth/me", "/api/auth/logout", "/api/auth/ui-lang",
                  "/api/auth/resend-verification", "/api/auth/change-email"}


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
    elif path.startswith("/audio/"):
        # Hash-named TTS clips never change under the same name → cache hard.
        resp.headers["Cache-Control"] = "public, max-age=31536000, immutable"
    elif path.startswith("/covers/"):
        # Cover art is effectively static (per-slug); cache on device so native
        # doesn't re-download megabytes every view. Regenerating a cover is rare —
        # if needed, change the filename / add a version to bust this.
        resp.headers["Cache-Control"] = "public, max-age=2592000"
    else:
        resp.headers["Cache-Control"] = "no-store, must-revalidate"
    return resp


@app.middleware("http")
async def _auth_gate(request: Request, call_next):
    # Let CORS preflight through untouched — the browser sends OPTIONS with no
    # credentials, and the CORS middleware must answer it (native POSTs with a
    # JSON body + Bearer header are non-simple and trigger preflight).
    if request.method == "OPTIONS":
        return await call_next(request)
    path = request.url.path
    # Only the JSON API is auth-gated. Static media (/audio, /covers) is public:
    # native <img>/<audio> can't carry the Bearer header, the filenames are
    # non-enumerable hashes, and the API still controls which URLs a user receives
    # (locked batches return no phrases/audio URLs).
    if not path.startswith("/api/"):
        return await call_next(request)
    if path in _PUBLIC:
        return await call_next(request)
    # Web sends the signed session in the httponly cookie; native clients (no
    # reliable cross-origin cookie in WKWebView) send the same token as a
    # Bearer header. Accept either.
    uid = parse_session(request.cookies.get(_COOKIE, ""))
    if uid is None:
        authz = request.headers.get("authorization", "")
        if authz[:7].lower() == "bearer ":
            uid = parse_session(authz[7:].strip())
    if uid is None:
        return Response(status_code=401)
    request.state.user_id = uid
    # Mandatory email verification: an authed-but-unconfirmed account may only hit
    # the account-management endpoints (resend/change/logout/me/ui-lang) until it
    # confirms its email. Everything else is blocked so the gate has real teeth.
    if path not in _VERIFY_EXEMPT:
        with Session(engine()) as s:
            u = s.get(models.User, uid)
            if u is not None and not u.email_verified:
                return JSONResponse({"code": "email_unverified",
                                     "msg": "Подтвердите email."}, status_code=403)
    return await call_next(request)

app.include_router(auth.router)
app.include_router(billing.router)
app.include_router(imports.router)
app.include_router(batches.router)
app.include_router(sessions.router)
app.include_router(settings.router)
app.include_router(training.router)
app.include_router(practice.router)
app.include_router(progress.router)
app.include_router(analyzer.router)
app.include_router(league.router)
app.include_router(tutorial.router)
# Stats cabinet — under /admin (NOT /api, so it bypasses the per-user auth gate)
# and self-guarded by its own HTTP Basic auth. Registered before the SPA catch-all
# mount so /admin resolves here, not the app shell.
app.include_router(admin_stats.router)


@app.on_event("startup")
async def _startup():
    init_db()
    # Daily in-process purge of old voice transcripts (data minimisation).
    import asyncio
    from .retention import retention_loop
    asyncio.create_task(retention_loop())
    # Daily content↔progress integrity report into the app log (report-only;
    # see app/doctor.py and CONTENT-GRAPH.md).
    from .doctor import doctor_loop
    asyncio.create_task(doctor_loop())


@app.get("/api/health")
def health():
    return {"ok": True}


# Public Privacy Policy (App Store requires a reachable URL). Registered before the
# SPA catch-all mount so /privacy returns the policy, not the app shell.
_privacy_file = Path(__file__).resolve().parent / "static" / "privacy.html"


@app.get("/privacy")
def privacy():
    return FileResponse(str(_privacy_file), media_type="text/html")


_terms_file = Path(__file__).resolve().parent / "static" / "terms.html"


@app.get("/terms")
def terms():
    return FileResponse(str(_terms_file), media_type="text/html")


@app.get("/api/policy/versions")
def policy_versions():
    from .policy import PRIVACY_VERSION, TERMS_VERSION
    return {"privacy": PRIVACY_VERSION, "terms": TERMS_VERSION}


# Static rendered audio (sessions + phrases)
_s = get_settings()
app.mount("/audio", StaticFiles(directory=str(_s.audio_dir)), name="audio")

# AI-generated batch cover art
app.mount("/covers", StaticFiles(directory=str(_s.covers_dir)), name="covers")

# Coach-mark tutorial videos (dropped in by the founder later; manifest lists them).
app.mount("/tutorial", StaticFiles(directory=str(_s.tutorial_dir)), name="tutorial")

# Serve built frontend if present (production single-container).
_dist = Path(__file__).resolve().parent.parent.parent / "frontend" / "dist"
if _dist.exists():
    app.mount("/", StaticFiles(directory=str(_dist), html=True), name="frontend")
