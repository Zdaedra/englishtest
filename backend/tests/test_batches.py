"""Batch catalog: listing, locking/freemium, per-user isolation, reviews,
audio, export, delete, cover, free-flag."""
from conftest import commit_sample_batch, phrase_ids


def test_list_includes_shared_catalog(make_user):
    admin = make_user(plan="ai", is_admin=True)
    bid = commit_sample_batch(admin)
    free = make_user(plan="free")
    assert any(b["id"] == bid for b in free.get("/api/batches").json())


def test_detail_unlocked_for_ai_user(make_user):
    admin = make_user(plan="ai", is_admin=True)
    bid = commit_sample_batch(admin)
    detail = admin.get(f"/api/batches/{bid}").json()
    assert detail["locked"] is False
    assert len(detail["phrases"]) == 5
    assert len(detail["mnemo"]["spans"]) == 5


def test_detail_locked_for_free_user_on_paid_batch(make_user):
    admin = make_user(plan="ai", is_admin=True)
    bid = commit_sample_batch(admin)            # shared, not is_free
    free = make_user(plan="free")
    detail = free.get(f"/api/batches/{bid}").json()
    assert detail["locked"] is True
    assert detail["phrases"] == []              # paid content withheld


def test_private_import_is_isolated_between_users(make_user):
    # both non-admin (the first registered user would otherwise bootstrap as
    # admin and commit to the shared catalog)
    owner = make_user(plan="core", is_admin=False)   # private import
    bid = commit_sample_batch(owner)
    other = make_user(plan="core", is_admin=False)
    # a different non-admin cannot even see it exists -> 404, not 403
    assert other.get(f"/api/batches/{bid}").status_code == 404


def test_legacy_reviews_endpoint_removed(make_user):
    """Removed 2026-07-02: SRS writes flow only through /api/training/*."""
    admin = make_user(plan="ai", is_admin=True)
    bid = commit_sample_batch(admin)
    pid = phrase_ids(admin, bid)[0]
    r = admin.post("/api/batches/reviews", json={"phrase_id": pid, "score": "easy"})
    assert r.status_code in (404, 405)


def test_phrase_audio_renders_stubbed(make_user):
    admin = make_user(plan="ai", is_admin=True)
    bid = commit_sample_batch(admin)
    pid = phrase_ids(admin, bid)[0]
    r = admin.get(f"/api/batches/phrase/{pid}/audio")
    assert r.status_code == 200, r.text
    assert r.json()["audio_url"].startswith("/audio/phrases/")
    assert r.json()["duration"] > 0


def test_mnemo_audio_anchors_layout(make_user):
    admin = make_user(plan="ai", is_admin=True)
    bid = commit_sample_batch(admin)
    r = admin.get(f"/api/batches/{bid}/mnemo/audio", params={"layout": "anchors"})
    assert r.status_code == 200, r.text
    assert r.json()["plan"]


def test_mnemo_audio_rejects_unknown_layout(make_user):
    admin = make_user(plan="ai", is_admin=True)
    bid = commit_sample_batch(admin)
    r = admin.get(f"/api/batches/{bid}/mnemo/audio", params={"layout": "spiral"})
    assert r.status_code == 400


def test_export_returns_authoring(make_user):
    admin = make_user(plan="ai", is_admin=True)
    bid = commit_sample_batch(admin)
    r = admin.get(f"/api/batches/{bid}/export")
    assert r.status_code == 200, r.text


def test_delete_own_import(make_user):
    owner = make_user(plan="core", is_admin=False)
    bid = commit_sample_batch(owner)
    assert owner.request("DELETE", f"/api/batches/{bid}").json() == {"ok": True}
    assert owner.get(f"/api/batches/{bid}").status_code == 404


def test_delete_missing_is_404(make_user):
    admin = make_user(plan="ai", is_admin=True)
    assert admin.request("DELETE", "/api/batches/999999").status_code == 404


def test_cover_owner_can_regenerate(make_user):
    owner = make_user(plan="core", is_admin=False)
    bid = commit_sample_batch(owner)
    r = owner.post(f"/api/batches/{bid}/cover", json={"force": True})
    assert r.status_code == 200, r.text
    assert r.json()["cover_url"] == "/covers/stub.png"


def test_free_flag_requires_admin(make_user):
    admin = make_user(plan="ai", is_admin=True)
    bid = commit_sample_batch(admin)
    non_admin = make_user(plan="core")
    assert non_admin.post(f"/api/batches/{bid}/free").status_code == 403
    ok = admin.post(f"/api/batches/{bid}/free")
    assert ok.status_code == 200, ok.text
    assert ok.json()["is_free"] is True
