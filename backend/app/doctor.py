"""Integrity doctor: find (and safely fix) internal inconsistencies between
curated content, derived caches and per-user progress state.

Why it exists: content changes (rephrase/restory/upsert) and out-of-app writes
(sqlite3 CLI runs with foreign_keys=OFF) can leave the DB in states the app never
creates itself — orphaned SRS rows, stats re-attached to recycled phrase ids,
stale mnemo spans. Each of those surfaces as a "мистическая" product bug: ghost
due-counts in mastery, spurious 409s in the Arena, tap-to-reveal highlighting the
wrong word. This tool makes them visible — and the safe ones fixable.

    python -m app.doctor            # report only (exit 1 if problems found)
    python -m app.doctor --fix      # also apply the SAFE fixes (see below)

Checks:
  1. orphans          — rows whose phrase_id points at no live Phrase:
                        UserPhraseStat / PhraseAttempt / ReviewEvent (fixable:
                        delete — they are unreachable and only corrupt rollups),
                        TrainingEvent (report-only: its timestamps feed the streak),
                        CheckPhrase / ContextExample (fixable: delete).
  2. cross-attach     — UserPhraseStat.batch_id != its Phrase.batch_id: the
                        signature of SQLite rowid reuse after an FK-off wipe
                        (stats silently re-attached to a different batch's
                        phrase). Report-only: needs human review.
  3. duplicate stats  — >1 UserPhraseStat per (user_id, phrase_id) (fixable:
                        keep the most-progressed row, delete the rest).
  4. spans            — MnemoStory.spans disagree with a fresh recompute against
                        current anchors, or span count != phrase count
                        (fix: run `python -m app.restory`).
  5. content drift    — content/*.json anchors/en differ from the DB
                        (fix: run `python -m app.rephrase`), or phrase count
                        differs (needs re-author).
  6. cache holes      — phrases missing situation_ru/task_ru (fix: gen_context);
                        i18n holes: for every language the catalog is translated
                        into (union over ALL curated batches — not per-batch
                        title_i18n keys, which go blind the moment a re-title
                        invalidates them), any missing title/subtitle/theme/
                        gloss/story translation (fix: i18n_content --refill).
  7. checkphrase gaps — cues (проверочные) live ONLY in the DB — no content
                        file to drift against — and app.rephrase DROPS a
                        phrase's cues when its text changes. This check is what
                        makes forgetting to re-author them impossible:
                        phrases without cues inside an otherwise-cued batch
                        (the rephrase signature), and whole uncued batches in
                        an otherwise-cued catalog. Report-only; the fix is
                        re-authoring cues (see CONTENT-GRAPH.md). Silent on
                        dev DBs that use no cues at all.

The full asset dependency map (what derives from what, which chain to run after
which edit) lives in CONTENT-GRAPH.md at the repo root.

Nobody has to remember to run this — it runs itself (report-only everywhere;
--fix stays a conscious human action):
  - in-process: shortly after app startup, then daily → docker logs
    (`doctor_loop`, wired in app/main.py startup);
  - after every catalog mutation over HTTP: /api/imports/upsert and /seed
    include the fresh report as a "doctor" key in their response — after a
    replace it doubles as the list of regeneration steps that remain;
  - at the end of every content chain tool (rephrase / restory / seed /
    seed_presence / gen_context / i18n_content) via `verdict()`.
"""
import argparse
import json

from sqlmodel import Session, select

from . import models
from .content import content_dir
from .db import engine, init_db
from .importer import _compute_spans
from .schemas import PhraseIn


def _pick_best_stat(rows: list) -> object:
    """The row to KEEP among duplicates: most attempts, then latest activity,
    then highest id (newest)."""
    def key(st):
        seen = st.last_seen_at.isoformat() if st.last_seen_at else ""
        return (st.attempts or 0, seen, st.id or 0)
    return max(rows, key=key)


def run(fix: bool = False) -> dict:
    problems: dict = {}
    with Session(engine()) as s:
        live_phrase_ids = {p.id for p in s.exec(select(models.Phrase)).all()}
        phrase_by_id = {p.id: p for p in s.exec(select(models.Phrase)).all()}

        # -- 1. orphans ------------------------------------------------------
        fixable_orphans = {models.UserPhraseStat: "user_phrase_stats",
                           models.PhraseAttempt: "phrase_attempts",
                           models.ReviewEvent: "review_events",
                           models.CheckPhrase: "check_phrases",
                           models.ContextExample: "context_examples"}
        for tbl, name in fixable_orphans.items():
            rows = [r for r in s.exec(select(tbl)).all()
                    if r.phrase_id not in live_phrase_ids]
            if rows:
                problems[f"orphaned_{name}"] = len(rows)
                print(f"  ORPHANS {name}: {len(rows)}"
                      + (" — deleting" if fix else " (run --fix to delete)"))
                if fix:
                    for r in rows:
                        s.delete(r)
                    s.commit()
        te_orphans = [r for r in s.exec(select(models.TrainingEvent)).all()
                      if r.phrase_id not in live_phrase_ids]
        if te_orphans:
            problems["orphaned_training_events"] = len(te_orphans)
            print(f"  ORPHANS training_events: {len(te_orphans)} — kept "
                  f"(their timestamps feed the day-streak); review manually")

        # -- 2. cross-attach (rowid reuse signature) --------------------------
        cross = [st for st in s.exec(select(models.UserPhraseStat)).all()
                 if st.phrase_id in phrase_by_id
                 and phrase_by_id[st.phrase_id].batch_id != st.batch_id]
        if cross:
            problems["cross_attached_stats"] = len(cross)
            print(f"  CROSS-ATTACH user_phrase_stats: {len(cross)} rows whose "
                  f"batch_id != their phrase's batch — likely rowid reuse after "
                  f"an FK-off wipe; review manually:")
            for st in cross[:10]:
                print(f"    stat id={st.id} user={st.user_id} phrase={st.phrase_id} "
                      f"stat.batch={st.batch_id} phrase.batch="
                      f"{phrase_by_id[st.phrase_id].batch_id}")

        # -- 3. duplicate (user, phrase) stats --------------------------------
        by_key: dict = {}
        for st in s.exec(select(models.UserPhraseStat)).all():
            by_key.setdefault((st.user_id, st.phrase_id), []).append(st)
        dups = {k: v for k, v in by_key.items() if len(v) > 1}
        if dups:
            problems["duplicate_stats"] = sum(len(v) - 1 for v in dups.values())
            print(f"  DUPLICATES user_phrase_stats: {len(dups)} (user,phrase) keys"
                  + (" — keeping the most-progressed row of each"
                     if fix else " (run --fix to dedup)"))
            if fix:
                for rows in dups.values():
                    keep = _pick_best_stat(rows)
                    for r in rows:
                        if r is not keep:
                            s.delete(r)
                s.commit()

        # -- 4. spans vs current anchors --------------------------------------
        # Content checks (4-6) scope to the CURATED catalog (owner_id NULL):
        # private user imports legitimately lack gen_context/i18n/content files,
        # and flagging them would keep doctor permanently red on a healthy DB.
        batches = {b.id: b for b in s.exec(select(models.Batch).where(
            models.Batch.deleted_at == None,   # noqa: E711
            models.Batch.owner_id == None)).all()}  # noqa: E711
        stale_spans, missing_anchors = [], []
        for m in s.exec(select(models.MnemoStory)).all():
            b = batches.get(m.batch_id)
            if not b or not (m.story_ru or "").strip():
                continue
            phrases = sorted((p for p in phrase_by_id.values()
                              if p.batch_id == m.batch_id),
                             key=lambda p: p.order_index)
            if not phrases:
                continue
            spans, warns = _compute_spans(m.story_ru, [
                PhraseIn(order_index=p.order_index, anchor=p.anchor,
                         phrase_en=p.phrase_en) for p in phrases])
            fresh = [sp.model_dump() for sp in spans]
            if (m.spans or []) != fresh:
                stale_spans.append(b.slug)
            elif len(fresh) != len(phrases):
                # spans match a fresh recompute — the story simply lacks some
                # anchor(s). restory would be a no-op; the CONTENT needs fixing.
                missing_anchors.append(f"{b.slug} (-{len(phrases) - len(fresh)})")
        if stale_spans:
            problems["stale_spans"] = len(stale_spans)
            print(f"  STALE SPANS: {len(stale_spans)} batch(es) — run "
                  f"`python -m app.restory`: {', '.join(sorted(stale_spans))}")
        if missing_anchors:
            problems["missing_anchors"] = len(missing_anchors)
            print(f"  MISSING ANCHORS: {len(missing_anchors)} batch(es) whose "
                  f"story lacks some anchor(s) — fix the story/anchor in the "
                  f"content file, then rephrase/restory: "
                  f"{', '.join(sorted(missing_anchors))}")

        # -- 5. content drift (files vs DB) -----------------------------------
        drifted, structural = [], []
        slug_to_batch = {b.slug: b for b in batches.values()}
        for path in sorted(content_dir().glob("*.json")):
            if path.name.startswith("."):
                continue
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except Exception:  # noqa: BLE001
                continue
            b = slug_to_batch.get(data.get("slug", ""))
            cphrases = data.get("phrases") or []
            if not b or not cphrases:
                continue
            phrases = sorted((p for p in phrase_by_id.values()
                              if p.batch_id == b.id),
                             key=lambda p: p.order_index)
            if len(phrases) != len(cphrases):
                structural.append(b.slug)
                continue
            for cp, dp in zip(cphrases, phrases):
                if (cp.get("anchor", dp.anchor) != dp.anchor
                        or cp.get("en", dp.phrase_en) != dp.phrase_en):
                    drifted.append(b.slug)
                    break
        if drifted:
            problems["content_drift"] = len(drifted)
            print(f"  CONTENT DRIFT: {len(drifted)} batch(es) differ from their "
                  f"content file — run `python -m app.rephrase`: "
                  f"{', '.join(sorted(drifted))}")
        if structural:
            problems["structural_drift"] = len(structural)
            print(f"  STRUCTURAL DRIFT: {len(structural)} batch(es) have a "
                  f"different phrase COUNT than their file (needs re-author): "
                  f"{', '.join(sorted(structural))}")

        # -- 6. cache holes ----------------------------------------------------
        no_ctx = [p for p in phrase_by_id.values()
                  if p.batch_id in batches
                  and (not (p.situation_ru or "").strip()
                       or not (p.task_ru or "").strip())]
        if no_ctx:
            problems["missing_situation_task"] = len(no_ctx)
            print(f"  CACHE HOLES situation_ru/task_ru: {len(no_ctx)} phrase(s) — "
                  f"run `python -m app.gen_context`")
        # Expected languages = union of every i18n dict across the curated
        # catalog. Per-batch title_i18n keys alone are a blind spot: a batch
        # whose translations were invalidated (retitle/re-author) or never
        # filled has no keys and would silently pass. Empty on dev DBs → the
        # whole i18n check stays silent there.
        mnemo_by_batch = {m.batch_id: m for m in
                          s.exec(select(models.MnemoStory)).all()}
        langs = set()
        for b in batches.values():
            for d in (b.title_i18n, b.subtitle_i18n, b.theme_i18n):
                langs |= set(d or {})
            m = mnemo_by_batch.get(b.id)
            if m:
                langs |= set(m.story_i18n or {})
        for p in phrase_by_id.values():
            if p.batch_id in batches:
                langs |= set(p.gloss_i18n or {})
        i18n_holes = set()
        for b in batches.values():
            m = mnemo_by_batch.get(b.id)
            for lang in langs:
                base_fields = (
                    (b.title, b.title_i18n), (b.subtitle, b.subtitle_i18n),
                    (b.theme, b.theme_i18n))
                hole = any((base or "").strip() and not (d or {}).get(lang)
                           for base, d in base_fields)
                if not hole and m and (m.story_ru or "").strip() and not (
                        (m.story_i18n or {}).get(lang)
                        and (m.spans_i18n or {}).get(lang)):
                    hole = True
                if not hole:
                    hole = any(
                        p.batch_id == b.id and (p.gloss_ru or "").strip()
                        and not (p.gloss_i18n or {}).get(lang)
                        for p in phrase_by_id.values())
                if hole:
                    i18n_holes.add(f"{b.slug}[{lang}]")
        if i18n_holes:
            problems["i18n_holes"] = len(i18n_holes)
            print(f"  CACHE HOLES i18n: {len(i18n_holes)} batch-lang(s) — run "
                  f"`python -m app.i18n_content --refill`: "
                  f"{', '.join(sorted(i18n_holes))}")

        # -- 7. checkphrase coverage -------------------------------------------
        cued = {cp.phrase_id for cp in s.exec(select(models.CheckPhrase)).all()}
        if cued:  # a catalog that uses cues at all (dev DBs stay silent)
            partial: dict = {}
            uncued = []
            for b in batches.values():
                phrases = [p for p in phrase_by_id.values()
                           if p.batch_id == b.id]
                if not phrases:
                    continue
                missing = sorted(p.order_index for p in phrases
                                 if p.id not in cued)
                if not missing:
                    continue
                if len(missing) == len(phrases):
                    uncued.append(b.slug)
                else:
                    partial[b.slug] = missing
            if partial:
                problems["checkphrase_holes"] = sum(
                    len(v) for v in partial.values())
                print(f"  CHECKPHRASE HOLES: "
                      f"{problems['checkphrase_holes']} phrase(s) without cues "
                      f"in otherwise-cued batch(es) — rephrase dropped them; "
                      f"re-author cues (see CONTENT-GRAPH.md): "
                      + ", ".join(f"{slug} #{','.join(map(str, v))}"
                                  for slug, v in sorted(partial.items())))
            if uncued:
                problems["uncued_batches"] = len(uncued)
                print(f"  UNCUED BATCHES: {len(uncued)} batch(es) with no cues "
                      f"at all in a cued catalog — author cues "
                      f"(see CONTENT-GRAPH.md): {', '.join(sorted(uncued))}")

    return problems


def verdict(label: str = "integrity") -> dict:
    """Report-only check for chain tools to END with, so 'run the doctor' is
    not a step anyone can forget. Never raises (a broken check must not kill
    the tool that just did real work); returns the problems dict."""
    print(f"\n-- doctor ({label}) " + "-" * 40)
    try:
        problems = run(fix=False)
    except Exception as e:  # noqa: BLE001
        print(f"DOCTOR ERROR: {e}")
        return {}
    print("DOCTOR: " + (", ".join(f"{k}={v}" for k, v in sorted(problems.items()))
                        if problems else "CLEAN"))
    return problems


async def doctor_loop() -> None:
    """In-process integrity monitor: report shortly after startup, then once a
    day, into the app log (`docker logs english_app`). Mirrors retention_loop.
    Report-only — fixes stay a conscious human action (--fix)."""
    import asyncio
    await asyncio.sleep(120)  # let startup/migrations settle first
    while True:
        try:
            await asyncio.to_thread(verdict, "daily monitor")
        except Exception:  # noqa: BLE001 — never let the monitor crash the app
            pass
        await asyncio.sleep(24 * 3600)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--fix", action="store_true",
                    help="apply the SAFE fixes (delete orphans except "
                         "training_events, dedup duplicate stats)")
    args = ap.parse_args()
    init_db()
    problems = run(fix=args.fix)
    if problems:
        total = sum(problems.values())
        print(f"\nPROBLEMS: {total} across {len(problems)} check(s): "
              + ", ".join(f"{k}={v}" for k, v in problems.items()))
        raise SystemExit(1)
    print("\nCLEAN: no integrity problems found")


if __name__ == "__main__":
    main()
