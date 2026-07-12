"""settitle / retitle / resubtitle must invalidate the field's i18n on change.

Without this, a re-titled batch keeps serving the OLD title's translations to
es/de/fr users forever — and app.doctor can't see it (there is no source hash
to compare against). Clearing on change makes the hole visible to doctor and
lets `i18n_content --refill` re-translate. A no-op run keeps translations.
"""
from sqlmodel import Session

from app import models, resubtitle, retitle, settitle, titling
from app.db import engine


def _seed(title="Старое", subtitle="Старый саб"):
    with Session(engine()) as s:
        b = models.Batch(title=title, subtitle=subtitle, status="approved",
                         slug="tt-1",
                         title_i18n={"es": "Viejo"},
                         subtitle_i18n={"es": "Sub viejo"})
        s.add(b)
        s.commit()
        s.refresh(b)
        return b.id


def _batch(bid):
    with Session(engine()) as s:
        return s.get(models.Batch, bid)


def test_settitle_clears_title_i18n_only_on_change():
    bid = _seed()
    settitle.run({bid: "Старое"}, dry=False)      # no-op: same title
    assert _batch(bid).title_i18n == {"es": "Viejo"}
    settitle.run({bid: "Новое"}, dry=False)
    b = _batch(bid)
    assert b.title == "Новое" and b.title_i18n == {}
    assert b.subtitle_i18n == {"es": "Sub viejo"}  # untouched


def test_retitle_clears_title_i18n(monkeypatch):
    bid = _seed()
    monkeypatch.setattr(titling, "suggest_title", lambda *a, **k: "Новое LLM")
    retitle.run([bid], all_=False, dry=False)
    b = _batch(bid)
    assert b.title == "Новое LLM" and b.title_i18n == {}


def test_resubtitle_clears_subtitle_i18n(monkeypatch):
    bid = _seed()
    monkeypatch.setattr(titling, "suggest_subtitle", lambda *a, **k: "Новый саб")
    resubtitle.run([bid], all_=False, dry=False)
    b = _batch(bid)
    assert b.subtitle == "Новый саб" and b.subtitle_i18n == {}
    assert b.title_i18n == {"es": "Viejo"}         # untouched
