"""Tutorial media manifest — the server-served video capability (drop a file in,
the step's slot fills, no app rebuild). New router => gets a test per the rule."""
from app.config import get_settings


def test_manifest_shape(client):
    r = client.get("/api/tutorial/manifest")
    assert r.status_code == 200
    body = r.json()
    assert "media" in body and isinstance(body["media"], dict)


def test_manifest_lists_dropped_clip(client):
    d = get_settings().tutorial_dir
    vid, poster = d / "mic.mp4", d / "mic.jpg"
    vid.write_bytes(b"\x00"); poster.write_bytes(b"\x00")
    try:
        media = client.get("/api/tutorial/manifest").json()["media"]
        assert media["mic"]["video"] == "/tutorial/mic.mp4"
        assert media["mic"]["poster"] == "/tutorial/mic.jpg"
    finally:
        vid.unlink(missing_ok=True); poster.unlink(missing_ok=True)


def test_manifest_video_without_poster(client):
    d = get_settings().tutorial_dir
    vid = d / "handsfree.mp4"
    vid.write_bytes(b"\x00")
    try:
        media = client.get("/api/tutorial/manifest").json()["media"]
        assert media["handsfree"]["video"] == "/tutorial/handsfree.mp4"
        assert "poster" not in media["handsfree"]
    finally:
        vid.unlink(missing_ok=True)
