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
    },
    "core": {
        "voice_answer": False,      # Core: swipe + reveal + audio/import, but no mic
        "server_stt": True,
        "ai_coach": False,
        "import": True,
        "max_active_batches": None,
        "scored_per_day": 200,
        "gapless_per_day": None,
    },
    "ai": {
        "voice_answer": True,       # mic active: speak + AI scoring/coaching
        "server_stt": True,
        "ai_coach": True,
        "import": True,
        "max_active_batches": None,
        "scored_per_day": 400,
        "gapless_per_day": None,
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
