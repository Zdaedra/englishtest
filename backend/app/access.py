"""Plan-based content access — the freemium gate.

Model (2026-06): exactly ONE batch is marked `is_free` and is FULLY open to
everyone, including the mic / AI coach. Every other shared-catalog batch requires
a paid plan (core or ai) to open/learn/practice. The mic + AI coach require the
`ai` plan EXCEPT on the free showcase batch, where everyone gets to feel them.

A user's own private imports (owner_id == user) are always usable by that user.
"""
from . import models

_PAID = ("core", "ai")


def batch_usable(plan: str | None, batch: "models.Batch | None", user_id: int) -> bool:
    """May this user open/learn/practice this batch's content at all?"""
    if batch is None:
        return False
    if batch.owner_id == user_id:   # own import
        return True
    if getattr(batch, "is_free", False):  # the free showcase batch
        return True
    return (plan or "free") in _PAID


def ai_on_batch(plan: str | None, batch: "models.Batch | None") -> bool:
    """May this user use the mic / AI scoring / AI coach on this batch?"""
    if batch is not None and getattr(batch, "is_free", False):
        return True                 # free batch demos the flagship AI to everyone
    return (plan or "free") == "ai"
