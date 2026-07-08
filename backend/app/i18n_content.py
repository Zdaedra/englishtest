"""Translate the curated catalog content into es/de/fr and store it in the
`*_i18n` JSON columns. Russian is the source. The English-being-learned (anchor
words, `phrase_en`) is NEVER translated — anchors stay English verbatim inside
the translated mnemonic story, in the same order, so we can recompute their
character spans against the translated text.

Run (inside the backend container / venv):
    python -m app.i18n_content            # translate all batches × es,de,fr
    python -m app.i18n_content --batch 12 # one batch
    python -m app.i18n_content --lang es  # one language
"""
from __future__ import annotations

import argparse
import json
from typing import Optional

from sqlmodel import Session, select

from . import llm, models
from .db import engine, init_db
from .localize import BASE

LANGS = ("es", "de", "fr")
_LANG_NAME = {"es": "Spanish", "de": "German", "fr": "French"}

# Delimiter protocol (NOT JSON): translated prose freely contains quotes, commas
# and dashes, which makes model-emitted JSON fragile (~13% invalid). A simple
# `@@@KEY` block format sidesteps all string-escaping — each value is just the raw
# lines under its marker until the next marker.
_SYSTEM = (
    "You are a professional localizer for a premium English-learning app. You "
    "translate the app's CONTENT from Russian into {lang_name}. CRITICAL RULES:\n"
    "1. The text contains lowercase or ALL-CAPS English ANCHOR words (e.g. "
    "understand, walk, read). These are the English the learner is studying — "
    "NEVER translate, alter, reorder, or remove them. Keep each anchor EXACTLY as "
    "written (same spelling and case) and in the SAME order it appears.\n"
    "2. In the mnemonic story, translate ONLY the connective {lang_name} prose "
    "around the anchors. Every anchor must still appear verbatim, in the same "
    "order, the same number of times as in the source.\n"
    "3. Keep the vivid, concrete, scene-building tone — it's a memory device.\n"
    "4. Translate titles, subtitles, theme, zone titles and glosses naturally and "
    "concisely for a {lang_name} speaker.\n"
    "5. OUTPUT FORMAT: blocks separated by marker lines. Each marker is on its own "
    "line and starts with @@@. After a marker line, put ONLY that field's "
    "translated text (it may span lines). Do NOT add quotes, JSON, or commentary. "
    "Emit markers EXACTLY as requested and ONLY for fields present in the source."
)

_USER_TMPL = (
    "Translate this batch's content into {lang_name}, using the @@@ block format. "
    "Emit these markers, in this order, each followed by the translated value:\n"
    "@@@TITLE\n@@@SUBTITLE\n@@@THEME\n@@@STORY\n"
    "then one @@@ZONE:<id> per zone and one @@@GLOSS:<id> per gloss, reusing the "
    "ids given below.\n"
    "The text after @@@STORY MUST contain these anchors verbatim, in this order: "
    "{anchors}\n\n"
    "SOURCE (Russian):\n{payload}"
)


def _parse_blocks(raw: str) -> dict:
    """Parse the @@@KEY block format into {title, subtitle, theme, story,
    zones:{id:txt}, glosses:{id:txt}}."""
    out: dict = {"zones": {}, "glosses": {}}
    cur_key = None
    cur_kind = None  # "scalar" | ("zones"|"glosses", id)
    buf: list[str] = []

    def flush():
        if cur_kind is None:
            return
        val = "\n".join(buf).strip()
        if cur_kind == "scalar":
            out[cur_key] = val
        elif isinstance(cur_kind, tuple):
            out[cur_kind[0]][cur_kind[1]] = val

    for line in raw.splitlines():
        m = line.strip()
        if m.startswith("@@@"):
            flush()
            buf = []
            tag = m[3:].strip()
            up = tag.upper()
            if up in ("TITLE", "SUBTITLE", "THEME", "STORY"):
                cur_key, cur_kind = up.lower(), "scalar"
            elif ":" in tag:
                kind, _, ident = tag.partition(":")
                k = kind.strip().upper()
                ident = ident.strip()
                if k == "ZONE":
                    cur_key, cur_kind = None, ("zones", ident)
                elif k == "GLOSS":
                    cur_key, cur_kind = None, ("glosses", ident)
                else:
                    cur_key, cur_kind = None, None
            else:
                cur_key, cur_kind = None, None
        else:
            buf.append(line)
    flush()
    return out


def _anchor_surfaces(story: str, spans: list[dict]) -> list[str]:
    """The English anchor words in story order (by char offset)."""
    ordered = sorted((s for s in spans if "start" in s and "end" in s),
                     key=lambda s: s["start"])
    return [story[s["start"]:s["end"]] for s in ordered]


def _all_occurrences(hay: str, needle: str) -> list[int]:
    """Every start index of `needle` in `hay`, case-insensitive."""
    if not needle:
        return []
    h, n = hay.lower(), needle.lower()
    out, i = [], h.find(n)
    while i >= 0:
        out.append(i)
        i = h.find(n, i + 1)
    return out


def recompute_spans(orig_story: str, orig_spans: list[dict],
                    new_story: str) -> Optional[list[dict]]:
    """Rebuild anchor spans against the translated story. The anchors are English
    and must appear verbatim, but a translation may legitimately REORDER them
    (German verb-final word order, French syntax). So we locate each anchor at any
    not-yet-used occurrence rather than requiring source order, then sort the
    resulting spans by position — every consumer reads spans sorted by offset and
    maps each span's anchor_id→phrase independently, so order-independence is safe.
    Returns None only if some anchor truly isn't present (caller keeps the Russian
    story for that language)."""
    ordered = sorted((s for s in orig_spans if "start" in s and "end" in s),
                     key=lambda s: s["start"])
    used: list[tuple[int, int]] = []
    out: list[dict] = []
    for sp in ordered:
        surface = orig_story[sp["start"]:sp["end"]]
        n = len(surface)
        pick = None
        for pos in _all_occurrences(new_story, surface):
            if all(pos + n <= u0 or pos >= u1 for (u0, u1) in used):  # no overlap
                pick = pos
                break
        if pick is None:
            return None
        used.append((pick, pick + n))
        out.append({"anchor_id": sp.get("anchor_id"), "phrase_id": sp.get("phrase_id"),
                    "start": pick, "end": pick + n})
    out.sort(key=lambda s: s["start"])
    return out


def _translate_call(payload: dict, anchors: list[str], lang: str) -> dict:
    name = _LANG_NAME[lang]
    system = _SYSTEM.format(lang_name=name)
    user = _USER_TMPL.format(lang_name=name, anchors=" → ".join(anchors) or "(none)",
                             payload=json.dumps(payload, ensure_ascii=False, indent=2))
    raw = llm.chat(system, user, temperature=0.2)
    return _parse_blocks(raw)


def _missing(anchors: list[str], story: Optional[str]) -> list[str]:
    s = (story or "").lower()
    return [a for a in anchors if a.lower() not in s]


def _translate_story(story_ru: str, anchors: list[str], lang: str,
                     missing: list[str], temperature: float) -> str:
    """Focused re-translation of JUST the mnemonic story, used to repair a story
    that dropped/translated an anchor. Names the offending anchors explicitly."""
    name = _LANG_NAME[lang]
    system = (
        f"You translate one short mnemonic story from Russian into {name}. The "
        "story embeds English ANCHOR words that the learner is studying. COPY every "
        "anchor EXACTLY as given (same spelling) — do NOT translate them into "
        f"{name}, even if a natural {name} word exists. Translate only the prose "
        "around them. Keep every anchor, all of them, the same number of times. "
        "Output ONLY the translated story text — no quotes, labels or commentary."
    )
    warn = (f"\nThese anchors were WRONGLY translated/dropped last time — they MUST "
            f"appear verbatim: {', '.join(missing)}." if missing else "")
    user = (f"Anchors to keep verbatim, in this order: {' → '.join(anchors)}.{warn}\n\n"
            f"Russian story:\n{story_ru}")
    return llm.chat(system, user, temperature=temperature).strip()


def translate_batch(session: Session, batch: models.Batch, lang: str,
                    force: bool = False, refill: bool = False) -> dict:
    """Translate one batch into `lang`, write the *_i18n columns, return a report.

    refill=True translates ONLY the missing pieces (e.g. gloss_i18n/story_i18n
    cleared by app.rephrase/app.restory) instead of skipping the whole batch
    because title_i18n already exists — the plain-run guard is whole-batch, so
    without this mode cleared caches would never refill short of --force (which
    retranslates everything at full LLM cost)."""
    zones = session.exec(select(models.Zone).where(models.Zone.batch_id == batch.id)
                         .order_by(models.Zone.order_index)).all()
    phrases = session.exec(select(models.Phrase).where(models.Phrase.batch_id == batch.id)
                           .order_by(models.Phrase.order_index)).all()
    mnemo = session.exec(select(models.MnemoStory)
                         .where(models.MnemoStory.batch_id == batch.id)).first()

    already = (batch.title_i18n or {}).get(lang)
    if already and not force and not refill:
        return {"batch": batch.id, "lang": lang, "skipped": "exists"}

    anchors = _anchor_surfaces(mnemo.story_ru, mnemo.spans) if mnemo else []

    def _missing_gloss(p: models.Phrase) -> bool:
        return not (p.gloss_i18n or {}).get(lang)

    def _missing_story() -> bool:
        # Mirror the write-guard preconditions: a story that could never be
        # persisted (empty story_ru, or no locatable anchors) must not be
        # requested — else --refill re-pays the LLM call on every run, forever.
        if not mnemo or not (mnemo.story_ru or "").strip() or not anchors:
            return False
        return not ((mnemo.story_i18n or {}).get(lang)
                    and (mnemo.spans_i18n or {}).get(lang))

    if refill and not force:
        payload = {}
        if not (batch.title_i18n or {}).get(lang):
            payload["title"] = batch.title
        if batch.subtitle and not (batch.subtitle_i18n or {}).get(lang):
            payload["subtitle"] = batch.subtitle
        if batch.theme and not (batch.theme_i18n or {}).get(lang):
            payload["theme"] = batch.theme
        zmiss = {str(z.id): z.title for z in zones
                 if not (z.title_i18n or {}).get(lang)}
        if zmiss:
            payload["zones"] = zmiss
        gmiss = {str(p.id): p.gloss_ru for p in phrases
                 if (p.gloss_ru or "").strip() and _missing_gloss(p)}
        if gmiss:
            payload["glosses"] = gmiss
        if _missing_story():
            payload["story"] = mnemo.story_ru
        if not payload:
            return {"batch": batch.id, "lang": lang, "skipped": "complete"}
    else:
        payload = {
            "title": batch.title,
            "subtitle": batch.subtitle,
            "theme": batch.theme,
            "zones": {str(z.id): z.title for z in zones},
            "glosses": {str(p.id): p.gloss_ru for p in phrases if (p.gloss_ru or "").strip()},
            "story": mnemo.story_ru if mnemo else "",
        }
    tr = _translate_call(payload, anchors, lang)

    def _set(d: Optional[dict], key: str, val: str) -> dict:
        d = dict(d or {})
        d[key] = val
        return d

    # Write back ONLY fields that were actually requested in the payload: the
    # model sometimes emits empty/hallucinated markers for fields it wasn't
    # given (esp. in refill mode), and an unguarded write would clobber an
    # existing good translation with "".
    if "title" in payload and tr.get("title"):
        batch.title_i18n = _set(batch.title_i18n, lang, tr["title"])
    if "subtitle" in payload and tr.get("subtitle") is not None:
        batch.subtitle_i18n = _set(batch.subtitle_i18n, lang, tr.get("subtitle", ""))
    if "theme" in payload and tr.get("theme") is not None:
        batch.theme_i18n = _set(batch.theme_i18n, lang, tr.get("theme", ""))
    session.add(batch)

    tr_zones = (tr.get("zones") or {}) if "zones" in payload else {}
    for z in zones:
        v = tr_zones.get(str(z.id))
        if v:
            z.title_i18n = _set(z.title_i18n, lang, v)
            session.add(z)

    tr_gloss = (tr.get("glosses") or {}) if "glosses" in payload else {}
    for p in phrases:
        v = tr_gloss.get(str(p.id))
        if v:
            p.gloss_i18n = _set(p.gloss_i18n, lang, v)
            session.add(p)

    story_ok = False
    if mnemo and anchors and payload.get("story"):
        cand = tr.get("story")
        # Up to 3 focused repair attempts when the model dropped/translated an
        # anchor (so a few stubborn anchors don't leave the story on the ru fallback).
        for attempt in range(3):
            if cand:
                new_spans = recompute_spans(mnemo.story_ru, mnemo.spans, cand)
                if new_spans is not None:
                    mnemo.story_i18n = _set(mnemo.story_i18n, lang, cand)
                    mnemo.spans_i18n = dict(mnemo.spans_i18n or {})
                    mnemo.spans_i18n[lang] = new_spans
                    session.add(mnemo)
                    story_ok = True
                    break
            cand = _translate_story(mnemo.story_ru, anchors, lang,
                                    _missing(anchors, cand), temperature=0.4 + 0.1 * attempt)
    session.commit()
    return {"batch": batch.id, "lang": lang, "zones": len(tr_zones),
            "glosses": len(tr_gloss), "story": story_ok,
            "anchors": len(anchors)}


def run(batch_id: Optional[int] = None, only_lang: Optional[str] = None,
        force: bool = False, refill: bool = False,
        shards: int = 1, shard: int = 0) -> None:
    init_db()
    langs = (only_lang,) if only_lang else LANGS
    with Session(engine()) as session:
        q = select(models.Batch).where(models.Batch.deleted_at == None)  # noqa: E711
        if batch_id:
            q = q.where(models.Batch.id == batch_id)
        batches = session.exec(q.order_by(models.Batch.id)).all()
        # Sharding partitions batches by id (disjoint rows → no two shards ever
        # read-modify-write the same *_i18n JSON column, so parallel shards are
        # race-free). Each shard still does all languages for its batches.
        if shards > 1:
            batches = [b for b in batches if (b.id % shards) == shard]
        for b in batches:
            for lang in langs:
                try:
                    rep = translate_batch(session, b, lang, force=force,
                                          refill=refill)
                    print(json.dumps(rep, ensure_ascii=False))
                except Exception as e:  # keep going; one bad batch shouldn't stop the run
                    print(json.dumps({"batch": b.id, "lang": lang, "error": str(e)},
                                     ensure_ascii=False))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--batch", type=int, default=None)
    ap.add_argument("--lang", choices=LANGS, default=None)
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--refill", action="store_true",
                    help="translate only the MISSING pieces (refills gloss_i18n/"
                         "story_i18n cleared by app.rephrase/app.restory) instead "
                         "of skipping batches that already have title_i18n")
    ap.add_argument("--shards", type=int, default=1)
    ap.add_argument("--shard", type=int, default=0)
    args = ap.parse_args()
    run(batch_id=args.batch, only_lang=args.lang, force=args.force,
        refill=args.refill, shards=args.shards, shard=args.shard)
    if args.shards == 1:  # parallel shards would print N duplicate reports
        from .doctor import verdict
        verdict("after i18n_content")
