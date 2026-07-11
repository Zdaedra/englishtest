"""Canonical export of each phrase's CONTEXT — situation/task + approved cues —
keyed by the STABLE slot `(slug, order_index)`.

Why this module exists (the bug it prevents):
    cues + situations are derived from a phrase's anchor+phrase_en, and BOTH
    change on `app.rephrase` (D1b replaced 340 anchors). Any snapshot keyed by
    anchor/text goes stale the moment content is rephrased — a consumer that
    joins by anchor then SILENTLY drops every rephrased phrase. This bit us once:
    a pre-D1b `check_phrases.json` joined at 57% and looked like "half the
    context is missing" when nothing was actually lost.

    The phrase's identity is the slot `(slug, order_index)` — it survives every
    text edit (CONTENT-GRAPH §1). So the ONE blessed export is keyed by slot and
    regenerated from the live DB on demand. Never hand-key a cues export by text.

Usage:
    docker exec english_app python -m app.export_context            # JSON → stdout
    docker exec english_app python -m app.export_context --md       # markdown → stdout
    docker exec english_app python -m app.export_context > ctx.json
"""
import json
import sys
from datetime import datetime, timezone

from sqlmodel import Session, select

from . import models
from .db import engine, init_db

KEY = "(slug, order_index)"
_JOIN_RULE = ("JOIN BY SLOT (slug, order_index) — anchor/phrase_en change on "
              "app.rephrase; joining by text/anchor silently drops rephrased phrases.")


def collect() -> dict:
    """Slot-keyed context for every live phrase, plus a provenance `_meta`."""
    with Session(engine()) as s:
        batches = {b.id: b for b in s.exec(
            select(models.Batch).where(models.Batch.deleted_at == None)).all()}  # noqa: E711
        cues: dict[int, list[str]] = {}
        for c in s.exec(select(models.CheckPhrase)
                        .where(models.CheckPhrase.status == "approved")
                        .order_by(models.CheckPhrase.phrase_id,
                                  models.CheckPhrase.order_index)).all():
            cues.setdefault(c.phrase_id, []).append(c.text)
        rows: list[dict] = []
        for p in s.exec(select(models.Phrase)
                        .order_by(models.Phrase.batch_id,
                                  models.Phrase.order_index)).all():
            b = batches.get(p.batch_id)
            if b is None:                       # soft-deleted batch → out
                continue
            rows.append({
                "slug": b.slug,
                "order_index": p.order_index,
                "anchor": p.anchor,
                "phrase_en": p.phrase_en,
                "gloss_ru": p.gloss_ru or "",
                "situation_ru": p.situation_ru or "",
                "task_ru": p.task_ru or "",
                "cues": cues.get(p.id, []),
            })
    meta = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "key": KEY,
        "join_rule": _JOIN_RULE,
        "phrases": len(rows),
        "with_situation": sum(1 for r in rows if r["situation_ru"]),
        "with_cues": sum(1 for r in rows if r["cues"]),
        "total_cues": sum(len(r["cues"]) for r in rows),
    }
    return {"_meta": meta, "phrases": rows}


def to_md(data: dict) -> str:
    m = data["_meta"]
    out = [
        "# Проверочные фразы (cues) + ситуации — снапшот с прода",
        "",
        f"> **АВТО-СНАПШОТ · {m['generated_at']}.** Регенерация:",
        "> `docker exec english_app python -m app.export_context --md > _prod_check_phrases.md`",
        f"> **Ключ = {m['key']}.** НИКОГДА не джойнить по `anchor` / `phrase_en` —",
        "> они меняются при `app.rephrase`, и джойн по тексту молча теряет переписанные фразы.",
        f"> {m['phrases']} фраз · ситуация у {m['with_situation']} · "
        f"cues у {m['with_cues']} ({m['total_cues']} шт).",
        "",
    ]
    cur = None
    for r in data["phrases"]:
        if r["slug"] != cur:
            cur = r["slug"]
            out.append(f"\n## {cur}\n")
        cues = " · ".join(r["cues"]) if r["cues"] else "—"
        out.append(f"- **#{r['order_index']} {r['anchor']}** — {r['phrase_en']}")
        out.append(f"  - ситуация: {r['situation_ru'] or '—'}")
        out.append(f"  - cues: {cues}")
    return "\n".join(out) + "\n"


def main(argv: list[str]) -> None:
    init_db()
    data = collect()
    if "--md" in argv:
        sys.stdout.write(to_md(data))
    else:
        sys.stdout.write(json.dumps(data, ensure_ascii=False))
        sys.stdout.write("\n")


if __name__ == "__main__":
    main(sys.argv[1:])
