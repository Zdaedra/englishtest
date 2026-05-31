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


# ---- DB write (single shared path for both paste-import and file-seed) ----

def _write_children(session: Session, batch: models.Batch, batch_in: BatchIn) -> None:
    zone_id_by_title: dict[str, int] = {}
    for z in batch_in.zones:
        zone = models.Zone(batch_id=batch.id, title=z.title, order_index=z.order_index,
                           intensity_label=z.intensity_label)
        session.add(zone)
        session.commit()
        session.refresh(zone)
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
    session.commit()


def _wipe_children(session: Session, batch_id: int) -> None:
    for tbl in (models.Phrase, models.Zone, models.MnemoStory, models.PlaybackSession):
        for row in session.exec(select(tbl).where(tbl.batch_id == batch_id)).all():
            session.delete(row)
    session.commit()


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
           force_cover: bool = False) -> tuple[models.Batch, bool]:
    """Create-or-replace a batch by slug. Returns (batch, created).

    auto_title: assign an essence title via LLM when none is provided.
    force_title: regenerate the essence title even if one already exists.
    auto_subtitle / force_subtitle: same lifecycle for the mnemonic-image subtitle.
    auto_cover: generate a scene cover when missing (None => the auto_cover setting,
    so the pipeline owns it consistently). force_cover always regenerates.
    """
    if auto_cover is None:
        auto_cover = get_settings().auto_cover
    existing = session.exec(
        select(models.Batch).where(models.Batch.slug == slug)
    ).first()
    created = existing is None

    batch_in.title = _resolve_title(batch_in, existing,
                                    auto_title=auto_title, force_title=force_title)
    batch_in.subtitle = _resolve_subtitle(batch_in, existing,
                                          auto_subtitle=auto_subtitle,
                                          force_subtitle=force_subtitle)

    if existing:
        batch = existing
        batch.title = batch_in.title
        batch.theme = batch_in.theme
        batch.subtitle = batch_in.subtitle
        batch.section = batch_in.section
        batch.difficulty = batch_in.difficulty
        batch.status = status
        batch.source_text = batch_in.source_text
        batch.deleted_at = None  # re-seeding un-deletes
        session.add(batch)
        session.commit()
        session.refresh(batch)
        _wipe_children(session, batch.id)
    else:
        batch = models.Batch(
            title=batch_in.title, slug=slug, theme=batch_in.theme,
            subtitle=batch_in.subtitle, section=batch_in.section,
            difficulty=batch_in.difficulty,
            status=status, source_text=batch_in.source_text,
        )
        session.add(batch)
        session.commit()
        session.refresh(batch)

    _write_children(session, batch, batch_in)
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
             "zone": zone_title_by_id.get(p.zone_id)}
            for p in phrases
        ],
        "mnemo": mnemo.story_ru if mnemo else "",
    }


# ---- File loaders ----

def content_dir() -> Path:
    return Path(__file__).resolve().parent.parent / "content"


def load_path(session: Session, path: Path) -> tuple[models.Batch, bool, list[str]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    author = BatchAuthor(**data)
    batch_in, warnings = to_batch_in(author)
    batch, created = upsert(session, batch_in, slug=author.slug,
                            auto_title=True, auto_subtitle=True)
    return batch, created, warnings


def load_all(session: Session) -> list[tuple[models.Batch, bool, list[str]]]:
    out = []
    for path in sorted(content_dir().glob("*.json")):
        out.append(load_path(session, path))
    return out
