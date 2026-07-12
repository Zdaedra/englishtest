"""app.export_context — the blessed, slot-keyed cues/situation export.

Guards the D1b-class confusion: a text/anchor-keyed snapshot silently drops
rephrased phrases (anchors change on rephrase). The export MUST key by
(slug, order_index), cover every live phrase, carry only approved cues, skip
soft-deleted batches, and its metadata/markdown must state the slot-join rule.
"""
from datetime import datetime, timezone

from sqlmodel import Session

from app import export_context, models
from app.db import engine


def _phrase(s, batch_id, i, **kw):
    p = models.Phrase(batch_id=batch_id, order_index=i, anchor=f"a{i}",
                      phrase_en=f"phrase {i}", **kw)
    s.add(p)
    s.flush()
    return p


def _seed():
    with Session(engine()) as s:
        b = models.Batch(title="Live", slug="live-1", status="approved")
        s.add(b)
        s.flush()
        p1 = _phrase(s, b.id, 1, situation_ru="ситуация 1", task_ru="задача 1")
        _phrase(s, b.id, 2)  # no situation, no cues
        # two approved cues on p1 (+ one draft that must be excluded)
        for i, (txt, st) in enumerate([("cue A", "approved"),
                                       ("cue B", "approved"),
                                       ("draft cue", "draft")]):
            s.add(models.CheckPhrase(phrase_id=p1.id, batch_id=b.id, text=txt,
                                     lang="en", kind="stimulus",
                                     order_index=i, status=st))
        # soft-deleted batch → must NOT appear in the export
        dead = models.Batch(title="Dead", slug="dead-1", status="approved",
                            deleted_at=datetime.now(timezone.utc))
        s.add(dead)
        s.flush()
        _phrase(s, dead.id, 1)
        s.commit()


def test_export_is_slot_keyed_and_skips_deleted():
    _seed()
    rows = export_context.collect()["phrases"]
    assert all("slug" in r and "order_index" in r for r in rows)
    assert {(r["slug"], r["order_index"]) for r in rows} == {("live-1", 1), ("live-1", 2)}
    assert "dead-1" not in {r["slug"] for r in rows}


def test_only_approved_cues_and_meta_declares_slot_key():
    _seed()
    data = export_context.collect()
    by = {(r["slug"], r["order_index"]): r for r in data["phrases"]}
    assert by[("live-1", 1)]["cues"] == ["cue A", "cue B"]   # draft excluded, order kept
    assert by[("live-1", 2)]["cues"] == []
    assert by[("live-1", 1)]["situation_ru"] == "ситуация 1"
    m = data["_meta"]
    assert m["key"] == "(slug, order_index)"
    assert m["phrases"] == 2 and m["with_cues"] == 1 and m["total_cues"] == 2


def test_md_carries_the_join_by_slot_warning():
    _seed()
    md = export_context.to_md(export_context.collect())
    assert "(slug, order_index)" in md
    assert "app.rephrase" in md          # explains WHY not to join by text
    assert "## live-1" in md
