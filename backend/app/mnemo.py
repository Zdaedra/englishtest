"""Mnemonic-story narration: ONE warm Russian narrator, ONE synthesis pass.

The earlier approach stitched per-fragment clips and switched voices on every
English anchor — choppy, and the anchors landed in a different timbre. Here the
whole story is spoken by a single gpt-4o-mini-tts narrator who simply pronounces
the embedded English anchors in clear American English (steered via
`instructions`), so the result is one smooth, continuous read.

`generate_story()` is the "neural net writes the short story" path: given a
batch's ordered anchors it composes a coherent ~70-word Russian narrative with
each English anchor woven inline, in order. `regenerate()` stores it and
recomputes the tap-to-reveal spans.
"""
from sqlmodel import Session, select

from . import importer, llm, models, tts

NARRATOR_VOICE = "shimmer"
NARRATOR_MODEL = "gpt-4o-mini-tts"

# Steering for the full-story read: one speaker, English anchors in English.
INSTR = (
    "You are one warm, calm Russian storyteller narrating a very short mnemonic "
    "story. Speak the Russian text naturally, unhurried, with a gentle engaging "
    "tone. Whenever an English word appears in the text, pronounce it with clear, "
    "natural American-English pronunciation — never with a Russian accent and never "
    "switching to a different speaker. It is the SAME narrator who simply says those "
    "words in English, with a light emphasis so they stand out as memory anchors. "
    "Keep one continuous, smooth flow from start to finish; no abrupt cuts."
)

# Localized stories (es/de/fr): same single warm narrator, but the surrounding
# prose is in the learner's language, not Russian. gpt-4o-mini-tts reads it
# natively; the embedded English anchors still land in clear American English.
# Kept separate from INSTR so the Russian narration cache (hashed on instructions)
# is untouched.
INSTR_INTL = (
    "You are one warm, calm storyteller narrating a very short mnemonic story. "
    "Speak the narration text naturally in its own language, unhurried, with a "
    "gentle engaging tone. Whenever an English word appears in the text, pronounce "
    "it with clear, natural American-English pronunciation — never switching to a "
    "different speaker. It is the SAME narrator who simply says those words in "
    "English, with a light emphasis so they stand out as memory anchors. Keep one "
    "continuous, smooth flow from start to finish; no abrupt cuts."
)

# Steering for the anchors-only drill: same narrator, just the English words.
ANCHOR_INSTR = (
    "You are a warm, calm narrator. Pronounce each English word clearly and "
    "naturally in American English, with a steady, gentle tone."
)


def render_full(story: str, instructions: str = INSTR) -> tuple[str, float]:
    """Synthesize the whole mnemonic story in one steered pass.

    Returns (audio_filename, duration_sec). MP3 (not WAV): the full story is a
    one-shot download to a phone, and a 30s WAV is ~1.4 MB vs ~200 KB as MP3 —
    far faster to load and it plays progressively. Duration isn't needed for the
    full layout (no per-word plan, no scrubber), so a 0.0 from the WAV-only meter
    is fine. Asset is content-hashed by tts.synth (story + voice + model + fmt +
    instructions)."""
    path, dur = tts.synth(story, voice=NARRATOR_VOICE, model=NARRATOR_MODEL,
                          instructions=instructions, fmt="mp3", speed=1.0)
    return path.name, dur


# ---- LLM story generation (V1-"mountain" register) ----

_SYSTEM = (
    "Ты — рассказчик мнемо-историй для запоминания английских фраз. На вход "
    "даётся тема и список английских слов-якорей в строгом порядке. Напиши ОДНУ "
    "короткую цельную историю на русском языке: живую, тёплую, образную, во "
    "втором лице («ты»), 55–90 слов. Вплети в неё ВСЕ английские слова-якоря — "
    "РОВНО в заданном порядке, каждое РОВНО один раз, латиницей строчными "
    "буквами, как естественную часть русской фразы (это глаголы/существительные "
    "из реальных фраз). Между якорями — связный русский текст, единый сюжет, без "
    "списков, заголовков и кавычек. Верни ТОЛЬКО текст истории."
)

_EXEMPLAR = (
    "Ты хочешь understand эту гору — и медленно walk вверх по тропе, на ходу "
    "read старую карту. Видишь, как far ещё до вершины, и внутри вспыхивает "
    "hesitation. Делаешь pause, выбираешь, куда land ногу, и push себя выше. Вот "
    "ты на пике — один, outlier над облаками. Снизу кричат: «why?» — и ты "
    "отвечаешь им straight."
)


def generate_story(phrases: list[models.Phrase], theme: str = "") -> str:
    """Compose a coherent short Russian story with the anchors woven in order."""
    ordered = sorted(phrases, key=lambda p: p.order_index)
    lines = [
        f"{i}. {p.anchor.lower()} — {p.phrase_en} — {p.gloss_ru}".rstrip(" —")
        for i, p in enumerate(ordered, start=1)
    ]
    user = (
        f"Тема: {theme}\n\n"
        "Якоря по порядку (слово — английская фраза — смысл):\n"
        + "\n".join(lines)
        + "\n\nПример нужного регистра (другие слова, тот же стиль):\n"
        + _EXEMPLAR
    )
    out = llm.chat(_SYSTEM, user, temperature=0.8).strip()
    # Strip stray wrapping quotes the model sometimes adds.
    if len(out) >= 2 and out[0] in "«\"'" and out[-1] in "»\"'":
        out = out[1:-1].strip()
    return out


def regenerate(session: Session, batch_id: int) -> tuple[str, list[dict], list[str]]:
    """Generate a fresh story for a batch, recompute spans, persist. Returns
    (story, spans, warnings). Warnings list any anchor not located in the story."""
    batch = session.get(models.Batch, batch_id)
    phrases = session.exec(
        select(models.Phrase).where(models.Phrase.batch_id == batch_id)
        .order_by(models.Phrase.order_index)
    ).all()
    if not phrases:
        raise ValueError(f"Batch {batch_id} has no phrases")
    story = generate_story(phrases, theme=batch.theme if batch else "")
    spans, warnings = importer._compute_spans(story, phrases)
    mnemo = session.exec(
        select(models.MnemoStory).where(models.MnemoStory.batch_id == batch_id)
    ).first()
    if not mnemo:
        mnemo = models.MnemoStory(batch_id=batch_id, story_ru=story, spans=[])
    mnemo.story_ru = story
    mnemo.spans = [s.model_dump() for s in spans]
    # stale translations would keep showing the OLD story to es/de/fr users
    # (same invalidation rule as app.restory)
    mnemo.story_i18n = None
    mnemo.spans_i18n = None
    session.add(mnemo)
    session.commit()
    return story, [s.model_dump() for s in spans], warnings
