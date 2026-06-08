"""Spoken-recall training with feedback — all per-user.

Per-user learning state lives on UserPhraseStat (one row per user+phrase); the
Phrase row is shared content. Every endpoint is scoped to the authenticated user
(current_user_id, set by the auth-gate middleware). We transcribe (STT), score
(local gate -> gpt-4.1-nano), persist the attempt, roll up the user's per-phrase
average, and return the score + correct answer + transcript. No raw audio stored.
"""
import random
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel
from sqlmodel import Session, select

from .. import entitlements, models, scoring, stt
from ..auth import current_user_id
from ..db import get_session

router = APIRouter(prefix="/api/training", tags=["training"])

_EWMA_ALPHA = 0.3
_NOVICE_AVG = 4.0
_MAX_AUDIO_BYTES = 8 * 1024 * 1024


def _today_start() -> datetime:
    now = datetime.now(timezone.utc)
    return now.replace(hour=0, minute=0, second=0, microsecond=0)


def _check_rate(session: Session, user_id: int) -> None:
    """Per-plan daily cap on scored attempts (the cost lever for free/core/ai)."""
    cap = entitlements.user_entitlements(session, user_id)["scored_per_day"]
    start = _today_start()
    n = len(session.exec(
        select(models.PhraseAttempt).where(
            models.PhraseAttempt.user_id == user_id,
            models.PhraseAttempt.created_at >= start)).all())
    n += len(session.exec(
        select(models.SequenceAttempt).where(
            models.SequenceAttempt.user_id == user_id,
            models.SequenceAttempt.created_at >= start)).all())
    if n >= cap:
        raise HTTPException(429, "Daily scoring limit reached — continue without feedback (self-grade).")


def _stat(session: Session, user_id: int, phrase: models.Phrase) -> models.UserPhraseStat:
    """Get-or-create the user's per-phrase stat row."""
    st = session.exec(select(models.UserPhraseStat).where(
        models.UserPhraseStat.user_id == user_id,
        models.UserPhraseStat.phrase_id == phrase.id)).first()
    if not st:
        st = models.UserPhraseStat(user_id=user_id, phrase_id=phrase.id, batch_id=phrase.batch_id)
        session.add(st)
    return st


def _stats_for(session: Session, user_id: int, phrase_ids: list[int]) -> dict[int, models.UserPhraseStat]:
    if not phrase_ids:
        return {}
    rows = session.exec(select(models.UserPhraseStat).where(
        models.UserPhraseStat.user_id == user_id,
        models.UserPhraseStat.phrase_id.in_(phrase_ids))).all()
    return {r.phrase_id: r for r in rows}


def _apply_rollup(st: models.UserPhraseStat, score: int) -> None:
    st.avg_score = float(score) if st.avg_score is None else _EWMA_ALPHA * score + (1 - _EWMA_ALPHA) * st.avg_score
    st.attempts = (st.attempts or 0) + 1
    st.last_score = score
    st.last_seen_at = datetime.now(timezone.utc)


async def _read_audio(audio: UploadFile) -> bytes:
    raw = await audio.read()
    if len(raw) > _MAX_AUDIO_BYTES:
        raise HTTPException(413, "Audio clip too large.")
    return raw


@router.post("/score-phrase")
async def score_phrase(audio: UploadFile = File(...), phrase_id: int = Form(...),
                       latency_ms: int | None = Form(None),
                       user_id: int = Depends(current_user_id),
                       session: Session = Depends(get_session)):
    """Test B: score one spoken phrase against its anchor's correct phrase."""
    p = session.get(models.Phrase, phrase_id)
    if not p:
        raise HTTPException(404, "Phrase not found")
    _check_rate(session, user_id)
    raw = await _read_audio(audio)
    transcript = stt.transcribe(raw, filename=audio.filename or "clip.webm", language="en")
    result = scoring.score_phrase(p.anchor, p.phrase_en, transcript)
    score = int(result["score"])

    st = _stat(session, user_id, p)
    _apply_rollup(st, score)
    session.add(st)
    session.add(models.PhraseAttempt(user_id=user_id, phrase_id=phrase_id, score=score,
                                     transcript=transcript, via=result["via"],
                                     latency_ms=latency_ms))
    session.commit()
    return {"phrase_id": phrase_id, "anchor": p.anchor, "transcript": transcript,
            "score": score, "correct_phrase": p.phrase_en, "via": result["via"],
            "avg_score": st.avg_score, "attempts": st.attempts}


@router.post("/score-anchor")
async def score_anchor(audio: UploadFile = File(...), phrase_id: int = Form(...),
                       latency_ms: int | None = Form(None),
                       user_id: int = Depends(current_user_id),
                       session: Session = Depends(get_session)):
    """Test C: name the single anchor keyword. Persisted (for the cap + history)
    but deliberately NOT rolled into avg_score — a weaker signal than the phrase."""
    p = session.get(models.Phrase, phrase_id)
    if not p:
        raise HTTPException(404, "Phrase not found")
    _check_rate(session, user_id)
    raw = await _read_audio(audio)
    transcript = stt.transcribe(raw, filename=audio.filename or "clip.webm", language="en")
    result = scoring.score_anchor(p.anchor, transcript)
    score = int(result["score"])

    session.add(models.PhraseAttempt(user_id=user_id, phrase_id=phrase_id, score=score,
                                     transcript=transcript, via=result["via"],
                                     latency_ms=latency_ms))
    session.commit()
    return {"phrase_id": phrase_id, "anchor": p.anchor, "transcript": transcript,
            "score": score, "correct_anchor": p.anchor, "via": result["via"]}


@router.post("/score-sequence")
async def score_sequence(audio: UploadFile = File(...), batch_id: int = Form(...),
                         latency_ms: int | None = Form(None),
                         user_id: int = Depends(current_user_id),
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
    _check_rate(session, user_id)

    story = mnemo.story_ru
    spans = sorted((s for s in mnemo.spans if "start" in s and "end" in s),
                   key=lambda s: s["start"])
    anchors_in_order = [story[s["start"]:s["end"]].strip().lower() for s in spans]

    raw = await _read_audio(audio)
    transcript = stt.transcribe(raw, filename=audio.filename or "clip.webm")
    result = scoring.score_sequence(anchors_in_order, story, transcript)
    score = int(result["score"])

    session.add(models.SequenceAttempt(
        user_id=user_id, batch_id=batch_id, score=score, transcript=transcript,
        missed_anchors=result["missed_anchors"], order_ok=result["order_ok"],
        via=result["via"], latency_ms=latency_ms))
    session.commit()
    return {"batch_id": batch_id, "transcript": transcript, "score": score,
            "missed_anchors": result["missed_anchors"], "order_ok": result["order_ok"],
            "passed": score >= 7, "via": result["via"]}


@router.get("/mastery")
def mastery(user_id: int = Depends(current_user_id), session: Session = Depends(get_session)):
    """Per-batch mastery rollup for THIS user, from their UserPhraseStat rows."""
    batches = session.exec(
        select(models.Batch).where(models.Batch.deleted_at == None)  # noqa: E711
        .where((models.Batch.owner_id == None) | (models.Batch.owner_id == user_id))  # noqa: E711
    ).all()
    stats = session.exec(select(models.UserPhraseStat).where(
        models.UserPhraseStat.user_id == user_id)).all()
    by_batch: dict[int, list] = {}
    for st in stats:
        by_batch.setdefault(st.batch_id, []).append(st)
    out = []
    for b in batches:
        rows = by_batch.get(b.id, [])
        scored = [s.avg_score for s in rows if s.avg_score is not None]
        seen = [s.last_seen_at for s in rows if s.last_seen_at is not None]
        out.append({
            "batch_id": b.id,
            "avg_score": (sum(scored) / len(scored)) if scored else None,
            "attempts": sum(s.attempts or 0 for s in rows),
            "last_seen_at": max(seen).isoformat() if seen else None,
        })
    return out


@router.get("/rotation/{batch_id}")
def rotation(batch_id: int, user_id: int = Depends(current_user_id),
             session: Session = Depends(get_session)):
    """Adaptive drill order: weighted-random permutation favouring poorly-recalled
    phrases (weight = 11 - this user's avg_score)."""
    b = session.get(models.Batch, batch_id)
    if not b or b.deleted_at:
        raise HTTPException(404, "Batch not found")
    phrases = session.exec(
        select(models.Phrase).where(models.Phrase.batch_id == batch_id)
        .order_by(models.Phrase.order_index)
    ).all()
    if not phrases:
        raise HTTPException(404, "No phrases in this batch")
    stats = _stats_for(session, user_id, [p.id for p in phrases])

    def weight(p: models.Phrase) -> float:
        st = stats.get(p.id)
        avg = st.avg_score if (st and st.avg_score is not None) else _NOVICE_AVG
        return max(1.0, 11.0 - avg)

    keyed = sorted(phrases, key=lambda p: random.random() ** (1.0 / weight(p)), reverse=True)
    out = []
    for p in keyed:
        st = stats.get(p.id)
        out.append({"phrase_id": p.id, "anchor": p.anchor, "order_index": p.order_index,
                    "avg_score": st.avg_score if st else None,
                    "attempts": st.attempts if st else 0,
                    "last_score": st.last_score if st else None})
    return out


# --- Swipe-deck Training (Tinder-style cards) -------------------------------
_SELF_ALPHA = 0.3
_COOLDOWN = timedelta(seconds=90)


def _parse_ids(csv: str) -> list[int]:
    return [int(x) for x in (csv or "").split(",") if x.strip().lstrip("-").isdigit()]


def _aware(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


@router.get("/deck")
def deck(batch_ids: str = "", maintenance_ids: str = "", limit: int = 30,
         exclude: str = "", user_id: int = Depends(current_user_id),
         session: Session = Depends(get_session)):
    """Cross-batch adaptive deck for the swipe-trainer, scoped to this user's stats.
    Weights toward weak spots (low phrase/batch mastery, recent fails, never-seen)
    and away from completed-strong (maintenance), then weighted-random samples
    without replacement. Excludes phrases seen in the last 90s or in `exclude`."""
    active = _parse_ids(batch_ids)
    maint = set(_parse_ids(maintenance_ids))
    excl = set(_parse_ids(exclude))
    all_ids = active + [m for m in maint if m not in active]
    if not all_ids:
        return []
    # Restrict to batches visible to this user (shared catalog or own imports) so
    # a guessed id can't surface another client's private import.
    visible = set(session.exec(select(models.Batch.id).where(
        models.Batch.id.in_(all_ids),
        (models.Batch.owner_id == None) | (models.Batch.owner_id == user_id),  # noqa: E711
    )).all())
    all_ids = [i for i in all_ids if i in visible]
    if not all_ids:
        return []
    now = datetime.now(timezone.utc)
    cutoff = now - _COOLDOWN

    phrases = session.exec(
        select(models.Phrase).where(models.Phrase.batch_id.in_(all_ids))
    ).all()
    if not phrases:
        return []
    stats = _stats_for(session, user_id, [p.id for p in phrases])

    by_batch: dict[int, list] = {}
    for p in phrases:
        by_batch.setdefault(p.batch_id, []).append(p)
    batch_avg: dict[int, float] = {}
    for bid, ps in by_batch.items():
        scored = [stats[p.id].avg_score for p in ps if stats.get(p.id) and stats[p.id].avg_score is not None]
        batch_avg[bid] = (sum(scored) / len(scored)) if scored else _NOVICE_AVG

    def _conf(p: models.Phrase) -> float:
        st = stats.get(p.id)
        attempts = (st.attempts if st else 0) or 0
        avg = (st.avg_score if st else None) or 0.0
        return (avg / 10.0) * (1 - 1.0 / (1 + attempts))

    def weight(p: models.Phrase) -> float:
        st = stats.get(p.id)
        phrase_weak = 1 - _conf(p)
        batch_weak = 1 - batch_avg.get(p.batch_id, _NOVICE_AVG) / 10.0
        lf = _aware(st.last_failed_at) if st else None
        recent_fail = lf is not None and timedelta(hours=24) <= (now - lf) <= timedelta(hours=72)
        fail_boost = 1.0 if recent_fail else 0.3
        new_boost = 0.6 if (not st or (st.attempts or 0) == 0) else 0.0
        maint_factor = 0.12 if (p.batch_id in maint and p.batch_id not in active) else 1.0
        w = (0.45 * phrase_weak + 0.30 * batch_weak
             + 0.15 * fail_boost + 0.10 * new_boost) * maint_factor
        return max(0.01, w)

    def _seen_recent(p: models.Phrase) -> bool:
        st = stats.get(p.id)
        ls = _aware(st.last_seen_at) if st else None
        return ls is not None and ls > cutoff

    pool = [p for p in phrases if p.id not in excl and not _seen_recent(p)]
    if not pool:
        pool = phrases
    keyed = sorted(pool, key=lambda p: random.random() ** (1.0 / weight(p)),
                   reverse=True)[:max(1, limit)]

    batches = {b.id: b for b in session.exec(
        select(models.Batch).where(models.Batch.id.in_(all_ids))).all()}
    cp_by_phrase: dict[int, list] = {}
    if keyed:
        for cp in session.exec(select(models.CheckPhrase)
                .where(models.CheckPhrase.phrase_id.in_([p.id for p in keyed]))).all():
            cp_by_phrase.setdefault(cp.phrase_id, []).append(cp)
    out = []
    for p in keyed:
        b = batches.get(p.batch_id)
        st = stats.get(p.id)
        cps = cp_by_phrase.get(p.id, [])
        approved = [c for c in cps if c.status == "approved"] or cps
        chosen = random.choice(approved) if approved else None
        out.append({
            "phrase_id": p.id, "batch_id": p.batch_id,
            "batch_title": b.title if b else "", "section": b.section if b else "",
            "slug": b.slug if b else "", "cover_url": b.cover_path if b else None,
            "anchor": p.anchor, "phrase_en": p.phrase_en,
            "stimulus": chosen.text if chosen else "",
            "stimulus_id": chosen.id if chosen else None,
            "stimulus_lang": chosen.lang if chosen else "en",
            "gloss_ru": p.gloss_ru,
            "conf": round(_conf(p), 3), "priority": round(weight(p), 3),
            "attempts": (st.attempts if st else 0) or 0,
            "avg_score": st.avg_score if st else None,
        })
    return out


class SwipeIn(BaseModel):
    session_id: str
    phrase_id: int
    swipe_direction: str  # left (don't know) | right (know)
    response_time_ms: int | None = None


@router.post("/swipe")
def swipe(body: SwipeIn, user_id: int = Depends(current_user_id),
          session: Session = Depends(get_session)):
    """Swipe Practice: record a self-assessed swipe. Updates the SEPARATE self_ewma
    (never avg_score) so subjective swipes can't corrupt the spoken-recall mastery."""
    p = session.get(models.Phrase, body.phrase_id)
    if not p:
        raise HTTPException(404, "Phrase not found")
    st = _stat(session, user_id, p)
    knew = body.swipe_direction == "right"
    val = 1.0 if knew else 0.0
    st.self_ewma = val if st.self_ewma is None else _SELF_ALPHA * val + (1 - _SELF_ALPHA) * st.self_ewma
    now = datetime.now(timezone.utc)
    st.last_seen_at = now
    if knew:
        st.last_success_at = now
    else:
        st.last_failed_at = now
    session.add(st)
    n = len(session.exec(select(models.TrainingEvent).where(
        models.TrainingEvent.user_id == user_id,
        models.TrainingEvent.phrase_id == body.phrase_id)).all())
    session.add(models.TrainingEvent(
        user_id=user_id, session_id=body.session_id, batch_id=p.batch_id, phrase_id=p.id,
        training_mode="swipe", swipe_direction=body.swipe_direction,
        manual_success=knew, response_time_ms=body.response_time_ms,
        attempt_number=n + 1))
    session.commit()
    return {"ok": True, "self_ewma": st.self_ewma}


def _record_answer(session: Session, user_id: int, p: models.Phrase, transcript: str,
                   score: int, feedback: str, via: str, latency_ms: int | None) -> models.TrainingEvent:
    st = _stat(session, user_id, p)
    _apply_rollup(st, score)
    now = datetime.now(timezone.utc)
    if score >= 8:
        st.last_success_at = now
    else:
        st.last_failed_at = now
    session.add(st)
    session.add(models.PhraseAttempt(user_id=user_id, phrase_id=p.id, score=score,
                                     transcript=transcript, via=via, latency_ms=latency_ms))
    n = len(session.exec(select(models.TrainingEvent).where(
        models.TrainingEvent.user_id == user_id,
        models.TrainingEvent.phrase_id == p.id)).all())
    ev = models.TrainingEvent(
        user_id=user_id, session_id="", batch_id=p.batch_id, phrase_id=p.id,
        training_mode="answer", transcript=transcript, ai_score=score,
        ai_feedback=feedback, response_time_ms=latency_ms, attempt_number=n + 1)
    session.add(ev)
    return ev


@router.post("/answer")
async def answer(audio: UploadFile = File(...), phrase_id: int = Form(...),
                 session_id: str = Form(...), latency_ms: int | None = Form(None),
                 user_id: int = Depends(current_user_id),
                 session: Session = Depends(get_session)):
    """Answer Check: spoken production. Reuses score-phrase pipeline (STT -> gate/LLM
    -> EWMA rollup -> PhraseAttempt) + a TrainingEvent. auto_success when score>=8."""
    p = session.get(models.Phrase, phrase_id)
    if not p:
        raise HTTPException(404, "Phrase not found")
    if not entitlements.user_entitlements(session, user_id)["voice_answer"]:
        raise HTTPException(403, "ai_required")  # the mic (spoken answer) is Executive AI
    _check_rate(session, user_id)
    raw = await _read_audio(audio)
    transcript = stt.transcribe(raw, filename=audio.filename or "clip.webm", language="en")
    result = scoring.score_phrase(p.anchor, p.phrase_en, transcript)
    score = int(result["score"])
    feedback = result.get("feedback", "")
    ev = _record_answer(session, user_id, p, transcript, score, feedback, result["via"], latency_ms)
    ev.session_id = session_id
    session.add(ev)
    st = _stat(session, user_id, p)
    session.commit()
    session.refresh(ev)
    return {"event_id": ev.id, "phrase_id": phrase_id, "anchor": p.anchor,
            "transcript": transcript, "score": score, "correct_phrase": p.phrase_en,
            "feedback": feedback, "via": result["via"], "avg_score": st.avg_score,
            "attempts": st.attempts, "auto_success": score >= 8}


class AnswerTextIn(BaseModel):
    session_id: str
    phrase_id: int
    transcript: str
    response_time_ms: int | None = None


@router.post("/answer-text")
def answer_text(body: AnswerTextIn, user_id: int = Depends(current_user_id),
                session: Session = Depends(get_session)):
    """Answer Check via client-side speech (free, e.g. iOS Web Speech): score the
    text with the same gate->cheap-LLM path, no server STT cost."""
    p = session.get(models.Phrase, body.phrase_id)
    if not p:
        raise HTTPException(404, "Phrase not found")
    if not entitlements.user_entitlements(session, user_id)["voice_answer"]:
        raise HTTPException(403, "ai_required")  # the mic (spoken answer) is Executive AI
    _check_rate(session, user_id)
    transcript = (body.transcript or "").strip()
    result = scoring.score_phrase(p.anchor, p.phrase_en, transcript)
    score = int(result["score"])
    feedback = result.get("feedback", "")
    ev = _record_answer(session, user_id, p, transcript, score, feedback, result["via"], body.response_time_ms)
    ev.session_id = body.session_id
    session.add(ev)
    st = _stat(session, user_id, p)
    session.commit()
    session.refresh(ev)
    return {"event_id": ev.id, "phrase_id": body.phrase_id, "anchor": p.anchor,
            "transcript": transcript, "score": score, "correct_phrase": p.phrase_en,
            "feedback": feedback, "via": result["via"], "avg_score": st.avg_score,
            "attempts": st.attempts, "auto_success": score >= 8}


class ConfirmIn(BaseModel):
    event_id: int
    manual_success: bool


@router.post("/answer/confirm")
def answer_confirm(body: ConfirmIn, user_id: int = Depends(current_user_id),
                   session: Session = Depends(get_session)):
    """Apply the learner's Success / Not Success override to an answer event."""
    ev = session.get(models.TrainingEvent, body.event_id)
    if not ev or ev.user_id != user_id:
        raise HTTPException(404, "Event not found")
    ev.manual_success = body.manual_success
    session.add(ev)
    p = session.get(models.Phrase, ev.phrase_id)
    if p:
        st = _stat(session, user_id, p)
        now = datetime.now(timezone.utc)
        if body.manual_success:
            st.last_success_at = now
        else:
            st.last_failed_at = now
        session.add(st)
    session.commit()
    return {"ok": True}


class CoachIn(BaseModel):
    phrase_id: int
    transcript: str = ""
    score: int = 0


@router.post("/coach")
def coach(body: CoachIn, user_id: int = Depends(current_user_id),
          session: Session = Depends(get_session)):
    """AI Coach (Executive AI plan only). A coaching breakdown of the spoken answer:
    {feedback, better, tone}. Free accounts get 403 'ai_plan_required' (the client
    shows the upgrade teaser)."""
    u = session.get(models.User, user_id)
    if not u:
        raise HTTPException(401, "Не авторизован.")
    if u.plan != "ai":
        raise HTTPException(403, "ai_plan_required")
    p = session.get(models.Phrase, body.phrase_id)
    if not p:
        raise HTTPException(404, "Phrase not found")
    _check_rate(session, user_id)
    cp = session.exec(select(models.CheckPhrase).where(
        models.CheckPhrase.phrase_id == p.id)).first()
    stimulus = cp.text if cp else (p.gloss_ru or "")
    res = scoring.coach_feedback(stimulus, p.phrase_en, body.transcript, body.score)
    return {"feedback": res["feedback"], "better": res["better"], "tone": res["tone"],
            "correct_phrase": p.phrase_en, "via": res["via"]}


@router.get("/session/{session_id}/summary")
def session_summary(session_id: str, user_id: int = Depends(current_user_id),
                    session: Session = Depends(get_session)):
    """Aggregate a finished training session from its events (this user only)."""
    evs = session.exec(select(models.TrainingEvent).where(
        models.TrainingEvent.user_id == user_id,
        models.TrainingEvent.session_id == session_id)).all()
    if not evs:
        return {"session_id": session_id, "cards_total": 0, "cards_known": 0,
                "cards_unknown": 0, "avg_score": None, "weakest": None,
                "strongest": None, "by_batch": []}

    def _known(e: models.TrainingEvent) -> bool:
        if e.training_mode == "swipe":
            return e.swipe_direction == "right"
        if e.manual_success is not None:
            return e.manual_success
        return (e.ai_score or 0) >= 8

    known = sum(1 for e in evs if _known(e))
    scores = [e.ai_score for e in evs if e.ai_score is not None]
    by_batch: dict[int, dict] = {}
    for e in evs:
        d = by_batch.setdefault(e.batch_id, {"batch_id": e.batch_id, "total": 0, "known": 0})
        d["total"] += 1
        if _known(e):
            d["known"] += 1
    titles = {b.id: b.title for b in session.exec(
        select(models.Batch).where(models.Batch.id.in_(list(by_batch.keys())))).all()}
    rows = []
    for bid, d in by_batch.items():
        rate = d["known"] / d["total"] if d["total"] else 0.0
        rows.append({**d, "batch_title": titles.get(bid, ""), "success_rate": round(rate, 2)})
    rows.sort(key=lambda r: r["success_rate"])
    return {
        "session_id": session_id, "cards_total": len(evs),
        "cards_known": known, "cards_unknown": len(evs) - known,
        "avg_score": round(sum(scores) / len(scores), 1) if scores else None,
        "weakest": rows[0] if rows else None,
        "strongest": rows[-1] if rows else None,
        "by_batch": rows,
    }
