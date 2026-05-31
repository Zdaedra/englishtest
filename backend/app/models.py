from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import Column, JSON
from sqlmodel import Field, SQLModel


def _now() -> datetime:
    return datetime.now(timezone.utc)


class Batch(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    title: str
    slug: str = Field(index=True)
    theme: str = ""
    # One-line mnemonic-flavoured preview shown on library cards. Curated per batch.
    subtitle: str = ""
    # Library section slug (see frontend lib/sections.ts). "" => unfiled.
    section: str = Field(default="", index=True)
    difficulty: str = ""
    version: int = 1
    status: str = Field(default="draft")  # draft | approved
    source_text: str = ""
    cover_path: Optional[str] = None  # URL path to AI-generated cover, e.g. /covers/<slug>.png
    created_at: datetime = Field(default_factory=_now)
    deleted_at: Optional[datetime] = None


class Zone(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    batch_id: int = Field(foreign_key="batch.id", index=True)
    title: str
    order_index: int = 0
    intensity_label: str = ""


class Phrase(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    batch_id: int = Field(foreign_key="batch.id", index=True)
    zone_id: Optional[int] = Field(default=None, foreign_key="zone.id")
    order_index: int = 0
    anchor: str = ""
    phrase_en: str = ""
    gloss_ru: str = ""
    intensity_score: float = 0.0
    tags: list = Field(default_factory=list, sa_column=Column(JSON))
    # SRS-lite status: new | shaky | familiar | automatic
    srs_status: str = Field(default="new")
    # Feedback-training rollup (Test B). EWMA of 0..10 scores; NULL until first attempt.
    avg_score: Optional[float] = None
    attempts: int = 0
    last_score: Optional[int] = None
    last_seen_at: Optional[datetime] = None


class MnemoStory(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    batch_id: int = Field(foreign_key="batch.id", index=True, unique=True)
    story_ru: str = ""
    # spans: [{anchor_id, phrase_id, start, end}]
    spans: list = Field(default_factory=list, sa_column=Column(JSON))


class ContextExample(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    phrase_id: int = Field(foreign_key="phrase.id", index=True)
    scenario_type: str = ""
    register_tone: str = ""
    intensity: str = ""
    speaker_role: str = ""
    listener_role: str = ""
    text: str = ""
    status: str = Field(default="draft")  # draft | approved
    audio_path: Optional[str] = None
    model: str = ""
    prompt_version: str = ""
    created_at: datetime = Field(default_factory=_now)


class AudioAsset(SQLModel, table=True):
    # Rich cache key: hash(text, voice, model, speed, format, normalization_version)
    hash: str = Field(primary_key=True)
    text: str
    model: str
    voice: str
    speed: float
    format: str
    normalization_version: int = 1
    path: str
    duration: float = 0.0
    created_at: datetime = Field(default_factory=_now)


class PlaybackSession(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    batch_id: int = Field(foreign_key="batch.id", index=True)
    mode: str = "recall"  # recall | listening | context
    order_mode: str = "ordered"  # ordered | zone_random | full_random
    shuffle_seed: Optional[int] = None
    plan: list = Field(default_factory=list, sa_column=Column(JSON))
    rendered_audio_path: Optional[str] = None
    duration: float = 0.0
    created_at: datetime = Field(default_factory=_now)


class ReviewEvent(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    phrase_id: int = Field(foreign_key="phrase.id", index=True)
    event_type: str = ""  # recall | listening
    score: str = ""  # easy | slow | failed
    latency_ms: Optional[int] = None
    date: datetime = Field(default_factory=_now)


class PhraseAttempt(SQLModel, table=True):
    """One spoken-recall attempt on a single phrase (Test B, feedback training)."""
    id: Optional[int] = Field(default=None, primary_key=True)
    phrase_id: int = Field(foreign_key="phrase.id", index=True)
    score: int = 0  # 0..10
    transcript: str = ""  # what STT heard the learner say
    via: str = ""  # how scored: gate | llm | cache | self
    latency_ms: Optional[int] = None
    created_at: datetime = Field(default_factory=_now)


class SequenceAttempt(SQLModel, table=True):
    """One spoken retelling of a whole mnemonic sequence (Test A, the exam)."""
    id: Optional[int] = Field(default=None, primary_key=True)
    batch_id: int = Field(foreign_key="batch.id", index=True)
    score: int = 0  # 0..10
    transcript: str = ""
    missed_anchors: list = Field(default_factory=list, sa_column=Column(JSON))
    order_ok: bool = True
    via: str = ""  # llm | self
    latency_ms: Optional[int] = None
    created_at: datetime = Field(default_factory=_now)


class Setting(SQLModel, table=True):
    # singleton row id=1
    id: Optional[int] = Field(default=None, primary_key=True)
    tts_voice: str = "alloy"
    tts_voice_ru: str = "onyx"
    tts_speed: float = 1.0
    tts_model: str = "tts-1"
    recall_gap_stimulus: float = 4.0
    recall_gap_after: float = 2.0
    listening_gap: float = 1.5
    listening_repeats: int = 0
    default_order_mode: str = "full_random"
    llm_provider: str = "auto"
