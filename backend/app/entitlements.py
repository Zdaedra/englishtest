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
    },
    "core": {
        "voice_answer": False,      # Core: swipe + reveal + audio/import, but no mic
        "server_stt": True,
        "ai_coach": False,
        "import": True,
        "max_active_batches": None,
        "scored_per_day": 200,
    },
    "ai": {
        "voice_answer": True,       # mic active: speak + AI scoring/coaching
        "server_stt": True,
        "ai_coach": True,
        "import": True,
        "max_active_batches": None,
        "scored_per_day": 400,
    },
}


def ents(plan: str | None) -> dict:
    return ENTITLEMENTS.get(plan or "free", ENTITLEMENTS["free"])


def user_entitlements(session: Session, user_id: int) -> dict:
    from . import models  # local import avoids a cycle at module load
    u = session.get(models.User, user_id)
    return ents(u.plan if u else "free")
