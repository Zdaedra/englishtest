"""Per-user batch progress + activation gates (lock + max-active-batches cap)."""
from sqlmodel import Session

from app import models
from app.db import engine
from conftest import commit_sample_batch


def _free_batch(slug):
    with Session(engine()) as s:
        b = models.Batch(title="T", slug=slug, status="approved",
                         owner_id=None, is_free=True)
        s.add(b)
        s.commit()
        s.refresh(b)
        return b.id


def test_progress_list_empty(make_user):
    c = make_user(plan="ai", is_admin=True)
    assert c.get("/api/progress").json() == []


def test_progress_single_is_empty_stub_not_404(make_user):
    c = make_user(plan="ai", is_admin=True)
    r = c.get("/api/progress/123")
    assert r.status_code == 200
    assert r.json()["batch_id"] == 123
    assert r.json()["activated"] is False


def test_progress_patch_updates_fields(make_user):
    admin = make_user(plan="ai", is_admin=True)
    bid = commit_sample_batch(admin)
    r = admin.put(f"/api/progress/{bid}",
                  json={"l1_listened": True, "l1_best_seq": 8.5})
    assert r.status_code == 200, r.text
    assert r.json()["l1_listened"] is True
    assert r.json()["l1_best_seq"] == 8.5


def test_activate_locked_batch_is_403(make_user):
    admin = make_user(plan="ai", is_admin=True)
    bid = commit_sample_batch(admin)             # paid catalog batch
    free = make_user(plan="free")
    r = free.put(f"/api/progress/{bid}", json={"activated": True})
    assert r.status_code == 403
    assert r.json()["detail"] == "locked"


def test_activate_free_batch_succeeds(make_user):
    bid = _free_batch("free-1")
    free = make_user(plan="free")
    r = free.put(f"/api/progress/{bid}", json={"activated": True})
    assert r.status_code == 200, r.text
    assert r.json()["activated"] is True


def test_patch_missing_batch_is_404(make_user):
    c = make_user(plan="ai", is_admin=True)
    assert c.put("/api/progress/999999", json={"l1_listened": True}).status_code == 404


def test_active_batch_cap_for_free(make_user):
    """free max_active_batches == 3 -> activating a 4th is rejected."""
    ids = [_free_batch(f"free-{i}") for i in range(4)]
    free = make_user(plan="free")
    for bid in ids[:3]:
        assert free.put(f"/api/progress/{bid}",
                        json={"activated": True}).status_code == 200
    r = free.put(f"/api/progress/{ids[3]}", json={"activated": True})
    assert r.status_code == 403
    assert r.json()["detail"] == "limit_active"
