import hashlib
import random
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, select

from .. import access, audio, content, cover, localize, models, srs, tts
from .. import mnemo as mnemo_render
from ..auth import current_user_id, is_admin
from ..db import get_session
from ..schemas import ReviewIn

router = APIRouter(prefix="/api/batches", tags=["batches"])


def _visible(b: models.Batch, user_id: int, admin: bool) -> bool:
    """A batch is visible if it's in the shared catalog (owner_id is NULL), the
    caller owns it, or the caller is admin. Keeps private imports per-user."""
    return b.owner_id is None or b.owner_id == user_id or admin


def _owner_filter(user_id: int):
    # noqa: E711 — SQLAlchemy needs `== None` for IS NULL.
    return (models.Batch.owner_id == None) | (models.Batch.owner_id == user_id)  # noqa: E711

# Recall pause baked after each anchor in the training drills (seconds): long
# enough for the learner to say the word back before the next one.
MNEMO_TRAIN_GAP = 3.5


def _preview(subtitle: str, theme: str, limit: int = 90) -> str:
    """A short one-line card caption: the mnemonic-image subtitle, else the theme.
    Never the mnemonic story itself — that reads as a meaningless mid-sentence cut."""
    if subtitle.strip():
        return subtitle.strip()
    theme = (theme or "").strip()
    return theme if len(theme) <= limit else theme[:limit].rstrip() + "…"


class CoverIn(BaseModel):
    metaphor: Optional[str] = None
    quality: Optional[str] = None
    force: bool = False


@router.get("")
def list_batches(lang: str = "", user_id: int = Depends(current_user_id),
                 session: Session = Depends(get_session)):
    rows = session.exec(
        select(models.Batch).where(models.Batch.deleted_at == None)  # noqa: E711
        .where(_owner_filter(user_id))
        .order_by(models.Batch.created_at.desc())
    ).all()
    u = session.get(models.User, user_id)
    plan = u.plan if u else "free"
    lng = localize.resolve_lang(lang, u)
    out = []
    for b in rows:
        phrases = session.exec(
            select(models.Phrase).where(models.Phrase.batch_id == b.id)
            .order_by(models.Phrase.order_index)
        ).all()
        anchors = [p.anchor for p in phrases if p.anchor]
        title = localize.pick(b.title_i18n, lng, b.title)
        subtitle = localize.pick(b.subtitle_i18n, lng, b.subtitle)
        theme = localize.pick(b.theme_i18n, lng, b.theme)
        out.append({"id": b.id, "title": title, "slug": b.slug, "theme": theme,
                    "subtitle": subtitle, "section": b.section,
                    "preview": _preview(subtitle, theme),
                    "status": b.status,
                    "phrase_count": len(phrases), "anchors": anchors,
                    "cover_url": b.cover_path,
                    "is_free": b.is_free,
                    "locked": not access.batch_usable(plan, b, user_id),
                    "created_at": b.created_at.isoformat()})
    return out


@router.get("/phrases")
def list_phrases(lang: str = "", user_id: int = Depends(current_user_id),
                 session: Session = Depends(get_session)):
    """Flat index of every phrase across non-deleted batches — powers the library
    search's per-phrase results block. Read-only, no audio. Declared before
    /{batch_id} so the literal path wins the route match."""
    lng = localize.resolve_lang(lang, session.get(models.User, user_id))
    batches = session.exec(
        select(models.Batch).where(models.Batch.deleted_at == None)  # noqa: E711
        .where(_owner_filter(user_id))
    ).all()
    title_by_id = {b.id: localize.pick(b.title_i18n, lng, b.title) for b in batches}
    ids = list(title_by_id.keys())
    if not ids:
        return []
    phrases = session.exec(
        select(models.Phrase).where(models.Phrase.batch_id.in_(ids))
        .order_by(models.Phrase.batch_id, models.Phrase.order_index)
    ).all()
    return [{"phrase_id": p.id, "batch_id": p.batch_id,
             "batch_title": title_by_id.get(p.batch_id, ""),
             "anchor": p.anchor, "phrase_en": p.phrase_en,
             "gloss_ru": localize.pick(p.gloss_i18n, lng, p.gloss_ru),
             "order_index": p.order_index}
            for p in phrases]


@router.get("/{batch_id}")
def get_batch(batch_id: int, lang: str = "", user_id: int = Depends(current_user_id),
              session: Session = Depends(get_session)):
    b = session.get(models.Batch, batch_id)
    if not b or b.deleted_at or not _visible(b, user_id, is_admin(session, user_id)):
        raise HTTPException(404, "Batch not found")
    u = session.get(models.User, user_id)
    lng = localize.resolve_lang(lang, u)
    locked = not access.batch_usable(u.plan if u else "free", b, user_id)
    head = {
        "id": b.id, "title": localize.pick(b.title_i18n, lng, b.title),
        "slug": b.slug, "theme": localize.pick(b.theme_i18n, lng, b.theme),
        "subtitle": localize.pick(b.subtitle_i18n, lng, b.subtitle), "section": b.section,
        "difficulty": b.difficulty, "status": b.status,
        "cover_url": b.cover_path, "is_free": b.is_free, "locked": locked,
    }
    if locked:
        # Don't ship the paid content (phrases/mnemo) behind the paywall.
        return {**head, "zones": [], "phrases": [], "mnemo": {"story_ru": "", "spans": []}}
    zones = session.exec(select(models.Zone).where(models.Zone.batch_id == batch_id)
                         .order_by(models.Zone.order_index)).all()
    phrases = session.exec(select(models.Phrase).where(models.Phrase.batch_id == batch_id)
                           .order_by(models.Phrase.order_index)).all()
    mnemo = session.exec(select(models.MnemoStory).where(models.MnemoStory.batch_id == batch_id)).first()

    def _zone(z: models.Zone) -> dict:
        d = z.model_dump()
        d["title"] = localize.pick(z.title_i18n, lng, z.title)
        return d

    def _phrase(p: models.Phrase) -> dict:
        d = p.model_dump()
        d["gloss_ru"] = localize.pick(p.gloss_i18n, lng, p.gloss_ru)
        return d

    mnemo_out = {"story_ru": "", "spans": []}
    if mnemo:
        story, spans = localize.story_and_spans(mnemo, lng)
        mnemo_out = {"story_ru": story, "spans": spans}
    return {
        **head,
        "zones": [_zone(z) for z in zones],
        "phrases": [_phrase(p) for p in phrases],
        "mnemo": mnemo_out,
    }


@router.post("/{batch_id}/free")
def set_free_batch(batch_id: int, user_id: int = Depends(current_user_id),
                   session: Session = Depends(get_session)):
    """Admin: designate THE free showcase batch (exactly one). Clears the flag on
    any other batch so there's always at most one fully-free batch."""
    if not is_admin(session, user_id):
        raise HTTPException(403, "admin_required")
    b = session.get(models.Batch, batch_id)
    if not b:
        raise HTTPException(404, "Batch not found")
    for other in session.exec(select(models.Batch).where(models.Batch.is_free == True)).all():  # noqa: E712
        if other.id != batch_id:
            other.is_free = False
            session.add(other)
    b.is_free = True
    session.add(b)
    session.commit()
    return {"id": b.id, "slug": b.slug, "is_free": True}


@router.get("/phrase/{phrase_id}/audio")
def phrase_audio(phrase_id: int, user_id: int = Depends(current_user_id),
                 session: Session = Depends(get_session)):
    """One cached English clip for a single phrase (tap-to-hear, no full session)."""
    p = session.get(models.Phrase, phrase_id)
    if not p:
        raise HTTPException(404, "Phrase not found")
    b = session.get(models.Batch, p.batch_id)
    if not b or not _visible(b, user_id, is_admin(session, user_id)):
        raise HTTPException(404, "Phrase not found")
    st = session.get(models.Setting, 1) or models.Setting(id=1)
    try:
        path, dur = tts.synth(p.phrase_en, voice=st.tts_voice)
    except Exception as e:
        raise HTTPException(502, f"TTS failed: {e}")
    return {"audio_url": f"/audio/phrases/{path.name}", "duration": dur}


def _lower_anchor_spans(story: str, spans: list[dict]) -> str:
    """Return the story with each anchor span lowercased — TTS reads e.g. 'read'
    as a word, not 'R-E-A-D'. Non-anchor (Russian) text is left untouched."""
    valid = sorted((s for s in spans if "start" in s and "end" in s), key=lambda s: s["start"])
    out, cursor = [], 0
    for sp in valid:
        a, b = sp["start"], sp["end"]
        if a < cursor or b > len(story):
            continue
        out.append(story[cursor:a])
        out.append(story[a:b].lower())
        cursor = b
    out.append(story[cursor:])
    return "".join(out)


def _anchor_segments(story: str, spans: list[dict], gap: float) -> list[dict]:
    """Anchors-only drill: each English anchor, then a recall gap so the learner
    can say it back before the next one. `spans` are taken in the order given
    (sequential or shuffled); the caller decides. Anchor positions come from the
    span char offsets; anchor_id keys the karaoke highlight, phrase_id is the
    phrase order_index."""
    segs: list[dict] = []
    for sp in spans:
        if "start" not in sp or "end" not in sp:
            continue
        text = story[sp["start"]:sp["end"]].strip()
        if not any(c.isalnum() for c in text):
            continue
        segs.append({"kind": "audio", "text": text, "lang": "en",
                     "phrase_order": sp.get("phrase_id"), "role": "anchor",
                     "anchor_id": sp.get("anchor_id")})
        segs.append({"kind": "silence", "dur": gap,
                     "phrase_order": sp.get("phrase_id"), "role": "gap",
                     "anchor_id": sp.get("anchor_id")})
    return segs


@router.get("/{batch_id}/mnemo/audio")
def mnemo_audio(batch_id: int, layout: str = "full", lang: str = "",
                user_id: int = Depends(current_user_id),
                session: Session = Depends(get_session)):
    """Render the mnemonic story as audio in one of three layouts.

    full    — LEARNING: the whole story spoken by ONE gpt-4o-mini-tts narrator in
              a single steered pass; embedded English anchors are pronounced in
              English by that same voice. Smooth and continuous.
    anchors — TRAINING: just the English anchors in story order, a long recall gap
              after each so the learner says it back from memory.
    shuffle — TRAINING: the same anchors out of story order (deterministic per
              batch), same recall gap — recall without leaning on the sequence.

    Content-addressed: re-requests hit the cached asset. Returns {audio_url,
    duration, plan} — plan is empty for `full` (no per-word timecodes from a
    single pass); the training layouts return per-anchor timings for the karaoke
    highlight.
    """
    if layout not in ("full", "anchors", "shuffle"):
        raise HTTPException(400, "Unknown layout")
    b = session.get(models.Batch, batch_id)
    if not b or b.deleted_at or not _visible(b, user_id, is_admin(session, user_id)):
        raise HTTPException(404, "Batch not found")
    mnemo = session.exec(select(models.MnemoStory).where(models.MnemoStory.batch_id == batch_id)).first()
    if not mnemo or not mnemo.story_ru.strip():
        raise HTTPException(404, "No mnemonic story for this batch")

    lng = localize.resolve_lang(lang, session.get(models.User, user_id))
    story_txt, story_spans = localize.story_and_spans(mnemo, lng)

    if layout == "full":
        # Lowercase the anchor spans for TTS so the narrator says them as words,
        # not spelled-out caps (display keeps whatever case is stored).
        tts_text = _lower_anchor_spans(story_txt, story_spans)
        instr = mnemo_render.INSTR if lng == localize.BASE else mnemo_render.INSTR_INTL
        try:
            name, dur = mnemo_render.render_full(tts_text, instructions=instr)
        except Exception as e:
            raise HTTPException(502, f"Render failed: {e}")
        return {"audio_url": f"/audio/phrases/{name}", "duration": dur,
                "plan": [], "layout": layout}

    # anchors | shuffle — training drills: each English anchor, long recall gap.
    # (Anchors are English in every language, so this audio is language-neutral —
    # but we still slice from the localized story so the offsets line up.)
    if not story_spans:
        raise HTTPException(404, "No anchors located in this story")
    spans = sorted((s for s in story_spans if "start" in s and "end" in s),
                   key=lambda s: s["start"])
    if layout == "shuffle":
        # Deterministic per-batch shuffle: stable (cacheable) yet out of story order.
        random.Random(batch_id).shuffle(spans)
    segments = _anchor_segments(story_txt, spans, gap=MNEMO_TRAIN_GAP)
    if not segments:
        raise HTTPException(404, "Mnemonic produced no audio segments")
    key = hashlib.sha256(
        f"{layout}|{MNEMO_TRAIN_GAP}|{story_txt}|{spans}".encode()
    ).hexdigest()[:16]
    out_name = f"mnemo-{batch_id}-{layout}-{key}.wav"
    try:
        path, dur, plan = audio.render_session(
            segments, out_name, voice=mnemo_render.NARRATOR_VOICE,
            model=mnemo_render.NARRATOR_MODEL, instructions=mnemo_render.ANCHOR_INSTR)
    except Exception as e:
        raise HTTPException(502, f"Render failed: {e}")
    return {"audio_url": f"/audio/sessions/{path.name}", "duration": dur,
            "plan": plan, "layout": layout}


@router.get("/{batch_id}/export")
def export_batch(batch_id: int, user_id: int = Depends(current_user_id),
                 session: Session = Depends(get_session)):
    """Round-trip a batch back to the authoring JSON format (for corrections)."""
    b = session.get(models.Batch, batch_id)
    if not b or b.deleted_at or not _visible(b, user_id, is_admin(session, user_id)):
        raise HTTPException(404, "Batch not found")
    return content.to_authoring(session, b)


@router.delete("/{batch_id}")
def soft_delete(batch_id: int, user_id: int = Depends(current_user_id),
                session: Session = Depends(get_session)):
    b = session.get(models.Batch, batch_id)
    if not b:
        raise HTTPException(404, "Batch not found")
    # Only the owner of a private import, or an admin (for the shared catalog),
    # may delete. Clients cannot vandalise the curated library.
    if not (is_admin(session, user_id) or b.owner_id == user_id):
        raise HTTPException(403, "admin_required")
    b.deleted_at = datetime.now(timezone.utc)
    session.add(b)
    session.commit()
    return {"ok": True}


@router.post("/{batch_id}/cover")
def make_cover(batch_id: int, body: Optional[CoverIn] = None,
               user_id: int = Depends(current_user_id),
               session: Session = Depends(get_session)):
    b = session.get(models.Batch, batch_id)
    if not b or b.deleted_at:
        raise HTTPException(404, "Batch not found")
    if not (is_admin(session, user_id) or b.owner_id == user_id):
        raise HTTPException(403, "admin_required")
    body = body or CoverIn()
    try:
        url = cover.generate_cover(b.id, b.slug, b.title, b.theme, b.subtitle,
                                   metaphor=body.metaphor, quality=body.quality,
                                   force=body.force)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Cover generation failed: {e}")
    b.cover_path = url
    session.add(b)
    session.commit()
    return {"id": b.id, "cover_url": url}


@router.post("/reviews")
def post_review(rev: ReviewIn, user_id: int = Depends(current_user_id),
                session: Session = Depends(get_session)):
    p = session.get(models.Phrase, rev.phrase_id)
    if not p:
        raise HTTPException(404, "Phrase not found")
    session.add(models.ReviewEvent(user_id=user_id, phrase_id=rev.phrase_id,
                                   event_type=rev.event_type, score=rev.score,
                                   latency_ms=rev.latency_ms))
    st = session.exec(select(models.UserPhraseStat).where(
        models.UserPhraseStat.user_id == user_id,
        models.UserPhraseStat.phrase_id == p.id)).first()
    if not st:
        st = models.UserPhraseStat(user_id=user_id, phrase_id=p.id, batch_id=p.batch_id)
    # Advance the full SM-2-lite schedule (interval/ease/next_review + srs_status).
    srs.advance(st, rev.score)
    session.add(st)
    session.commit()
    return {"phrase_id": p.id, "srs_status": st.srs_status,
            "next_review_at": st.next_review_at.isoformat() if st.next_review_at else None}
