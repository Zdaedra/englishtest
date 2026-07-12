"""Conversational-move (intent) taxonomy for Live mode — phrase-level, DB-backed.

The relevance axis is the MOVE a line makes, not word overlap: every dictated
moment maps to a conversational move (расположить, повести, поддержать,
возразить…), the LLM ranks the top moves, the user can override with one tap,
and the candidate pool prefilters to the phrases TAGGED with that move.

Tags are a linked entity in OUR database, at TWO levels:

  * models.PhraseIntent — the AUTHORITATIVE per-phrase tag (1–3 moves/phrase).
    Battle picks by this: filter_rows keeps phrases tagged with the chosen move.
  * models.BatchIntent  — a coarse per-batch tag, the FALLBACK for a phrase that
    has no PhraseIntent rows (e.g. a user's private import). No rows at either
    level = universal (serves every move).

Both are seeded from OUR authored map and re-syncable at any time:

    python -m app.intents            # seed/resync from intents_curated.json
    python -m app.intents --dry      # report only, no writes

app/intents_curated.json is the source of truth (keyed by slug+order_index, so
it survives a rephrase that keeps order). SECTION_INTENTS below is only a
FALLBACK derivation for NEW batches not yet in that map. Per CONTENT-GRAPH.md,
replacing a phrase or its anchor requires re-authoring its tags — the move can
shift with the wording. The key list is FIXED: the scoring prompt, the client
chips (intent.* i18n) and the tests all speak it.
"""
import json
from pathlib import Path

from sqlmodel import Session, select

# key -> RU gloss (prompt-side; the client localizes chip labels itself).
# Order = the display/ranking order of the ten moves.
INTENTS: dict[str, str] = {
    "warm": "расположить — тепло, симпатия, интерес, включить в контакт",
    "clarify": "прояснить — уточнить, спросить, проверить сигнал, вытащить мнение",
    "pushback": "возразить — не согласиться, осадить, отбить неверную рамку, назвать риск",
    "hold": "удержать границу — не уступить, сказать нет, не оправдываться под давлением",
    "buy_time": "взять паузу — выиграть время, подумать, проверить, не отвечать сразу",
    "lead": "повести — взять управление, задать структуру, собрать комнату, дать следующий шаг",
    "ask": "попросить — попросить, пригласить, предложить действие или следующий шаг",
    "close": "зафиксировать — закрепить договорённость, закрыть встречу/сделку, поставить точку",
    "repair": "восстановить — извиниться, сгладить неловкость, починить контакт, снять напряжение",
    "support": "поддержать/открыться — быть рядом, валидировать чувство, признать боль, страх, желание",
}

# FALLBACK ONLY: what moves a batch SECTION serves, for content not present in
# intents_curated.json. Existing catalog batches are all curated (this map is
# never consulted for them); it just gives a freshly-authored batch a sane
# starting BatchIntent until a curator revises it. 10-key vocabulary.
SECTION_INTENTS: dict[str, tuple[str, ...]] = {
    "live-tone": ("pushback", "clarify", "hold"),
    "pressure": ("pushback", "hold", "buy_time"),
    "negotiation": ("hold", "close", "buy_time", "clarify"),
    "composure": ("hold", "buy_time", "pushback"),
    "gravitas": ("hold", "lead"),
    "lead-presence": ("lead", "hold"),
    "leadership": ("lead", "ask"),
    "requests": ("ask",),
    "small-talk": ("warm",),
    "charisma": ("warm", "lead"),
    "flirt": ("warm",),
    "intimacy": ("warm", "support"),
    "repair": ("repair", "support"),
    "pitch": ("close", "lead"),
    "stage": ("close", "hold", "lead"),
    "written": ("clarify", "ask"),
}

_MIN_POOL = 8


def _curated() -> dict:
    """The authored tag map. Missing file => empty (seed becomes a no-op)."""
    p = Path(__file__).resolve().parent / "intents_curated.json"
    if not p.exists():
        return {"batches": {}, "phrases": []}
    return json.loads(p.read_text(encoding="utf-8"))


def phrase_intent_map(session: Session, phrase_ids) -> dict[int, set[str]]:
    """phrase_id -> set of tagged moves. Phrases absent from the result have no
    phrase-level tag (caller falls back to the batch, then universal)."""
    from . import models
    ids = [i for i in set(phrase_ids) if i is not None]
    if not ids:
        return {}
    out: dict[int, set[str]] = {}
    for r in session.exec(select(models.PhraseIntent)
                          .where(models.PhraseIntent.phrase_id.in_(ids))).all():
        out.setdefault(r.phrase_id, set()).add(r.intent)
    return out


def batch_intent_map(session: Session, batch_ids) -> dict[int, set[str]]:
    """batch_id -> set of tagged moves (the coarse fallback). Batches absent from
    the result have no tags = universal."""
    from . import models
    ids = [i for i in set(batch_ids) if i is not None]
    if not ids:
        return {}
    out: dict[int, set[str]] = {}
    for r in session.exec(select(models.BatchIntent)
                          .where(models.BatchIntent.batch_id.in_(ids))).all():
        out.setdefault(r.batch_id, set()).add(r.intent)
    return out


# Back-compat alias (older callers referenced intent_map for the batch level).
intent_map = batch_intent_map


def filter_rows(rows, intent: str, pmap: dict[int, set[str]],
                bmap: dict[int, set[str]]):
    """Rows (Phrase, stat, Batch) that make the chosen move. A phrase with its own
    PhraseIntent tags qualifies iff `intent` is among them; a phrase with no
    phrase tags falls back to its batch's BatchIntent (untagged batch = universal).
    Falls back to ALL rows when the filter starves the pool — the LLM needs real
    options to pick from."""
    keep = []
    for r in rows:
        p, _st, b = r
        ptags = pmap.get(p.id)
        if ptags is not None:
            if intent in ptags:
                keep.append(r)
            continue
        btags = bmap.get(b.id)
        if btags is None or intent in btags:
            keep.append(r)
    return keep if len(keep) >= _MIN_POOL else rows


def seed(session: Session, dry: bool = False) -> dict:
    """Resync PhraseIntent + BatchIntent from app/intents_curated.json. Idempotent:
    auto rows (source="curated") are added/removed to match the map; manual rows
    are never touched. A batch not present in the curated map gets a section-derived
    fallback BatchIntent (no phrase rows). Migrates the old taxonomy automatically:
    any auto tag no longer in INTENTS (e.g. the retired "smooth", or old
    section-derived rows) is dropped and replaced by the curated ones. Returns
    counters."""
    from . import models
    cur = _curated()
    batch_tags: dict = cur.get("batches", {})       # slug -> [keys]
    phrase_tags: list = cur.get("phrases", [])      # [{slug, oi, intents}]

    batches = {b.slug: b for b in session.exec(
        select(models.Batch).where(models.Batch.deleted_at == None)).all()}  # noqa: E711
    pid_by_key: dict[tuple, int] = {}
    for b in batches.values():
        for p in session.exec(select(models.Phrase)
                              .where(models.Phrase.batch_id == b.id)).all():
            pid_by_key[(b.slug, p.order_index)] = p.id

    # ---- BatchIntent (coarse fallback) ----
    b_existing: dict[int, list] = {}
    for r in session.exec(select(models.BatchIntent)).all():
        b_existing.setdefault(r.batch_id, []).append(r)
    b_added = b_removed = 0
    for slug, b in batches.items():
        if slug in batch_tags:
            desired = {k for k in batch_tags[slug] if k in INTENTS}
        else:                                        # not curated -> section fallback
            desired = set(SECTION_INTENTS.get((b.section or "").strip(), ()))
        cur_rows = b_existing.get(b.id, [])
        manual = {r.intent for r in cur_rows if r.source == "manual"}
        auto = [r for r in cur_rows if r.source != "manual"]
        want = {k for k in desired if k not in manual}
        for r in auto:
            if r.intent not in want:
                b_removed += 1
                if not dry:
                    session.delete(r)
        have = {r.intent for r in auto}
        for k in sorted(want - have):
            b_added += 1
            if not dry:
                session.add(models.BatchIntent(batch_id=b.id, intent=k, source="curated"))

    # ---- PhraseIntent (authoritative) ----
    p_existing: dict[int, list] = {}
    for r in session.exec(select(models.PhraseIntent)).all():
        p_existing.setdefault(r.phrase_id, []).append(r)
    p_added = p_removed = p_missing = 0
    for rec in phrase_tags:
        pid = pid_by_key.get((rec.get("slug"), rec.get("oi")))
        if pid is None:
            p_missing += 1
            continue
        desired = {k for k in rec.get("intents", []) if k in INTENTS}
        cur_rows = p_existing.get(pid, [])
        manual = {r.intent for r in cur_rows if r.source == "manual"}
        auto = [r for r in cur_rows if r.source != "manual"]
        want = {k for k in desired if k not in manual}
        for r in auto:
            if r.intent not in want:
                p_removed += 1
                if not dry:
                    session.delete(r)
        have = {r.intent for r in auto}
        for k in sorted(want - have):
            p_added += 1
            if not dry:
                session.add(models.PhraseIntent(phrase_id=pid, intent=k, source="curated"))

    if not dry:
        session.commit()
    return {"batches": len(batches), "phrases_in_map": len(phrase_tags),
            "phrase_rows_added": p_added, "phrase_rows_removed": p_removed,
            "phrases_unmatched": p_missing,
            "batch_rows_added": b_added, "batch_rows_removed": b_removed}


if __name__ == "__main__":
    import argparse
    import json as _json

    from .db import engine, init_db

    ap = argparse.ArgumentParser(
        description="Seed/resync intent tags from app/intents_curated.json.")
    ap.add_argument("--dry", action="store_true", help="report only, no writes")
    a = ap.parse_args()
    init_db()                       # ensure PhraseIntent/BatchIntent tables exist
    with Session(engine()) as s:
        print(_json.dumps(seed(s, dry=a.dry), ensure_ascii=False))
