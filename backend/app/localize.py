"""Content i18n resolver. The catalog (batch titles, glosses, zone titles, the
mnemonic story + its anchor spans) is authored in Russian; per-language
translations live in additive JSON columns (`*_i18n`). This module resolves the
right value for a request's content language, always falling back to the base
Russian field when a translation is missing.

The English-being-learned (anchor words, `phrase_en`) is never translated — it
stays English in every language, including inside the mnemonic story.
"""
from __future__ import annotations

from typing import Optional

SUPPORTED = {"ru", "es", "de", "fr"}
BASE = "ru"


def resolve_lang(lang: Optional[str], user) -> str:
    """Effective content language for a request: explicit `?lang=` wins, else the
    user's saved UI language, else Russian. Unknown codes collapse to ru."""
    cand = (lang or "").strip().lower()
    if cand not in SUPPORTED:
        cand = (getattr(user, "ui_lang", None) or "").strip().lower()
    return cand if cand in SUPPORTED else BASE


def pick(i18n: Optional[dict], lang: str, base: str) -> str:
    """One field: the translation for `lang` if present & non-empty, else `base`."""
    if lang and lang != BASE and i18n:
        v = i18n.get(lang)
        if isinstance(v, str) and v.strip():
            return v
    return base


def story_and_spans(mnemo, lang: str) -> tuple[str, list]:
    """The mnemonic story text + its anchor spans for `lang`. Both must come from
    the SAME language (spans index into that language's text), so we only use a
    translation when BOTH the story and its recomputed spans exist; otherwise the
    Russian base pair."""
    if lang and lang != BASE:
        si = getattr(mnemo, "story_i18n", None) or {}
        sp = getattr(mnemo, "spans_i18n", None) or {}
        story = si.get(lang)
        spans = sp.get(lang)
        if isinstance(story, str) and story.strip() and isinstance(spans, list) and spans:
            return story, spans
    return mnemo.story_ru, (mnemo.spans or [])
