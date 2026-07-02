"""Coach-mark tutorial media manifest.

The frontend tutorial is text + an arrow by default. Each step can OPTIONALLY show
a short video — but the clips are NOT bundled in the app. Instead they're served
from the persistent tutorial dir, and this manifest reports which steps currently
have one. To add a clip for the "mic" step later: drop `mic.mp4` (and optionally
`mic.jpg` as a poster) into the tutorial dir on the server — that step's slot fills
on next launch, with no app rebuild or App Store resubmission. The key is the
step's `data-tour` value.
"""
from fastapi import APIRouter

from ..config import get_settings

router = APIRouter(prefix="/api/tutorial", tags=["tutorial"])

_POSTER_EXTS = (".jpg", ".jpeg", ".png", ".webp")


@router.get("/manifest")
def manifest() -> dict:
    """{ media: { "<key>": {"video": "/tutorial/<key>.mp4", "poster"?: "..."} } }."""
    d = get_settings().tutorial_dir
    out: dict[str, dict] = {}
    for mp4 in sorted(d.glob("*.mp4")):
        key = mp4.stem
        entry = {"video": f"/tutorial/{mp4.name}"}
        for ext in _POSTER_EXTS:
            poster = d / f"{key}{ext}"
            if poster.exists():
                entry["poster"] = f"/tutorial/{poster.name}"
                break
        out[key] = entry
    return {"media": out}
