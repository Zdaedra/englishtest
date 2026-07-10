"""Live→SRS demand loop: a phrase the learner asks the Live suffleur for in a
real conversation is the truest "I need this" signal — it gets stamped on the
phrase's stat (WITHOUT faking a recall score) and lifted in the practice deck.
"""
import struct
from datetime import datetime, timedelta, timezone

from sqlmodel import Session, select

from app import models
from app.config import get_settings
from app.db import engine


def _seed_batch(slug: str, n: int = 3) -> tuple[int, list[int]]:
    with Session(engine()) as s:
        b = models.Batch(title=f"T-{slug}", slug=slug, status="approved")
        s.add(b)
        s.commit()
        s.refresh(b)
        pids = []
        for i in range(1, n + 1):
            p = models.Phrase(batch_id=b.id, order_index=i, anchor=f"a{i}",
                              phrase_en=f"Phrase {slug} {i}.", gloss_ru=f"смысл {i}",
                              situation_ru=f"c{i}", task_ru=f"t{i}")
            s.add(p)
            s.commit()
            s.refresh(p)
            pids.append(p.id)
        return b.id, pids


def _activate(uid: int, bid: int) -> None:
    with Session(engine()) as s:
        s.add(models.BatchProgress(user_id=uid, batch_id=bid,
                                   on_path=True, activated=True))
        s.commit()


def _stat_row(uid: int, pid: int):
    with Session(engine()) as s:
        return s.exec(select(models.UserPhraseStat).where(
            models.UserPhraseStat.user_id == uid,
            models.UserPhraseStat.phrase_id == pid)).first()


# ---- recording the demand signal ---------------------------------------------

def test_suggest_stamps_live_demand_on_the_best_pick(make_user):
    c = make_user(plan="ai", is_admin=True)
    uid = c.user["id"]  # type: ignore[attr-defined]
    bid, pids = _seed_batch("ld-hit")
    _activate(uid, bid)
    r = c.post("/api/battle/suggest", json={"situation": "надо мягко осадить коллегу"})
    assert r.status_code == 200, r.text
    best_pid = r.json()["picks"][0]["phrase_id"]      # stub picks n=1 = pool head
    st = _stat_row(uid, best_pid)
    assert st is not None and st.live_requested_at is not None
    assert st.live_request_count == 1


def test_live_demand_never_fakes_a_recall_score(make_user):
    """Critical: asking for a line is NOT answering it — avg_score/srs must stay
    pristine, or the SRS engine would think the phrase was practiced."""
    c = make_user(plan="ai", is_admin=True)
    uid = c.user["id"]  # type: ignore[attr-defined]
    bid, pids = _seed_batch("ld-clean")
    _activate(uid, bid)
    c.post("/api/battle/suggest", json={"situation": "хочу выиграть паузу"})
    best_pid = c.post("/api/battle/suggest",
                      json={"situation": "хочу выиграть паузу"}).json()["picks"][0]["phrase_id"]
    st = _stat_row(uid, best_pid)
    assert st.avg_score is None and st.attempts == 0
    assert st.srs_status == "new" and st.next_review_at is None
    assert st.live_request_count == 2                 # both asks counted


def test_live_demand_creates_arsenal_row_for_unstudied_all_scope_phrase(make_user):
    """An 'all'-scope ask for a phrase the user never studied CREATES the stat —
    a real-world need becomes a study target (enters the battle corpus)."""
    c = make_user(plan="ai", is_admin=True)
    uid = c.user["id"]  # type: ignore[attr-defined]
    bid, pids = _seed_batch("ld-cat")                 # exists in catalog, not activated
    assert _stat_row(uid, pids[0]) is None
    r = c.post("/api/battle/suggest?scope=all", json={"situation": "надо мягко осадить"})
    assert r.status_code == 200 and r.json()["via"] == "llm"
    best_pid = r.json()["picks"][0]["phrase_id"]
    st = _stat_row(uid, best_pid)
    assert st is not None and st.live_requested_at is not None


def test_live_demand_isolated_per_user(make_user):
    a = make_user(plan="ai", is_admin=True)
    b = make_user(plan="ai")
    uid_a = a.user["id"]  # type: ignore[attr-defined]
    bid, pids = _seed_batch("ld-iso")
    _activate(uid_a, bid)
    a.post("/api/battle/suggest", json={"situation": "надо осадить"})
    uid_b = b.user["id"]  # type: ignore[attr-defined]
    assert all(_stat_row(uid_b, pid) is None for pid in pids)   # B untouched


def test_fallback_pick_does_not_record_demand(make_user, monkeypatch):
    """No LLM pick (fallback) = no real suggestion shown = no demand stamped."""
    monkeypatch.setattr(
        "app.scoring.battle_pick",
        lambda situation, items, intent=None: {"via": "fallback", "picks": [], "intents": []})
    c = make_user(plan="ai", is_admin=True)
    uid = c.user["id"]  # type: ignore[attr-defined]
    bid, pids = _seed_batch("ld-fb")
    _activate(uid, bid)
    c.post("/api/battle/suggest", json={"situation": "надо осадить"})
    assert all(_stat_row(uid, pid) is None for pid in pids)


# ---- the deck lift ------------------------------------------------------------

def test_deck_lifts_a_live_requested_phrase(make_user):
    """The truest need surfaces in practice: with everything else equal, a phrase
    asked for in Live outranks its unrequested neighbour in the deck weighting."""
    c = make_user(plan="ai", is_admin=True)
    uid = c.user["id"]  # type: ignore[attr-defined]
    bid, pids = _seed_batch("ld-deck", n=2)
    _activate(uid, bid)
    with Session(engine()) as s:                       # stamp demand on pids[0] only
        s.add(models.UserPhraseStat(
            user_id=uid, phrase_id=pids[0], batch_id=bid,
            live_requested_at=datetime.now(timezone.utc), live_request_count=1))
        s.commit()
    rows = c.get(f"/api/training/deck?batch_ids={bid}&limit=20").json()
    pri = {row["phrase_id"]: row["priority"] for row in rows}
    assert pri[pids[0]] > pri[pids[1]]                 # live-requested is weighted higher


def test_deck_lift_decays_after_a_week(make_user):
    """An 8-day-old ask is back to neutral — the boost is a nudge, not permanent."""
    c = make_user(plan="ai", is_admin=True)
    uid = c.user["id"]  # type: ignore[attr-defined]
    bid, pids = _seed_batch("ld-decay", n=2)
    _activate(uid, bid)
    with Session(engine()) as s:
        s.add(models.UserPhraseStat(
            user_id=uid, phrase_id=pids[0], batch_id=bid,
            live_requested_at=datetime.now(timezone.utc) - timedelta(days=8),
            live_request_count=1))
        s.commit()
    rows = c.get(f"/api/training/deck?batch_ids={bid}&limit=20").json()
    pri = {row["phrase_id"]: row["priority"] for row in rows}
    # pids[0] now has a stat (attempts 0) but no live lift; pids[1] has none.
    # Neither is boosted, so the stale-ask phrase is NOT above its neighbour.
    assert pri[pids[0]] <= pri[pids[1]] + 1e-6


# ---- moment of the day: the live_only deck + mastery counter ------------------

def _mark_live(uid: int, pid: int, bid: int, days_ago: float = 0.0) -> None:
    with Session(engine()) as s:
        s.add(models.UserPhraseStat(
            user_id=uid, phrase_id=pid, batch_id=bid, live_request_count=1,
            live_requested_at=datetime.now(timezone.utc) - timedelta(days=days_ago)))
        s.commit()


def test_live_only_deck_returns_just_the_asked_phrases(make_user):
    c = make_user(plan="ai", is_admin=True)
    uid = c.user["id"]  # type: ignore[attr-defined]
    bid, pids = _seed_batch("mom-1", n=3)
    _mark_live(uid, pids[0], bid)                     # only #0 asked in Live
    # No embeddings seeded → no neighbours → the session is exactly the ask.
    rows = c.get("/api/training/deck?live_only=1&limit=20").json()
    assert {r["phrase_id"] for r in rows} == {pids[0]}


def test_live_only_self_scopes_without_batch_ids(make_user):
    """The moment-of-the-day session needs no batch scope — even a user who never
    activated the batch (only used Live) gets their asked phrase back to drill."""
    c = make_user(plan="ai", is_admin=True)
    uid = c.user["id"]  # type: ignore[attr-defined]
    bid, pids = _seed_batch("mom-noscope", n=2)       # never activated
    _mark_live(uid, pids[1], bid)
    rows = c.get("/api/training/deck?live_only=1").json()   # no batch_ids at all
    assert [r["phrase_id"] for r in rows] == [pids[1]]


def test_live_only_pulls_in_semantic_neighbours(make_user):
    """With the embedding index seeded, the session expands from the asked phrase
    to its nearest neighbour — 'more like what you needed'."""
    c = make_user(plan="ai", is_admin=True)
    uid = c.user["id"]  # type: ignore[attr-defined]
    bid, pids = _seed_batch("mom-nbr", n=3)
    st_cfg = get_settings()
    dim = st_cfg.embed_dim

    def vec(x, y):
        return struct.pack(f"<{dim}f", x, y, *([0.0] * (dim - 2)))
    with Session(engine()) as s:                      # deterministic vectors
        s.add(models.PhraseEmbedding(phrase_id=pids[0], model=st_cfg.model_embed, dim=dim, text_hash="h", vector=vec(1.0, 0.0)))
        s.add(models.PhraseEmbedding(phrase_id=pids[1], model=st_cfg.model_embed, dim=dim, text_hash="h", vector=vec(0.99, 0.14)))  # close to #0
        s.add(models.PhraseEmbedding(phrase_id=pids[2], model=st_cfg.model_embed, dim=dim, text_hash="h", vector=vec(0.0, 1.0)))    # far
        s.commit()
    _mark_live(uid, pids[0], bid)
    got = {r["phrase_id"] for r in c.get("/api/training/deck?live_only=1&limit=20").json()}
    assert pids[0] in got and pids[1] in got          # ask + its nearest neighbour
    assert pids[2] not in got                          # the far phrase stays out


def test_mastery_reports_live_count(make_user):
    c = make_user(plan="ai", is_admin=True)
    uid = c.user["id"]  # type: ignore[attr-defined]
    bid, pids = _seed_batch("mom-mast", n=3)
    _mark_live(uid, pids[0], bid)
    _mark_live(uid, pids[1], bid, days_ago=30)         # outside the 14-day window
    row = next(m for m in c.get("/api/training/mastery").json() if m["batch_id"] == bid)
    assert row["live"] == 1                            # only the recent ask counts


def test_mastery_due_only_counts_activated_batches(make_user):
    """F1 dead-end fix: a due phrase in a NON-activated batch must NOT inflate the
    'N to refresh' count — the review deck draws from activated batches only, so
    counting it would open an empty session. Activating the batch makes it count."""
    from datetime import datetime, timedelta, timezone
    c = make_user(plan="ai", is_admin=True)
    uid = c.user["id"]  # type: ignore[attr-defined]
    bid, pids = _seed_batch("due-scope", n=2)
    past = datetime.now(timezone.utc) - timedelta(days=1)
    with Session(engine()) as s:
        s.add(models.UserPhraseStat(user_id=uid, phrase_id=pids[0], batch_id=bid,
                                    srs_status="familiar", next_review_at=past))
        s.commit()
    row = lambda: next(m for m in c.get("/api/training/mastery").json() if m["batch_id"] == bid)
    assert row()["due"] == 0                           # not activated → doesn't nag
    assert row()["srs"].get("familiar") == 1           # but the competence map still sees it
    _activate(uid, bid)
    assert row()["due"] == 1                           # activated → the deck can serve it
