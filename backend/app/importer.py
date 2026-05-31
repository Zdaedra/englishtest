"""Import pipeline: raw paste -> canonical BatchIn JSON.

Primary: deterministic parser for the known "N. Keyword -> phrase" format plus a
"Мнемо-текст:" block. Fallback: LLM (llm.parse_batch) for unstructured input.
Anchors in the mnemonic story are located by position (spans), not regex-by-word,
so repeated words and punctuation don't break tap-to-reveal.
"""
import re

from . import llm
from .schemas import BatchIn, MnemoIn, ParseResponse, PhraseIn, SpanIn, ZoneIn

_ARROW = re.compile(r"\s*(?:→|->|⇒|⟶)\s*")
_PHRASE_LINE = re.compile(r"^\s*(\d+)\s*[.)]\s*(.+)$")
_ZONE_LINE = re.compile(r"^\s*([^\d()\n][^()\n]*?)\s*\(\s*(\d+)\s*[-–—]\s*(\d+)\s*\)\s*:?\s*$")
_MNEMO_HEAD = re.compile(r"^\s*мнем[оа][\s\-]*(?:текст|история|техника)?\s*:?\s*(.*)$", re.IGNORECASE)
_RASKLAD = re.compile(r"раскладк|ключи на фраз", re.IGNORECASE)


def _compute_spans(story: str, phrases: list[PhraseIn]) -> tuple[list[SpanIn], list[str]]:
    spans: list[SpanIn] = []
    warnings: list[str] = []
    low = story.lower()
    cursor = 0
    for p in phrases:
        anchor = p.anchor.strip()
        if not anchor:
            continue
        idx = low.find(anchor.lower(), cursor)
        if idx == -1:
            # retry from the very start (anchor may appear out of strict order)
            idx = low.find(anchor.lower())
        if idx == -1:
            warnings.append(f"Якорь «{anchor}» (фраза {p.order_index}) не найден в мнемо-истории")
            continue
        spans.append(SpanIn(anchor_id=f"a{p.order_index}", phrase_id=p.order_index,
                            start=idx, end=idx + len(anchor)))
        cursor = idx + len(anchor)
    return spans, warnings


def _zone_for(order: int, zones: list[ZoneIn]) -> str | None:
    for z in zones:
        if z.range_start is not None and z.range_end is not None:
            if z.range_start <= order <= z.range_end:
                return z.title
    return None


def parse_deterministic(raw_text: str) -> ParseResponse:
    lines = raw_text.splitlines()
    title = ""
    theme = ""
    zones: list[ZoneIn] = []
    phrases: list[PhraseIn] = []
    warnings: list[str] = []

    mnemo_start = None
    mnemo_first_line = ""
    for i, line in enumerate(lines):
        m = _MNEMO_HEAD.match(line)
        if m and ("мнем" in line.lower()):
            mnemo_start = i
            mnemo_first_line = m.group(1).strip()
            break

    body = lines[:mnemo_start] if mnemo_start is not None else lines

    zone_order = 0
    for line in body:
        if not line.strip():
            continue
        if _RASKLAD.search(line):
            continue
        pm = _PHRASE_LINE.match(line)
        if pm:
            order = int(pm.group(1))
            rest = pm.group(2).strip()
            parts = _ARROW.split(rest, maxsplit=1)
            if len(parts) == 2:
                anchor, phrase_en = parts[0].strip(), parts[1].strip()
            else:
                anchor, phrase_en = "", rest
                warnings.append(f"Фраза {order}: не найден разделитель «→», якорь пуст")
            phrases.append(PhraseIn(order_index=order, anchor=anchor, phrase_en=phrase_en,
                                    intensity_score=float(order)))
            continue
        zm = _ZONE_LINE.match(line)
        if zm:
            zone_order += 1
            zones.append(ZoneIn(title=zm.group(1).strip(), order_index=zone_order,
                                range_start=int(zm.group(2)), range_end=int(zm.group(3))))
            continue
        # first non-phrase, non-zone line before phrases -> title
        if not phrases and not title:
            title = line.strip()

    # assign zones
    for p in phrases:
        p.zone = _zone_for(p.order_index, zones)

    # mnemo story
    story = ""
    if mnemo_start is not None:
        tail = [mnemo_first_line] if mnemo_first_line else []
        tail += [l for l in lines[mnemo_start + 1:]]
        story = "\n".join(tail).strip()

    spans, span_warnings = _compute_spans(story, phrases)
    warnings += span_warnings

    if not title:
        title = "Без названия"
        warnings.append("Заголовок батча не распознан — задай вручную")
    if not phrases:
        warnings.append("Не найдено ни одной фразы формата «N. Keyword → phrase»")

    batch = BatchIn(title=title, theme=theme, zones=zones, phrases=phrases,
                    mnemo=MnemoIn(story_ru=story, spans=spans), source_text=raw_text)
    return ParseResponse(batch=batch, warnings=warnings, parser="deterministic")


def parse(raw_text: str, use_llm: bool = False) -> ParseResponse:
    if not use_llm:
        det = parse_deterministic(raw_text)
        if det.batch.phrases:
            return det
    # LLM fallback
    data = llm.parse_batch(raw_text)
    zones = [ZoneIn(**z) for z in data.get("zones", [])]
    phrases = [PhraseIn(**p) for p in data.get("phrases", [])]
    for p in phrases:
        if p.zone is None:
            p.zone = _zone_for(p.order_index, zones)
    story = (data.get("mnemo") or {}).get("story_ru", "")
    spans, warnings = _compute_spans(story, phrases)
    batch = BatchIn(title=data.get("title", "Без названия"), theme=data.get("theme", ""),
                    zones=zones, phrases=phrases,
                    mnemo=MnemoIn(story_ru=story, spans=spans), source_text=raw_text)
    return ParseResponse(batch=batch, warnings=warnings, parser="llm")
