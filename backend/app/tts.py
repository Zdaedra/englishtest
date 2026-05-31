"""OpenAI TTS with on-disk cache keyed by a rich hash.

Cache key includes text, voice, model, speed, format and a normalization version,
so changing any of them yields a fresh asset instead of a stale cache hit.
"""
import hashlib
import wave
from pathlib import Path

import httpx

from .config import get_secrets, get_settings

NORMALIZATION_VERSION = 1


def cache_key(text: str, voice: str, model: str, speed: float, fmt: str,
              instructions: str | None = None) -> str:
    raw = f"{NORMALIZATION_VERSION}|{model}|{voice}|{speed}|{fmt}|{text}"
    if instructions:
        # Only widen the key when steering is used, so existing phrase assets
        # (no instructions) keep their cache hits.
        raw = f"{NORMALIZATION_VERSION}|{model}|{voice}|{speed}|{fmt}|i:{instructions}|{text}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]


def _wav_duration(path: Path) -> float:
    # OpenAI tts-1 WAVs are streamed with placeholder sizes (data = 0xFFFFFFFF),
    # so the header nframes is bogus. Measure from the actual PCM bytes instead.
    try:
        with wave.open(str(path), "rb") as w:
            data = w.readframes(w.getnframes())
            frame_size = w.getsampwidth() * w.getnchannels()
            return len(data) / float(frame_size) / float(w.getframerate())
    except Exception:
        return 0.0


def synth(text: str, voice: str | None = None, model: str | None = None,
          speed: float | None = None, fmt: str | None = None,
          instructions: str | None = None) -> tuple[Path, float]:
    s = get_settings()
    voice = voice or s.tts_voice
    model = model or s.tts_model
    speed = speed if speed is not None else s.tts_speed
    fmt = fmt or s.tts_format

    key = cache_key(text, voice, model, speed, fmt, instructions)
    path = s.audio_dir / "phrases" / f"{key}.{fmt}"
    if path.exists() and path.stat().st_size > 0:
        return path, _wav_duration(path)

    api_key = get_secrets().openai_api_key
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY not set — cannot synthesize TTS.")

    body: dict = {"model": model, "input": text, "voice": voice, "response_format": fmt}
    if model.startswith("gpt-4o"):
        # gpt-4o-*-tts is steerable via `instructions` and rejects `speed`.
        if instructions:
            body["instructions"] = instructions
    else:
        body["speed"] = speed

    resp = httpx.post(
        "https://api.openai.com/v1/audio/speech",
        headers={"Authorization": f"Bearer {api_key}", "content-type": "application/json"},
        json=body,
        timeout=180,
    )
    resp.raise_for_status()
    path.write_bytes(resp.content)
    return path, _wav_duration(path)
