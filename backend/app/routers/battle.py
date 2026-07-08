"""Battle mode («Боевой режим»): the user is IN a live conversation and needs
the right trained line NOW.

Two tiers (F2 spec), each in one of two SCOPES the user picks in the UI:
- scope="learned" (default): only the phrases the user actually studies (batches
  they activated/put on the path + anything with per-phrase stats).
- scope="all": the whole visible catalog — advise from a phrase the user hasn't
  reached yet. Cost-bounded so this is NOT more expensive per call (below).

Endpoints:
- Every plan: GET /corpus?scope= — the arsenal, with SRS state. The client caches
  it and runs instant keyword search fully offline — also the degradation path.
- AI plan: POST /suggest?scope= — the user dictates the moment (STT on the
  client), one fast LLM call picks up to 3 lines. Learned-first: the pool ranks
  automatic > familiar > shaky > touched-new.

Cost control (why scope="all" is not a money hole):
- The LLM prompt is bounded REGARDLESS of scope. For "learned" the pool is small
  (≤ _POOL_CAP, already learned-first). For "all" we keyword-PREFILTER the whole
  catalog against the dictated moment and send only the top _ALL_CAP candidates —
  so a 40-phrase and a 4000-phrase catalog cost the same per call.
- Typing (arsenal search) is a free, fully-local keyword filter — only the mic
  spends an LLM call.
- The per-plan monthly AI-cost cap (entitlements.monthly_ai_cost_cap_usd) is the
  hard money backstop: /suggest 429s once the month's estimated spend crosses it.
"""
import re

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, select

from .. import localize, models, scoring, usage
from ..auth import current_user_id
from ..db import get_session
from ..entitlements import user_entitlements

router = APIRouter(prefix="/api/battle", tags=["battle"])

_POOL_CAP = 160          # learned scope: max phrases shown to the LLM (already small)
_ALL_CAP = 60            # "all" scope: keyword-prefiltered top-N → bounds prompt/cost
_CORPUS_ALL_CAP = 1500   # "all" corpus payload ceiling (client caches it; text only)
_MAX_PICKS = 3
_MIN_CHARS = 4
_MAX_CHARS = 600

# Learned-first ordering; ties keep (batch_id, order_index) stability.
_RANK = {"automatic": 0, "familiar": 1, "shaky": 2, "new": 3}

_norm = lambda s: (s or "").lower().replace("ё", "е")  # noqa: E731


def _toks(q: str) -> list[str]:
    return [t for t in re.split(r"[^a-zа-я0-9']+", _norm(q)) if len(t) >= 2]


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


def _catalog_rows(session: Session, user_id: int):
    """(phrase, stat|None, batch) for the WHOLE visible catalog — every
    non-deleted batch in the shared catalog (owner_id NULL) or owned by the user
    — with the user's SRS stat merged in where present. Mirrors the visibility of
    /api/batches/phrases (which already exposes every phrase to every plan), so
    "all" scope leaks nothing new."""
    batches = {b.id: b for b in session.exec(
        select(models.Batch).where(models.Batch.deleted_at == None)  # noqa: E711
        .where((models.Batch.owner_id == None) | (models.Batch.owner_id == user_id))  # noqa: E711
    ).all()}
    if not batches:
        return []
    stat_by_pid = {st.phrase_id: st for st in session.exec(
        select(models.UserPhraseStat).where(
            models.UserPhraseStat.user_id == user_id)).all()}
    phrases = session.exec(
        select(models.Phrase).where(models.Phrase.batch_id.in_(list(batches.keys())))
        .order_by(models.Phrase.batch_id, models.Phrase.order_index)
    ).all()
    return [(p, stat_by_pid.get(p.id), batches[p.batch_id])
            for p in phrases if p.batch_id in batches]


def _rows_for_scope(session: Session, user_id: int, scope: str):
    return _catalog_rows(session, user_id) if scope == "all" \
        else _user_rows(session, user_id)


def _kw_score(row, tt: list[str]) -> int:
    p, _st, _b = row
    a, e, g, si = _norm(p.anchor), _norm(p.phrase_en), _norm(p.gloss_ru or ""), _norm(p.situation_ru or "")
    s = 0
    for t in tt:
        if t in a: s += 3
        if t in e: s += 2
        if t in g: s += 2
        if t in si: s += 1
    return s


def _keyword_pool(rows, situation: str, cap: int):
    """Bound the LLM pool for a big ("all") corpus: rank the catalog against the
    dictated moment (keyword overlap on anchor/phrase/gloss/situation), keep the
    top `cap`. Keeps the prompt — and the cost — flat no matter how big the
    catalog is. Learned-first is the stable tiebreak, and pads out the tail when
    the moment has few literal matches so the LLM still has real options."""
    ranked = _sort_learned_first(rows)          # learned-first base order
    tt = _toks(situation)
    if not tt:
        return ranked[:cap]
    scored = sorted(enumerate(ranked), key=lambda x: (-_kw_score(x[1], tt), x[0]))
    hits = [r for i, r in scored if _kw_score(r, tt) > 0]
    if len(hits) >= cap:
        return hits[:cap]
    rest = [r for i, r in scored if _kw_score(r, tt) <= 0]
    return (hits + rest)[:cap]


def _row_dict(p, st, b, lng: str) -> dict:
    return {
        "phrase_id": p.id,
        "batch_id": p.batch_id,
        "batch_title": localize.pick(b.title_i18n, lng, b.title),
        "anchor": p.anchor,
        "phrase_en": p.phrase_en,
        "gloss_ru": localize.pick(p.gloss_i18n, lng, p.gloss_ru or ""),
        "situation_ru": p.situation_ru or "",
        "srs_status": (st.srs_status if st else "new"),
        "attempts": (st.attempts if st else 0),
    }


@router.get("/corpus")
def corpus(lang: str = "", scope: str = "learned",
           user_id: int = Depends(current_user_id),
           session: Session = Depends(get_session)):
    """The user's searchable battle corpus (all plans). The client caches this
    and searches it locally — typing must give results with zero network.
    scope="all" returns the whole visible catalog (learned-first, capped)."""
    lng = localize.resolve_lang(lang, session.get(models.User, user_id))
    rows = _sort_learned_first(_rows_for_scope(session, user_id, scope))
    if scope == "all":
        rows = rows[:_CORPUS_ALL_CAP]
    return [_row_dict(p, st, b, lng) for p, st, b in rows]


class SuggestIn(BaseModel):
    situation: str


@router.post("/suggest")
def suggest(body: SuggestIn, scope: str = "learned",
            user_id: int = Depends(current_user_id),
            session: Session = Depends(get_session)):
    """AI tier: dictated moment → up to 3 picks, best first. scope="learned"
    picks from the study set; scope="all" from the whole catalog (keyword-
    prefiltered so the prompt stays bounded). via="empty" = nothing to pick from;
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

    rows = _rows_for_scope(session, user_id, scope)
    if scope == "all":
        pool = _keyword_pool(rows, situation, _ALL_CAP)      # bounded prompt
    else:
        pool = _sort_learned_first(rows)[:_POOL_CAP]
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
