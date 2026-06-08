"""Practice drill: situational recall from mastered batches.

Questions are generated at request time from each batch's own phrases (stub
prompts keyed by zone/theme), so there is no fragile content-file↔DB mapping —
the per-batch JSON files under content/questions/ are the future store for real
authored prompts. Scoring picks the single best-matching batch phrase (cheap
string pre-rank → one real scoring call) and flags session-level repeats for the
variety mechanic.
"""
import random
from difflib import SequenceMatcher

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlmodel import Session, select

from .. import models, scoring, stt, tts
from ..auth import current_user_id
from ..db import get_session
from .training import _check_rate

router = APIRouter(prefix="/api/practice", tags=["practice"])

_MAX_AUDIO_BYTES = 8 * 1024 * 1024

# RU situational STUB frames — set the moment + tone (zone) without revealing the
# English phrase. (Mirror of the gen_practice_stubs generator.)
_FRAMES = [
    "Собеседник только что высказался — нужна твоя реакция в тоне «{z}». Ответь одной уместной фразой.",
    "Момент в разговоре ({t}). Дай реплику в регистре «{z}».",
    "Ситуация требует ответа в тоне «{z}». Скажи фразу, которая здесь уместна.",
    "Тебе нужно отреагировать — регистр «{z}». Произнеси подходящую фразу.",
    "Разговор идёт к развязке ({t}). Вступи в тоне «{z}» одной фразой.",
    "Подбери и скажи уместную реплику для этого момента (тон: «{z}»).",
]
_PER_BATCH = 12


def _zone_titles(session: Session, batch_id: int) -> dict:
    zs = session.exec(select(models.Zone).where(models.Zone.batch_id == batch_id)).all()
    return {z.id: z.title for z in zs}


def _questions_for(session: Session, batch: models.Batch) -> list[dict]:
    phrases = session.exec(
        select(models.Phrase).where(models.Phrase.batch_id == batch.id)
        .order_by(models.Phrase.order_index)
    ).all()
    if not phrases:
        return []
    all_ids = [p.id for p in phrases]
    zt = _zone_titles(session, batch.id)
    theme = (batch.theme or "")[:46]
    out = []
    for i in range(_PER_BATCH):
        p = phrases[i % len(phrases)]
        zone = zt.get(p.zone_id) or "—"
        frame = _FRAMES[i % len(_FRAMES)]
        out.append({
            "id": f"b{batch.id}q{i + 1}",
            "batch_id": batch.id,
            "batch_title": batch.title,
            "prompt_ru": frame.format(z=zone, t=theme),
            "zone": zone,
            # Any phrase of the batch is a valid answer («ответь из бетча»);
            # the variety mechanic (anti-repeat) pushes for different phrases.
            "accept_phrase_ids": all_ids,
            "hint_anchor": p.anchor,
        })
    return out


@router.get("/questions")
def questions(batch_ids: str = "", session: Session = Depends(get_session)):
    """Shuffled pool of situational prompts from the given (passed) batches.
    `batch_ids` = comma-separated; empty → all non-deleted batches."""
    ids = [int(x) for x in batch_ids.split(",") if x.strip().isdigit()]
    q = select(models.Batch).where(models.Batch.deleted_at == None)  # noqa: E711
    if ids:
        q = q.where(models.Batch.id.in_(ids))
    batches = session.exec(q).all()
    pool: list[dict] = []
    for b in batches:
        pool += _questions_for(session, b)
    random.shuffle(pool)
    return {"questions": pool}


@router.post("/prompt-audio")
def prompt_audio(text: str = Form(...), session: Session = Depends(get_session)):
    """TTS of a RU situational prompt (voice-first). Cached on disk by tts."""
    st = session.get(models.Setting, 1) or models.Setting(id=1)
    try:
        path, dur = tts.synth(text, voice=st.tts_voice_ru)
    except Exception as e:
        raise HTTPException(502, f"TTS failed: {e}")
    return {"audio_url": f"/audio/phrases/{path.name}", "duration": dur}


@router.post("/score")
async def score(audio: UploadFile = File(...),
                phrase_ids: str = Form(...),
                used_phrase_ids: str = Form(""),
                latency_ms: int | None = Form(None),
                user_id: int = Depends(current_user_id),
                session: Session = Depends(get_session)):
    """Score a spoken answer against the batch repertoire. Cheap string pre-rank
    picks the single likeliest phrase, then one real scoring call. Flags a session
    repeat if the best phrase was already scored ≥8 this session (variety mechanic)."""
    cand = [int(x) for x in phrase_ids.split(",") if x.strip().isdigit()]
    used = {int(x) for x in used_phrase_ids.split(",") if x.strip().isdigit()}
    if not cand:
        raise HTTPException(400, "No candidate phrases")
    _check_rate(session, user_id)
    raw = await audio.read()
    if len(raw) > _MAX_AUDIO_BYTES:
        raise HTTPException(413, "Audio clip too large.")
    transcript = stt.transcribe(raw, filename=audio.filename or "clip.webm", language="en")

    nu = scoring._normalize(transcript)
    best_pid, best_ratio = None, -1.0
    phrase_by_id: dict[int, models.Phrase] = {}
    for pid in cand:
        p = session.get(models.Phrase, pid)
        if not p:
            continue
        phrase_by_id[pid] = p
        ratio = SequenceMatcher(None, scoring._normalize(p.phrase_en), nu).ratio()
        if ratio > best_ratio:
            best_ratio, best_pid = ratio, pid
    if best_pid is None:
        raise HTTPException(404, "Candidate phrases not found")

    p = phrase_by_id[best_pid]
    result = scoring.score_phrase(p.anchor, p.phrase_en, transcript)
    sc = int(result["score"])
    is_repeat = sc >= 8 and best_pid in used
    session.add(models.PhraseAttempt(user_id=user_id, phrase_id=best_pid, score=sc,
                                     transcript=transcript, via="practice", latency_ms=latency_ms))
    session.commit()
    return {"score": sc, "phrase_id": best_pid, "anchor": p.anchor,
            "phrase_en": p.phrase_en, "transcript": transcript, "is_repeat": is_repeat}
