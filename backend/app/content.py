"""Content pipeline: author batches as plain files, load/correct them idempotently.

The authoring format (see backend/content/*.json) is deliberately minimal — a human
writes title, zones, phrases (anchor + English line + zone name) and one mnemonic
story with the anchors in UPPERCASE. Everything mechanical is derived here:

  * order_index        -> position in the phrases list (1-based)
  * intensity_score    -> normalised 0..1 across the ladder
  * zone order_index   -> position in the zones list
  * mnemo spans        -> located in the story by importer._compute_spans

`upsert()` is create-or-replace keyed by slug: editing a file and re-loading it
rewrites that batch in place (children wiped, Batch id + cover preserved), so
corrections never need a hand-written migration script. `to_authoring()` is the
inverse, so an existing batch can be exported, edited, and re-loaded.

Progress-preservation contract: wiping children mints NEW phrase ids, which
destroys every user's per-phrase state (UserPhraseStat SRS schedule, attempt
history). So `upsert()` refuses to replace a batch that has live user progress
unless the caller passes `on_live_progress="wipe"` — and in that case it deletes
the dependent user rows FIRST, so nothing is ever orphaned and FK enforcement
never explodes mid-write. Text-only edits should use `app.rephrase` /
`app.restory` instead: they update in place and progress survives.
"""
import json
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field
from sqlmodel import Session, select

from . import cover, importer, models, titling
from .config import get_settings
from .schemas import BatchIn, MnemoIn, PhraseIn, ZoneIn


# ---- Authoring format (the human-editable source of truth) ----

class PhraseAuthor(BaseModel):
    anchor: str
    en: str
    zone: Optional[str] = None
    gloss_ru: str = ""
    tags: list[str] = Field(default_factory=list)


class BatchAuthor(BaseModel):
    slug: str
    title: str = ""          # empty => the pipeline assigns an essence title via LLM
    theme: str = ""
    subtitle: str = ""
    section: str = ""        # library section slug (see frontend lib/sections.ts)
    difficulty: str = ""
    zones: list[str] = Field(default_factory=list)
    phrases: list[PhraseAuthor]
    mnemo: str = ""


def to_batch_in(a: BatchAuthor) -> tuple[BatchIn, list[str]]:
    """Expand the authoring format into the canonical BatchIn + parser warnings."""
    n = len(a.phrases)
    zones = [ZoneIn(title=z, order_index=i + 1) for i, z in enumerate(a.zones)]
    phrases: list[PhraseIn] = []
    for i, p in enumerate(a.phrases, start=1):
        score = round((i - 1) / (n - 1), 3) if n > 1 else 0.0
        phrases.append(PhraseIn(
            order_index=i, anchor=p.anchor, phrase_en=p.en, gloss_ru=p.gloss_ru,
            intensity_score=score, zone=p.zone, tags=p.tags,
        ))
    spans, warnings = importer._compute_spans(a.mnemo, phrases)
    batch_in = BatchIn(
        title=a.title, theme=a.theme, subtitle=a.subtitle, section=a.section,
        difficulty=a.difficulty, zones=zones, phrases=phrases,
        mnemo=MnemoIn(story_ru=a.mnemo, spans=spans), source_text="",
    )
    return batch_in, warnings


# ---- Progress-preservation guard ----

class LiveProgressError(RuntimeError):
    """Refused to wipe a batch's children: real users have per-phrase progress.

    Raised by upsert() BEFORE anything is written. The caller chooses: keep the
    batch and edit it SRS-safely via `app.rephrase` / `app.restory`, or pass
    on_live_progress="wipe" to consciously destroy that progress (dependent user
    rows are then deleted first — no orphans, no mid-write IntegrityError)."""

    def __init__(self, slug: str, counts: dict):
        self.slug = slug
        self.counts = counts
        detail = ", ".join(f"{k}={v}" for k, v in counts.items())
        super().__init__(
            f"batch '{slug}' has live user progress ({detail}) — "
            f"edit via app.rephrase/app.restory, or force with on_live_progress="
            f"'wipe' (destroys SRS state, attempt history AND the training-event "
            f"days feeding users' day-streaks)"
        )


# Per-user tables keyed by phrase_id. A child wipe would orphan (FK off) or
# crash on (FK on) every one of these rows, so they gate/accompany the wipe.
_PROGRESS_TABLES = (models.UserPhraseStat, models.TrainingEvent,
                    models.PhraseAttempt, models.ReviewEvent)


def _batch_phrase_ids(session: Session, batch_id: int) -> list[int]:
    return [p.id for p in session.exec(
        select(models.Phrase).where(models.Phrase.batch_id == batch_id)).all()]


def progress_census(session: Session, batch_id: int) -> dict:
    """Count per-user rows that reference the batch's phrases, by table."""
    pids = _batch_phrase_ids(session, batch_id)
    if not pids:
        return {}
    counts = {}
    for tbl in _PROGRESS_TABLES:
        n = len(session.exec(select(tbl.id).where(tbl.phrase_id.in_(pids))).all())
        if n:
            counts[tbl.__tablename__] = n
    return counts


def _wipe_user_progress(session: Session, batch_id: int) -> None:
    """Delete the per-user rows tied to the batch's phrases (explicit force path).
    Runs BEFORE the child wipe so FK enforcement never fails and nothing orphans.
    Deliberately does NOT commit — upsert() wraps the whole destructive replace in
    ONE transaction, so a failure later rolls this back too (no window where
    progress is gone but the batch is stale/childless)."""
    pids = _batch_phrase_ids(session, batch_id)
    if not pids:
        return
    for tbl in _PROGRESS_TABLES:
        for row in session.exec(select(tbl).where(tbl.phrase_id.in_(pids))).all():
            session.delete(row)


# ---- DB write (single shared path for both paste-import and file-seed) ----

def _write_children(session: Session, batch: models.Batch, batch_in: BatchIn) -> None:
    # No commits here: upsert() owns the transaction (all-or-nothing replace).
    zone_id_by_title: dict[str, int] = {}
    for z in batch_in.zones:
        zone = models.Zone(batch_id=batch.id, title=z.title, order_index=z.order_index,
                           intensity_label=z.intensity_label)
        session.add(zone)
        session.flush()  # assigns zone.id without ending the transaction
        zone_id_by_title[z.title] = zone.id

    for p in batch_in.phrases:
        session.add(models.Phrase(
            batch_id=batch.id,
            zone_id=zone_id_by_title.get(p.zone) if p.zone else None,
            order_index=p.order_index, anchor=p.anchor, phrase_en=p.phrase_en,
            gloss_ru=p.gloss_ru, intensity_score=p.intensity_score, tags=p.tags,
        ))

    session.add(models.MnemoStory(
        batch_id=batch.id, story_ru=batch_in.mnemo.story_ru,
        spans=[s.model_dump() for s in batch_in.mnemo.spans],
    ))


def _wipe_children(session: Session, batch_id: int) -> None:
    # Content-side children keyed by phrase_id die with their phrases (leaving
    # them would orphan rows pointing at dead — or worse, recycled — phrase ids).
    pids = _batch_phrase_ids(session, batch_id)
    if pids:
        for tbl in (models.CheckPhrase, models.ContextExample):
            for row in session.exec(select(tbl).where(tbl.phrase_id.in_(pids))).all():
                session.delete(row)
    for tbl in (models.Phrase, models.Zone, models.MnemoStory):
        for row in session.exec(select(tbl).where(tbl.batch_id == batch_id)).all():
            session.delete(row)
    # PlaybackSession is deliberately KEPT: it is per-user listening history keyed
    # by batch_id (which survives), its plan is never re-read after rendering, and
    # deleting it would silently reset the free-plan daily session cap.
    # No commit here: upsert() owns the transaction.


def _resolve_title(batch_in: BatchIn, existing: Optional[models.Batch], *,
                   auto_title: bool, force_title: bool) -> str:
    """Decide the final title. Human-authored wins; an empty title is filled by the
    LLM once and then kept stable across re-seeds. force_title always regenerates.
    LLM failure is swallowed so a missing provider never breaks a write."""
    authored = (batch_in.title or "").strip()
    prior = (existing.title or "").strip() if existing else ""

    if not force_title:
        if authored:
            return authored
        if prior:
            return prior

    if force_title or auto_title:
        try:
            generated = titling.suggest_title(batch_in.phrases, batch_in.theme)
            if generated:
                return generated
        except Exception:
            pass

    return authored or prior


def _resolve_subtitle(batch_in: BatchIn, existing: Optional[models.Batch], *,
                      auto_subtitle: bool, force_subtitle: bool) -> str:
    """Decide the final subtitle — a 1–3 word name for the mnemonic's image.
    Same lifecycle as the title: human-authored wins, an empty one is filled by the
    LLM once and kept stable; force_subtitle always regenerates."""
    authored = (batch_in.subtitle or "").strip()
    prior = (existing.subtitle or "").strip() if existing else ""

    if not force_subtitle:
        if authored:
            return authored
        if prior:
            return prior

    if force_subtitle or auto_subtitle:
        try:
            generated = titling.suggest_subtitle(batch_in.mnemo.story_ru)
            if generated:
                return generated
        except Exception:
            pass

    return authored or prior


def _maybe_generate_cover(session: Session, batch: models.Batch, *,
                          auto_cover: bool, force_cover: bool) -> None:
    """Generate the batch's scene cover via the active prompt version (same style
    for every batch). Fill-once lifecycle like the title/subtitle: skip if a cover
    already exists unless force_cover. A paid network call, so failures are swallowed
    — a missing cover just falls back to procedural art and never breaks a write."""
    if not (auto_cover or force_cover):
        return
    if batch.cover_path and not force_cover:
        return
    try:
        url = cover.generate_cover(batch.id, batch.slug, batch.title, batch.theme,
                                   batch.subtitle, force=force_cover)
        batch.cover_path = url
        session.add(batch)
        session.commit()
    except Exception:
        pass


def upsert(session: Session, batch_in: BatchIn, *, slug: str,
           status: str = "approved", auto_title: bool = False,
           force_title: bool = False, auto_subtitle: bool = False,
           force_subtitle: bool = False, auto_cover: Optional[bool] = None,
           force_cover: bool = False,
           on_live_progress: str = "block") -> tuple[models.Batch, bool]:
    """Create-or-replace a batch by slug. Returns (batch, created).

    auto_title: assign an essence title via LLM when none is provided.
    force_title: regenerate the essence title even if one already exists.
    auto_subtitle / force_subtitle: same lifecycle for the mnemonic-image subtitle.
    auto_cover: generate a scene cover when missing (None => the auto_cover setting,
    so the pipeline owns it consistently). force_cover always regenerates.
    on_live_progress: what to do when the existing batch has per-user progress —
    "block" (default) raises LiveProgressError before anything is written;
    "wipe" deletes the users' progress rows first, then replaces the children.
    """
    if auto_cover is None:
        auto_cover = get_settings().auto_cover
    existing = session.exec(
        select(models.Batch).where(models.Batch.slug == slug)
    ).first()
    created = existing is None

    if existing:
        census = progress_census(session, existing.id)
        if census:
            if on_live_progress != "wipe":
                raise LiveProgressError(slug, census)
            _wipe_user_progress(session, existing.id)

    batch_in.title = _resolve_title(batch_in, existing,
                                    auto_title=auto_title, force_title=force_title)
    batch_in.subtitle = _resolve_subtitle(batch_in, existing,
                                          auto_subtitle=auto_subtitle,
                                          force_subtitle=force_subtitle)

    # From here on the replace is ONE transaction (single commit below): a failure
    # anywhere rolls back everything — no window where user progress is deleted
    # but the batch is left stale or childless.
    if existing:
        batch = existing
        # An authoring payload without glosses must not zero curated DB glosses
        # (files historically omit gloss_ru) — same "empty means keep" semantics
        # as app.rephrase. Matched by anchor so re-authoring survives reorders.
        old_gloss = {p.anchor.lower(): p.gloss_ru
                     for p in session.exec(select(models.Phrase).where(
                         models.Phrase.batch_id == batch.id)).all()
                     if (p.gloss_ru or "").strip()}
        for p in batch_in.phrases:
            if not (p.gloss_ru or "").strip():
                kept = old_gloss.get(p.anchor.lower())
                if kept:
                    p.gloss_ru = kept
        # Batch-level i18n caches must not outlive their base field (else es/de/fr
        # users keep the OLD translated title forever — --refill only fills holes).
        if (batch.title or "") != (batch_in.title or ""):
            batch.title_i18n = {}
        if (batch.subtitle or "") != (batch_in.subtitle or ""):
            batch.subtitle_i18n = {}
        if (batch.theme or "") != (batch_in.theme or ""):
            batch.theme_i18n = {}
        batch.title = batch_in.title
        batch.theme = batch_in.theme
        batch.subtitle = batch_in.subtitle
        batch.section = batch_in.section
        batch.difficulty = batch_in.difficulty
        batch.status = status
        batch.source_text = batch_in.source_text
        batch.deleted_at = None  # re-seeding un-deletes
        session.add(batch)
        session.flush()
        _wipe_children(session, batch.id)
    else:
        batch = models.Batch(
            title=batch_in.title, slug=slug, theme=batch_in.theme,
            subtitle=batch_in.subtitle, section=batch_in.section,
            difficulty=batch_in.difficulty,
            status=status, source_text=batch_in.source_text,
        )
        session.add(batch)
        session.flush()  # assigns batch.id

    _write_children(session, batch, batch_in)
    session.commit()
    session.refresh(batch)
    _maybe_generate_cover(session, batch, auto_cover=auto_cover, force_cover=force_cover)
    return batch, created


# ---- Export (round-trip an existing batch back to the authoring format) ----

def to_authoring(session: Session, batch: models.Batch) -> dict:
    zones = session.exec(
        select(models.Zone).where(models.Zone.batch_id == batch.id)
        .order_by(models.Zone.order_index)
    ).all()
    phrases = session.exec(
        select(models.Phrase).where(models.Phrase.batch_id == batch.id)
        .order_by(models.Phrase.order_index)
    ).all()
    mnemo = session.exec(
        select(models.MnemoStory).where(models.MnemoStory.batch_id == batch.id)
    ).first()
    zone_title_by_id = {z.id: z.title for z in zones}
    return {
        "slug": batch.slug,
        "title": batch.title,
        "theme": batch.theme,
        "subtitle": batch.subtitle,
        "section": batch.section,
        "difficulty": batch.difficulty,
        "zones": [z.title for z in zones],
        "phrases": [
            {"anchor": p.anchor, "en": p.phrase_en,
             "zone": zone_title_by_id.get(p.zone_id),
             "gloss_ru": p.gloss_ru, "tags": p.tags}
            for p in phrases
        ],
        "mnemo": mnemo.story_ru if mnemo else "",
    }


def authoring_unchanged(session: Session, batch: models.Batch,
                        author: BatchAuthor) -> bool:
    """True when re-loading `author` would be a pure no-op — so seed runs can SKIP
    trained-but-unedited batches instead of blocking on (or force-wiping) them.
    Empty authored title/subtitle/gloss mean "keep the existing value" (they may
    be LLM-filled / curated only in the DB), so they never count as a change."""
    cur = to_authoring(session, batch)
    if author.title.strip() and author.title.strip() != (cur["title"] or "").strip():
        return False
    if (author.subtitle.strip()
            and author.subtitle.strip() != (cur["subtitle"] or "").strip()):
        return False
    for field in ("theme", "section", "difficulty"):
        if (getattr(author, field) or "") != (cur[field] or ""):
            return False
    if list(author.zones) != list(cur["zones"]):
        return False
    if (author.mnemo or "").strip() != (cur["mnemo"] or "").strip():
        return False
    if len(author.phrases) != len(cur["phrases"]):
        return False
    for ap, cp in zip(author.phrases, cur["phrases"]):
        if ap.anchor != cp["anchor"] or ap.en != cp["en"]:
            return False
        if (ap.zone or "") != (cp["zone"] or ""):
            return False
        if ((ap.gloss_ru or "").strip()
                and ap.gloss_ru.strip() != (cp["gloss_ru"] or "").strip()):
            return False
    return True


# ---- File loaders ----

def content_dir() -> Path:
    return Path(__file__).resolve().parent.parent / "content"


def load_path(session: Session, path: Path, *,
              on_live_progress: str = "block",
              ) -> tuple[models.Batch, bool, list[str], bool]:
    """Load one content file. Returns (batch, created, warnings, unchanged).

    An UNCHANGED file is a no-op (batch untouched, phrase ids preserved) — this
    is what makes a catalog-wide seed with force safe: only genuinely edited
    batches are replaced, everything else is skipped before any guard fires."""
    data = json.loads(path.read_text(encoding="utf-8"))
    author = BatchAuthor(**data)
    existing = session.exec(
        select(models.Batch).where(models.Batch.slug == author.slug)
    ).first()
    if (existing and existing.deleted_at is None
            and authoring_unchanged(session, existing, author)):
        return existing, False, [], True
    batch_in, warnings = to_batch_in(author)
    batch, created = upsert(session, batch_in, slug=author.slug,
                            auto_title=True, auto_subtitle=True,
                            on_live_progress=on_live_progress)
    return batch, created, warnings, False


def load_all(session: Session, *, on_live_progress: str = "block") -> list[dict]:
    """Load every content file. Returns one report dict per file; a batch whose
    replacement is blocked by live user progress is reported, not raised, so one
    trained batch never aborts the rest of a seed run."""
    out = []
    for path in sorted(content_dir().glob("*.json")):
        if path.name.startswith("."):
            continue  # skip macOS AppleDouble (._*) and other dotfiles
        try:
            batch, created, warnings, unchanged = load_path(
                session, path, on_live_progress=on_live_progress)
            out.append({"batch": batch, "slug": batch.slug, "created": created,
                        "warnings": warnings, "blocked": False,
                        "unchanged": unchanged})
        except LiveProgressError as e:
            out.append({"batch": None, "slug": e.slug, "created": False,
                        "warnings": [str(e)], "blocked": True,
                        "unchanged": False})
    return out
