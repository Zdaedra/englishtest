"""QA pre-App-Store §11a "инварианты и гонки" (+ the paywall half of §4).

Each block is one row of the plan: a rule the app may never break, attacked the
way the plan says — repeats, races (two requests released together by a barrier,
so the interleaving is deterministic, not luck), stale/out-of-order inputs, a
client that lies, a plan that has expired.

Plain tests = the rule holds. `xfail(strict=True, reason="BUG: ...")` = a real
defect reproduced 2026-11-27; once fixed it XPASSes, strict turns the suite red,
and the marker must be dropped (the test then guards the fix).
"""
import ast
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
import sqlmodel
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app import models, usage
from app.db import engine
from app.entitlements import ENTITLEMENTS, FOCUS_CAP
from app.main import app
from conftest import commit_sample_batch, phrase_ids

AUDIO = {"audio": ("clip.webm", b"\x00" * 2048, "audio/webm")}
AI_MONTHLY = "net.executiveenglish.ai.monthly"


# ---- helpers -----------------------------------------------------------------

def _uid(c) -> int:
    return c.user["id"]  # type: ignore[attr-defined]


def _clone(c, raise_errors: bool = True) -> TestClient:
    """A second client carrying the same credentials (own portal / thread).
    raise_errors=False turns a server crash into a 500 response instead of an
    exception inside a worker thread (needed by the race tests)."""
    t = TestClient(app, raise_server_exceptions=raise_errors)
    t.headers.update(c.headers)
    return t


def _free_showcase(admin) -> int:
    bid = commit_sample_batch(admin)
    assert admin.post(f"/api/batches/{bid}/free").status_code == 200
    return bid


def _expire(uid: int, days: int = 2) -> None:
    """plan column still says 'ai', the Apple period ended `days` ago (a lost
    EXPIRED webhook). Not linked to a transaction, so /me never calls Apple."""
    with Session(engine()) as s:
        u = s.get(models.User, uid)
        u.plan, u.plan_source = "ai", "apple"
        u.plan_expires_at = datetime.now(timezone.utc) - timedelta(days=days)
        s.add(u)
        s.commit()


def _bare_batches(n: int) -> list[int]:
    with Session(engine()) as s:
        rows = [models.Batch(title=f"T{i}", slug=f"bare-{i}", status="approved")
                for i in range(n)]
        s.add_all(rows)
        s.commit()
        return [b.id for b in rows]


def _parallel(*calls):
    """Run the calls in parallel threads; return their results in order."""
    out: list = [None] * len(calls)

    def run(i, f):
        out[i] = f()

    ts = [threading.Thread(target=run, args=(i, f)) for i, f in enumerate(calls)]
    for t in ts:
        t.start()
    for t in ts:
        t.join(30)
    return out


def _barrier_before(m, owner, attr: str, parties: int = 2) -> None:
    """Hold every caller of owner.attr until `parties` of them arrived — i.e.
    both racing requests have done their check before either one writes."""
    orig = getattr(owner, attr)
    bar = threading.Barrier(parties, timeout=5)

    def held(*a, **k):
        try:
            bar.wait()
        except threading.BrokenBarrierError:
            pass
        return orig(*a, **k)

    m.setattr(owner, attr, held)


def _notif(ntype, product, expires_ms, orig):
    class _Tx:
        productId = product
        expiresDate = expires_ms
        originalTransactionId = orig

    class _NType:
        name = ntype

    class _Data:
        signedTransactionInfo = "signed"

    class _Notif:
        notificationType = _NType()
        rawNotificationType = ntype
        data = _Data()

    return _Notif(), _Tx()


def _stub_verifier(monkeypatch, orig_tx="orig-shared", product=AI_MONTHLY,
                   expires_ms=1893456000000):
    import app.routers.billing as billing

    class _Tx:
        productId = product
        expiresDate = expires_ms
        originalTransactionId = orig_tx

    class _Verifier:
        def verify_and_decode_signed_transaction(self, jws):
            return _Tx()

    monkeypatch.setattr(billing, "_build_verifiers", lambda: [_Verifier()])


def _ms(dt: datetime) -> int:
    return int(dt.timestamp() * 1000)


# ==== Rule: a paid feature can't be had for free ==============================
# "Подмена плана в клиенте, старый кэш, прямой запрос к эндпоинту": the server
# never reads a plan from the client, so the only question is whether EVERY door
# asks effective_plan. Sweep them per plan state, collect all misses at once.

def _content_denied(c, bid, pid) -> list[str]:
    miss = []
    d = c.get(f"/api/batches/{bid}").json()
    if not d.get("locked") or d.get("phrases"):
        miss.append("batch detail served paid content")
    if bid in {r["batch_id"] for r in c.get("/api/batches/phrases").json()}:
        miss.append("phrase index leaked a paid topic")
    for name, r in (
        ("phrase audio", c.get(f"/api/batches/phrase/{pid}/audio")),
        ("mnemo audio", c.get(f"/api/batches/{bid}/mnemo/audio?layout=anchors")),
        ("gapless session", c.post("/api/sessions", json={"batch_id": bid})),
        ("activate", c.put(f"/api/progress/{bid}", json={"activated": True})),
    ):
        if r.status_code != 403:
            miss.append(f"{name}: {r.status_code}")
    if c.get(f"/api/training/deck?batch_ids={bid}").json() != []:
        miss.append("deck drew from a paid topic")
    return miss


def _ai_denied(c, bid, pid) -> list[str]:
    miss = []
    calls = (
        ("answer-text", lambda: c.post("/api/training/answer-text", json={
            "session_id": "s", "phrase_id": pid, "transcript": "x"})),
        ("answer", lambda: c.post("/api/training/answer", files=AUDIO,
                                  data={"phrase_id": pid, "session_id": "s"})),
        ("score-phrase", lambda: c.post("/api/training/score-phrase", files=AUDIO,
                                        data={"phrase_id": pid})),
        ("score-anchor", lambda: c.post("/api/training/score-anchor", files=AUDIO,
                                        data={"phrase_id": pid})),
        ("score-sequence", lambda: c.post("/api/training/score-sequence", files=AUDIO,
                                          data={"batch_id": bid})),
        ("coach", lambda: c.post("/api/training/coach", json={
            "phrase_id": pid, "transcript": "x", "score": 4})),
        ("battle suggest", lambda: c.post("/api/battle/suggest",
                                          json={"situation": "they push on price"})),
        ("battle suggest-voice", lambda: c.post("/api/battle/suggest-voice", files=AUDIO)),
        ("arena scenario", lambda: c.post("/api/practice/scenario")),
        ("call analyzer", lambda: c.post("/api/analyzer/call",
                                         json={"text": "x" * 80})),
    )
    for name, call in calls:
        r = call()
        if r.status_code != 403:
            miss.append(f"{name}: {r.status_code}")
    return miss


def _import_denied(c) -> list[str]:
    from conftest import SAMPLE
    from app import importer
    miss = []
    if c.post("/api/imports/parse", json={"raw_text": SAMPLE}).status_code != 403:
        miss.append("import parse open")
    body = importer.parse(SAMPLE).batch.model_dump()
    if c.post("/api/imports/commit", json=body).status_code != 403:
        miss.append("import commit open")
    return miss


@pytest.mark.parametrize("state", ["free", "expired_ai"])
def test_paid_doors_closed_for_free_and_lapsed(make_user, state):
    admin = make_user(plan="ai", is_admin=True)
    bid = commit_sample_batch(admin)
    pid = phrase_ids(admin, bid)[0]
    c = make_user(plan="free" if state == "free" else "ai")
    if state == "expired_ai":
        _expire(_uid(c))
    me = c.get("/api/auth/me").json()
    assert me["plan"] == "free" and me["entitlements"]["voice_answer"] is False
    miss = _content_denied(c, bid, pid) + _ai_denied(c, bid, pid) + _import_denied(c)
    assert miss == [], f"{state}: " + "; ".join(miss)


def test_core_gets_content_and_import_but_no_ai(make_user):
    admin = make_user(plan="ai", is_admin=True)
    bid = commit_sample_batch(admin)
    pid = phrase_ids(admin, bid)[0]
    core = make_user(plan="core")
    assert core.get(f"/api/batches/{bid}").json()["locked"] is False
    assert core.post("/api/sessions", json={"batch_id": bid}).status_code == 200
    from conftest import SAMPLE
    assert core.post("/api/imports/parse", json={"raw_text": SAMPLE}).status_code == 200
    miss = _ai_denied(core, bid, pid)
    assert miss == [], "core reached an ai-only door: " + "; ".join(miss)


def test_free_showcase_topic_is_fully_open_to_free(make_user):
    admin = make_user(plan="ai", is_admin=True)
    bid = _free_showcase(admin)
    pid = phrase_ids(admin, bid)[0]
    free = make_user(plan="free")
    assert free.get(f"/api/batches/{bid}").json()["phrases"]
    assert free.post("/api/training/answer-text", json={
        "session_id": "s", "phrase_id": pid, "transcript": "x"}).status_code == 200


def test_no_gate_reads_the_raw_plan_column():
    """Static guard for the 2026-11-26 class of bug (15 gates read user.plan, so
    a lapsed subscription kept paid topics open): outside billing (which owns the
    column) and effective_plan itself, nothing in app/ may READ `<x>.plan`."""
    root = Path(__file__).resolve().parents[1] / "app"
    hits = []
    for f in sorted(root.rglob("*.py")):
        if f.name == "billing.py":
            continue
        tree = ast.parse(f.read_text(encoding="utf-8"))
        for fn in ast.walk(tree):
            if not isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            if fn.name == "effective_plan":
                continue
            for node in ast.walk(fn):
                if (isinstance(node, ast.Attribute) and node.attr == "plan"
                        and isinstance(node.ctx, ast.Load)):
                    hits.append(f"{f.relative_to(root.parent)}:{node.lineno} in {fn.name}")
    assert hits == [], "raw .plan read (use entitlements.effective_plan): " + ", ".join(hits)


# ---- paid content still reachable for free (bugs) -----------------------------

def test_battle_corpus_all_scope_hides_locked_topics_from_free(make_user):
    admin = make_user(plan="ai", is_admin=True)
    paid = commit_sample_batch(admin)
    free = make_user(plan="free")
    got = {r["batch_id"] for r in free.get("/api/battle/corpus?scope=all").json()}
    assert paid not in got


@pytest.mark.parametrize("vector", ["swipe", "lesson_flag"])
def test_battle_corpus_learned_scope_hides_locked_topics_from_free(make_user, vector):
    admin = make_user(plan="ai", is_admin=True)
    paid = commit_sample_batch(admin)
    pid = phrase_ids(admin, paid)[0]
    free = make_user(plan="free")
    if vector == "swipe":
        free.post("/api/training/swipe", json={
            "session_id": "s", "phrase_id": pid, "swipe_direction": "left"})
    else:
        free.put(f"/api/progress/{paid}", json={"l1_listened": True})
    got = {r["batch_id"] for r in free.get("/api/battle/corpus").json()}
    assert paid not in got


def test_batch_export_is_closed_for_locked_topics(make_user):
    admin = make_user(plan="ai", is_admin=True)
    paid = commit_sample_batch(admin)
    free = make_user(plan="free")
    r = free.get(f"/api/batches/{paid}/export")
    assert r.status_code in (403, 404) or not r.json().get("phrases")


def test_prompt_audio_is_metered(make_user):
    make_user(plan="ai", is_admin=True)
    free = make_user(plan="free")
    r = free.post("/api/practice/prompt-audio", data={"text": "Any text at all.", "lang": "en"})
    assert r.status_code == 200
    with Session(engine()) as s:
        assert usage.month_cost_usd(s, _uid(free)) > 0


# ==== Rule: one payment never makes two subscriptions =========================

def test_same_transaction_twice_on_one_account_is_idempotent(make_user, monkeypatch):
    """Double tap, retry after a timeout, restore on a second device."""
    _stub_verifier(monkeypatch, orig_tx="orig-1")
    make_user(plan="ai", is_admin=True)
    c = make_user(plan="free")
    for _ in range(3):
        r = c.post("/api/billing/verify", json={"signed_transaction": "jws"})
        assert r.status_code == 200 and r.json()["plan"] == "ai"
    with Session(engine()) as s:
        linked = s.exec(select(models.User).where(
            models.User.apple_original_tx_id == "orig-1")).all()
    assert [u.id for u in linked] == [_uid(c)]
    # A second device of the SAME account: same answer, still one link.
    r = _clone(c).post("/api/billing/verify", json={"signed_transaction": "jws"})
    assert r.status_code == 200 and r.json()["plan"] == "ai"


def test_sign_in_sync_does_not_unlock_a_second_account(make_user, monkeypatch):
    """Was BUG (high), fixed 2026-11-27 (billing._why_not_apply): the app re-posts
    every device entitlement on each sign-in, and /verify applied it to whoever
    was signed in — one Apple subscription unlocked every account on that iPhone.
    A silent sync of a subscription linked elsewhere is now ignored."""
    _stub_verifier(monkeypatch, orig_tx="orig-shared")
    make_user(plan="ai", is_admin=True)
    payer = make_user(plan="free")
    other = make_user(plan="free")
    r = payer.post("/api/billing/verify", json={"signed_transaction": "jws"})
    assert r.json()["plan"] == "ai"
    other.post("/api/billing/verify", json={"signed_transaction": "jws", "source": "sync"})
    assert other.get("/api/auth/me").json()["plan"] == "free"
    assert payer.get("/api/auth/me").json()["plan"] == "ai"


@pytest.mark.parametrize("source", ["restore", None])
def test_restore_moves_a_subscription_instead_of_copying_it(make_user, monkeypatch, source):
    _stub_verifier(monkeypatch, orig_tx="orig-moved")
    make_user(plan="ai", is_admin=True)
    payer = make_user(plan="free")
    other = make_user(plan="free")
    assert payer.post("/api/billing/verify", json={"signed_transaction": "jws"}).json()["plan"] == "ai"
    body = {"signed_transaction": "jws"} | ({"source": source} if source else {})
    other.post("/api/billing/verify", json=body)
    plans = [c.get("/api/auth/me").json()["plan"] for c in (payer, other)]
    assert plans.count("ai") == 1, f"one payment, two paid accounts: {plans}"


# ==== Rule: paid access doesn't vanish without a reason =======================

def test_paid_access_survives_restart_and_a_new_device(make_user, monkeypatch):
    """State lives in the DB; in-process caches (self-repair throttle) are empty
    after a restart and that must not flip anyone to free."""
    import app.routers.billing as billing
    _stub_verifier(monkeypatch, orig_tx="orig-r", expires_ms=_ms(
        datetime.now(timezone.utc) + timedelta(days=20)))
    make_user(plan="ai", is_admin=True)
    c = make_user(plan="free")
    assert c.post("/api/billing/verify", json={"signed_transaction": "j"}).json()["plan"] == "ai"
    monkeypatch.setattr(billing, "_next_try", {})          # "restart"
    assert _clone(c).get("/api/auth/me").json()["plan"] == "ai"   # "new device"


def test_late_expired_notification_does_not_cut_a_renewed_subscriber(make_user, monkeypatch, client):
    import app.routers.billing as billing
    make_user(plan="ai", is_admin=True)
    c = make_user(plan="ai")
    now = datetime.now(timezone.utc)
    with Session(engine()) as s:
        u = s.get(models.User, _uid(c))
        u.plan_source, u.apple_original_tx_id = "apple", "orig-late"
        u.plan_expires_at = now + timedelta(days=29)       # renewal already applied
        s.add(u)
        s.commit()
    stale = _notif("EXPIRED", AI_MONTHLY, _ms(now - timedelta(days=1)), "orig-late")
    monkeypatch.setattr(billing, "_decode_notification", lambda signed: stale)
    monkeypatch.setattr(billing, "_build_verifiers", lambda: ["stub"])
    assert client.post("/api/billing/apple-notifications",
                       json={"signedPayload": "x"}).status_code == 200
    assert c.get("/api/auth/me").json()["plan"] == "ai"


# ==== Rule: one answer / one lesson is never counted twice ====================
# Note: /answer, /answer-text, /score-* and /swipe carry no idempotency key, so a
# retried POST after a dropped response is indistinguishable from a new attempt
# and IS scored again (see the QA report). Where the request does carry an id,
# repeating it must be a no-op:

def test_exam_pass_repeated_keeps_the_first_completion(make_user):
    admin = make_user(plan="ai", is_admin=True)
    bid = commit_sample_batch(admin)
    u = make_user(plan="core")
    with Session(engine()) as s:
        s.add(models.SequenceAttempt(user_id=_uid(u), batch_id=bid, score=9))
        s.commit()
    first = u.put(f"/api/progress/{bid}", json={"l3_passed": True}).json()
    again = u.put(f"/api/progress/{bid}", json={"l3_passed": True}).json()
    assert first["completed_at"] and again["completed_at"] == first["completed_at"]
    with Session(engine()) as s:
        assert len(s.exec(select(models.BatchProgress).where(
            models.BatchProgress.user_id == _uid(u))).all()) == 1


def test_repeated_not_success_confirm_lapses_once(make_user):
    admin = make_user(plan="ai", is_admin=True)
    bid = commit_sample_batch(admin)
    pid = phrase_ids(admin, bid)[0]
    u = make_user(plan="ai")
    ev = u.post("/api/training/answer-text", json={
        "session_id": "s", "phrase_id": pid, "transcript": "x"}).json()  # stub score 9

    def ease():
        with Session(engine()) as s:
            return s.exec(select(models.UserPhraseStat).where(
                models.UserPhraseStat.user_id == _uid(u),
                models.UserPhraseStat.phrase_id == pid)).one().ease

    body = {"event_id": ev["event_id"], "manual_success": False}
    assert u.post("/api/training/answer/confirm", json=body).status_code == 200
    once = ease()
    assert u.post("/api/training/answer/confirm", json=body).status_code == 200
    assert ease() == once


# ==== Rule: progress never goes backwards without an explicit reset ===========

def test_partial_patch_never_clears_other_progress(make_user):
    admin = make_user(plan="ai", is_admin=True)
    bid = commit_sample_batch(admin)
    u = make_user(plan="core")
    assert u.put(f"/api/progress/{bid}", json={
        "l1_listened": True, "l1_retold": True, "l3_s1": True}).status_code == 200
    # another device sends only what IT changed (path order) — nothing else moves
    r = _clone(u).put(f"/api/progress/{bid}", json={"path_rank": 3}).json()
    assert r["l1_listened"] and r["l1_retold"] and r["l3_s1"] and r["activated"]


def test_best_retell_score_never_goes_down(make_user):
    admin = make_user(plan="ai", is_admin=True)
    bid = commit_sample_batch(admin)
    u = make_user(plan="core")
    u.put(f"/api/progress/{bid}", json={"l1_retold": True, "l1_best_seq": 9.0})
    stale_device = _clone(u)
    stale_device.put(f"/api/progress/{bid}", json={"l1_retold": True, "l1_best_seq": 6.0})
    assert u.get(f"/api/progress/{bid}").json()["l1_best_seq"] == 9.0


# ==== Rule: an 11th active topic is never created ==============================

def test_focus_cap_holds_for_rapid_sequential_activation(make_user):
    make_user(plan="ai", is_admin=True)
    ids = _bare_batches(FOCUS_CAP + 3)
    u = make_user(plan="core")
    codes = [u.put(f"/api/progress/{b}", json={"activated": True}).status_code for b in ids]
    assert codes.count(200) == FOCUS_CAP and set(codes[FOCUS_CAP:]) == {403}


@pytest.mark.xfail(strict=True, reason=(
    "BUG (low, race): progress.py counts the active set, then inserts, with nothing "
    "serialising the two — two activations that both read 9 both commit, leaving 11 "
    "topics in focus. Fix: re-count after flush inside the same transaction "
    "(BEGIN IMMEDIATE) and roll back if over the cap"))
def test_focus_cap_holds_under_concurrent_activation(make_user, monkeypatch):
    make_user(plan="ai", is_admin=True)
    ids = _bare_batches(FOCUS_CAP + 1)
    u = make_user(plan="core")
    with Session(engine()) as s:
        for b in ids[:FOCUS_CAP - 1]:
            s.add(models.BatchProgress(user_id=_uid(u), batch_id=b,
                                       on_path=True, activated=True))
        s.commit()
    c1, c2 = _clone(u, False), _clone(u, False)
    with monkeypatch.context() as m:      # scoped: keeps the autouse network stubs
        _barrier_before(m, sqlmodel.Session, "commit")
        r1, r2 = _parallel(
            lambda: c1.put(f"/api/progress/{ids[-2]}", json={"activated": True}),
            lambda: c2.put(f"/api/progress/{ids[-1]}", json={"activated": True}))
    with Session(engine()) as s:
        active = len(s.exec(select(models.BatchProgress).where(
            models.BatchProgress.user_id == _uid(u),
            models.BatchProgress.activated == True,     # noqa: E712
            models.BatchProgress.l3_passed == False)).all())  # noqa: E712
    assert active <= FOCUS_CAP, f"{active} topics in focus ({r1.status_code}, {r2.status_code})"


# ==== Rule: the daily limit can't be bypassed =================================

def test_daily_cap_ignores_the_client_clock(make_user):
    """The day boundary is the SERVER's UTC midnight: no client timezone or date
    reaches _check_rate, so moving the phone's clock changes nothing."""
    admin = make_user(plan="ai", is_admin=True)
    bid = _free_showcase(admin)
    pid = phrase_ids(admin, bid)[0]
    u = make_user(plan="free")
    with Session(engine()) as s:
        for _ in range(ENTITLEMENTS["free"]["scored_per_day"]):
            s.add(models.PhraseAttempt(user_id=_uid(u), phrase_id=pid, score=5))
        s.commit()
    tomorrow = (datetime.now(timezone.utc) + timedelta(days=1)).strftime(
        "%a, %d %b %Y %H:%M:%S GMT")
    r = u.post("/api/training/answer-text?tz_offset=-840",
               headers={"Date": tomorrow},
               json={"session_id": "s", "phrase_id": pid, "transcript": "x"})
    assert r.status_code == 429


@pytest.mark.xfail(strict=True, reason=(
    "BUG (low, race): training._check_rate counts today's attempts and the write "
    "happens later in the request; parallel requests that all read N-1 all pass, so "
    "the daily scoring cap overshoots by the number of in-flight requests (each one "
    "a paid STT/LLM call)"))
def test_daily_cap_holds_under_parallel_requests(make_user, monkeypatch):
    admin = make_user(plan="ai", is_admin=True)
    bid = _free_showcase(admin)
    pid = phrase_ids(admin, bid)[0]
    u = make_user(plan="free")
    cap = ENTITLEMENTS["free"]["scored_per_day"]
    with Session(engine()) as s:
        for _ in range(cap - 1):
            s.add(models.PhraseAttempt(user_id=_uid(u), phrase_id=pid, score=5))
        s.commit()
    p2 = phrase_ids(admin, bid)[1]      # two phrases: keep the stat race out of it
    c1, c2 = _clone(u, False), _clone(u, False)
    with monkeypatch.context() as m:
        # month_cost_usd is called right AFTER the daily count inside _check_rate,
        # so both requests have counted N-1 before either one writes.
        _barrier_before(m, usage, "month_cost_usd")
        r1, r2 = _parallel(
            lambda: c1.post("/api/training/answer-text", json={
                "session_id": "s", "phrase_id": pid, "transcript": "x"}),
            lambda: c2.post("/api/training/answer-text", json={
                "session_id": "s", "phrase_id": p2, "transcript": "x"}))
    assert {r1.status_code, r2.status_code} <= {200, 429}
    with Session(engine()) as s:
        n = len(s.exec(select(models.PhraseAttempt).where(
            models.PhraseAttempt.user_id == _uid(u))).all())
    assert n <= cap, f"{n} scored attempts today, cap {cap}"


@pytest.mark.xfail(strict=True, reason=(
    "BUG (low): /answer, /answer-text and /score-phrase get-or-create the per-phrase "
    "stat without the AUDIT-1 IntegrityError retry that /swipe and PUT /progress "
    "have. Two first answers on a never-seen phrase in flight together (double "
    "tap, two devices, Arena + deck) -> the loser dies with 500 'UNIQUE constraint "
    "failed: userphrasestat' after its paid STT/LLM call; the answer is lost"))
def test_concurrent_first_answers_on_a_new_phrase_both_land(make_user):
    from sqlalchemy import event
    admin = make_user(plan="ai", is_admin=True)
    bid = commit_sample_batch(admin)
    pid = phrase_ids(admin, bid)[0]
    u = make_user(plan="ai")
    bar = threading.Barrier(2, timeout=5)
    held: set[int] = set()

    def hold(*_a):
        # The request's first flush (stat + attempt) comes right after _stat()
        # looked for the row and found none. Holding both requests there, before
        # any SQL is written, means both saw "no stat yet". One-shot per thread:
        # the commit flush must not wait again (the first writer holds SQLite's
        # write lock until it commits).
        me = threading.get_ident()
        if me in held:
            return
        held.add(me)
        try:
            bar.wait()
        except threading.BrokenBarrierError:
            pass

    event.listen(sqlmodel.Session, "before_flush", hold)
    try:
        c1, c2 = _clone(u, False), _clone(u, False)
        body = {"session_id": "s", "phrase_id": pid, "transcript": "x"}
        r1, r2 = _parallel(lambda: c1.post("/api/training/answer-text", json=body),
                           lambda: c2.post("/api/training/answer-text", json=body))
    finally:
        event.remove(sqlmodel.Session, "before_flush", hold)
    assert (r1.status_code, r2.status_code) == (200, 200)
    with Session(engine()) as s:
        st = s.exec(select(models.UserPhraseStat).where(
            models.UserPhraseStat.user_id == _uid(u))).one()
    assert st.attempts == 2


# ==== Rule: the server trusts nothing the client says about identity/plan ======

def test_register_ignores_client_supplied_plan_and_admin(client):
    client.post("/api/auth/register", json={"email": "owner@example.com",
                                            "password": "password123"})
    r = client.post("/api/auth/register", json={
        "email": "sneaky@example.com", "password": "password123",
        "plan": "ai", "is_admin": True, "plan_expires_at": "2099-01-01"})
    assert r.status_code == 200
    assert r.json()["plan"] == "free" and r.json()["is_admin"] is False


def test_body_user_id_and_profile_plan_are_ignored(make_user):
    admin = make_user(plan="ai", is_admin=True)
    bid = _free_showcase(admin)
    pid = phrase_ids(admin, bid)[0]
    victim = make_user(plan="free")
    attacker = make_user(plan="free")
    attacker.post("/api/training/swipe", json={
        "session_id": "s", "phrase_id": pid, "swipe_direction": "left",
        "user_id": _uid(victim)})
    attacker.post("/api/auth/learn-profile", json={"profile": {"plan": "ai"},
                                                   "plan": "ai"})
    with Session(engine()) as s:
        owners = {st.user_id for st in s.exec(select(models.UserPhraseStat)).all()}
    assert owners == {_uid(attacker)}
    assert attacker.get("/api/auth/me").json()["plan"] == "free"
