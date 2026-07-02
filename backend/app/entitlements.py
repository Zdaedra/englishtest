"""Subscription entitlements — the single source of truth for what each plan can
do. Tiers: free | core | ai (see SUBSCRIPTION-TIERS.md). Packaging only; no new
features. Defaults are tunable here without touching endpoints.
"""
from sqlmodel import Session

ENTITLEMENTS: dict[str, dict] = {
    "free": {
        "voice_answer": False,      # the big mic (spoken answer) — AI only
        "server_stt": False,
        "ai_coach": False,
        "import": False,
        "max_active_batches": 3,    # None => unlimited
        "scored_per_day": 30,
        "gapless_per_day": 3,       # gapless audio sessions/day (TTS cost lever)
        # Monthly estimated-AI-cost ceiling (USD). Bounds worst-case COGS to a known
        # fraction of revenue — see usage.py / TZ-ai-cost-strategy.md. Free generates
        # no revenue, so this is a tight abuse backstop; the daily cap is the main gate.
        "monthly_ai_cost_cap_usd": 0.30,
    },
    "core": {
        "voice_answer": False,      # Core: swipe + reveal + audio/import, but no mic
        "server_stt": True,
        "ai_coach": False,
        "import": True,
        "max_active_batches": None,
        "scored_per_day": 200,
        "gapless_per_day": None,
        "monthly_ai_cost_cap_usd": 0.60,
    },
    "ai": {
        "voice_answer": True,       # mic active: speak + AI scoring/coaching
        "server_stt": True,
        "ai_coach": True,
        "import": True,
        "max_active_batches": None,
        "scored_per_day": 400,
        "gapless_per_day": None,
        # AI tier: floor net revenue ≈ $5.67/mo (annual plan, 15% Apple). $1.50 cap =>
        # worst-case AI COGS ≤ ~26% of that; a real heavy user sits near $0.5–1.0/mo,
        # so the cap only ever bites scripted/abusive usage.
        "monthly_ai_cost_cap_usd": 1.50,
    },
}


def ents(plan: str | None) -> dict:
    return ENTITLEMENTS.get(plan or "free", ENTITLEMENTS["free"])


def effective_plan(u) -> str:
    """The plan in force right now — an expired Apple subscription falls back to
    free. Naive datetimes are treated as UTC."""
    if not u:
        return "free"
    exp = getattr(u, "plan_expires_at", None)
    if exp is not None:
        from datetime import datetime, timezone
        e = exp if exp.tzinfo else exp.replace(tzinfo=timezone.utc)
        if e < datetime.now(timezone.utc):
            return "free"
    return u.plan or "free"


def user_entitlements(session: Session, user_id: int) -> dict:
    from . import models  # local import avoids a cycle at module load
    u = session.get(models.User, user_id)
    return ents(effective_plan(u))
