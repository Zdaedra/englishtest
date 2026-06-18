"""Server-side per-batch learning state (single-user). Source of truth for the
swipe-trainer's 'active in-progress batches' and the learning path. Mirrors what
used to live in client localStorage (ee-progress-*); PUT upserts partial fields.
"""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, select

from .. import access, models
from ..auth import current_user_id
from ..db import get_session
from ..entitlements import user_entitlements

router = APIRouter(prefix="/api/progress", tags=["progress"])


def _serialize(bp: models.BatchProgress) -> dict:
    return {
        "batch_id": bp.batch_id,
        "activated": bp.activated,
        "activated_at": bp.activated_at.isoformat() if bp.activated_at else None,
        "l1_listened": bp.l1_listened,
        "l1_retold": bp.l1_retold,
        "l1_best_seq": bp.l1_best_seq,
        "l3_s1": bp.l3_s1,
        "l3_s2": bp.l3_s2,
        "l3_passed": bp.l3_passed,
        "completed_at": bp.completed_at.isoformat() if bp.completed_at else None,
    }


def _empty(batch_id: int) -> dict:
    return {"batch_id": batch_id, "activated": False, "activated_at": None,
            "l1_listened": False, "l1_retold": False, "l1_best_seq": None,
            "l3_s1": False, "l3_s2": False, "l3_passed": False, "completed_at": None}


class ProgressPatch(BaseModel):
    activated: bool | None = None
    l1_listened: bool | None = None
    l1_retold: bool | None = None
    l1_best_seq: float | None = None
    l3_s1: bool | None = None
    l3_s2: bool | None = None
    l3_passed: bool | None = None


@router.get("")
def list_progress(user_id: int = Depends(current_user_id), session: Session = Depends(get_session)):
    return [_serialize(bp) for bp in session.exec(select(models.BatchProgress)
            .where(models.BatchProgress.user_id == user_id)).all()]


@router.get("/{batch_id}")
def get_progress(batch_id: int, user_id: int = Depends(current_user_id),
                 session: Session = Depends(get_session)):
    bp = session.exec(select(models.BatchProgress).where(
        models.BatchProgress.user_id == user_id,
        models.BatchProgress.batch_id == batch_id)).first()
    return _serialize(bp) if bp else _empty(batch_id)


@router.put("/{batch_id}")
def put_progress(batch_id: int, patch: ProgressPatch,
                 user_id: int = Depends(current_user_id),
                 session: Session = Depends(get_session)):
    batch = session.get(models.Batch, batch_id)
    if not batch:
        raise HTTPException(404, "Batch not found")
    bp = session.exec(select(models.BatchProgress).where(
        models.BatchProgress.user_id == user_id,
        models.BatchProgress.batch_id == batch_id)).first()
    if not bp:
        bp = models.BatchProgress(user_id=user_id, batch_id=batch_id)
    now = datetime.now(timezone.utc)
    data = patch.model_dump(exclude_unset=True)
    if data.get("activated") and not bp.activated:
        # Freemium gate: free users can only activate the free batch (+ own imports).
        u = session.get(models.User, user_id)
        if not access.batch_usable(u.plan if u else "free", batch, user_id):
            raise HTTPException(403, "locked")
        # Free plan: cap simultaneously-active skills (an upgrade trigger).
        cap = user_entitlements(session, user_id)["max_active_batches"]
        if cap is not None:
            active = len(session.exec(select(models.BatchProgress).where(
                models.BatchProgress.user_id == user_id,
                models.BatchProgress.activated == True)).all())  # noqa: E712
            if active >= cap:
                raise HTTPException(403, "limit_active")
        bp.activated_at = now
    if data.get("l3_passed") and not bp.l3_passed:
        bp.completed_at = now
    for k, v in data.items():
        setattr(bp, k, v)
    bp.updated_at = now
    session.add(bp)
    session.commit()
    return _serialize(bp)
