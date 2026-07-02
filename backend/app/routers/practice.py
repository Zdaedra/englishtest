"""Practice extras around the swipe-trainer: cue TTS + the Arena.

The Arena is where learned phrases return "in battle" (the Langua pattern): three
due/learned phrases from ACROSS the user's batches are woven by the LLM into one
fresh coherent scene (3 beats, each leading to its target phrase). Answers go
through the normal /api/training/answer* endpoints, so Arena work feeds the same
mastery + SRS as the deck. (The old stub /questions + /score drill was removed
2026-07-03 — content-free frames, zero frontend callers.)
"""
import random
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Form, HTTPException
from sqlmodel import Session, select

from .. import models, scoring, tts, usage
from ..auth import current_user_id
from ..db import get_session
from ..entitlements import user_entitlements

router = APIRouter(prefix="/api/practice", tags=["practice"])

_SCENE_BEATS = 3


@router.post("/prompt-audio")
def prompt_audio(text: str = Form(...), lang: str = Form("ru"),
                 session: Session = Depends(get_session)):
    """TTS of a short prompt/cue (voice-first). `lang` picks the voice: en → the
    English voice, anything else → the Russian voice (so an English conversation
    cue isn't read by a RU-tuned voice). Cached on disk by tts."""
    st = session.get(models.Setting, 1) or models.Setting(id=1)
    voice = st.tts_voice if lang.lower().startswith("en") else st.tts_voice_ru
    try:
        path, dur = tts.synth(text, voice=voice)
    except Exception as e:
        raise HTTPException(502, f"TTS failed: {e}")
    return {"audio_url": f"/audio/phrases/{path.name}", "duration": dur}


def _aware(dt):
    if dt is None:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


@router.post("/scenario")
def scenario(user_id: int = Depends(current_user_id),
             session: Session = Depends(get_session)):
    """Arena scene: 3 learned/due phrases → one fresh LLM-woven scenario.
    AI-plan feature (LLM spend); the due-most phrases go first so the Arena IS
    spaced repetition, just staged as a story instead of cards."""
    ents = user_entitlements(session, user_id)
    if not ents.get("ai_coach"):
        raise HTTPException(403, "locked")
    budget = ents.get("monthly_ai_cost_cap_usd")
    if budget is not None and usage.month_cost_usd(session, user_id) >= budget:
        raise HTTPException(429, "Monthly AI limit reached.")

    now = datetime.now(timezone.utc)
    stats = session.exec(select(models.UserPhraseStat).where(
        models.UserPhraseStat.user_id == user_id)).all()
    learned = [st for st in stats
               if st.srs_status in ("familiar", "automatic")
               or (_aware(st.next_review_at) or now) < now]
    if len(learned) < _SCENE_BEATS:
        raise HTTPException(409, "not_enough")

    # Due-first (overdue = most valuable to resurface), random within ties, then
    # keep one phrase per batch where possible so the scene crosses contexts.
    far_future = now.replace(year=now.year + 10)
    learned.sort(key=lambda st: (_aware(st.next_review_at) or far_future,
                                 random.random()))
    picked: list[models.UserPhraseStat] = []
    seen_batches: set[int] = set()
    for st in learned:
        if st.batch_id in seen_batches:
            continue
        picked.append(st)
        seen_batches.add(st.batch_id)
        if len(picked) == _SCENE_BEATS:
            break
    for st in learned:                       # not enough distinct batches → fill up
        if len(picked) == _SCENE_BEATS:
            break
        if st not in picked:
            picked.append(st)

    phrases = {p.id: p for p in session.exec(select(models.Phrase).where(
        models.Phrase.id.in_([st.phrase_id for st in picked]))).all()}
    items, order = [], []
    for st in picked:
        p = phrases.get(st.phrase_id)
        if not p:
            continue
        order.append(p)
        items.append({"anchor": p.anchor, "phrase_en": p.phrase_en,
                      "gloss_ru": p.gloss_ru or ""})
    if len(order) < _SCENE_BEATS:
        raise HTTPException(409, "not_enough")

    woven = scoring.weave_scenario(items)
    if woven["via"] == "llm":
        usage.accrue(session, user_id, "scenario")
        session.commit()
        beats_txt = woven["beats"]
        title = woven["title_ru"]
    else:
        # LLM unavailable → each phrase's own authored situation still works as a
        # (non-woven) 3-beat round; the Arena degrades, it doesn't break.
        beats_txt = [{"situation_ru": p.situation_ru or "", "task_ru": p.task_ru or ""}
                     for p in order]
        title = ""

    return {
        "title_ru": title,
        "via": woven["via"],
        "beats": [{
            "phrase_id": p.id, "anchor": p.anchor, "phrase_en": p.phrase_en,
            "gloss_ru": p.gloss_ru or "",
            "situation_ru": beats_txt[i]["situation_ru"],
            "task_ru": beats_txt[i]["task_ru"],
        } for i, p in enumerate(order)],
    }
