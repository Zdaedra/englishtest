"""LLM-assigned batch titles.

The collection name should reflect the *functional essence* of its phrases —
what they let you DO in a business conversation (express disagreement, probe for
detail, take the floor) — NOT the mnemonic metaphor used to memorise them.

Used by the standard creation pipeline (content.upsert, auto_title) and by the
one-off retitle CLI. Network/LLM failures are the caller's concern: suggest_title
raises, and the pipeline guards it so a missing LLM never breaks a seed.
"""
import re

from . import llm

_SYSTEM = (
    "Ты редактор каталога деловых фраз (Executive English). На вход — фразы одной "
    "коллекции: английская реплика + слово-якорь. Придумай НАЗВАНИЕ коллекции на "
    "русском, отражающее её ФУНКЦИОНАЛЬНУЮ СУТЬ — что эти фразы позволяют делать в "
    "деловом разговоре (например: «Выражение несогласия», «Уточняющие вопросы», "
    "«Перехват инициативы», «Мягкий отказ»). "
    "НЕ называй метафору, сюжет или мнемонику. Не используй слова вроде «лестница», "
    "«восхождение», «сцена», если они не описывают саму речевую функцию. "
    "2–4 слова, без кавычек и без точки в конце. Регистр — как в обычном русском "
    "предложении: с заглавной только первое слово (аббревиатуры вроде KPI оставляй "
    "как есть). Верни ТОЛЬКО название, одной строкой."
)

_SUBTITLE_SYSTEM = (
    "Ты редактор каталога деловых фраз. На вход — мнемоническая история "
    "(текст-ассоциация), с помощью которой запоминают набор фраз. Назови САМ ОБРАЗ "
    "этой мнемоники одной очень короткой подписью: что за сцена, место или метафора. "
    "Например: «Восхождение на гору», «Игра на поле», «Сцена», «Зал суда», «Кухня». "
    "НЕ пересказывай сюжет и НЕ описывай функцию фраз — только назови образ. "
    "1–3 слова, без кавычек и без точки в конце. Регистр — с заглавной только первое "
    "слово. Верни ТОЛЬКО подпись, одной строкой."
)


def _phrase_line(p) -> str:
    anchor = (getattr(p, "anchor", "") or "").strip()
    en = (getattr(p, "phrase_en", None) or getattr(p, "en", "") or "").strip()
    return f"- {anchor}: {en}" if anchor else f"- {en}"


def _sentence_case(t: str) -> str:
    """Russian sentence case: capitalise only the first word; de-Title-Case the
    rest (a habit of weaker models) while preserving acronyms like KPI/CEO."""
    words = t.split(" ")
    out: list[str] = []
    for i, w in enumerate(words):
        if not w:
            continue
        if i == 0:
            out.append(w[0].upper() + w[1:])
        elif w.isupper():
            out.append(w)  # acronym
        elif len(w) > 1 and w[0].isupper() and w[1:].islower():
            out.append(w[0].lower() + w[1:])
        else:
            out.append(w)
    return " ".join(out)


def _clean(raw: str) -> str:
    t = (raw or "").strip()
    if not t:
        return ""
    t = t.splitlines()[0].strip()
    t = t.strip("\"'«»").strip()
    t = re.sub(r"[.\s]+$", "", t)
    return _sentence_case(t[:80])


def suggest_title(phrases, theme: str = "") -> str:
    """Generate an essence title from a batch's phrases. Raises on LLM failure."""
    phrases = list(phrases or [])
    if not phrases:
        return ""
    block = "\n".join(_phrase_line(p) for p in phrases)
    user = block
    if (theme or "").strip():
        user = f"Тема (подсказка, можно игнорировать): {theme.strip()}\n\nФразы:\n{block}"
    return _clean(llm.chat(_SYSTEM, user, temperature=0.4))


def suggest_subtitle(mnemo: str) -> str:
    """Name the mnemonic's image/scene in 1–3 words, read straight from the story.
    Deliberately ignores the batch theme — the theme is a parallel metaphor that can
    diverge from the actual mnemonic image (e.g. a 'ladder' theme over a mountain
    story), and the caption should label what the learner will actually read.
    Raises on LLM failure."""
    mnemo = (mnemo or "").strip()
    if not mnemo:
        return ""
    return _clean(llm.chat(_SUBTITLE_SYSTEM, mnemo, temperature=0.4))
