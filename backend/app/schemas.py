from typing import Optional

from pydantic import BaseModel, Field


# ---- Import / canonical JSON (source of truth) ----

class SpanIn(BaseModel):
    anchor_id: str
    phrase_id: int  # order_index of the phrase this anchor belongs to
    start: int
    end: int


class PhraseIn(BaseModel):
    order_index: int
    anchor: str
    phrase_en: str
    gloss_ru: str = ""
    intensity_score: float = 0.0
    zone: Optional[str] = None
    tags: list[str] = Field(default_factory=list)


class ZoneIn(BaseModel):
    title: str
    order_index: int = 0
    intensity_label: str = ""
    range_start: Optional[int] = None
    range_end: Optional[int] = None


class MnemoIn(BaseModel):
    story_ru: str = ""
    spans: list[SpanIn] = Field(default_factory=list)


class BatchIn(BaseModel):
    title: str
    theme: str = ""
    subtitle: str = ""
    section: str = ""
    difficulty: str = ""
    zones: list[ZoneIn] = Field(default_factory=list)
    phrases: list[PhraseIn] = Field(default_factory=list)
    mnemo: MnemoIn = Field(default_factory=MnemoIn)
    source_text: str = ""


class ParseRequest(BaseModel):
    raw_text: str
    use_llm: bool = False  # force LLM path even if deterministic parse succeeds


class ParseResponse(BaseModel):
    batch: BatchIn
    warnings: list[str] = Field(default_factory=list)
    parser: str = "deterministic"  # deterministic | llm


# ---- Sessions ----

class SessionRequest(BaseModel):
    batch_id: int
    mode: str = "recall"  # recall | listening
    order_mode: str = "ordered"  # ordered | zone_random | full_random
    voice: Optional[str] = None
    voice_ru: Optional[str] = None
    repeats: Optional[int] = None


class SessionResponse(BaseModel):
    id: int
    batch_id: int
    mode: str
    order_mode: str
    audio_url: str
    duration: float
    plan: list[dict]


# ---- Review (SRS-lite) ----

class ReviewIn(BaseModel):
    phrase_id: int
    event_type: str = "recall"
    score: str  # easy | slow | failed
    latency_ms: Optional[int] = None
