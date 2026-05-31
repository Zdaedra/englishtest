"""AI-generated batch cover art (OpenAI images), cached on disk in the data volume.

The prompt has versioned styles so we can experiment and always roll back:

  * version 1 — abstract, editorial album art keyed to a visual metaphor (the
    original look). No people, no literal objects: soft gradients, depth, light.
  * version 2 — a single cinematic photographic style depicting the batch's
    mnemonic scene (the subtitle, e.g. «Восхождение на гору»). One consistent
    look across the whole library; only the scene changes.

The active version is `ENGLISH_COVER_PROMPT_VERSION` (default 2). Generated files
are keyed by version (`<slug>.v<N>.png`), so flipping the version swaps in the
cached image with no re-generation cost. The frontend falls back to procedural art
when no cover exists, so generation failures are never fatal.
"""
import base64

import httpx

from .config import get_secrets, get_settings

# Mirror the frontend accent palette (lib/accent.ts) so a batch's cover and its
# card tint share the same dominant colour. Keyed by batch.id % 5.
_PALETTE = [
    ("Soft Indigo", "#6B6FCF"),
    ("Warm Sand", "#B08D57"),
    ("Sage Green", "#789A66"),
    ("Muted Coral", "#CB7A6E"),
    ("Dusty Blue", "#6E92B4"),
]


def accent_for(batch_id: int) -> tuple[str, str]:
    return _PALETTE[batch_id % len(_PALETTE)]


# Keyword → visual metaphor. First match wins; order matters (specific first).
_METAPHORS: list[tuple[tuple[str, ...], str]] = [
    (("восхожд", "ascen", "ladder", "climb", "восхожден", "intensit", "disagree"),
     "bold translucent horizontal strata stacking and ascending, each band brighter and "
     "more intense than the last, climbing toward a luminous threshold of light at the top, "
     "a powerful sense of escalating force rising through the frame"),
    (("раскоп", "excavat", "dig", "probe", "probing", "question", "curious", "вопрос"),
     "deep layered strata split open down the centre to reveal an intense glowing seam of "
     "light buried far below, a dramatic vertical descent into something hidden, shadow "
     "above giving way to a radiant molten core"),
    (("сцена", "stage", "charis", "presence", "харизм", "spotlight"),
     "a single powerful volumetric shaft of light cutting down through a dark, hazy "
     "atmospheric void onto a focal point, theatrical spotlight drama, deep shadow framing "
     "a radiant centre, overwhelming sense of presence and command"),
    (("negotiat", "перегов", "deal"),
     "two large smooth flowing forms approaching each other with controlled tension, "
     "held in poised balance"),
    (("stakeholder", "network", "align", "связ"),
     "a constellation of softly connected luminous nodes forming a quiet, ordered network"),
    (("influence", "persuad", "signal", "wave", "влиян", "убежд"),
     "concentric waves expanding gently outward from a single origin point, "
     "soft signal propagation through space"),
    (("lead", "лидер", "direction", "clarity", "vision"),
     "a single clean beam of light moving through dim space, a sense of direction and clarity"),
]


def metaphor_for(title: str, theme: str) -> str:
    hay = f"{title} {theme}".lower()
    for keys, metaphor in _METAPHORS:
        if any(k in hay for k in keys):
            return metaphor
    subject = (theme or title).strip()
    return (f"abstract layered gradient forms with atmospheric depth, evoking the idea "
            f"of {subject}" if subject else
            "abstract layered gradient forms with atmospheric depth and soft light")


# ---- Prompt styles (versioned so we can experiment and always roll back) ----

def _build_prompt_v1(*, title: str, theme: str, subtitle: str,
                     accent_name: str, accent_hex: str,
                     metaphor: str | None = None) -> str:
    """Version 1: abstract, editorial album art (the original look). Preserved
    verbatim so ENGLISH_COVER_PROMPT_VERSION=1 reproduces the previous covers."""
    m = metaphor or metaphor_for(title, theme)
    return (
        "Abstract fine-art album cover for a premium executive communication playbook, "
        "in the visual language of an Apple Music album cover and Linear app marketing art. "
        f"{m}. "
        "Rich, deep, immersive composition with a strong dramatic focal point and a clear "
        "sense of three-dimensional depth: bold volumetric light cutting through a dark, "
        "moody atmospheric gradient field, glowing core surrounded by deep shadow, high "
        "tonal contrast, luminous highlights, fine film grain and a subtle haze. Saturated, "
        f"confident colour built around a deep {accent_name} ({accent_hex}) — the accent owns "
        "the frame, not a pale wash. Cinematic, sophisticated, gallery-grade, instantly "
        "recognisable. Absolutely no text, no letters, no numbers, no words, no logos, no UI, "
        "no people, no faces, no hands, no literal objects, no charts, no icons, no clichéd "
        "illustration, no stock-photo look, not flat, not washed-out, not empty. "
        "Square 1:1 composition."
    )


def _build_prompt_v2(*, title: str, theme: str, subtitle: str,
                     accent_name: str, accent_hex: str,
                     metaphor: str | None = None) -> str:
    """Version 2: one consistent cinematic photographic style; only the scene
    changes. The scene is the mnemonic image (subtitle), so the cover literally
    shows what the learner pictures — a photo of what is happening."""
    scene = (subtitle or theme or title or "").strip()
    return (
        "A single cinematic editorial photograph for the cover of a premium "
        "executive-communication playbook. "
        f"The scene shows: {scene}. "
        "Bright, uplifting, life-affirming mood with fresh, vivid, optimistic colour and "
        "warm natural daylight. For an outdoor scene, include clear blue sky, lush green "
        "grass and sunlit nature; for any scene keep the light bright, airy and hopeful. "
        "Shot like a beautiful cinematic film still: shallow depth of field, soft natural "
        "light, rich but true-to-life colour. Never dark, never gloomy, never moody or "
        "apocalyptic, never washed-out. If a person is in frame, show them from behind or "
        "at a distance with the face not visible, as an anonymous evocative figure. "
        "Gallery-grade, polished, expensive-looking, instantly evoking the scene at a "
        "glance. Absolutely no text, no letters, no numbers, no words, no captions, no "
        "logos, no watermarks, no UI. Square 1:1 full-bleed composition."
    )


PROMPT_VERSIONS = {1: _build_prompt_v1, 2: _build_prompt_v2}


def active_prompt_version() -> int:
    v = get_settings().cover_prompt_version
    return v if v in PROMPT_VERSIONS else 2


def build_prompt(title: str, theme: str, accent_name: str, accent_hex: str,
                 metaphor: str | None = None, *, subtitle: str = "",
                 version: int | None = None) -> str:
    builder = PROMPT_VERSIONS.get(version or active_prompt_version(), _build_prompt_v2)
    return builder(title=title, theme=theme, subtitle=subtitle,
                   accent_name=accent_name, accent_hex=accent_hex, metaphor=metaphor)


def _request_image(prompt: str, model: str, size: str, quality: str) -> bytes:
    api_key = get_secrets().openai_api_key
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY not set — cannot generate cover art.")

    payload: dict = {"model": model, "prompt": prompt, "size": size, "n": 1}
    if model.startswith("gpt-image"):
        payload["quality"] = quality  # low | medium | high | auto
    else:  # dall-e-3
        payload["response_format"] = "b64_json"
        payload["quality"] = "hd" if quality in ("hd", "high") else "standard"

    resp = httpx.post(
        "https://api.openai.com/v1/images/generations",
        headers={"Authorization": f"Bearer {api_key}", "content-type": "application/json"},
        json=payload,
        timeout=240,
    )
    resp.raise_for_status()
    b64 = resp.json()["data"][0]["b64_json"]
    return base64.b64decode(b64)


def generate_cover(batch_id: int, slug: str, title: str, theme: str,
                   subtitle: str = "", *, metaphor: str | None = None,
                   quality: str | None = None, force: bool = False,
                   version: int | None = None) -> str:
    """Generate (or reuse) a cover PNG and return its public URL path.

    Files are keyed by prompt version (`<slug>.v<N>.png`) so switching versions
    swaps in a cached image with no re-generation cost."""
    s = get_settings()
    v = version or active_prompt_version()
    out = s.covers_dir / f"{slug}.v{v}.png"
    url = f"/covers/{slug}.v{v}.png"
    if out.exists() and out.stat().st_size > 0 and not force:
        return url

    accent_name, accent_hex = accent_for(batch_id)
    prompt = build_prompt(title, theme, accent_name, accent_hex, metaphor,
                          subtitle=subtitle, version=v)
    data = _request_image(prompt, s.image_model, s.cover_size, quality or s.cover_quality)
    out.write_bytes(data)
    return url
