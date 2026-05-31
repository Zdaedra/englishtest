"""Gapless audio session renderer (pure-python WAV concat).

The challenge takeaway: iOS background playback can't rely on JS timers between
short clips. So pauses/repeats are baked INTO one rendered WAV. The client plays a
single <audio> element; lock-screen survives because it's just one long file.

WAV (PCM) concatenation needs no system deps. ffmpeg is optional and only used in
v0.2 to compress the final WAV -> MP3 for smaller offline cache.
"""
import wave
from pathlib import Path

from . import tts
from .config import get_settings


def _silence_bytes(params: wave._wave_params, seconds: float) -> bytes:
    frames = int(params.framerate * seconds)
    return b"\x00" * (frames * params.sampwidth * params.nchannels)


def render_session(segments: list[dict], out_name: str,
                   voice: str | None = None, voice_ru: str | None = None,
                   model: str | None = None, instructions: str | None = None) -> tuple[Path, float, list[dict]]:
    """segments: ordered list of
         {"kind": "audio", "text": str, "lang": "en"|"ru", "phrase_order": int, "role": str}
         {"kind": "silence", "dur": float, "phrase_order": int, "role": str}
    Returns (path, duration_sec, plan_with_times).
    `model`/`instructions` (optional) steer every audio segment, e.g. a single
    gpt-4o-mini-tts narrator for the mnemonic drills.
    """
    s = get_settings()
    voice = voice or s.tts_voice
    voice_ru = voice_ru or s.tts_voice_ru

    # Pass 1: synth all audio segments (cached) so we know PCM params.
    rendered: list[dict] = []
    params: wave._wave_params | None = None
    for seg in segments:
        if seg["kind"] == "audio":
            v = voice_ru if seg.get("lang") == "ru" else voice
            path, _dur = tts.synth(seg["text"], voice=v, model=model, instructions=instructions)
            with wave.open(str(path), "rb") as w:
                if params is None:
                    params = w.getparams()
                frames = w.readframes(w.getnframes())
            rendered.append({**seg, "_frames": frames})
        else:
            rendered.append(dict(seg))

    if params is None:
        raise RuntimeError("No audio segments to render.")

    # Pass 2: assemble + compute per-segment timecodes.
    out_path = s.audio_dir / "sessions" / out_name
    plan: list[dict] = []
    offset = 0.0
    bytes_per_sec = params.framerate * params.sampwidth * params.nchannels
    with wave.open(str(out_path), "wb") as out:
        # NB: copy only the PCM format, not nframes. OpenAI tts-1 returns a
        # streaming WAV with placeholder sizes (RIFF/data = 0xFFFFFFFF), so the
        # source nframes is bogus (2^31-1); propagating it overflows the uint32
        # header field. Let wave count frames from what we actually write.
        out.setnchannels(params.nchannels)
        out.setsampwidth(params.sampwidth)
        out.setframerate(params.framerate)
        for seg in rendered:
            if seg["kind"] == "audio":
                data = seg["_frames"]
            else:
                data = _silence_bytes(params, float(seg.get("dur", 0)))
            dur = len(data) / float(bytes_per_sec)
            out.writeframes(data)
            plan.append({k: v for k, v in seg.items() if k != "_frames"} |
                        {"start": round(offset, 3), "end": round(offset + dur, 3)})
            offset += dur

    return out_path, round(offset, 3), plan
