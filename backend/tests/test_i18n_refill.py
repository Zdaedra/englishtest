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


def test_tokenized_fallback_rescues_cognate_absorbed_anchor(monkeypatch):
    """personally→personalmente-class failure: the main call AND the focused
    repair keep absorbing the anchor into the target language's natural word;
    the tokenized pass must rescue the story."""
    with Session(engine()) as s:
        b = models.Batch(title="T", slug="i18n-4", status="approved")
        s.add(b)
        s.commit()
        s.refresh(b)
        p = models.Phrase(batch_id=b.id, order_index=1, anchor="personally",
                          phrase_en="Personally.")
        s.add(p)
        s.commit()
        s.refresh(p)
        story = "ты вбиваешь кол personally сам"
        s.add(models.MnemoStory(batch_id=b.id, story_ru=story,
                                spans=[{"anchor_id": "a1", "phrase_id": p.id,
                                        "start": 16, "end": 26}]))
        s.commit()
        bid = b.id
    assert story[16:26] == "personally"

    monkeypatch.setattr(i18n_content, "_translate_call",
                        lambda *a: {"title": "T", "subtitle": "", "theme": "",
                                    "story": "clavas la estaca personalmente"})
    monkeypatch.setattr(i18n_content, "_translate_story",
                        lambda *a, **k: "sigue personalmente sin ancla")

    def fake_chat(system, user, temperature=0.0):
        assert "[[A1]]" in user            # anchors left as opaque tokens…
        assert "personally" not in user    # …not as absorbable English words
        return "clavas la estaca [[A1]] tú mismo"

    monkeypatch.setattr(i18n_content.llm, "chat", fake_chat)

    with Session(engine()) as s:
        b = s.get(models.Batch, bid)
        rep = i18n_content.translate_batch(s, b, "es")
    assert rep["story"] is True
    with Session(engine()) as s:
        m = s.exec(select(models.MnemoStory)
                   .where(models.MnemoStory.batch_id == bid)).first()
        assert m.story_i18n["es"] == "clavas la estaca personally tú mismo"
        sp = m.spans_i18n["es"][0]
        assert m.story_i18n["es"][sp["start"]:sp["end"]] == "personally"


def test_tokenized_fallback_rejects_lost_token(monkeypatch):
    """A model that drops or duplicates a token yields None (ru fallback), never
    a half-substituted story."""
    spans = [{"anchor_id": "a1", "phrase_id": 1, "start": 3, "end": 7},
             {"anchor_id": "a2", "phrase_id": 2, "start": 10, "end": 14}]
    story = "ты beta и gamm тут"
    monkeypatch.setattr(i18n_content.llm, "chat",
                        lambda *a, **k: "solo [[A1]] aquí")  # [[A2]] lost
    assert i18n_content._translate_story_tokenized(story, spans, "es", 0.3) is None
