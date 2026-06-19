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

    # LLM provider abstraction: auto | meridian | anthropic | openai
    llm_provider: str = "auto"
    meridian_url: str = "http://172.17.0.1:3456"

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


# These come from the master .env (no ENGLISH_ prefix), read separately.
class Secrets(BaseSettings):
    model_config = SettingsConfigDict(extra="ignore")

    openai_api_key: str = ""
    anthropic_api_key: str = ""
    anthropic_base_url: str = "https://api.anthropic.com"


@lru_cache
def get_settings() -> Settings:
    s = Settings()
    s.audio_dir.joinpath("phrases").mkdir(parents=True, exist_ok=True)
    s.audio_dir.joinpath("sessions").mkdir(parents=True, exist_ok=True)
    s.covers_dir.mkdir(parents=True, exist_ok=True)
    s.exports_dir.mkdir(parents=True, exist_ok=True)
    return s


@lru_cache
def get_secrets() -> Secrets:
    return Secrets()
