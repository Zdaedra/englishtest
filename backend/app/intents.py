"""Conversational-move (intent) taxonomy for Live mode — DB-backed.

The relevance axis is the MOVE, not word overlap: every dictated moment maps
to a conversational move (осадить, попросить, удержать позицию…), the LLM
ranks the top moves for the moment, the user can override with one tap, and
the candidate pool prefilters to batches TAGGED with that move.

The tags are a linked entity in OUR database (models.BatchIntent), derived
from OUR content and re-syncable at any time:

    python -m app.intents            # seed/resync from Batch.section
    python -m app.intents --llm      # + LLM-classify batches with no mapping
    python -m app.intents --dry      # report only, no writes

SECTION_INTENTS below is the DERIVATION RULE (section → moves), not the
runtime source: runtime reads BatchIntent rows, so curators can hand-tag any
batch (source="manual" — the seeder never touches those). A batch with NO
rows serves every move (universal — e.g. private imports). The key list is
FIXED: prompt (scoring), client chips (intent.* i18n) and tests speak it.
"""
from sqlmodel import Session, select

# key -> RU gloss (prompt-side; the client localizes chip labels itself)
INTENTS: dict[str, str] = {
    "pushback": "осадить / не согласиться",
    "hold": "удержать позицию",
    "ask": "попросить / добиться",
    "warm": "расположить",
    "buy_time": "выиграть время",
    "clarify": "уточнить / переспросить",
    "close": "зафиксировать / закрыть",
    "smooth": "сгладить / извиниться",
}

# Derivation rule: what moves a batch SECTION serves. Applied by seed(); the
# result lives in BatchIntent rows (re-derivable, so editing this map + re-run
# is the "migration").
SECTION_INTENTS: dict[str, tuple[str, ...]] = {
    "live-tone": ("pushback", "clarify", "hold"),
    "pressure": ("pushback", "hold", "buy_time"),
    "negotiation": ("hold", "close", "buy_time", "clarify"),
    "composure": ("hold", "buy_time"),
    "gravitas": ("hold",),
    "lead-presence": ("hold",),
    "leadership": ("hold", "ask"),
    "requests": ("ask",),
    "small-talk": ("warm",),
    "charisma": ("warm",),
    "flirt": ("warm",),
    "intimacy": ("warm", "smooth"),
    "repair": ("smooth",),
    "pitch": ("close",),
    "stage": ("close", "hold"),
    "written": ("clarify", "ask"),
}

_MIN_POOL = 8


def intent_map(session: Session, batch_ids) -> dict[int, set[str]]:
    """batch_id -> set of tagged moves, for the given batches. Batches absent
    from the result have no tags = universal (serve every move)."""
    from . import models
    ids = [i for i in set(batch_ids) if i is not None]
    if not ids:
        return {}
    out: dict[int, set[str]] = {}
    for r in session.exec(select(models.BatchIntent)
                          .where(models.BatchIntent.batch_id.in_(ids))).all():
        out.setdefault(r.batch_id, set()).add(r.intent)
    return out


def filter_rows(rows, intent: str, imap: dict[int, set[str]]):
    """Rows whose batch is tagged with the intent; untagged batches always
    qualify (universal). Falls back to ALL rows when the filter leaves too
    little to pick from — a starved pool gives the LLM nothing to work with."""
    keep = []
    for r in rows:
        tags = imap.get(r[2].id)
        if tags is None or intent in tags:
            keep.append(r)
    return keep if len(keep) >= _MIN_POOL else rows


def seed(session: Session, use_llm: bool = False, dry: bool = False) -> dict:
    """Derive BatchIntent rows for every non-deleted batch from OUR content:
    Batch.section via SECTION_INTENTS (+ optional LLM classification of the
    batch's own phrases when the section has no mapping). Idempotent resync:
    auto rows (section/llm) are added/removed to match; manual rows are never
    touched. Returns counters."""
    from . import models
    batches = session.exec(select(models.Batch)
                           .where(models.Batch.deleted_at == None)).all()  # noqa: E711
    existing: dict[int, list] = {}
    for r in session.exec(select(models.BatchIntent)).all():
        existing.setdefault(r.batch_id, []).append(r)

    added = removed = tagged = universal = llm_used = 0
    for b in batches:
        desired = set(SECTION_INTENTS.get((b.section or "").strip(), ()))
        src = "section"
        if not desired and use_llm:
            phrases = list(session.exec(
                select(models.Phrase.phrase_en)
                .where(models.Phrase.batch_id == b.id)
                .order_by(models.Phrase.order_index)).all())
            if phrases:
                from . import scoring
                desired = set(scoring.classify_intents(b.title, phrases))
                if desired:
                    src, llm_used = "llm", llm_used + 1
        cur = existing.get(b.id, [])
        manual = {r.intent for r in cur if r.source == "manual"}
        auto_rows = [r for r in cur if r.source != "manual"]
        want_auto = {k for k in desired if k in INTENTS and k not in manual}
        for r in auto_rows:                       # drop stale auto tags
            if r.intent not in want_auto:
                removed += 1
                if not dry:
                    session.delete(r)
        have_auto = {r.intent for r in auto_rows}
        for k in sorted(want_auto - have_auto):   # add missing auto tags
            added += 1
            if not dry:
                session.add(models.BatchIntent(batch_id=b.id, intent=k, source=src))
        if desired or manual:
            tagged += 1
        else:
            universal += 1
    if not dry:
        session.commit()
    return {"batches": len(batches), "tagged": tagged, "universal": universal,
            "rows_added": added, "rows_removed": removed, "llm_classified": llm_used}


if __name__ == "__main__":
    import argparse
    import json as _json

    from .db import engine

    ap = argparse.ArgumentParser(
        description="Seed/resync BatchIntent tags from batch sections.")
    ap.add_argument("--llm", action="store_true",
                    help="LLM-classify batches whose section has no mapping")
    ap.add_argument("--dry", action="store_true", help="report only, no writes")
    a = ap.parse_args()
    with Session(engine()) as s:
        print(_json.dumps(seed(s, use_llm=a.llm, dry=a.dry), ensure_ascii=False))
