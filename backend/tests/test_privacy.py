"""Privacy/compliance surface: data export, consent audit, deletion audit, and
transcript retention. Covers the testing-rule invariants (access/isolation +
export⊇delete coverage + deletion completeness)."""
from datetime import datetime, timedelta, timezone

from sqlmodel import Session, select

from app import models
from app.db import engine
from app.retention import purge_old_transcripts


def _make_phrase(s: Session) -> int:
    """A real batch+phrase so PhraseAttempt FK constraints pass."""
    b = models.Batch(title="t", slug="t-priv")
    s.add(b); s.commit(); s.refresh(b)
    p = models.Phrase(batch_id=b.id, phrase_en="x")
    s.add(p); s.commit(); s.refresh(p)
    return p.id


def test_policy_versions_public(client):
    r = client.get("/api/policy/versions")
    assert r.status_code == 200
    j = r.json()
    assert j["privacy"] and j["terms"]


def test_export_has_account_without_password(make_user):
    c = make_user()
    r = c.get("/api/auth/export")
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["account"]["email"] == c.user["email"]
    assert "password_hash" not in j["account"]
    # export must cover every per-user table the deletion wipes (no drift)
    for name in ("UserPhraseStat", "PhraseAttempt", "SequenceAttempt",
                 "TrainingEvent", "BatchProgress", "ConsentRecord"):
        assert name in j


def test_export_requires_auth(client):
    assert client.get("/api/auth/export").status_code == 401


def test_consent_is_recorded(make_user):
    c = make_user()
    assert c.post("/api/auth/consent", json={"kind": "voice_ai", "granted": True}).status_code == 200
    j = c.get("/api/auth/export").json()
    rows = j["ConsentRecord"]
    assert any(r["kind"] == "voice_ai" and r["granted"] for r in rows)


def test_delete_writes_audit_and_wipes_user(make_user):
    c = make_user()
    uid = c.user["id"]
    # leave a consent + a transcript behind so the audit count is exercised
    c.post("/api/auth/consent", json={"kind": "voice_ai"})
    with Session(engine()) as s:
        pid = _make_phrase(s)
        s.add(models.PhraseAttempt(user_id=uid, phrase_id=pid, score=5, transcript="hello"))
        s.commit()
    assert c.delete("/api/auth/me").status_code == 200
    with Session(engine()) as s:
        assert s.get(models.User, uid) is None
        assert not s.exec(select(models.ConsentRecord).where(models.ConsentRecord.user_id == uid)).all()
        log = s.exec(select(models.DeletionLog).where(models.DeletionLog.deleted_user_id == uid)).first()
        assert log is not None and log.transcripts_purged >= 1


def test_retention_blanks_old_transcripts_only(make_user):
    c = make_user()
    uid = c.user["id"]
    now = datetime.now(timezone.utc)
    with Session(engine()) as s:
        pid = _make_phrase(s)
        s.add(models.PhraseAttempt(user_id=uid, phrase_id=pid, score=5, transcript="OLD",
                                   created_at=now - timedelta(days=100)))
        s.add(models.PhraseAttempt(user_id=uid, phrase_id=pid, score=7, transcript="NEW",
                                   created_at=now))
        s.commit()
    cleared = purge_old_transcripts(days=30)
    assert cleared >= 1
    with Session(engine()) as s:
        rows = s.exec(select(models.PhraseAttempt).where(models.PhraseAttempt.user_id == uid)).all()
        by_score = {r.score: r.transcript for r in rows}
        assert by_score[5] == ""      # old → blanked
        assert by_score[7] == "NEW"   # recent → kept
        # numeric score survives the purge
        assert all(r.score in (5, 7) for r in rows)


# --- The three public legal/help pages ---------------------------------------
# App Store Connect requires a reachable Support URL, and Apple checks the
# Privacy and Terms links too. All three must answer WITHOUT a session, because
# a reviewer (and a locked-out user) opens them signed out.

def test_public_pages_are_reachable_without_auth(client):
    for path in ("/privacy", "/terms", "/support"):
        r = client.get(path)
        assert r.status_code == 200, f"{path} -> {r.status_code}"
        assert r.headers["content-type"].startswith("text/html"), path
        assert "<html" in r.text.lower(), f"{path} did not return a page"


def test_support_page_answers_the_questions_a_user_is_locked_out_by(client):
    """The page exists to be useful, not to satisfy a URL field: a user who
    cannot sign in or wants their data must find the way out on it."""
    html = client.get("/support").text
    assert "support@executive-english.net" in html, "no way to reach us"
    for needle in ("password", "Restore purchases", "Subscriptions", "delete"):
        assert needle.lower() in html.lower(), f"support page never mentions {needle!r}"
    for link in ('href="/privacy"', 'href="/terms"'):
        assert link in html, f"support page does not link {link}"
