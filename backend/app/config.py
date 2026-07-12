from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="ENGLISH_", extra="ignore")

    # Storage
    data_dir: Path = Path(__file__).resolve().parent.parent / "data"

    # Single-user auth gate (cookie-based, so iOS Safari/PWA stops re-prompting).
    # Empty password => gate disabled (local dev). Set ENGLISH_APP_PASSWORD on host.
    app_password: str = ""
    cookie_secret: str = "change-me"

    # Stats cabinet (admin analytics dashboard). Served at /admin behind HTTP Basic
    # auth using these two values; if EITHER is empty the cabinet is fully disabled
    # (every /admin route → 404), so it can never be left open by accident.
    stats_user: str = ""
    stats_password: str = ""

    # Privacy: voice transcripts (free text of spoken answers) are auto-purged after
    # this many days; numeric scores/progress are kept. 0 disables purging.
    transcript_retention_days: int = 365

    # Email verification (magic link). public_base_url is the origin the link points
    # at (must be the user-facing site, NOT capacitor://localhost). mail_from is the
    # verified Resend sender. The Resend API key is a secret (see Secrets below).
    public_base_url: str = "https://executive-english.net"
    mail_from: str = "Executive English <noreply@executive-english.net>"

    # LLM provider abstraction: auto | meridian | anthropic | openai
    llm_provider: str = "auto"
    meridian_url: str = "http://172.17.0.1:3456"

    # Task → model routing (the "bridges"). Env-overridable so a model swaps with an
    # env change + restart (get_settings is lru-cached) — no code deploy. Defaults are
    # the current production models, so an unset env is byte-identical to before.
    # Strategy / candidates: TZ-ai-cost-strategy.md.
    model_stt: str = "gpt-4o-mini-transcribe"           # ENGLISH_MODEL_STT
    model_score: str = "gpt-4.1-nano"                   # ENGLISH_MODEL_SCORE (phrase drill, Test B)
    model_sequence: str = "gpt-4.1-mini"               # ENGLISH_MODEL_SEQUENCE (sequence exam, Test A)
    model_coach: str = "gpt-4.1-mini"                  # ENGLISH_MODEL_COACH (AI coach)
    model_import: str = "gpt-4o-mini"                  # ENGLISH_MODEL_IMPORT (llm chat/parse, OpenAI leg)
    model_import_anthropic: str = "claude-sonnet-4-6"  # ENGLISH_MODEL_IMPORT_ANTHROPIC (Anthropic leg)
    # Live semantic retrieval (app/embeddings.py). Changing either invalidates the
    # whole PhraseEmbedding index — rerun `python -m app.embeddings` after a swap.
    model_embed: str = "text-embedding-3-small"        # ENGLISH_MODEL_EMBED
    embed_dim: int = 512                               # ENGLISH_EMBED_DIM

    # Cascade: the cheap scoring model (model_score) is trusted at the extremes
    # (clear pass / clear fail); only its ambiguous-band verdicts are re-scored on the
    # stronger model (model_sequence) — that's the only place the two actually disagree.
    # Cheap for the easy 90%, the strong model only for the hard cases. Env-tunable.
    cascade_score_enabled: bool = True   # ENGLISH_CASCADE_SCORE (set 0 to disable)
    cascade_score_low: int = 4           # ENGLISH_CASCADE_SCORE_LOW  (inclusive)
    cascade_score_high: int = 7          # ENGLISH_CASCADE_SCORE_HIGH (inclusive)

    # TTS
    tts_model: str = "tts-1"
    tts_voice: str = "alloy"
    tts_voice_ru: str = "onyx"
    tts_format: str = "wav"  # wav => pure-python gapless concat without ffmpeg
    tts_speed: float = 1.0

    # Active Recall default timings (seconds)
    recall_gap_stimulus: float = 4.0
    recall_gap_after: float = 2.0
    listening_gap: float = 1.5
    listening_repeats: int = 1

    # AI cover art (OpenAI images). gpt-image-1 => b64; dall-e-3 is the fallback model.
    image_model: str = "gpt-image-1"
    cover_size: str = "1024x1024"
    cover_quality: str = "high"  # gpt-image-1: low|medium|high; dall-e-3: standard|hd
    auto_cover: bool = True  # pipeline auto-generates a scene cover per batch (v2 style)
    # Cover prompt style version: 1 = abstract editorial art, 2 = single-style scene photo.
    # Set ENGLISH_COVER_PROMPT_VERSION=1 to roll back to the abstract look.
    cover_prompt_version: int = 2

    # Apple In-App Purchase (StoreKit 2) — App Store Server API verification.
    # Set via ENGLISH_APPLE_* env (private key path points to the .p8, kept out of git).
    apple_bundle_id: str = "net.executiveenglish.app"
    apple_app_apple_id: int = 0
    apple_environment: str = "sandbox"   # sandbox | production
    apple_key_id: str = ""
    apple_issuer_id: str = ""
    apple_private_key_path: str = ""

    @property
    def db_path(self) -> Path:
        return self.data_dir / "app.db"

    @property
    def audio_dir(self) -> Path:
        return self.data_dir / "audio"

    @property
    def covers_dir(self) -> Path:
        return self.data_dir / "covers"

    @property
    def exports_dir(self) -> Path:
        return self.data_dir / "exports"

    @property
    def tutorial_dir(self) -> Path:
        # Coach-mark tutorial videos. Lives under the persistent data volume so
        # clips dropped here survive redeploys; <data-tour key>.mp4 (+ optional
        # poster) auto-fills that step's slot — no app rebuild. See routers/tutorial.py.
        return self.data_dir / "tutorial"


# These come from the master .env (no ENGLISH_ prefix), read separately.
class Secrets(BaseSettings):
    model_config = SettingsConfigDict(extra="ignore")

    openai_api_key: str = ""
    anthropic_api_key: str = ""
    anthropic_base_url: str = "https://api.anthropic.com"
    # Resend (transactional email for verification links). Empty => dev mode: the
    # link is logged instead of sent, so the flow is testable without a live key.
    resend_api_key: str = ""


@lru_cache
def get_settings() -> Settings:
    s = Settings()
    s.audio_dir.joinpath("phrases").mkdir(parents=True, exist_ok=True)
    s.audio_dir.joinpath("sessions").mkdir(parents=True, exist_ok=True)
    s.covers_dir.mkdir(parents=True, exist_ok=True)
    s.exports_dir.mkdir(parents=True, exist_ok=True)
    s.tutorial_dir.mkdir(parents=True, exist_ok=True)
    return s


@lru_cache
def get_secrets() -> Secrets:
    return Secrets()
