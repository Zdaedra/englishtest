"""Practice router: cue TTS + the Arena (scene woven from learned phrases).
The old stub /questions + /score drill was removed 2026-07-03."""
from datetime import datetime, timedelta, timezone

from sqlmodel import Session, select

from app import models
from app.db import engine
from conftest import commit_sample_batch, phrase_ids


def test_prompt_audio_renders_stubbed(make_user):
    admin = make_user(plan="ai", is_admin=True)
    r = admin.post("/api/practice/prompt-audio", data={"text": "Привет"})
    assert r.status_code == 200, r.text
    assert r.json()["audio_url"].startswith("/audio/phrases/")


def test_stub_drill_endpoints_removed(make_user):
    admin = make_user(plan="ai", is_admin=True)
    assert admin.get("/api/practice/questions").status_code in (404, 405)


# --- Arena (/api/practice/scenario) -------------------------------------------
def _learn_phrases(uid, pids, *, status="familiar", overdue=False):
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    with Session(engine()) as s:
        for pid in pids:
            p = s.get(models.Phrase, pid)
            s.add(models.UserPhraseStat(
                user_id=uid, phrase_id=pid, batch_id=p.batch_id,
                srs_status=status,
                next_review_at=(now - timedelta(days=1)) if overdue else None))
        s.commit()


def test_scenario_locked_below_ai_plan(make_user):
    make_user(plan="ai", is_admin=True)
    core = make_user(plan="core")
    r = core.post("/api/practice/scenario")
    assert r.status_code == 403 and r.json()["detail"] == "locked"


def test_scenario_requires_three_learned_phrases(make_user):
    admin = make_user(plan="ai", is_admin=True)
    bid = commit_sample_batch(admin)
    _learn_phrases(admin.user["id"], phrase_ids(admin, bid)[:2])
    r = admin.post("/api/practice/scenario")
    assert r.status_code == 409 and r.json()["detail"] == "not_enough"


def test_scenario_weaves_learned_phrases(make_user):
    admin = make_user(plan="ai", is_admin=True)
    bid = commit_sample_batch(admin)
    pids = phrase_ids(admin, bid)[:3]
    _learn_phrases(admin.user["id"], pids)
    r = admin.post("/api/practice/scenario")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["via"] == "llm" and body["title_ru"] == "Сцена"
    assert len(body["beats"]) == 3
    assert {b["phrase_id"] for b in body["beats"]} <= set(pids)
    assert all(b["situation_ru"] and b["phrase_en"] for b in body["beats"])


def test_scenario_prefers_overdue_phrases(make_user):
    admin = make_user(plan="ai", is_admin=True)
    bid = commit_sample_batch(admin)
    pids = phrase_ids(admin, bid)
    uid = admin.user["id"]
    _learn_phrases(uid, pids[:3])                       # learned, unscheduled
    _learn_phrases(uid, [pids[3]], status="shaky", overdue=True)  # overdue lapse
    body = admin.post("/api/practice/scenario").json()
    assert pids[3] in {b["phrase_id"] for b in body["beats"]}


def test_scenario_accrues_usage(make_user):
    admin = make_user(plan="ai", is_admin=True)
    bid = commit_sample_batch(admin)
    uid = admin.user["id"]
    _learn_phrases(uid, phrase_ids(admin, bid)[:3])
    admin.post("/api/practice/scenario")
    from app.usage import _period
    with Session(engine()) as s:
        row = s.exec(select(models.UsageLedger).where(
            models.UsageLedger.user_id == uid,
            models.UsageLedger.period == _period())).first()
    assert row is not None and row.micros > 0
