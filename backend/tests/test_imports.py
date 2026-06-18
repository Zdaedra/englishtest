"""Import parse/commit + the import/admin entitlement gates."""
from app import importer
from conftest import SAMPLE, commit_sample_batch


def test_parse_deterministic_for_entitled_user(make_user):
    c = make_user(plan="ai")
    r = c.post("/api/imports/parse", json={"raw_text": SAMPLE})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["parser"] == "deterministic"
    assert len(body["batch"]["phrases"]) == 5


def test_parse_blocked_for_free_plan(make_user):
    c = make_user(plan="free")
    r = c.post("/api/imports/parse", json={"raw_text": SAMPLE})
    assert r.status_code == 403
    assert r.json()["detail"] == "core_required"


def test_commit_blocked_for_free_plan(make_user):
    c = make_user(plan="free")
    batch = importer.parse(SAMPLE).batch
    r = c.post("/api/imports/commit", json=batch.model_dump())
    assert r.status_code == 403
    assert r.json()["detail"] == "core_required"


def test_commit_admin_creates_shared_catalog(make_user):
    admin = make_user(plan="ai", is_admin=True)
    bid = commit_sample_batch(admin)
    # a different, non-owning free user can still SEE the shared catalog batch
    free = make_user(plan="free")
    listing = free.get("/api/batches").json()
    assert any(b["id"] == bid for b in listing)


def test_commit_rejects_empty_phrases(make_user):
    c = make_user(plan="core")
    batch = importer.parse(SAMPLE).batch.model_dump()
    batch["phrases"] = []
    r = c.post("/api/imports/commit", json=batch)
    assert r.status_code == 400
    assert "no phrases" in r.json()["detail"].lower()


def test_seed_requires_admin(make_user):
    c = make_user(plan="ai", is_admin=False)  # entitled but not admin
    r = c.post("/api/imports/seed")
    assert r.status_code == 403
    assert r.json()["detail"] == "admin_required"
