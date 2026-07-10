"""Live semantic retrieval (app/embeddings.py): the embed-text composition
(triggers = the situational core), idempotent seeding with hash-based
staleness, cosine ordering of the battle pool, and the graceful fallback to
keyword retrieval when the index/API is unavailable.
"""
import struct

from sqlmodel import Session, select

from app import embeddings, models
from app.config import get_settings
from app.db import engine


def _seed_batch(slug: str, n: int = 3) -> tuple[int, list[int]]:
    with Session(engine()) as s:
        b = models.Batch(title=f"T-{slug}", slug=slug, status="approved")
        s.add(b)
        s.commit()
        s.refresh(b)
        pids = []
        for i in range(1, n + 1):
            p = models.Phrase(batch_id=b.id, order_index=i, anchor=f"a{i}",
                              phrase_en=f"Phrase {slug} {i}.",
                              gloss_ru=f"смысл {i}", situation_ru=f"ситуация {i}",
                              task_ru=f"задача {i}")
            s.add(p)
            s.commit()
            s.refresh(p)
            pids.append(p.id)
        return b.id, pids


def _activate(uid: int, bid: int) -> None:
    with Session(engine()) as s:
        s.add(models.BatchProgress(user_id=uid, batch_id=bid,
                                   on_path=True, activated=True))
        s.commit()


def _vec(x: float, y: float) -> bytes:
    d = get_settings().embed_dim
    return struct.pack(f"<{d}f", x, y, *([0.0] * (d - 2)))


def _qvec(x: float, y: float) -> tuple[float, ...]:
    d = get_settings().embed_dim
    return (x, y) + (0.0,) * (d - 2)


def _put_vector(pid: int, raw: bytes) -> None:
    s_ = get_settings()
    with Session(engine()) as s:
        s.add(models.PhraseEmbedding(phrase_id=pid, model=s_.model_embed,
                                     dim=s_.embed_dim, text_hash="h", vector=raw))
        s.commit()


# ---- embed text: the situational identity -----------------------------------

def test_phrase_embed_text_includes_triggers_and_situation():
    p = models.Phrase(batch_id=1, order_index=1, anchor="якорь",
                      phrase_en="Let me push back on that.",
                      gloss_ru="возразить", situation_ru="Коллега давит на встрече.",
                      task_ru="Осади его.")
    text = embeddings.phrase_embed_text(
        p, ["I think we should cut the budget by half.", "Second cue."])
    for part in ("Let me push back on that.", "якорь", "возразить",
                 "Коллега давит на встрече.", "Осади его.",
                 "I think we should cut the budget by half.", "Second cue."):
        assert part in text
    # the trigger cap bounds token cost
    many = embeddings.phrase_embed_text(p, [f"cue {i}" for i in range(50)])
    assert "cue 11" in many and "cue 12" not in many


# ---- seed: idempotent, hash-driven -------------------------------------------

def test_seed_embeds_missing_then_skips_fresh(monkeypatch):
    _bid, pids = _seed_batch("emb-seed")
    calls = {"texts": 0}

    def fake_embed(texts):
        calls["texts"] += len(texts)
        return [_vec(1.0, 0.0) for _ in texts]

    monkeypatch.setattr("app.embeddings.embed_texts", fake_embed)
    with Session(engine()) as s:
        out = embeddings.seed(s)
    assert out["embedded"] == 3 and calls["texts"] == 3
    with Session(engine()) as s:
        rows = s.exec(select(models.PhraseEmbedding)).all()
    st = get_settings()
    assert {r.phrase_id for r in rows} == set(pids)
    assert all(r.model == st.model_embed and r.dim == st.embed_dim
               and len(r.vector) == st.embed_dim * 4 for r in rows)

    with Session(engine()) as s:                     # second run: all fresh
        out2 = embeddings.seed(s)
    assert out2 == {"phrases": 3, "fresh": 3, "embedded": 0, "would_embed": 0,
                    "pruned": 0}
    assert calls["texts"] == 3


def test_seed_reembeds_only_what_changed(monkeypatch):
    _bid, pids = _seed_batch("emb-stale")
    monkeypatch.setattr("app.embeddings.embed_texts",
                        lambda texts: [_vec(1.0, 0.0) for _ in texts])
    with Session(engine()) as s:
        embeddings.seed(s)
    # a text edit AND a new approved cue each make exactly that phrase stale
    with Session(engine()) as s:
        p = s.get(models.Phrase, pids[0])
        p.phrase_en = "Rewritten line."
        s.add(p)
        s.add(models.CheckPhrase(phrase_id=pids[1], batch_id=p.batch_id,
                                 text="New cue.", lang="en", kind="stimulus",
                                 order_index=1, status="approved"))
        s.commit()
        out = embeddings.seed(s)
    assert out["embedded"] == 2 and out["fresh"] == 1
    with Session(engine()) as s:                     # dry run reports, no writes
        p = s.get(models.Phrase, pids[2])
        p.anchor = "новый якорь"
        s.add(p)
        s.commit()
        dry = embeddings.seed(s, dry=True)
        assert dry["would_embed"] == 1 and dry["embedded"] == 0
        assert embeddings.seed(s)["embedded"] == 1


def test_seed_prunes_orphaned_vectors(monkeypatch):
    """A vector whose phrase is gone (content replace / hard delete) is dead
    weight at best and a mis-attach at worst once the id recycles — seed removes
    it (audit census, 2026-07-10)."""
    _bid, pids = _seed_batch("emb-prune", n=2)
    monkeypatch.setattr("app.embeddings.embed_texts",
                        lambda texts: [_vec(1.0, 0.0) for _ in texts])
    with Session(engine()) as s:
        # simulate a pre-fix orphan (FK-off, like the prod sqlite3-CLI path)
        s.connection().exec_driver_sql("PRAGMA foreign_keys=OFF")
        s.add(models.PhraseEmbedding(phrase_id=999_999, model="m", dim=2,
                                     text_hash="h", vector=b"\x00" * 8))
        s.commit()
        out = embeddings.seed(s)
        assert out["pruned"] == 1 and out["embedded"] == 2
        left = {e.phrase_id for e in s.exec(select(models.PhraseEmbedding)).all()}
    assert left == set(pids)                       # orphan gone, live ones indexed


# ---- semantic_pool: cosine order, tail, cap -----------------------------------

def test_semantic_pool_orders_by_cosine_and_keeps_unembedded_tail():
    bid, pids = _seed_batch("emb-pool")
    _put_vector(pids[0], _vec(1.0, 0.0))     # far from the query
    _put_vector(pids[1], _vec(0.6, 0.8))     # close
    # pids[2] has NO vector -> tail
    with Session(engine()) as s:
        b = s.get(models.Batch, bid)
        rows = [(s.get(models.Phrase, pid), None, b) for pid in pids]
        pool = embeddings.semantic_pool(s, rows, _qvec(0.0, 1.0), cap=10)
        assert [r[0].id for r in pool] == [pids[1], pids[0], pids[2]]
        capped = embeddings.semantic_pool(s, rows, _qvec(0.0, 1.0), cap=2)
        assert [r[0].id for r in capped] == [pids[1], pids[0]]


def test_semantic_pool_none_when_index_empty():
    bid, pids = _seed_batch("emb-none")
    with Session(engine()) as s:
        b = s.get(models.Batch, bid)
        rows = [(s.get(models.Phrase, pid), None, b) for pid in pids]
        assert embeddings.semantic_pool(s, rows, _qvec(0.0, 1.0), cap=10) is None


# ---- /suggest: the semantic order drives the pick, with graceful fallback -----

def test_suggest_picks_by_semantic_similarity(make_user, monkeypatch):
    c = make_user(plan="ai", is_admin=True)
    uid = c.user["id"]  # type: ignore[attr-defined]
    bid, pids = _seed_batch("emb-e2e")
    _activate(uid, bid)
    _put_vector(pids[0], _vec(1.0, 0.0))
    _put_vector(pids[1], _vec(0.6, 0.8))
    _put_vector(pids[2], _vec(0.0, 1.0))     # the semantic head for this moment
    monkeypatch.setattr("app.embeddings.embed_query",
                        lambda text: _qvec(0.0, 1.0))
    r = c.post("/api/battle/suggest", json={"situation": "клиент требует скидку"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["via"] == "llm"
    # the stub battle_pick answers n=1 = the head of the pool = the cosine top
    assert body["picks"][0]["phrase_id"] == pids[2]


def test_suggest_falls_back_to_learned_first_without_vectors(make_user, monkeypatch):
    c = make_user(plan="ai", is_admin=True)
    uid = c.user["id"]  # type: ignore[attr-defined]
    bid, pids = _seed_batch("emb-fb")
    _activate(uid, bid)
    monkeypatch.setattr("app.embeddings.embed_query",
                        lambda text: _qvec(0.0, 1.0))   # API up, index empty
    r = c.post("/api/battle/suggest", json={"situation": "клиент требует скидку"})
    assert r.status_code == 200, r.text
    assert r.json()["picks"][0]["phrase_id"] == pids[0]  # old learned-first head
