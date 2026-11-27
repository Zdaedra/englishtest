"""Plan-based content access — the freemium gate.

Model (2026-06): exactly ONE batch is marked `is_free` and is FULLY open to
everyone, including the mic / AI coach. Every other shared-catalog batch requires
a paid plan (core or ai) to open/learn/practice. The mic + AI coach require the
`ai` plan EXCEPT on the free showcase batch, where everyone gets to feel them.

A user's own private imports (owner_id == user) are always usable by that user.
"""
from . import models

_PAID = ("core", "ai")


def visible(batch: "models.Batch | None", user_id: int) -> bool:
    """Shared catalog or the user's own import — never someone else's private
    import, never a deleted batch. Batch and phrase ids are sequential, so every
    route taking an id must ask this first (found 2026-11-27: nine didn't)."""
    if batch is None or getattr(batch, "deleted_at", None):
        return False
    return batch.owner_id is None or batch.owner_id == user_id


def batch_usable(plan: str | None, batch: "models.Batch | None", user_id: int) -> bool:
    """May this user open/learn/practice this batch's content at all?

    `plan` must be `entitlements.effective_plan(user)`, NEVER the raw `user.plan`
    column. The column keeps saying "ai" after an Apple subscription lapses — it
    is only corrected when a webhook arrives, and a webhook can be lost, late or
    duplicated. Passing the column meant the profile screen said "free" while the
    paid topics stayed open. Every call site in the routers was fixed on
    2026-11-26; keep it that way.
    """
    if not visible(batch, user_id):
        return False                # someone else's private import was "usable" by any paid plan
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
