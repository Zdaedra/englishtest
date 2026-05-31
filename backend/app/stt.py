"""Speech-to-text for spoken-recall training via OpenAI gpt-4o-mini-transcribe.

The learner's short audio clip (a phrase, or a whole mnemonic retelling) is sent
as multipart and returned as plain text. Audio is processed in-flight only — we
never persist the raw clip, just the resulting transcript downstream.
"""
import httpx

from .config import get_secrets

STT_MODEL = "gpt-4o-mini-transcribe"


def transcribe(audio_bytes: bytes, filename: str = "clip.webm",
               language: str | None = None) -> str:
    """Transcribe a short audio clip. `language` is an optional ISO-639-1 hint
    (e.g. 'en' for the phrase test); omit it for the mixed RU+EN sequence test
    so the model auto-detects."""
    api_key = get_secrets().openai_api_key
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY not set — cannot transcribe.")
    if not audio_bytes:
        return ""
    data = {"model": STT_MODEL, "response_format": "json"}
    if language:
        data["language"] = language
    r = httpx.post(
        "https://api.openai.com/v1/audio/transcriptions",
        headers={"Authorization": f"Bearer {api_key}"},
        data=data,
        files={"file": (filename, audio_bytes, "application/octet-stream")},
        timeout=120,
    )
    r.raise_for_status()
    return (r.json().get("text") or "").strip()
