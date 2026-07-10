"""Semantic retrieval for Live mode: phrase vectors in OUR OWN SQLite.

The relevance problem this solves: a dictated moment («клиент требует скидку и
давит…») shares almost no literal tokens with the phrase texts — RU morphology
breaks substring matching («скидку» ≠ «скидка»), and the line that answers the
moment is English anyway. So Live's candidate pool was keyword-luck. Here every
phrase gets a vector of its SITUATIONAL identity, and candidates are ranked by
cosine similarity to the moment's vector — cross-lingual and morphology-proof.

What gets embedded per phrase (the situations a line answers, not its wording):
phrase_en + anchor + gloss + situation_ru/task_ru + its approved CheckPhrase
triggers (реплики собеседника, вызывающие эту фразу — 3191 authored cues, the
strongest signal here: they ARE examples of moments that call for the line).

Storage: PhraseEmbedding rows in the same SQLite. At catalog scale (~811
phrases ≈ 1.6 MB at 512 dims) a dedicated vector DB buys nothing — vectors are
L2-normalized float32 bytes (cosine == plain dot), and a brute-force dot over
the candidate set is ~10 ms in dependency-free Python.

Query path (routers/battle.py): embed_query(moment) — one small API call
(~100 ms, ≈$0.0000004, LRU-cached so one-tap intent re-picks are free) →
semantic_pool ranks the scope's rows → the LLM picker judges only the top-N.
Missing key / API error / index not seeded → None → the router keeps its old
bounded keyword pools, so Live degrades instead of breaking.

Reseeding (idempotent, ~$0.003 for the full catalog on text-embedding-3-small):

    python -m app.embeddings          # embed missing/stale phrases only
    python -m app.embeddings --dry    # report what would be embedded
    python -m app.embeddings --force  # re-embed everything

text_hash marks staleness: any edit to a phrase's texts or cues — or an
ENGLISH_MODEL_EMBED / ENGLISH_EMBED_DIM swap — makes the stored row stale, and
`app.doctor` reports it until this module is rerun (CONTENT-GRAPH.md §3).
"""
import hashlib
import struct
from collections import OrderedDict
from math import sqrt
from operator import mul

import httpx
from sqlmodel import Session, select

from .config import get_secrets, get_settings

_EMBED_URL = "https://api.openai.com/v1/embeddings"
_CHUNK = 96           # texts per embeddings request (bounds request size)
_MAX_TRIGGERS = 12    # cues per phrase in the embed text (bounds token cost)

# Moment-vector LRU: a chip re-pick sends the SAME moment again — no reason to
# pay (or wait for) a second embedding round trip mid-conversation.
_qcache: "OrderedDict[tuple, tuple[float, ...]]" = OrderedDict()
_QCACHE_MAX = 128


def text_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def phrase_embed_text(phrase, triggers: list[str]) -> str:
    """The canonical text a phrase's vector represents. Triggers are the
    situational core; the phrase's own texts anchor wording and meaning."""
    parts = [phrase.phrase_en, phrase.anchor, phrase.gloss_ru or "",
             phrase.situation_ru or "", phrase.task_ru or ""]
    parts += [t for t in triggers[:_MAX_TRIGGERS]]
    return "\n".join(p.strip() for p in parts if p and p.strip())


def _pack(vec: list[float]) -> bytes:
    """L2-normalize and pack to float32 LE — after this, cosine == dot."""
    norm = sqrt(sum(v * v for v in vec)) or 1.0
    return struct.pack(f"<{len(vec)}f", *(v / norm for v in vec))


def _unpack(raw: bytes) -> tuple[float, ...]:
    return struct.unpack(f"<{len(raw) // 4}f", raw)


def embed_texts(texts: list[str]) -> list[bytes]:
    """Embed a list of texts → packed normalized vectors, order preserved.
    Raises on any failure — callers decide how to degrade."""
    s = get_settings()
    api_key = get_secrets().openai_api_key
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY not set — cannot embed.")
    out: list[bytes] = []
    for i in range(0, len(texts), _CHUNK):
        r = httpx.post(
            _EMBED_URL,
            headers={"Authorization": f"Bearer {api_key}",
                     "content-type": "application/json"},
            json={"model": s.model_embed, "input": texts[i:i + _CHUNK],
                  "dimensions": s.embed_dim},
            timeout=60,
        )
        r.raise_for_status()
        data = sorted(r.json()["data"], key=lambda d: d["index"])
        out += [_pack(d["embedding"]) for d in data]
    return out


def embed_query(text: str) -> tuple[float, ...] | None:
    """Vector for a dictated/typed moment; None = embeddings unavailable
    (no key / API error) — battle falls back to keyword retrieval."""
    s = get_settings()
    key = (s.model_embed, s.embed_dim, (text or "").strip())
    if not key[2]:
        return None
    if key in _qcache:
        _qcache.move_to_end(key)
        return _qcache[key]
    try:
        vec = _unpack(embed_texts([key[2]])[0])
    except Exception:
        return None
    _qcache[key] = vec
    if len(_qcache) > _QCACHE_MAX:
        _qcache.popitem(last=False)
    return vec


def semantic_pool(session: Session, rows, qvec: tuple[float, ...], cap: int):
    """Rows (Phrase, stat, Batch) reordered by cosine to the moment, top `cap`.
    Rows without a usable vector (not yet seeded / dim mismatch) keep their
    incoming order at the TAIL — pass rows learned-first-sorted so the tail and
    ties stay deterministic. Returns None when NO row has a vector (index not
    seeded) — the caller falls back to keyword retrieval."""
    from . import models
    ids = [p.id for p, _st, _b in rows]
    if not ids:
        return None
    vecs: dict[int, tuple[float, ...]] = {}
    for e in session.exec(select(models.PhraseEmbedding)
                          .where(models.PhraseEmbedding.phrase_id.in_(ids))).all():
        if len(e.vector) == len(qvec) * 4:
            vecs[e.phrase_id] = _unpack(e.vector)
    if not vecs:
        return None
    scored, tail = [], []
    for i, row in enumerate(rows):
        v = vecs.get(row[0].id)
        if v is None:
            tail.append(row)
            continue
        scored.append((-sum(map(mul, qvec, v)), i, row))
    scored.sort(key=lambda x: (x[0], x[1]))
    return ([r for _d, _i, r in scored] + tail)[:cap]


# A neighbour must be genuinely related, not just the least-far phrase in a small
# pool. Vectors are L2-normalized so dot == cosine ∈ [-1,1]; 0.5 keeps "same kind
# of moment" and drops the unrelated. In a full catalog the top-N are all well
# above this, so the floor only bites when the pool is small/sparse.
_NEIGHBOR_MIN_SIM = 0.5


def neighbors(session: Session, user_id: int, seed_pids, cap: int) -> list[int]:
    """Phrase ids semantically CLOSEST to any seed phrase — "more like what you
    needed in Live" (the moment-of-the-day expansion). Ranks the embedding index
    by max cosine to any seed, keeps only genuinely-related ones (≥
    _NEIGHBOR_MIN_SIM), restricted to phrases VISIBLE to this user (shared catalog
    or their own imports — never another account's private import), excluding the
    seeds. Returns [] when seeds/index are absent (caller degrades to the seeds)."""
    from . import models
    seeds = [i for i in set(seed_pids) if i is not None]
    if not seeds:
        return []
    seed_vecs = [_unpack(e.vector) for e in session.exec(
        select(models.PhraseEmbedding)
        .where(models.PhraseEmbedding.phrase_id.in_(seeds))).all() if e.vector]
    if not seed_vecs:
        return []
    dim = len(seed_vecs[0])
    exclude = set(seeds)
    vis_batches = set(session.exec(select(models.Batch.id).where(
        models.Batch.deleted_at == None,  # noqa: E711
        (models.Batch.owner_id == None) | (models.Batch.owner_id == user_id),  # noqa: E711
    )).all())
    pid_batch = dict(session.exec(select(models.Phrase.id, models.Phrase.batch_id)).all())
    scored: list[tuple[float, int]] = []
    for e in session.exec(select(models.PhraseEmbedding)).all():
        pid = e.phrase_id
        if pid in exclude or pid_batch.get(pid) not in vis_batches:
            continue
        if len(e.vector) != dim * 4:
            continue
        v = _unpack(e.vector)
        best = max(sum(map(mul, sv, v)) for sv in seed_vecs)
        if best >= _NEIGHBOR_MIN_SIM:
            scored.append((-best, pid))
    scored.sort()
    return [pid for _s, pid in scored[:cap]]


def _trigger_map(session: Session) -> dict[int, list[str]]:
    """phrase_id -> approved cue texts, stable order (the situational corpus)."""
    from . import models
    out: dict[int, list[str]] = {}
    for cp in session.exec(
            select(models.CheckPhrase)
            .where(models.CheckPhrase.status == "approved")
            .order_by(models.CheckPhrase.phrase_id,
                      models.CheckPhrase.order_index,
                      models.CheckPhrase.id)).all():
        if (cp.text or "").strip():
            out.setdefault(cp.phrase_id, []).append(cp.text.strip())
    return out


def seed(session: Session, force: bool = False, dry: bool = False) -> dict:
    """Backfill/refresh PhraseEmbedding for every phrase in non-deleted batches
    (private imports included — their owner's Live benefits too). Idempotent:
    a row is re-embedded only when its text_hash / model / dim no longer match.
    Returns counters."""
    from . import models
    s = get_settings()
    batch_ids = {b.id for b in session.exec(
        select(models.Batch).where(models.Batch.deleted_at == None)).all()}  # noqa: E711
    phrases = [p for p in session.exec(select(models.Phrase)).all()
               if p.batch_id in batch_ids]
    triggers = _trigger_map(session)
    existing = {e.phrase_id: e for e in
                session.exec(select(models.PhraseEmbedding)).all()}

    # Prune vectors whose phrase is gone (or whose batch was soft-deleted):
    # orphans are silent dead weight at best, and a mis-attached stale vector
    # at worst once SQLite recycles the phrase id.
    live_pids = {p.id for p in phrases}
    pruned = 0
    for pid, e in list(existing.items()):
        if pid not in live_pids:
            pruned += 1
            if not dry:
                session.delete(e)
            existing.pop(pid)

    stale: list[tuple] = []   # (phrase, text, hash)
    fresh = 0
    for p in phrases:
        text = phrase_embed_text(p, triggers.get(p.id, []))
        h = text_hash(text)
        e = existing.get(p.id)
        if (not force and e is not None and e.text_hash == h
                and e.model == s.model_embed and e.dim == s.embed_dim
                and len(e.vector) == s.embed_dim * 4):
            fresh += 1
            continue
        stale.append((p, text, h))

    counters = {"phrases": len(phrases), "fresh": fresh,
                "embedded": 0 if dry else len(stale),
                "would_embed": len(stale) if dry else 0,
                "pruned": pruned}
    if dry or not stale:
        if pruned and not dry:
            session.commit()
        return counters

    vectors = embed_texts([t for _p, t, _h in stale])
    from .models import PhraseEmbedding
    for (p, _text, h), vec in zip(stale, vectors):
        e = existing.get(p.id)
        if e is None:
            e = PhraseEmbedding(phrase_id=p.id)
            session.add(e)
        e.model, e.dim, e.text_hash, e.vector = s.model_embed, s.embed_dim, h, vec
    session.commit()
    return counters


if __name__ == "__main__":
    import argparse
    import json as _json

    from .db import engine, init_db

    ap = argparse.ArgumentParser(
        description="Seed/refresh the Live-mode phrase-embedding index.")
    ap.add_argument("--dry", action="store_true", help="report only, no writes")
    ap.add_argument("--force", action="store_true", help="re-embed everything")
    a = ap.parse_args()
    init_db()                       # ensure the PhraseEmbedding table exists
    with Session(engine()) as s:
        print(_json.dumps(seed(s, force=a.force, dry=a.dry), ensure_ascii=False))
    from . import doctor
    doctor.verdict("embeddings")
