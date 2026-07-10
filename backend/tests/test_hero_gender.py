"""Hero-gender cover preference (D3, #24): the per-user protagonist choice that
swaps batch cover art (male v2 back / female v3 back / mixed), its endpoint, and
the batches-list wiring. cover_url_for is pure (no network), so it's unit-tested
directly; the stub_network autouse fixture doesn't touch it."""
from sqlmodel import Session

from app import cover, models
from app.config import get_settings
from app.db import engine
from conftest import commit_sample_batch


def _make_v3(slug: str) -> None:
    (get_settings().covers_dir / f"{slug}.v3.jpg").write_bytes(b"jpg")


# --- cover.cover_url_for (pure variant resolution) ---------------------------

def test_male_keeps_v2_untouched():
    assert cover.cover_url_for("/covers/flirt-1.v2.jpg", 1, "male") == "/covers/flirt-1.v2.jpg"


def test_female_swaps_to_v3_when_file_exists():
    _make_v3("hg-flirt")
    assert cover.cover_url_for("/covers/hg-flirt.v2.jpg", 1, "female") == "/covers/hg-flirt.v3.jpg"


def test_female_falls_back_to_v2_when_no_variant():
    # No v3 file for this slug -> female users keep the male cover (the 56
    # not-yet-regenerated batches behave this way).
    assert cover.cover_url_for("/covers/hg-nolead.v2.jpg", 3, "female") == "/covers/hg-nolead.v2.jpg"


def test_mixed_alternates_by_batch_id_where_variant_exists():
    _make_v3("hg-mix")
    assert cover.cover_url_for("/covers/hg-mix.v2.jpg", 2, "mixed") == "/covers/hg-mix.v3.jpg"   # even
    assert cover.cover_url_for("/covers/hg-mix.v2.jpg", 3, "mixed") == "/covers/hg-mix.v2.jpg"   # odd


def test_mixed_without_variant_is_always_v2():
    assert cover.cover_url_for("/covers/hg-none.v2.jpg", 2, "mixed") == "/covers/hg-none.v2.jpg"


def test_none_and_non_v2_paths_pass_through():
    assert cover.cover_url_for(None, 1, "female") is None
    assert cover.cover_url_for("/covers/x.png", 2, "female") == "/covers/x.png"


# --- endpoint + serialization ------------------------------------------------

def test_default_hero_gender_is_male(make_user):
    admin = make_user(plan="ai", is_admin=True)
    assert admin.get("/api/auth/me").json()["hero_gender"] == "male"


def test_set_hero_gender_persists_and_shows_in_me(make_user):
    u = make_user()
    r = u.post("/api/auth/hero-gender", json={"gender": "female"})
    assert r.status_code == 200, r.text
    assert r.json()["hero_gender"] == "female"
    assert u.get("/api/auth/me").json()["hero_gender"] == "female"


def test_set_hero_gender_rejects_bad_value(make_user):
    u = make_user()
    assert u.post("/api/auth/hero-gender", json={"gender": "other"}).status_code == 400


def test_set_hero_gender_requires_auth(client):
    assert client.post("/api/auth/hero-gender", json={"gender": "female"}).status_code == 401


# --- integration: the batches list honours the preference --------------------

def test_batches_list_reflects_gender(make_user):
    admin = make_user(plan="ai", is_admin=True)
    bid = commit_sample_batch(admin)
    with Session(engine()) as s:
        b = s.get(models.Batch, bid)
        b.cover_path = f"/covers/{b.slug}.v2.jpg"
        s.add(b)
        s.commit()
        slug = b.slug
    _make_v3(slug)

    def cover_of(c):
        return next(x for x in c.get("/api/batches").json() if x["id"] == bid)["cover_url"]

    assert cover_of(admin) == f"/covers/{slug}.v2.jpg"          # male (default)
    admin.post("/api/auth/hero-gender", json={"gender": "female"})
    assert cover_of(admin) == f"/covers/{slug}.v3.jpg"          # female -> v3
