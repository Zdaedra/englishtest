import re

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlmodel import Session, select

from .. import content, cover, importer, models
from ..auth import current_user_id, is_admin, require_admin
from ..config import get_settings
from ..content import BatchAuthor
from ..db import engine, get_session
from ..entitlements import user_entitlements
from ..schemas import BatchIn, ParseRequest, ParseResponse

router = APIRouter(prefix="/api/imports", tags=["imports"])


def _require_import(session: Session, user_id: int) -> None:
    if not user_entitlements(session, user_id)["import"]:
        raise HTTPException(403, "core_required")


def _slugify(title: str) -> str:
    base = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
    return base or "batch"


def _unique_slug(session: Session, title: str) -> str:
    slug = _slugify(title)
    n = 1
    while session.exec(select(models.Batch).where(models.Batch.slug == slug)).first():
        n += 1
        slug = f"{_slugify(title)}-{n}"
    return slug


def _gen_cover_bg(batch_id: int, slug: str, title: str, theme: str,
                  subtitle: str) -> None:
    # Best-effort: a paid network call that must never break import or block the
    # response. Runs after commit; the cover surfaces on the next library load.
    try:
        url = cover.generate_cover(batch_id, slug, title, theme, subtitle)
        with Session(engine()) as s:
            b = s.get(models.Batch, batch_id)
            if b:
                b.cover_path = url
                s.add(b)
                s.commit()
    except Exception:
        pass


@router.post("/parse", response_model=ParseResponse)
def parse(req: ParseRequest, user_id: int = Depends(current_user_id),
          session: Session = Depends(get_session)):
    _require_import(session, user_id)
    try:
        return importer.parse(req.raw_text, use_llm=req.use_llm)
    except Exception as e:  # LLM/network failure shouldn't 500 silently
        raise HTTPException(status_code=502, detail=f"Parse failed: {e}")


@router.post("/commit")
def commit(batch_in: BatchIn, background_tasks: BackgroundTasks,
           user_id: int = Depends(current_user_id),
           session: Session = Depends(get_session)):
    """Create a new batch from the paste→parse UI flow (always a fresh slug)."""
    _require_import(session, user_id)
    if not batch_in.phrases:
        raise HTTPException(status_code=400, detail="Batch has no phrases")

    slug = _unique_slug(session, batch_in.title or "batch")
    # auto_cover=False here: the paste→commit flow generates the cover in the
    # background (below) so the HTTP response isn't blocked on a slow image call.
    batch, _ = content.upsert(session, batch_in, slug=slug,
                              auto_title=True, auto_subtitle=True, auto_cover=False)

    # Admin imports populate the shared catalog (owner_id NULL); a client's import
    # is private to them (owner_id = the client) so it never leaks into the library.
    batch.owner_id = None if is_admin(session, user_id) else user_id
    session.add(batch)
    session.commit()
    session.refresh(batch)

    if get_settings().auto_cover:
        background_tasks.add_task(_gen_cover_bg, batch.id, batch.slug,
                                  batch.title, batch.theme, batch.subtitle)
    return {"id": batch.id, "slug": batch.slug, "status": batch.status}


@router.post("/upsert")
def upsert_authored(author: BatchAuthor, user_id: int = Depends(require_admin),
                    session: Session = Depends(get_session)):
    """Create-or-replace a batch from the authoring format, keyed by its slug.

    This is the corrections path: POST the same slug with edited content and the
    batch is rewritten in place (id + cover preserved). Admin-only — it edits the
    shared curated catalog by slug, so clients must not reach it.
    """
    if not author.phrases:
        raise HTTPException(status_code=400, detail="Batch has no phrases")
    batch_in, warnings = content.to_batch_in(author)
    batch, created = content.upsert(session, batch_in, slug=author.slug,
                                    auto_title=True, auto_subtitle=True)
    return {"id": batch.id, "slug": batch.slug, "created": created,
            "warnings": warnings}


@router.post("/seed")
def seed(user_id: int = Depends(require_admin), session: Session = Depends(get_session)):
    """Load every backend/content/*.json file (idempotent upsert by slug).
    Admin-only — it populates the shared curated catalog."""
    results = content.load_all(session)
    return {"loaded": [
        {"id": b.id, "slug": b.slug, "created": created, "warnings": warnings}
        for b, created, warnings in results
    ]}
