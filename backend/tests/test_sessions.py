"""Gapless session render endpoint (POST /api/sessions): happy path, visibility,
freemium lock, empty-batch guard, and the free-tier daily-session cap."""
from sqlmodel import Session

from app import models
from app.db import engine
from conftest import commit_sample_batch


def _insert_batch(**kw):
    defaults = dict(title="T", slug="empty-batch", status="approved",
                    owner_id=None, is_free=True)
    defaults.update(kw)
    with Session(engine()) as s:
        b = models.Batch(**defaults)
        s.add(b)
        s.commit()
        s.refresh(b)
        return b.id


def test_session_render_happy_path(make_user):
    admin = make_user(plan="ai", is_admin=True)
    bid = commit_sample_batch(admin)
    r = admin.post("/api/sessions", json={"batch_id": bid, "mode": "recall",
                                          "order_mode": "ordered"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["audio_url"].startswith("/audio/sessions/")
    assert body["duration"] > 0
    assert body["plan"]


def test_session_missing_batch_is_404(make_user):
    admin = make_user(plan="ai", is_admin=True)
    r = admin.post("/api/sessions", json={"batch_id": 999999})
    assert r.status_code == 404


def test_session_locked_for_free_user(make_user):
    admin = make_user(plan="ai", is_admin=True)
    bid = commit_sample_batch(admin)             # paid catalog batch
    free = make_user(plan="free")
    r = free.post("/api/sessions", json={"batch_id": bid})
    assert r.status_code == 403
    assert r.json()["detail"] == "locked"


def test_session_empty_batch_is_400(make_user):
    bid = _insert_batch()                         # is_free, no phrases
    free = make_user(plan="free")
    r = free.post("/api/sessions", json={"batch_id": bid})
    assert r.status_code == 400


def test_free_tier_daily_session_cap(make_user):
    """free gapless_per_day == 3: pre-seed 3 sessions today, 4th is rejected."""
    bid = commit_sample_batch(make_user(plan="ai", is_admin=True))
    # make the catalog batch free so a free user is allowed past the lock
    with Session(engine()) as s:
        b = s.get(models.Batch, bid)
        b.is_free = True
        s.add(b)
        s.commit()
    free = make_user(plan="free")
    uid = free.user["id"]  # type: ignore[attr-defined]
    # Three separate sittings today (three other topics), so the 4th is a new one.
    with Session(engine()) as s:
        for _ in range(3):
            s.add(models.PlaybackSession(user_id=uid, batch_id=_insert_batch()))
        s.commit()
    r = free.post("/api/sessions", json={"batch_id": bid})
    assert r.status_code == 429
    assert r.json()["detail"] == "daily_limit"


def test_reshuffle_or_mode_switch_is_not_a_new_session(make_user):
    """Shuffle and Listen/Recall each re-render the same topic. Counting those as
    sessions let a free user hit the 3-a-day wall after one play, one shuffle and
    one mode switch — and that's exactly what an App Store reviewer would do."""
    bid = commit_sample_batch(make_user(plan="ai", is_admin=True))
    with Session(engine()) as s:
        b = s.get(models.Batch, bid)
        b.is_free = True
        s.add(b)
        s.commit()
    free = make_user(plan="free")
    uid = free.user["id"]  # type: ignore[attr-defined]
    with Session(engine()) as s:
        s.add(models.PlaybackSession(user_id=uid, batch_id=_insert_batch()))
        s.add(models.PlaybackSession(user_id=uid, batch_id=_insert_batch()))
        s.add(models.PlaybackSession(user_id=uid, batch_id=bid))   # 3rd sitting: this topic
        s.commit()
    for mode in ("recall", "listening", "recall"):
        r = free.post("/api/sessions", json={"batch_id": bid, "mode": mode})
        assert r.status_code == 200, f"{mode}: {r.status_code} {r.text}"
