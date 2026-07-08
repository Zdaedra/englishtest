"""i18n_content.translate_batch --refill: fill ONLY the missing pieces.

Two hazards this locks down: (1) the model emitting empty/hallucinated markers
for fields that were NOT requested must never clobber existing translations;
(2) a batch whose story can never be persisted (empty story_ru / no anchors)
must converge to skipped:"complete" instead of re-paying the LLM call forever.
"""
from sqlmodel import Session, select

from app import i18n_content, models
from app.db import engine


def _seed_batch(slug, *, story="", gloss="", title_i18n=None, subtitle_i18n=None,
                theme_i18n=None, gloss_i18n=None):
    with Session(engine()) as s:
        b = models.Batch(title="T", slug=slug, status="approved",
                         subtitle="Sub", theme="Theme",
                         title_i18n=title_i18n or {},
                         subtitle_i18n=subtitle_i18n or {},
                         theme_i18n=theme_i18n or {})
        s.add(b)
        s.commit()
        s.refresh(b)
        p = models.Phrase(batch_id=b.id, order_index=1, anchor="beta",
                          phrase_en="Beta.", gloss_ru=gloss,
                          gloss_i18n=gloss_i18n or {})
        s.add(p)
        s.commit()
        s.refresh(p)
        s.add(models.MnemoStory(batch_id=b.id, story_ru=story, spans=[]))
        s.commit()
        return b.id, p.id


def test_refill_translates_only_missing_and_never_clobbers(monkeypatch):
    bid, pid = _seed_batch(
        "i18n-1", gloss="перевод",
        title_i18n={"es": "Título"}, subtitle_i18n={"es": "Subtítulo"},
        theme_i18n={"es": "Tema"})

    seen_payloads = []

    def fake_call(payload, anchors, lang):
        seen_payloads.append(payload)
        # model misbehaves: emits EMPTY subtitle/theme it was never asked for
        return {"subtitle": "", "theme": "",
                "glosses": {str(pid): "traducción"}}

    monkeypatch.setattr(i18n_content, "_translate_call", fake_call)

    with Session(engine()) as s:
        b = s.get(models.Batch, bid)
        rep = i18n_content.translate_batch(s, b, "es", refill=True)
    assert rep.get("skipped") is None

    # only the missing gloss was requested…
    assert seen_payloads == [{"glosses": {str(pid): "перевод"}}]
    with Session(engine()) as s:
        b = s.get(models.Batch, bid)
        p = s.get(models.Phrase, pid)
        # …and written; the unrequested empty markers touched NOTHING
        assert p.gloss_i18n == {"es": "traducción"}
        assert b.subtitle_i18n == {"es": "Subtítulo"}
        assert b.theme_i18n == {"es": "Tema"}
        assert b.title_i18n == {"es": "Título"}


def test_refill_converges_for_empty_story(monkeypatch):
    """story_ru="" can never be persisted (write guard requires a non-empty
    story with anchors) — so it must not be requested at all: once everything
    else is filled, refill returns skipped:'complete' with ZERO LLM calls."""
    bid, pid = _seed_batch(
        "i18n-2", story="",  # every batch gets a MnemoStory row, often empty
        title_i18n={"es": "Título"}, subtitle_i18n={"es": "Subtítulo"},
        theme_i18n={"es": "Tema"})
    # no gloss_ru → nothing to translate at all

    calls = []
    monkeypatch.setattr(i18n_content, "_translate_call",
                        lambda *a: calls.append(a) or {})

    with Session(engine()) as s:
        b = s.get(models.Batch, bid)
        rep = i18n_content.translate_batch(s, b, "es", refill=True)
    assert rep["skipped"] == "complete"
    assert calls == []  # converged: no recurring LLM spend


def test_plain_run_still_skips_translated_batches(monkeypatch):
    bid, pid = _seed_batch("i18n-3", title_i18n={"es": "Título"})
    monkeypatch.setattr(i18n_content, "_translate_call",
                        lambda *a: (_ for _ in ()).throw(AssertionError("called")))
    with Session(engine()) as s:
        b = s.get(models.Batch, bid)
        rep = i18n_content.translate_batch(s, b, "es")
    assert rep["skipped"] == "exists"
