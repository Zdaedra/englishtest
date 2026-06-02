"""Spoken-recall training with feedback.

Flow (client-driven): the app speaks an anchor (Test B) or asks for the whole
retelling (Test A); the learner records a short clip; the client POSTs the clip
here. We transcribe (STT), score it (local gate -> gpt-4.1-nano), persist the
attempt, update the per-phrase rolling average, and return the score + the
correct answer + what we heard. No raw audio is stored.
"""
import random
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlmodel import Session, select

from .. import models, scoring, stt
from ..db import get_session

router = APIRouter(prefix="/api/training", tags=["training"])

# EWMA smoothing for the per-phrase rolling score (higher = forgets faster).
_EWMA_ALPHA = 0.3
# Virtual avg for never-attempted phrases: above the mean so new phrases get
# introduced, but not so high they dominate the weighted draw.
_NOVICE_AVG = 4.0
# Cost guardrail: global cap on scored attempts per day (placeholder for the
# future per-user limit). Over this -> client falls back to self-grade.
_DAILY_CAP = 400
# Max audio we accept per attempt (defensive; ~30s of opus/aac is well under this).
_MAX_AUDIO_BYTES = 8 * 1024 * 1024


def _today_start() -> datetime:
    now = datetime.now(timezone.utc)
    return now.replace(hour=0, minute=0, second=0, microsecond=0)


def _check_rate(session: Session) -> None:
    start = _today_start()
    n = len(session.exec(
        select(models.PhraseAttempt).where(models.PhraseAttempt.created_at >= start)
    ).all())
    n += len(session.exec(
        select(models.SequenceAttempt).where(models.SequenceAttempt.created_at >= start)
    ).all())
    if n >= _DAILY_CAP:
        raise HTTPException(429, "Daily scoring limit reached — continue without feedback (self-grade).")


def _apply_rollup(p: models.Phrase, score: int) -> None:
    p.avg_score = float(score) if p.avg_score is None else _EWMA_ALPHA * score + (1 - _EWMA_ALPHA) * p.avg_score
    p.attempts = (p.attempts or 0) + 1
    p.last_score = score
    p.last_seen_at = datetime.now(timezone.utc)


async def _read_audio(audio: UploadFile) -> bytes:
    raw = await audio.read()
    if len(raw) > _MAX_AUDIO_BYTES:
        raise HTTPException(413, "Audio clip too large.")
    return raw


@router.post("/score-phrase")
async def score_phrase(audio: UploadFile = File(...), phrase_id: int = Form(...),
                       latency_ms: int | None = Form(None),
                       session: Session = Depends(get_session)):
    """Test B: score one spoken phrase against its anchor's correct phrase."""
    p = session.get(models.Phrase, phrase_id)
    if not p:
        raise HTTPException(404, "Phrase not found")
    _check_rate(session)
    raw = await _read_audio(audio)
    transcript = stt.transcribe(raw, filename=audio.filename or "clip.webm", language="en")
    result = scoring.score_phrase(p.anchor, p.phrase_en, transcript)
    score = int(result["score"])

    _apply_rollup(p, score)
    session.add(p)
    session.add(models.PhraseAttempt(phrase_id=phrase_id, score=score,
                                     transcript=transcript, via=result["via"],
                                     latency_ms=latency_ms))
    session.commit()
    return {"phrase_id": phrase_id, "anchor": p.anchor, "transcript": transcript,
            "score": score, "correct_phrase": p.phrase_en, "via": result["via"],
            "avg_score": p.avg_score, "attempts": p.attempts}


@router.post("/score-anchor")
async def score_anchor(audio: UploadFile = File(...), phrase_id: int = Form(...),
                       latency_ms: int | None = Form(None),
                       session: Session = Depends(get_session)):
    """Test C (Lesson 3 stage 3): the app speaks the English phrase, the learner
    names its single anchor keyword. We persist the attempt (for the daily cap and
    history) but deliberately do NOT roll it into the per-phrase EWMA — naming the
    keyword is a weaker signal than reproducing the whole phrase, so it must not
    inflate the phrase mastery the drills/rotation depend on."""
    p = session.get(models.Phrase, phrase_id)
    if not p:
        raise HTTPException(404, "Phrase not found")
    _check_rate(session)
    raw = await _read_audio(audio)
    transcript = stt.transcribe(raw, filename=audio.filename or "clip.webm", language="en")
    result = scoring.score_anchor(p.anchor, transcript)
    score = int(result["score"])

    session.add(models.PhraseAttempt(phrase_id=phrase_id, score=score,
                                     transcript=transcript, via=result["via"],
                                     latency_ms=latency_ms))
    session.commit()
    return {"phrase_id": phrase_id, "anchor": p.anchor, "transcript": transcript,
            "score": score, "correct_anchor": p.anchor, "via": result["via"]}


@router.post("/score-sequence")
async def score_sequence(audio: UploadFile = File(...), batch_id: int = Form(...),
                         latency_ms: int | None = Form(None),
                         session: Session = Depends(get_session)):
    """Test A (the exam): score a spoken retelling of the whole mnemonic sequence."""
    b = session.get(models.Batch, batch_id)
    if not b or b.deleted_at:
        raise HTTPException(404, "Batch not found")
    mnemo = session.exec(
        select(models.MnemoStory).where(models.MnemoStory.batch_id == batch_id)
    ).first()
    if not mnemo or not mnemo.story_ru.strip():
        raise HTTPException(404, "No mnemonic story for this batch")
    _check_rate(session)

    story = mnemo.story_ru
    spans = sorted((s for s in mnemo.spans if "start" in s and "end" in s),
                   key=lambda s: s["start"])
    anchors_in_order = [story[s["start"]:s["end"]].strip().lower() for s in spans]

    raw = await _read_audio(audio)
    transcript = stt.transcribe(raw, filename=audio.filename or "clip.webm")
    result = scoring.score_sequence(anchors_in_order, story, transcript)
    score = int(result["score"])

    session.add(models.SequenceAttempt(
        batch_id=batch_id, score=score, transcript=transcript,
        missed_anchors=result["missed_anchors"], order_ok=result["order_ok"],
        via=result["via"], latency_ms=latency_ms))
    session.commit()
    return {"batch_id": batch_id, "transcript": transcript, "score": score,
            "missed_anchors": result["missed_anchors"], "order_ok": result["order_ok"],
            "passed": score >= 7, "via": result["via"]}


@router.get("/mastery")
def mastery(session: Session = Depends(get_session)):
    """Per-batch mastery rollup for the path's adaptive review ('Закрепление').

    Aggregates the per-phrase EWMA the drills already maintain: a batch's
    avg_score is the mean over its *attempted* phrases (unattempted ones carry no
    signal), attempts is the sum, last_seen_at is the most recent touch. The
    client derives 'due for review' from this — a closed batch whose recall has
    drifted (low avg) or gone stale (not seen in a while). Read-only; no storage
    of its own, so 'a miss re-queues but never re-locks' falls out for free: a
    weak drill lowers avg_score (keeps it due) while the closed flag lives in the
    client and is never cleared here.
    """
    batches = session.exec(
        select(models.Batch).where(models.Batch.deleted_at == None)  # noqa: E711
    ).all()
    out = []
    for b in batches:
        phrases = session.exec(
            select(models.Phrase).where(models.Phrase.batch_id == b.id)
        ).all()
        scored = [p.avg_score for p in phrases if p.avg_score is not None]
        seen = [p.last_seen_at for p in phrases if p.last_seen_at is not None]
        out.append({
            "batch_id": b.id,
            "avg_score": (sum(scored) / len(scored)) if scored else None,
            "attempts": sum(p.attempts or 0 for p in phrases),
            "last_seen_at": max(seen).isoformat() if seen else None,
        })
    return out


@router.get("/rotation/{batch_id}")
def rotation(batch_id: int, session: Session = Depends(get_session)):
    """Adaptive drill order for 'Вразнобой' feedback mode: weighted-random
    permutation favouring poorly-recalled phrases (weight = 11 - avg_score)."""
    b = session.get(models.Batch, batch_id)
    if not b or b.deleted_at:
        raise HTTPException(404, "Batch not found")
    phrases = session.exec(
        select(models.Phrase).where(models.Phrase.batch_id == batch_id)
        .order_by(models.Phrase.order_index)
    ).all()
    if not phrases:
        raise HTTPException(404, "No phrases in this batch")

    # Efraimidis-Spirakis weighted sampling without replacement: key = U^(1/w),
    # sort descending. Harder phrases (low avg_score -> high weight) trend earlier.
    def weight(p: models.Phrase) -> float:
        avg = p.avg_score if p.avg_score is not None else _NOVICE_AVG
        return max(1.0, 11.0 - avg)

    keyed = sorted(
        phrases, key=lambda p: random.random() ** (1.0 / weight(p)), reverse=True
    )
    return [{"phrase_id": p.id, "anchor": p.anchor, "order_index": p.order_index,
             "avg_score": p.avg_score, "attempts": p.attempts,
             "last_score": p.last_score} for p in keyed]
