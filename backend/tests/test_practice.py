"""Practice router. NB: the handlers don't read a user, but the global auth
gate still requires a valid token for any /api/* path, so we call authenticated."""
from sqlmodel import Session

from app import models
from app.db import engine
from conftest import commit_sample_batch, phrase_ids

_AUDIO = {"audio": ("clip.webm", b"\x00\x00\x00\x00", "audio/webm")}


def test_questions_returns_prompts(make_user):
    admin = make_user(plan="ai", is_admin=True)
    commit_sample_batch(admin)
    r = admin.get("/api/practice/questions")
    assert r.status_code == 200, r.text
    assert isinstance(r.json()["questions"], list)
    assert r.json()["questions"]


def test_prompt_audio_renders_stubbed(make_user):
    admin = make_user(plan="ai", is_admin=True)
    r = admin.post("/api/practice/prompt-audio", data={"text": "Привет"})
    assert r.status_code == 200, r.text
    assert r.json()["audio_url"].startswith("/audio/phrases/")


def test_score_happy(make_user):
    admin = make_user(plan="ai", is_admin=True)
    bid = commit_sample_batch(admin)
    pids = phrase_ids(admin, bid)
    r = admin.post("/api/practice/score", files=_AUDIO,
                   data={"phrase_ids": ",".join(str(p) for p in pids)})
    assert r.status_code == 200, r.text
    assert r.json()["phrase_id"] in pids


def test_score_no_candidates_is_400(make_user):
    admin = make_user(plan="ai", is_admin=True)
    r = admin.post("/api/practice/score", files=_AUDIO, data={"phrase_ids": ""})
    assert r.status_code == 400


def test_score_daily_limit_is_429(make_user):
    admin = make_user(plan="ai", is_admin=True)
    bid = commit_sample_batch(admin)
    pids = phrase_ids(admin, bid)
    free = make_user(plan="free")
    uid = free.user["id"]  # type: ignore[attr-defined]
    with Session(engine()) as s:
        for _ in range(30):
            s.add(models.PhraseAttempt(user_id=uid, phrase_id=pids[0], score=5))
        s.commit()
    r = free.post("/api/practice/score", files=_AUDIO,
                  data={"phrase_ids": ",".join(str(p) for p in pids)})
    assert r.status_code == 429
