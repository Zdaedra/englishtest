"""Battle mode («Боевой режим»): corpus scoped to the user's OWN study set
(cross-user isolation), the free·core·ai matrix on /suggest, the monthly budget
guardrail, and the learned-first candidate ordering the AI pool relies on.
"""
from sqlmodel import Session

from app import models
from app.db import engine
from app.routers.battle import (
    _ALL_CAP, _catalog_rows, _keyword_pool, _sort_learned_first, _user_rows,
)


def _seed_batch(slug: str, n: int = 3, owner_id: int | None = None) -> tuple[int, list[int]]:
    with Session(engine()) as s:
        b = models.Batch(title=f"T-{slug}", slug=slug, status="approved",
                         owner_id=owner_id)
        s.add(b)
        s.commit()
        s.refresh(b)
        pids = []
        for i in range(1, n + 1):
            p = models.Phrase(batch_id=b.id, order_index=i, anchor=f"a{i}",
                              phrase_en=f"Phrase {slug} {i}.",
                              gloss_ru=f"смысл {i}", situation_ru=f"ситуация {i}")
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


def _stat(uid: int, pid: int, bid: int, status: str = "familiar",
          attempts: int = 3) -> None:
    with Session(engine()) as s:
        s.add(models.UserPhraseStat(user_id=uid, phrase_id=pid, batch_id=bid,
                                    srs_status=status, attempts=attempts))
        s.commit()


# ---- corpus -----------------------------------------------------------------

def test_corpus_empty_until_user_studies_something(make_user):
    c = make_user(plan="ai", is_admin=True)
    _seed_batch("bt-cold")          # exists in the catalog, but never touched
    r = c.get("/api/battle/corpus")
    assert r.status_code == 200
    assert r.json() == []


def test_corpus_is_own_study_set_with_srs_state(make_user):
    a = make_user(plan="ai", is_admin=True)
    b = make_user(plan="free")
    bid, pids = _seed_batch("bt-own")
    _activate(a.user["id"], bid)  # type: ignore[attr-defined]
    _stat(a.user["id"], pids[1], bid, status="automatic", attempts=9)  # type: ignore[attr-defined]

    mine = a.get("/api/battle/corpus").json()
    assert [x["phrase_id"] for x in mine] and len(mine) == 3
    by_pid = {x["phrase_id"]: x for x in mine}
    assert by_pid[pids[1]]["srs_status"] == "automatic"
    assert by_pid[pids[0]]["srs_status"] == "new"
    assert by_pid[pids[0]]["situation_ru"] == "ситуация 1"

    # the other user studied nothing — their battle corpus stays empty
    assert b.get("/api/battle/corpus").json() == []


def test_corpus_includes_stat_only_batches_and_skips_deleted(make_user):
    from datetime import datetime, timezone
    c = make_user(plan="core", is_admin=True)
    uid = c.user["id"]  # type: ignore[attr-defined]
    bid1, pids1 = _seed_batch("bt-stat")
    bid2, _ = _seed_batch("bt-gone")
    _stat(uid, pids1[0], bid1)          # stats alone pull the batch in
    _activate(uid, bid2)
    with Session(engine()) as s:        # ... but a deleted batch drops out
        b2 = s.get(models.Batch, bid2)
        b2.deleted_at = datetime.now(timezone.utc)
        s.add(b2)
        s.commit()
    got = c.get("/api/battle/corpus").json()
    assert {x["batch_id"] for x in got} == {bid1}


# ---- scope="all": the whole catalog, cost-bounded ----------------------------

def test_corpus_all_scope_spans_whole_catalog_even_untouched(make_user):
    a = make_user(plan="ai", is_admin=True)
    _seed_batch("bt-all-1")          # never activated / no stats
    _seed_batch("bt-all-2")
    learned = a.get("/api/battle/corpus").json()               # study set = empty
    everything = a.get("/api/battle/corpus?scope=all").json()  # catalog = 6 phrases
    assert learned == []
    assert len(everything) == 6
    assert {x["srs_status"] for x in everything} == {"new"}


def test_corpus_flags_due_phrases_for_the_widget(make_user):
    """The lock-screen widget leads with what's slipping — so /corpus marks each
    phrase due iff its SRS next_review_at has passed. never-scheduled = not due."""
    from datetime import datetime, timedelta, timezone
    c = make_user(plan="ai", is_admin=True)
    uid = c.user["id"]  # type: ignore[attr-defined]
    bid, pids = _seed_batch("bt-due")
    _activate(uid, bid)
    now = datetime.now(timezone.utc)
    with Session(engine()) as s:
        # pids[0]: due (next_review in the past); pids[1]: not due (future); pids[2]: unscheduled
        s.add(models.UserPhraseStat(user_id=uid, phrase_id=pids[0], batch_id=bid,
                                    next_review_at=now - timedelta(days=1)))
        s.add(models.UserPhraseStat(user_id=uid, phrase_id=pids[1], batch_id=bid,
                                    next_review_at=now + timedelta(days=3)))
        s.commit()
    by_pid = {x["phrase_id"]: x for x in c.get("/api/battle/corpus").json()}
    assert by_pid[pids[0]]["due"] is True
    assert by_pid[pids[1]]["due"] is False
    assert by_pid[pids[2]]["due"] is False        # no schedule yet → not due


def test_corpus_all_scope_excludes_other_users_private_imports(make_user):
    a = make_user(plan="ai", is_admin=True)
    b = make_user(plan="ai")
    _seed_batch("bt-shared")                       # owner_id NULL → everyone
    _seed_batch("bt-b-private", owner_id=b.user["id"])  # type: ignore[attr-defined]
    ids_seen = {x["batch_id"] for x in a.get("/api/battle/corpus?scope=all").json()}
    with Session(engine()) as s:
        priv = s.exec(models.Batch.__table__.select().where(
            models.Batch.slug == "bt-b-private")).first()
    assert priv.id not in ids_seen        # a can't see b's private import


def test_all_scope_suggest_pool_is_keyword_bounded():
    """The whole point of the cost guard: a huge catalog is prefiltered to
    ≤ _ALL_CAP candidates before the LLM ever sees it."""
    class _P:
        def __init__(self, i):
            self.id = i; self.batch_id = 1; self.order_index = i
            self.anchor = f"a{i}"; self.phrase_en = f"line {i}"
            self.gloss_ru = "перебить и удержать слово" if i == 3 else f"смысл {i}"
            self.situation_ru = ""
    rows = [(_P(i), None, object()) for i in range(500)]
    pool = _keyword_pool(rows, "хочу удержать слово на встрече", _ALL_CAP)
    assert len(pool) == _ALL_CAP
    assert pool[0][0].id == 3          # the keyword hit floats to the front


def test_all_scope_suggest_can_pick_an_unlearned_catalog_phrase(make_user):
    c = make_user(plan="ai", is_admin=True)
    _seed_batch("bt-cat")             # exists in catalog, user studied nothing
    # learned scope has no pool → empty; all scope picks from the catalog
    assert c.post("/api/battle/suggest",
                  json={"situation": "надо мягко осадить"}).json()["via"] == "empty"
    r = c.post("/api/battle/suggest?scope=all",
               json={"situation": "надо мягко осадить"}).json()
    assert r["via"] == "llm" and len(r["picks"]) == 1


# ---- suggest: the entitlements matrix ----------------------------------------

def test_suggest_locked_for_free_and_core(make_user):
    make_user(plan="ai", is_admin=True)   # burn the first-user auto-admin slot
    for plan in ("free", "core"):
        c = make_user(plan=plan)
        r = c.post("/api/battle/suggest", json={"situation": "надо мягко осадить коллегу"})
        assert r.status_code == 403, f"{plan}: {r.text}"
        assert r.json()["detail"] == "locked"


def test_suggest_happy_on_ai_plan_accrues_usage(make_user):
    c = make_user(plan="ai", is_admin=True)
    uid = c.user["id"]  # type: ignore[attr-defined]
    bid, pids = _seed_batch("bt-ai")
    _activate(uid, bid)
    _stat(uid, pids[2], bid, status="automatic")   # learned → pool position 1

    r = c.post("/api/battle/suggest", json={"situation": "хочу перехватить слово на встрече"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["via"] == "llm"
    # the stub picks n=1 = the learned-first head of the pool = the automatic phrase
    assert body["picks"][0]["phrase_id"] == pids[2]
    assert body["picks"][0]["note"] == "коротко и сразу"
    assert body["picks"][0]["srs_status"] == "automatic"

    from app.usage import _period
    with Session(engine()) as s:
        row = s.exec(models.UsageLedger.__table__.select().where(
            models.UsageLedger.user_id == uid,
            models.UsageLedger.period == _period())).first()
    assert row is not None and row.micros > 0


def test_suggest_too_short_is_400(make_user):
    c = make_user(plan="ai", is_admin=True)
    r = c.post("/api/battle/suggest", json={"situation": "ну"})
    assert r.status_code == 400


def test_suggest_monthly_budget_is_429(make_user):
    c = make_user(plan="ai", is_admin=True)
    uid = c.user["id"]  # type: ignore[attr-defined]
    from app.usage import _period
    with Session(engine()) as s:
        s.add(models.UsageLedger(user_id=uid, period=_period(),
                                 micros=10_000_000))   # $10 — over any cap
        s.commit()
    r = c.post("/api/battle/suggest", json={"situation": "надо выиграть паузу"})
    assert r.status_code == 429


def test_suggest_empty_corpus_is_via_empty_and_free(make_user):
    c = make_user(plan="ai", is_admin=True)
    uid = c.user["id"]  # type: ignore[attr-defined]
    r = c.post("/api/battle/suggest", json={"situation": "что сказать инвестору"})
    assert r.status_code == 200
    assert r.json() == {"via": "empty", "picks": [], "intents": []}
    from app.usage import _period
    with Session(engine()) as s:      # no LLM call → no ledger row
        row = s.exec(models.UsageLedger.__table__.select().where(
            models.UsageLedger.user_id == uid,
            models.UsageLedger.period == _period())).first()
    assert row is None


def test_suggest_drops_out_of_range_pick(make_user, monkeypatch):
    monkeypatch.setattr(
        "app.scoring.battle_pick",
        lambda situation, items, intent=None: {
            "via": "llm", "intents": [],
            "picks": [{"n": 99, "note": "x"}, {"n": 0, "note": "y"}]})
    c = make_user(plan="ai", is_admin=True)
    uid = c.user["id"]  # type: ignore[attr-defined]
    bid, _pids = _seed_batch("bt-oor")
    _activate(uid, bid)
    r = c.post("/api/battle/suggest", json={"situation": "осадить оппонента"})
    assert r.status_code == 200
    assert r.json()["picks"] == []     # hallucinated numbers never 500


# ---- intents: the ranked-move axis --------------------------------------------

def test_suggest_returns_ranked_intents(make_user):
    c = make_user(plan="ai", is_admin=True)
    uid = c.user["id"]  # type: ignore[attr-defined]
    bid, _ = _seed_batch("bt-int")
    _activate(uid, bid)
    body = c.post("/api/battle/suggest",
                  json={"situation": "хочу мягко осадить коллегу"}).json()
    assert body["intents"] == ["pushback", "hold", "ask", "warm", "clarify"]  # stub ranking


def test_suggest_forced_intent_echoes_and_bad_intent_400(make_user):
    c = make_user(plan="ai", is_admin=True)
    uid = c.user["id"]  # type: ignore[attr-defined]
    bid, _ = _seed_batch("bt-int2")
    _activate(uid, bid)
    ok = c.post("/api/battle/suggest?intent=warm",
                json={"situation": "надо расположить собеседника"}).json()
    assert ok["intents"] == ["warm"] and ok["via"] == "llm"
    bad = c.post("/api/battle/suggest?intent=nonsense",
                 json={"situation": "надо расположить собеседника"})
    assert bad.status_code == 400


def test_intent_tags_are_phrase_level_db_entities_seeded_from_curated(make_user, monkeypatch):
    """The linked-entity system for Live mode: PhraseIntent (authoritative) +
    BatchIntent (fallback) are seeded from the curated map, re-seed is idempotent,
    manual tags survive, and filter_rows resolves phrase → batch → universal."""
    import app.intents as intents_mod
    from app.intents import (batch_intent_map, filter_rows, phrase_intent_map,
                             seed)
    make_user(plan="ai", is_admin=True)      # forces app/db init

    with Session(engine()) as s:
        # b_tag: a phrase carries its own move ("hold"); the batch is tagged "warm".
        # b_uni: no curated entry at all → universal (serves every move).
        b_tag = models.Batch(title="T", slug="it-tag", status="approved")
        b_uni = models.Batch(title="U", slug="it-uni", status="approved")
        s.add(b_tag); s.add(b_uni); s.commit()
        s.refresh(b_tag); s.refresh(b_uni)
        p_hold = models.Phrase(batch_id=b_tag.id, order_index=0, anchor="A", phrase_en="a")
        p_none = models.Phrase(batch_id=b_tag.id, order_index=1, anchor="B", phrase_en="b")
        s.add(p_hold); s.add(p_none); s.commit()
        s.refresh(p_hold); s.refresh(p_none)

        curated = {
            "batches": {"it-tag": ["warm"]},               # batch-level fallback
            "phrases": [{"slug": "it-tag", "oi": 0, "intents": ["hold"]}],
        }
        monkeypatch.setattr(intents_mod, "_curated", lambda: curated)

        r1 = seed(s)
        assert r1["phrase_rows_added"] == 1 and r1["batch_rows_added"] == 1
        assert seed(s)["phrase_rows_added"] == 0            # idempotent resync

        pmap = phrase_intent_map(s, {p_hold.id, p_none.id})
        bmap = batch_intent_map(s, {b_tag.id, b_uni.id})
        assert pmap[p_hold.id] == {"hold"}
        assert p_none.id not in pmap                        # phrase has no own tag
        assert bmap[b_tag.id] == {"warm"} and b_uni.id not in bmap

        # filter_rows: phrase tag is authoritative; untagged phrase falls back to
        # its batch; a batch with no rows is universal. Enough rows to beat _MIN_POOL.
        rows = ([(p_hold, None, b_tag)] * 5              # own tag "hold"
                + [(p_none, None, b_tag)] * 5            # falls back to batch "warm"
                + [(models.Phrase(batch_id=b_uni.id, order_index=0), None, b_uni)] * 5)
        hold = filter_rows(rows, "hold", pmap, bmap)      # p_hold rows + universal
        assert all(r[0] is not p_none for r in hold)      # p_none is "warm", excluded
        assert any(r[2].id == b_uni.id for r in hold)     # universal always in
        warm = filter_rows(rows, "warm", pmap, bmap)      # p_none (via batch) + universal
        assert all(r[0] is not p_hold for r in warm)      # p_hold is "hold", excluded

        # a curator's manual phrase tag joins the system and survives re-seed
        s.add(models.PhraseIntent(phrase_id=p_hold.id, intent="lead", source="manual"))
        # a stale auto row from the OLD taxonomy is migrated away on re-seed
        s.add(models.PhraseIntent(phrase_id=p_hold.id, intent="smooth", source="curated"))
        s.commit()
        seed(s)
        got = phrase_intent_map(s, {p_hold.id})[p_hold.id]
        assert got == {"hold", "lead"}                     # manual kept, smooth dropped


# ---- suggest-voice: audio in, STT + pick in one round trip -------------------

def test_suggest_voice_locked_for_free_and_core(make_user):
    make_user(plan="ai", is_admin=True)   # burn the first-user auto-admin slot
    for plan in ("free", "core"):
        c = make_user(plan=plan)
        r = c.post("/api/battle/suggest-voice",
                   files={"audio": ("clip.webm", b"xx", "audio/webm")})
        assert r.status_code == 403, f"{plan}: {r.text}"


def test_suggest_voice_happy_accrues_stt_plus_battle(make_user):
    c = make_user(plan="ai", is_admin=True)
    uid = c.user["id"]  # type: ignore[attr-defined]
    bid, pids = _seed_batch("bt-voice")
    _activate(uid, bid)
    r = c.post("/api/battle/suggest-voice?scope=learned",
               files={"audio": ("clip.webm", b"fake-bytes", "audio/webm")})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["heard"] == "stub transcript"        # conftest stt stub
    assert body["via"] == "llm" and body["picks"][0]["phrase_id"] == pids[0]

    from app.usage import EST_USD, _period
    with Session(engine()) as s:
        row = s.exec(models.UsageLedger.__table__.select().where(
            models.UsageLedger.user_id == uid,
            models.UsageLedger.period == _period())).first()
    want = int(round((EST_USD["stt"] + EST_USD["battle"]) * 1_000_000))
    assert row is not None and row.micros == want


def test_suggest_voice_short_transcript_charges_stt_only(make_user, monkeypatch):
    monkeypatch.setattr("app.stt.transcribe",
                        lambda raw, filename="c.webm", language=None: "ну")
    c = make_user(plan="ai", is_admin=True)
    uid = c.user["id"]  # type: ignore[attr-defined]
    r = c.post("/api/battle/suggest-voice",
               files={"audio": ("clip.webm", b"quiet", "audio/webm")})
    assert r.status_code == 200
    assert r.json() == {"via": "empty_stt", "heard": "ну", "picks": [], "intents": []}
    from app.usage import EST_USD, _period
    with Session(engine()) as s:
        row = s.exec(models.UsageLedger.__table__.select().where(
            models.UsageLedger.user_id == uid,
            models.UsageLedger.period == _period())).first()
    assert row is not None and row.micros == int(round(EST_USD["stt"] * 1_000_000))


# ---- the learned-first pool order --------------------------------------------

def test_pool_orders_learned_before_touched_before_new(make_user):
    c = make_user(plan="ai", is_admin=True)
    uid = c.user["id"]  # type: ignore[attr-defined]
    bid, pids = _seed_batch("bt-rank", n=4)
    _activate(uid, bid)
    _stat(uid, pids[3], bid, status="familiar", attempts=5)
    _stat(uid, pids[1], bid, status="automatic", attempts=9)
    _stat(uid, pids[2], bid, status="new", attempts=1)     # touched but not learned

    with Session(engine()) as s:
        ordered = [p.id for p, _st, _b in _sort_learned_first(_user_rows(s, uid))]
    assert ordered == [pids[1], pids[3], pids[2], pids[0]]
