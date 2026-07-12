"""Кабинет статистики — admin analytics dashboard.

Lives OUTSIDE the /api namespace on purpose: the global `_auth_gate` middleware
(main.py) 401s any /api/* without a user session, which would block this surface.
Everything here sits under /admin and is guarded by its own HTTP Basic auth keyed
to ENGLISH_STATS_USER / ENGLISH_STATS_PASSWORD. If either is unset the whole
cabinet returns 404 (fail-closed — never accidentally public).

All queries are READ-ONLY aggregates over the existing tables; no schema changes.
Metrics are computed from event timestamps because there is no explicit last_login
(see /admin dashboard notes). Table names are SQLModel defaults (lowercased class
names): user, batch, batchprogress, userphrasestat, trainingevent, phraseattempt,
sequenceattempt, playbacksession.
"""
from __future__ import annotations

import base64
import secrets as _secrets
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse
from sqlalchemy import text
from sqlmodel import Session

from ..config import get_settings
from ..db import engine

router = APIRouter(tags=["admin-stats"])

_STATIC = Path(__file__).resolve().parent.parent / "static"

# Union of every "did something" event with its timestamp — the activity signal
# (DAU/WAU/MAU, retention) since there is no last_login column.
_EV = """
  SELECT user_id, created_at AS ts FROM trainingevent
  UNION ALL SELECT user_id, created_at FROM phraseattempt
  UNION ALL SELECT user_id, created_at FROM sequenceattempt
  UNION ALL SELECT user_id, created_at FROM playbacksession
"""
# Scored active-recall only — the product's core value event.
_SC = """
  SELECT user_id, created_at AS ts FROM phraseattempt
  UNION ALL SELECT user_id, created_at FROM sequenceattempt
  UNION ALL SELECT user_id, created_at FROM trainingevent WHERE ai_score IS NOT NULL
"""


def require_stats_auth(request: Request) -> None:
    """HTTP Basic gate keyed to env creds. 404 when disabled, 401 when wrong."""
    cfg = get_settings()
    user, pw = cfg.stats_user, cfg.stats_password
    if not user or not pw:
        raise HTTPException(status_code=404)  # cabinet disabled / not configured
    hdr = request.headers.get("authorization", "")
    ok = False
    if hdr[:6].lower() == "basic ":
        try:
            raw = base64.b64decode(hdr[6:].strip()).decode("utf-8")
            u, _, p = raw.partition(":")
            ok = _secrets.compare_digest(u, user) and _secrets.compare_digest(p, pw)
        except Exception:
            ok = False
    if not ok:
        raise HTTPException(
            status_code=401,
            detail="auth required",
            headers={"WWW-Authenticate": 'Basic realm="Executive English stats"'},
        )


def _q(sql: str, **params):
    with Session(engine()) as s:
        return s.execute(text(sql), params).mappings().all()


def _scalar(sql: str, **params):
    with Session(engine()) as s:
        return s.execute(text(sql), params).scalar()


@router.get("/admin")
def dashboard(_: None = Depends(require_stats_auth)):
    return FileResponse(str(_STATIC / "stats.html"), media_type="text/html")


@router.get("/admin/api/overview")
def overview(_: None = Depends(require_stats_auth)):
    total = _scalar("SELECT COUNT(*) FROM user") or 0
    paid = _scalar("SELECT COUNT(*) FROM user WHERE plan IN ('core','ai')") or 0
    verified = _scalar("SELECT COUNT(*) FROM user WHERE email_verified=1") or 0
    new7 = _scalar("SELECT COUNT(*) FROM user WHERE created_at >= datetime('now','-7 days')") or 0
    new30 = _scalar("SELECT COUNT(*) FROM user WHERE created_at >= datetime('now','-30 days')") or 0
    dau = _scalar(f"SELECT COUNT(DISTINCT user_id) FROM ({_EV}) WHERE ts >= datetime('now','-1 days')") or 0
    wau = _scalar(f"SELECT COUNT(DISTINCT user_id) FROM ({_EV}) WHERE ts >= datetime('now','-7 days')") or 0
    mau = _scalar(f"SELECT COUNT(DISTINCT user_id) FROM ({_EV}) WHERE ts >= datetime('now','-30 days')") or 0
    wal = _scalar(f"SELECT COUNT(DISTINCT user_id) FROM ({_SC}) WHERE ts >= datetime('now','-7 days')") or 0
    attempts7 = _scalar(f"SELECT COUNT(*) FROM ({_SC}) WHERE ts >= datetime('now','-7 days')") or 0
    # Activation: of users who signed up in the last 30 days, the share who
    # activated at least one batch.
    cohort30 = _scalar("SELECT COUNT(*) FROM user WHERE created_at >= datetime('now','-30 days')") or 0
    activ30 = _scalar(
        "SELECT COUNT(DISTINCT u.id) FROM user u JOIN batchprogress bp ON bp.user_id=u.id "
        "AND bp.activated=1 WHERE u.created_at >= datetime('now','-30 days')"
    ) or 0

    def pct(a, b):
        return round(100.0 * a / b, 1) if b else 0.0

    return {
        "total_users": total, "new_7d": new7, "new_30d": new30,
        "dau": dau, "wau": wau, "mau": mau,
        "stickiness": pct(dau, mau),
        "wal": wal, "attempts_7d": attempts7,
        "paid_users": paid, "paid_pct": pct(paid, total),
        "verified_pct": pct(verified, total),
        "activation_rate": pct(activ30, cohort30),
    }


@router.get("/admin/api/timeseries")
def timeseries(days: int = 30, _: None = Depends(require_stats_auth)):
    days = max(7, min(180, days))
    since = f"-{days} days"
    sign = {r["d"]: r["n"] for r in _q(
        "SELECT date(created_at) d, COUNT(*) n FROM user "
        "WHERE created_at >= datetime('now', :s) GROUP BY d", s=since)}
    act = {r["d"]: r["n"] for r in _q(
        f"SELECT date(ts) d, COUNT(DISTINCT user_id) n FROM ({_EV}) "
        "WHERE ts >= datetime('now', :s) GROUP BY d", s=since)}
    att = {r["d"]: r["n"] for r in _q(
        f"SELECT date(ts) d, COUNT(*) n FROM ({_SC}) "
        "WHERE ts >= datetime('now', :s) GROUP BY d", s=since)}
    # Dense day axis so the chart has no gaps.
    axis = [r["d"] for r in _q(
        "WITH RECURSIVE seq(d) AS ("
        " SELECT date('now', :s) UNION ALL SELECT date(d,'+1 day') FROM seq WHERE d < date('now')) "
        "SELECT d FROM seq", s=since)]
    return [{"date": d, "signups": sign.get(d, 0), "active": act.get(d, 0),
             "attempts": att.get(d, 0)} for d in axis]


@router.get("/admin/api/funnel")
def funnel(_: None = Depends(require_stats_auth)):
    total = _scalar("SELECT COUNT(*) FROM user") or 0
    return {
        "signed_up": total,
        "verified": _scalar("SELECT COUNT(*) FROM user WHERE email_verified=1") or 0,
        "activated_batch": _scalar("SELECT COUNT(DISTINCT user_id) FROM batchprogress WHERE activated=1") or 0,
        "first_scored": _scalar(f"SELECT COUNT(DISTINCT user_id) FROM ({_SC})") or 0,
        "completed_batch": _scalar("SELECT COUNT(DISTINCT user_id) FROM batchprogress WHERE l3_passed=1") or 0,
    }


@router.get("/admin/api/retention")
def retention(_: None = Depends(require_stats_auth)):
    # Weekly cohorts vs weeks-since-signup, computed off a fixed Monday epoch so
    # cohort/active week indices line up. Activity = any event that week.
    sizes = {r["cw"]: r["n"] for r in _q(
        "SELECT CAST((julianday(date(created_at))-julianday('2020-01-06'))/7 AS INT) cw, "
        "COUNT(*) n FROM user GROUP BY cw")}
    grid = _q(
        f"WITH ev AS ({_EV}), "
        "u AS (SELECT id, CAST((julianday(date(created_at))-julianday('2020-01-06'))/7 AS INT) cw FROM user), "
        "act AS (SELECT DISTINCT user_id uid, CAST((julianday(date(ts))-julianday('2020-01-06'))/7 AS INT) aw FROM ev) "
        "SELECT u.cw cw, (a.aw-u.cw) k, COUNT(DISTINCT u.id) n "
        "FROM u JOIN act a ON a.uid=u.id WHERE a.aw>=u.cw GROUP BY u.cw, k")
    if not sizes:
        return {"cohorts": []}
    cells: dict[int, dict[int, int]] = {}
    for r in grid:
        cells.setdefault(r["cw"], {})[r["k"]] = r["n"]
    recent = sorted(sizes.keys())[-8:]   # last 8 weekly cohorts
    maxk = 7
    out = []
    for cw in recent:
        size = sizes[cw]
        row = {"week": _week_label(cw), "size": size, "cells": []}
        for k in range(maxk + 1):
            n = cells.get(cw, {}).get(k, 0)
            row["cells"].append({"k": k, "n": n,
                                 "pct": round(100.0 * n / size, 0) if size else 0})
        out.append(row)
    return {"cohorts": out}


def _week_label(cw: int) -> str:
    # cw = weeks since 2020-01-06 (a Monday). Render the cohort's Monday date.
    days = cw * 7
    return _scalar("SELECT date('2020-01-06', :d)", d=f"+{days} days") or str(cw)


@router.get("/admin/api/plans")
def plans(_: None = Depends(require_stats_auth)):
    dist = {r["plan"]: r["n"] for r in _q("SELECT plan, COUNT(*) n FROM user GROUP BY plan")}
    src = {r["plan_source"]: r["n"] for r in _q(
        "SELECT plan_source, COUNT(*) n FROM user WHERE plan IN ('core','ai') GROUP BY plan_source")}
    expiring = _scalar(
        "SELECT COUNT(*) FROM user WHERE plan_expires_at IS NOT NULL "
        "AND plan_expires_at >= datetime('now') AND plan_expires_at <= datetime('now','+30 days')") or 0
    return {
        "free": dist.get("free", 0), "core": dist.get("core", 0), "ai": dist.get("ai", 0),
        "source": src, "expiring_30d": expiring,
    }


@router.get("/admin/api/quality")
def quality(_: None = Depends(require_stats_auth)):
    srs = {r["srs_status"]: r["n"] for r in _q(
        "SELECT srs_status, COUNT(*) n FROM userphrasestat GROUP BY srs_status")}
    hist = _q(
        "SELECT CASE "
        " WHEN avg_score < 2 THEN '0–2' WHEN avg_score < 4 THEN '2–4' "
        " WHEN avg_score < 6 THEN '4–6' WHEN avg_score < 8 THEN '6–8' ELSE '8–10' END bucket, "
        "COUNT(*) n FROM userphrasestat WHERE avg_score IS NOT NULL GROUP BY bucket")
    scored = _scalar("SELECT COUNT(*) FROM userphrasestat WHERE avg_score IS NOT NULL") or 0
    gap = _scalar("SELECT COUNT(*) FROM userphrasestat WHERE self_ewma >= 0.6 "
                  "AND avg_score IS NOT NULL AND avg_score < 6") or 0
    testb = _scalar("SELECT AVG(score) FROM phraseattempt")
    seq_total = _scalar("SELECT COUNT(*) FROM sequenceattempt") or 0
    seq_pass = _scalar("SELECT COUNT(*) FROM sequenceattempt WHERE score >= 7") or 0
    return {
        "srs": {k: srs.get(k, 0) for k in ("new", "shaky", "familiar", "automatic")},
        "score_hist": {r["bucket"]: r["n"] for r in hist},
        "confidence_gap_pct": round(100.0 * gap / scored, 1) if scored else 0.0,
        "testb_avg": round(testb, 2) if testb is not None else None,
        "testa_pass_pct": round(100.0 * seq_pass / seq_total, 1) if seq_total else 0.0,
    }


@router.get("/admin/api/content")
def content(_: None = Depends(require_stats_auth)):
    rows = _q(
        "SELECT b.id id, b.title title, b.section section, b.is_free is_free, "
        " (SELECT COUNT(DISTINCT user_id) FROM userphrasestat WHERE batch_id=b.id) reach, "
        " (SELECT COUNT(*) FROM batchprogress WHERE batch_id=b.id AND activated=1) activated, "
        " (SELECT COUNT(*) FROM batchprogress WHERE batch_id=b.id AND l3_passed=1) completed, "
        " (SELECT AVG(avg_score) FROM userphrasestat WHERE batch_id=b.id AND avg_score IS NOT NULL) avg_score "
        "FROM batch b WHERE b.deleted_at IS NULL ORDER BY reach DESC, activated DESC LIMIT 60")
    out = []
    for r in rows:
        act = r["activated"] or 0
        comp = r["completed"] or 0
        out.append({
            "id": r["id"], "title": r["title"], "section": r["section"] or "—",
            "is_free": bool(r["is_free"]), "reach": r["reach"] or 0,
            "activated": act, "completed": comp,
            "completion_pct": round(100.0 * comp / act, 0) if act else 0,
            "avg_score": round(r["avg_score"], 1) if r["avg_score"] is not None else None,
        })
    return out
