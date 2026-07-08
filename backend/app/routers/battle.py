"""Battle mode («Боевой режим»): the user is IN a live conversation and needs
the right trained line NOW.

Two tiers (F2 spec):
- Every plan: GET /corpus — the phrases the user actually studies (batches they
  activated/put on the path + anything with per-phrase stats), with their SRS
  state. The client caches it and runs instant keyword search fully offline —
  this is also the degradation path when the LLM/network is down.
- AI plan: POST /suggest — the user dictates the moment (STT on the client),
  one fast LLM call picks up to 3 lines from that same corpus. Learned-first:
  the candidate pool ranks automatic > familiar > shaky > touched-new, capped
  so the prompt stays small and the round-trip real-time.

The corpus is deliberately NOT the whole catalog: battle mode surfaces what the
user trained (spec: «приоритет фраз, которые пользователь реально учил»), and
that also keeps paywalled batch content out of free-plan payloads.
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, select

from .. import localize, models, scoring, usage
from ..auth import current_user_id
from ..db import get_session
from ..entitlements import user_entitlements

router = APIRouter(prefix="/api/battle", tags=["battle"])

_POOL_CAP = 160          # max phrases shown to the LLM (prompt-size / latency bound)
_MAX_PICKS = 3
_MIN_CHARS = 4
_MAX_CHARS = 600

# Learned-first ordering; ties keep (batch_id, order_index) stability.
_RANK = {"automatic": 0, "familiar": 1, "shaky": 2, "new": 3}


def _user_rows(session: Session, user_id: int) -> list[tuple[models.Phrase, models.UserPhraseStat | None, models.Batch]]:
    """(phrase, stat|None, batch) for every phrase in the user's study set:
    batches with a BatchProgress row (on_path/activated) plus any phrase the user
    has a stat for. Deleted batches drop out; other users' rows never enter."""
    prog_batch_ids = set(session.exec(
        select(models.BatchProgress.batch_id).where(
            models.BatchProgress.user_id == user_id,
            (models.BatchProgress.on_path == True) | (models.BatchProgress.activated == True))  # noqa: E712
    ).all())
    stats = session.exec(select(models.UserPhraseStat).where(
        models.UserPhraseStat.user_id == user_id)).all()
    stat_by_pid = {st.phrase_id: st for st in stats}

    batch_ids = prog_batch_ids | {st.batch_id for st in stats}
    if not batch_ids:
        return []
    batches = {b.id: b for b in session.exec(
        select(models.Batch).where(models.Batch.id.in_(batch_ids))
        .where(models.Batch.deleted_at == None)  # noqa: E711
    ).all()}
    if not batches:
        return []
    phrases = session.exec(
        select(models.Phrase).where(models.Phrase.batch_id.in_(list(batches.keys())))
        .order_by(models.Phrase.batch_id, models.Phrase.order_index)
    ).all()
    return [(p, stat_by_pid.get(p.id), batches[p.batch_id])
            for p in phrases if p.batch_id in batches]


def _sort_learned_first(rows):
    def key(row):
        p, st, _b = row
        status = st.srs_status if st else "new"
        attempted = 0 if (st and (st.attempts or 0) > 0) else 1
        return (_RANK.get(status, 3), attempted, p.batch_id, p.order_index)
    return sorted(rows, key=key)


@router.get("/corpus")
def corpus(lang: str = "", user_id: int = Depends(current_user_id),
           session: Session = Depends(get_session)):
    """The user's searchable battle corpus (all plans). The client caches this
    and searches it locally — typing must give results with zero network."""
    lng = localize.resolve_lang(lang, session.get(models.User, user_id))
    rows = _sort_learned_first(_user_rows(session, user_id))
    return [{
        "phrase_id": p.id,
        "batch_id": p.batch_id,
        "batch_title": localize.pick(b.title_i18n, lng, b.title),
        "anchor": p.anchor,
        "phrase_en": p.phrase_en,
        "gloss_ru": localize.pick(p.gloss_i18n, lng, p.gloss_ru or ""),
        "situation_ru": p.situation_ru or "",
        "srs_status": (st.srs_status if st else "new"),
        "attempts": (st.attempts if st else 0),
    } for p, st, b in rows]


class SuggestIn(BaseModel):
    situation: str


@router.post("/suggest")
def suggest(body: SuggestIn, user_id: int = Depends(current_user_id),
            session: Session = Depends(get_session)):
    """AI tier: dictated moment → up to 3 picks from the user's corpus, best
    first. via="empty" = nothing studied yet (client shows the cold-start hint);
    via="fallback" = LLM unavailable (client keeps its local keyword results)."""
    ents = user_entitlements(session, user_id)
    if not ents.get("ai_coach"):
        raise HTTPException(403, "locked")
    situation = (body.situation or "").strip()
    if len(situation) < _MIN_CHARS:
        raise HTTPException(400, "too_short")
    budget = ents.get("monthly_ai_cost_cap_usd")
    if budget is not None and usage.month_cost_usd(session, user_id) >= budget:
        raise HTTPException(429, "Monthly AI limit reached.")

    pool = _sort_learned_first(_user_rows(session, user_id))[:_POOL_CAP]
    if not pool:
        return {"via": "empty", "picks": []}

    items = [{"n": i + 1, "anchor": p.anchor, "phrase_en": p.phrase_en,
              "gloss_ru": p.gloss_ru or ""} for i, (p, _st, _b) in enumerate(pool)]
    res = scoring.battle_pick(situation[:_MAX_CHARS], items)

    picks, seen = [], set()
    for pick in res.get("picks", []):
        n = pick.get("n")
        if not isinstance(n, int) or not (1 <= n <= len(pool)) or n in seen:
            continue
        seen.add(n)
        p, st, b = pool[n - 1]
        picks.append({
            "phrase_id": p.id, "batch_id": p.batch_id,
            "batch_title": b.title,
            "anchor": p.anchor, "phrase_en": p.phrase_en,
            "gloss_ru": p.gloss_ru or "",
            "note": pick.get("note", ""),
            "srs_status": (st.srs_status if st else "new"),
        })
        if len(picks) == _MAX_PICKS:
            break

    if res["via"] == "llm":
        usage.accrue(session, user_id, "battle")
        session.commit()
    return {"via": res["via"], "picks": picks}
