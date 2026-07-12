import random
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from .. import access, audio, models
from ..auth import current_user_id, is_admin
from ..config import get_settings
from ..db import get_session
from ..entitlements import user_entitlements
from ..schemas import SessionRequest, SessionResponse

router = APIRouter(prefix="/api/sessions", tags=["sessions"])


def _order_phrases(phrases: list[models.Phrase], order_mode: str, seed: int) -> list[models.Phrase]:
    rng = random.Random(seed)
    if order_mode == "full_random":
        out = list(phrases)
        rng.shuffle(out)
        return out
    if order_mode == "zone_random":
        by_zone: dict = {}
        for p in phrases:
            by_zone.setdefault(p.zone_id, []).append(p)
        out = []
        for zid in sorted(by_zone, key=lambda z: (z is None, z)):
            grp = by_zone[zid]
            rng.shuffle(grp)
            out += grp
        return out
    return list(phrases)  # ordered


def _build_segments(mode: str, phrases: list[models.Phrase], st: models.Setting) -> list[dict]:
    segs: list[dict] = []
    for p in phrases:
        if mode == "recall":
            if p.gloss_ru:
                segs.append({"kind": "audio", "text": p.gloss_ru, "lang": "ru",
                             "phrase_order": p.order_index, "role": "stimulus"})
            segs.append({"kind": "silence", "dur": st.recall_gap_stimulus,
                         "phrase_order": p.order_index, "role": "think"})
            segs.append({"kind": "audio", "text": p.phrase_en, "lang": "en",
                         "phrase_order": p.order_index, "role": "answer"})
            segs.append({"kind": "silence", "dur": st.recall_gap_after,
                         "phrase_order": p.order_index, "role": "repeat_gap"})
            segs.append({"kind": "audio", "text": p.phrase_en, "lang": "en",
                         "phrase_order": p.order_index, "role": "shadow"})
            segs.append({"kind": "silence", "dur": st.listening_gap,
                         "phrase_order": p.order_index, "role": "between"})
        else:  # listening
            segs.append({"kind": "audio", "text": p.phrase_en, "lang": "en",
                         "phrase_order": p.order_index, "role": "phrase"})
            for _ in range(max(0, st.listening_repeats)):
                segs.append({"kind": "silence", "dur": st.listening_gap,
                             "phrase_order": p.order_index, "role": "gap"})
                segs.append({"kind": "audio", "text": p.phrase_en, "lang": "en",
                             "phrase_order": p.order_index, "role": "repeat"})
            segs.append({"kind": "silence", "dur": st.listening_gap,
                         "phrase_order": p.order_index, "role": "between"})
    return segs


@router.post("", response_model=SessionResponse)
def create_session(req: SessionRequest, user_id: int = Depends(current_user_id),
                   session: Session = Depends(get_session)):
    batch = session.get(models.Batch, req.batch_id)
    admin = is_admin(session, user_id)
    if (not batch or batch.deleted_at
            or not (batch.owner_id is None or batch.owner_id == user_id or admin)):
        raise HTTPException(404, "Batch not found")
    # Freemium gate: only the free batch (+ own imports) is usable without a paid plan.
    if not admin:
        u = session.get(models.User, user_id)
        if not access.batch_usable(u.plan if u else "free", batch, user_id):
            raise HTTPException(403, "locked")
    phrases = session.exec(select(models.Phrase).where(models.Phrase.batch_id == req.batch_id)
                           .order_by(models.Phrase.order_index)).all()
    if not phrases:
        raise HTTPException(400, "Batch has no phrases")

    # Free plan: cap gapless audio sessions/day (TTS cost lever; upgrade trigger).
    cap = user_entitlements(session, user_id)["gapless_per_day"]
    if cap is not None:
        day_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
        used = len(session.exec(select(models.PlaybackSession).where(
            models.PlaybackSession.user_id == user_id,
            models.PlaybackSession.created_at >= day_start)).all())
        if used >= cap:
            raise HTTPException(429, "daily_limit")

    # Read-only snapshot of the global config: detach so per-request overrides
    # (e.g. repeats) never persist back onto the shared singleton.
    st = session.get(models.Setting, 1)
    if st is not None:
        session.expunge(st)
    else:
        st = models.Setting(id=1)
    if req.repeats is not None:
        st.listening_repeats = req.repeats

    seed = random.randint(1, 10_000_000)
    ordered = _order_phrases(phrases, req.order_mode, seed)
    segments = _build_segments(req.mode, ordered, st)

    ps = models.PlaybackSession(user_id=user_id, batch_id=req.batch_id, mode=req.mode,
                                order_mode=req.order_mode, shuffle_seed=seed, plan=[])
    session.add(ps)
    session.commit()
    session.refresh(ps)

    voice = req.voice or st.tts_voice
    voice_ru = req.voice_ru or st.tts_voice_ru
    try:
        path, duration, plan = audio.render_session(
            segments, f"{ps.id}.{get_settings().tts_format}", voice=voice, voice_ru=voice_ru)
    except Exception as e:
        raise HTTPException(502, f"Audio render failed: {e}")

    ps.rendered_audio_path = path.name
    ps.duration = duration
    ps.plan = plan
    session.add(ps)
    session.commit()

    return SessionResponse(id=ps.id, batch_id=req.batch_id, mode=req.mode,
                           order_mode=req.order_mode,
                           audio_url=f"/audio/sessions/{path.name}",
                           duration=duration, plan=plan)
