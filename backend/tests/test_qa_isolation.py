"""QA pre-App-Store §9 "изоляция аккаунтов" + the isolation row of §11a.

What this file pins, by the test plan's rows:
- two accounts on one topic, progress/scores that never cross accounts, a fresh
  third account (full library, nothing active), limits counted per account;
- the DB schema against the models (the class of bug behind two prod incidents);
- "прямой запрос по чужому id": every route that takes a batch / phrase / event /
  session id, called by ANOTHER account against a private import;
- account lifecycle: logout, old token, delete, id reuse.

Plain tests = the rule holds. `xfail(strict=True, reason="BUG: ...")` = a real
defect reproduced 2026-11-27; once fixed it XPASSes, strict turns the suite red,
and the marker must be dropped (the test then guards the fix).
"""
import os
import sqlite3
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, select

from app import models
from app.config import get_settings
from app.db import engine
from app.main import app
from conftest import commit_sample_batch, phrase_ids

AUDIO = {"audio": ("clip.webm", b"\x00" * 2048, "audio/webm")}


# ---- helpers -----------------------------------------------------------------

def _uid(c) -> int:
    return c.user["id"]  # type: ignore[attr-defined]


def _bearer(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _free_showcase(admin) -> int:
    """A catalog topic flagged as THE free one (open to every plan, mic included)."""
    bid = commit_sample_batch(admin)
    assert admin.post(f"/api/batches/{bid}/free").status_code == 200
    return bid


def _tenants(make_user, b_plan="ai"):
    """Owner (bootstrap admin), account A with a PRIVATE import, account B."""
    admin = make_user(plan="ai", is_admin=True)
    a = make_user(plan="ai")
    b = make_user(plan=b_plan)
    a_bid = commit_sample_batch(a)              # non-admin commit => owner_id = A
    with Session(engine()) as s:
        assert s.get(models.Batch, a_bid).owner_id == _uid(a)
        a_pids = [p.id for p in s.exec(select(models.Phrase).where(
            models.Phrase.batch_id == a_bid)).all()]
    return admin, a, b, a_bid, a_pids


def _a_phrase_texts(a_bid: int) -> set[str]:
    with Session(engine()) as s:
        return {p.phrase_en for p in s.exec(select(models.Phrase).where(
            models.Phrase.batch_id == a_bid)).all()}


# ==== §9 row 1: two accounts activate the same topic ==========================

def test_two_accounts_activate_the_same_topic(make_user):
    """Regression of the 2026-11-27 prod bug (UNIQUE index on batch_id let only
    ONE account in the system hold progress per topic): both must land."""
    admin = make_user(plan="ai", is_admin=True)
    bid = commit_sample_batch(admin)
    u1 = make_user(plan="core")
    u2 = make_user(plan="core")
    for u in (u1, u2):
        r = u.put(f"/api/progress/{bid}", json={"activated": True})
        assert r.status_code == 200, r.text
    for u in (u1, u2):
        rows = {r["batch_id"]: r for r in u.get("/api/progress").json()}
        assert rows[bid]["activated"] is True and rows[bid]["on_path"] is True
    with Session(engine()) as s:
        n = len(s.exec(select(models.BatchProgress).where(
            models.BatchProgress.batch_id == bid)).all())
    assert n == 2


# ==== §9 row 2: progress and scores never leak between accounts ===============

def test_progress_and_scores_stay_with_their_account(make_user):
    admin = make_user(plan="ai", is_admin=True)
    bid = commit_sample_batch(admin)
    pid = phrase_ids(admin, bid)[0]
    u1 = make_user(plan="ai")
    u2 = make_user(plan="ai")

    assert u1.put(f"/api/progress/{bid}",
                  json={"activated": True, "l1_listened": True,
                        "l1_best_seq": 8.0}).status_code == 200
    r = u1.post("/api/training/answer-text", json={
        "session_id": "u1-sess", "phrase_id": pid, "transcript": "x"})
    assert r.status_code == 200, r.text
    event_id = r.json()["event_id"]
    assert u1.post("/api/training/swipe", json={
        "session_id": "u1-sess", "phrase_id": pid,
        "swipe_direction": "right"}).status_code == 200

    # u2 sees none of it — through every read that exposes per-user state.
    assert u2.get("/api/progress").json() == []
    stub = u2.get(f"/api/progress/{bid}").json()
    assert stub["activated"] is False and stub["l1_listened"] is False
    m2 = {r["batch_id"]: r for r in u2.get("/api/training/mastery").json()}
    assert m2[bid]["attempts"] == 0 and m2[bid]["avg_score"] is None
    rot = {r["phrase_id"]: r for r in u2.get(f"/api/training/rotation/{bid}").json()}
    assert rot[pid]["attempts"] == 0 and rot[pid]["avg_score"] is None
    assert u2.get("/api/progress/streak").json()["streak"] == 0
    assert u2.get("/api/training/weekly").json()["attempts"] == 0
    assert u2.get("/api/battle/corpus").json() == []
    # u1's session id and event id, replayed by u2, reach nothing of u1's.
    assert u2.get("/api/training/session/u1-sess/summary").json()["cards_total"] == 0
    assert u2.post("/api/training/answer/confirm", json={
        "event_id": event_id, "manual_success": False}).status_code == 404
    exp = u2.get("/api/auth/export").json()
    for table in ("UserPhraseStat", "PhraseAttempt", "TrainingEvent", "BatchProgress"):
        assert all(row["user_id"] == _uid(u2) for row in exp[table]), table
    # ...and u1 still has all of it.
    assert u1.get(f"/api/progress/{bid}").json()["l1_best_seq"] == 8.0
    m1 = {r["batch_id"]: r for r in u1.get("/api/training/mastery").json()}
    assert m1[bid]["attempts"] == 1


# ==== §9 row 3: a third account on a fresh device =============================

def test_fresh_account_sees_full_library_and_nothing_active(make_user):
    admin = make_user(plan="ai", is_admin=True)
    free_bid = _free_showcase(admin)
    paid = [commit_sample_batch(admin) for _ in range(3)]
    for u in (make_user(plan="core"), make_user(plan="core")):   # others are busy
        for bid in paid:
            assert u.put(f"/api/progress/{bid}",
                         json={"activated": True}).status_code == 200

    fresh = make_user(plan="free")
    lib = {b["id"]: b for b in fresh.get("/api/batches").json()}
    assert set(lib) == {free_bid, *paid}, "library is not the full catalog"
    assert lib[free_bid]["locked"] is False
    assert all(lib[b]["locked"] for b in paid)
    assert fresh.get("/api/progress").json() == []          # nothing active
    mastery = fresh.get("/api/training/mastery").json()
    assert {r["batch_id"] for r in mastery} == set(lib)
    assert all(r["attempts"] == 0 and r["due"] == 0 for r in mastery)
    assert {r["batch_id"] for r in fresh.get("/api/batches/phrases").json()} == {free_bid}


# ==== §9 row 4: DB schema against the models ==================================
# Twice in a row the prod bug was schema drift the model no longer declared: a
# legacy NOT NULL column on `phrase` (broke every import) and a single-user UNIQUE
# index on batchprogress.batch_id (one account per topic). This check runs on the
# fresh test DB always, and on a COPY of the prod DB when QA_SCHEMA_DB points at
# one:  QA_SCHEMA_DB=/tmp/app-copy.db .venv/bin/python -m pytest -k schema

# Unique indexes created by db._migrate on purpose (not declared on the models).
_MIGRATION_UNIQUE = {"ux_stat_user_phrase", "ux_progress_user_batch"}


def schema_violations(db_path: str) -> list[str]:
    con = sqlite3.connect(db_path)
    out: list[str] = []
    try:
        for table in SQLModel.metadata.sorted_tables:
            info = con.execute(f"PRAGMA table_info('{table.name}')").fetchall()
            if not info:
                out.append(f"{table.name}: table missing")
                continue
            db_cols = {r[1]: r for r in info}
            model_cols = {c.name for c in table.columns}
            for col in sorted(model_cols - db_cols.keys()):
                out.append(f"{table.name}.{col}: declared by the model, missing in the DB")
            for col in sorted(db_cols.keys() - model_cols):
                notnull, default = db_cols[col][3], db_cols[col][4]
                if notnull and default is None:
                    out.append(f"{table.name}.{col}: legacy NOT NULL column with no "
                               "default — every INSERT through the model fails")
            declared = {ix.name: [c.name for c in ix.columns]
                        for ix in table.indexes if ix.unique}
            per_user = "user_id" in model_cols
            for _seq, name, unique, origin, *_ in con.execute(
                    f"PRAGMA index_list('{table.name}')").fetchall():
                if not unique or origin == "pk":
                    continue
                cols = [r[2] for r in con.execute(f"PRAGMA index_info('{name}')")]
                if per_user and "user_id" not in cols:
                    out.append(f"{table.name}: UNIQUE index {name}({', '.join(cols)}) on a "
                               "per-user table without user_id — one account blocks all others")
                elif name not in declared and name not in _MIGRATION_UNIQUE:
                    out.append(f"{table.name}: UNIQUE index {name}({', '.join(cols)}) "
                               "not declared by the model")
    finally:
        con.close()
    return out


@pytest.mark.parametrize("which", ["fresh", "prod_copy"])
def test_schema_matches_models(which):
    if which == "fresh":
        path = str(get_settings().db_path)
    else:
        path = os.environ.get("QA_SCHEMA_DB", "")
        if not path:
            pytest.skip("set QA_SCHEMA_DB to a copy of the prod SQLite file")
    assert schema_violations(path) == []


def test_schema_check_catches_the_known_prod_drift(tmp_path):
    """The checker itself must see both historic prod bugs."""
    db = tmp_path / "drift.db"
    from sqlalchemy import create_engine
    eng = create_engine(f"sqlite:///{db}")
    SQLModel.metadata.create_all(eng)
    eng.dispose()
    con = sqlite3.connect(db)
    con.execute("DROP INDEX ix_batchprogress_batch_id")
    con.execute("CREATE UNIQUE INDEX ix_batchprogress_batch_id ON batchprogress(batch_id)")
    # The legacy phrase table: SQLite can't ADD a NOT NULL column without a
    # default, so rebuild the table the way the single-user era had it.
    ddl = con.execute("SELECT sql FROM sqlite_master WHERE name='phrase'").fetchone()[0]
    con.execute("DROP TABLE phrase")
    con.execute(ddl.replace("(", "(srs_status VARCHAR NOT NULL, ", 1))
    con.commit()
    con.close()
    found = "\n".join(schema_violations(str(db)))
    assert "ix_batchprogress_batch_id" in found
    assert "phrase.srs_status" in found


# ==== §9 row 5: limits are counted per account ================================

def test_daily_scoring_cap_is_per_account(make_user):
    from app.entitlements import ENTITLEMENTS
    admin = make_user(plan="ai", is_admin=True)
    bid = _free_showcase(admin)
    pid = phrase_ids(admin, bid)[0]
    u1 = make_user(plan="free")
    u2 = make_user(plan="free")
    with Session(engine()) as s:
        for _ in range(ENTITLEMENTS["free"]["scored_per_day"]):
            s.add(models.PhraseAttempt(user_id=_uid(u1), phrase_id=pid, score=5))
        s.commit()
    body = {"session_id": "s", "phrase_id": pid, "transcript": "x"}
    assert u1.post("/api/training/answer-text", json=body).status_code == 429
    assert u2.post("/api/training/answer-text", json=body).status_code == 200


def test_gapless_audio_cap_is_per_account(make_user):
    admin = make_user(plan="ai", is_admin=True)
    free_bid = _free_showcase(admin)
    others = [commit_sample_batch(admin) for _ in range(3)]
    u1 = make_user(plan="free")
    u2 = make_user(plan="free")
    now = datetime.now(timezone.utc)
    with Session(engine()) as s:            # three sittings today, other topics
        for bid in others:
            s.add(models.PlaybackSession(user_id=_uid(u1), batch_id=bid,
                                         created_at=now - timedelta(minutes=1)))
        s.commit()
    body = {"batch_id": free_bid, "mode": "recall"}
    r1 = u1.post("/api/sessions", json=body)
    assert r1.status_code == 429 and r1.json()["detail"] == "daily_limit"
    assert u2.post("/api/sessions", json=body).status_code == 200


def test_monthly_ai_budget_is_per_account(make_user):
    from app import usage
    from app.entitlements import ENTITLEMENTS
    make_user(plan="ai", is_admin=True)
    u1 = make_user(plan="ai")
    u2 = make_user(plan="ai")
    cap = ENTITLEMENTS["ai"]["monthly_ai_cost_cap_usd"]
    with Session(engine()) as s:
        s.add(models.UsageLedger(user_id=_uid(u1), period=usage._period(),
                                 micros=int(cap * 1_000_000)))
        s.commit()
    body = {"situation": "they push back on price"}
    assert u1.post("/api/battle/suggest", json=body).status_code == 429
    assert u2.post("/api/battle/suggest", json=body).status_code == 200


def test_league_daily_runs_are_per_account(make_user, monkeypatch):
    import app.routers.league as league
    monkeypatch.setattr(league, "_runs", {})      # process-wide dict: isolate it
    make_user(plan="ai", is_admin=True)
    u1 = make_user(plan="free")
    u2 = make_user(plan="free")
    body = {"answers": [{"id": "1", "situation": "s", "text": "I hear you."}]}
    for _ in range(league._DAILY_RUNS):
        assert u1.post("/api/league/score", json=body).status_code == 200
    assert u1.post("/api/league/score", json=body).status_code == 429
    assert u2.post("/api/league/score", json=body).status_code == 200


# ==== §11a: "прямой запрос по чужому id" =====================================
# B calls every id-taking route against A's PRIVATE import. Two groups: the ones
# that already refuse (pinned), and the ones that answer (bugs, xfail below).

_REFUSING = [
    ("batch detail", lambda b, bid, pid: b.get(f"/api/batches/{bid}"), (404,)),
    ("batch export", lambda b, bid, pid: b.get(f"/api/batches/{bid}/export"), (404,)),
    ("phrase audio", lambda b, bid, pid: b.get(f"/api/batches/phrase/{pid}/audio"), (404,)),
    ("mnemo audio", lambda b, bid, pid: b.get(f"/api/batches/{bid}/mnemo/audio?layout=anchors"), (404,)),
    ("audio session", lambda b, bid, pid: b.post("/api/sessions", json={"batch_id": bid}), (404,)),
    ("delete batch", lambda b, bid, pid: b.request("DELETE", f"/api/batches/{bid}"), (403, 404)),
    ("cover regen", lambda b, bid, pid: b.post(f"/api/batches/{bid}/cover"), (403, 404)),
]


@pytest.mark.parametrize("name,call,codes", _REFUSING, ids=[x[0] for x in _REFUSING])
def test_foreign_private_import_refused_by_id(make_user, name, call, codes):
    _admin, _a, b, a_bid, a_pids = _tenants(make_user)
    r = call(b, a_bid, a_pids[0])
    assert r.status_code in codes, f"{name}: {r.status_code} {r.text[:200]}"


def test_foreign_private_import_absent_from_every_listing(make_user):
    _admin, _a, b, a_bid, a_pids = _tenants(make_user)
    assert a_bid not in {x["id"] for x in b.get("/api/batches").json()}
    assert a_bid not in {x["batch_id"] for x in b.get("/api/batches/phrases").json()}
    assert a_bid not in {x["batch_id"] for x in b.get("/api/training/mastery").json()}
    assert a_bid not in {x["batch_id"] for x in
                         b.get("/api/battle/corpus?scope=all").json()}
    assert b.get(f"/api/training/deck?batch_ids={a_bid}").json() == []


_BUG_FOREIGN_ID = (
    "BUG: route checks only that the id exists, not that the batch is visible to "
    "the caller (owner_id NULL or == caller) — another account's private import is "
    "reachable by a guessed sequential id")
_LEAKING = [
    ("progress PUT", lambda b, bid, pid: b.put(f"/api/progress/{bid}", json={"activated": True})),
    ("swipe", lambda b, bid, pid: b.post("/api/training/swipe", json={
        "session_id": "x", "phrase_id": pid, "swipe_direction": "right"})),
    ("rotation", lambda b, bid, pid: b.get(f"/api/training/rotation/{bid}")),
    ("answer-text", lambda b, bid, pid: b.post("/api/training/answer-text", json={
        "session_id": "x", "phrase_id": pid, "transcript": "x"})),
    ("answer", lambda b, bid, pid: b.post("/api/training/answer", files=AUDIO,
                                          data={"phrase_id": pid, "session_id": "x"})),
    ("score-phrase", lambda b, bid, pid: b.post("/api/training/score-phrase", files=AUDIO,
                                                data={"phrase_id": pid})),
    ("score-anchor", lambda b, bid, pid: b.post("/api/training/score-anchor", files=AUDIO,
                                                data={"phrase_id": pid})),
    ("score-sequence", lambda b, bid, pid: b.post("/api/training/score-sequence", files=AUDIO,
                                                  data={"batch_id": bid})),
    ("coach", lambda b, bid, pid: b.post("/api/training/coach", json={
        "phrase_id": pid, "transcript": "x", "score": 5})),
]


@pytest.mark.parametrize("name,call", [
    pytest.param(n, c, id=n)
    for n, c in _LEAKING])
def test_foreign_private_import_ids_must_be_refused(make_user, name, call):
    _admin, _a, b, a_bid, a_pids = _tenants(make_user)
    r = call(b, a_bid, a_pids[0])
    assert r.status_code in (403, 404), f"{name}: {r.status_code} {r.text[:200]}"


def test_free_account_cannot_read_foreign_private_import_via_corpus(make_user):
    _admin, _a, b, a_bid, _a_pids = _tenants(make_user, b_plan="free")
    b.put(f"/api/progress/{a_bid}", json={"l1_listened": True})
    leaked = {x["phrase_en"] for x in b.get("/api/battle/corpus").json()}
    assert not (leaked & _a_phrase_texts(a_bid)), f"leaked: {sorted(leaked)[:3]}"


def test_paid_account_cannot_read_foreign_phrase_via_scoring(make_user):
    _admin, _a, b, a_bid, a_pids = _tenants(make_user, b_plan="ai")
    r = b.post("/api/training/answer-text", json={
        "session_id": "x", "phrase_id": a_pids[0], "transcript": "x"})
    assert r.json().get("correct_phrase") not in _a_phrase_texts(a_bid)


# ==== §11a: rendered session audio is public and named by a sequential id ====

def test_session_audio_is_not_fetchable_by_guessing_its_id(make_user, client):
    admin = make_user(plan="ai", is_admin=True)
    bid = commit_sample_batch(admin)                  # a paid catalog topic
    payer = make_user(plan="ai")
    r = payer.post("/api/sessions", json={"batch_id": bid, "mode": "recall"})
    assert r.status_code == 200, r.text
    sid = r.json()["id"]
    anon = client.get(f"/audio/sessions/{sid}.wav")   # no token, id only
    assert anon.status_code == 404, "anonymous client downloaded a paid session render"


# ==== §11a: logout, old token, account deletion ===============================

def test_logged_out_web_cookie_is_cleared(make_user):
    c = make_user()
    r = c.post("/api/auth/logout")
    assert r.status_code == 200
    assert 'eng_auth=""' in r.headers.get("set-cookie", "") or \
        "Max-Age=0" in r.headers.get("set-cookie", "")


@pytest.mark.xfail(strict=True, reason=(
    "BUG (low): tokens are stateless HMAC(uid.exp), so logout only deletes the web "
    "cookie — the same bearer token keeps working for its full 60 days"))
def test_logout_revokes_the_bearer_token(make_user, client):
    c = make_user()
    token = c.user["token"]  # type: ignore[attr-defined]
    assert c.post("/api/auth/logout").status_code == 200
    assert client.get("/api/auth/me", headers=_bearer(token)).status_code == 401


def test_deleted_account_token_is_dead_while_its_id_is_free(make_user, client):
    make_user(plan="ai", is_admin=True)
    gone = make_user()
    token = gone.user["token"]  # type: ignore[attr-defined]
    assert gone.request("DELETE", "/api/auth/me").status_code == 200
    assert client.get("/api/auth/me", headers=_bearer(token)).status_code == 401


def _signup_later(uid: int, seconds: int) -> None:
    """Pretend the account now holding `uid` signed up `seconds` after the old
    token was issued (in a test everything happens within one second)."""
    with Session(engine()) as s:
        u = s.get(models.User, uid)
        u.created_at = datetime.now(timezone.utc) + timedelta(seconds=seconds)
        s.add(u)
        s.commit()


def test_deleted_account_token_does_not_open_the_next_signup(make_user, client):
    """Was BUG (critical), fixed 2026-11-27 (auth.token_fits_user): user.id is a
    plain SQLite INTEGER PRIMARY KEY, so the next signup inherits a deleted
    account's id, and the deleted account's 60-day token opened the new person's
    account. The gate now refuses a token issued before its account existed."""
    make_user(plan="ai", is_admin=True)
    leaver = make_user()
    token = leaver.user["token"]  # type: ignore[attr-defined]
    assert leaver.request("DELETE", "/api/auth/me").status_code == 200
    nxt = make_user(email="next.person@example.com")
    _signup_later(_uid(nxt), 60)
    r = client.get("/api/auth/me", headers=_bearer(token))
    assert r.status_code == 401, f"old token opened {r.json().get('email')}"


def test_deleted_account_token_does_not_open_a_signup_seconds_later(make_user, client):
    make_user(plan="ai", is_admin=True)
    leaver = make_user()
    token = leaver.user["token"]  # type: ignore[attr-defined]
    assert leaver.request("DELETE", "/api/auth/me").status_code == 200
    nxt = make_user(email="quick.person@example.com")
    _signup_later(_uid(nxt), 3)
    assert client.get("/api/auth/me", headers=_bearer(token)).status_code == 401


def test_account_with_ai_usage_can_be_deleted(make_user):
    admin = make_user(plan="ai", is_admin=True)
    bid = _free_showcase(admin)
    pid = phrase_ids(admin, bid)[0]
    u = make_user(plan="free")
    r = u.post("/api/training/answer", files=AUDIO,
               data={"phrase_id": pid, "session_id": "s"})   # accrues server STT
    assert r.status_code == 200, r.text
    raw = TestClient(app, raise_server_exceptions=False)
    raw.headers.update(u.headers)
    r = raw.request("DELETE", "/api/auth/me")
    assert r.status_code == 200, f"account deletion failed: {r.status_code}"
    with Session(engine()) as s:
        assert s.get(models.User, _uid(u)) is None
        assert s.exec(select(models.UsageLedger).where(
            models.UsageLedger.user_id == _uid(u))).all() == []


def test_delete_wipes_every_per_user_table_but_touches_no_one_else(make_user):
    """Deletion scope: all of the leaver's rows go, a bystander's rows stay."""
    admin = make_user(plan="ai", is_admin=True)
    bid = commit_sample_batch(admin)
    pid = phrase_ids(admin, bid)[0]
    leaver, stay = make_user(plan="core"), make_user(plan="core")
    for u in (leaver, stay):
        assert u.put(f"/api/progress/{bid}", json={"activated": True}).status_code == 200
        assert u.post("/api/training/swipe", json={
            "session_id": "s", "phrase_id": pid, "swipe_direction": "left"}).status_code == 200
        assert u.post("/api/auth/consent", json={"kind": "voice_ai"}).status_code == 200
        assert u.post("/api/sessions", json={"batch_id": bid}).status_code == 200
    assert leaver.request("DELETE", "/api/auth/me").status_code == 200
    per_user = [m for m in SQLModel.metadata.tables.values() if "user_id" in m.c]
    with engine().connect() as con:
        for t in per_user:
            rows = con.execute(t.select()).fetchall()
            uids = {r._mapping["user_id"] for r in rows}
            assert _uid(leaver) not in uids, f"{t.name} kept the deleted account's rows"
        assert _uid(stay) in {r._mapping["user_id"] for r in
                              con.execute(models.BatchProgress.__table__.select())}
