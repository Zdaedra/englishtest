"""Offline smoke test: import parse -> commit -> get -> session render.
TTS is stubbed (writes tiny silent WAVs) so no OpenAI calls / spend.
Run: . .venv/bin/activate && python tests/smoke.py
"""
import os
import tempfile
import wave
from pathlib import Path

os.environ["ENGLISH_DATA_DIR"] = tempfile.mkdtemp(prefix="eng_smoke_")

from app import audio, importer, tts  # noqa: E402
from app.config import get_settings  # noqa: E402

SAMPLE = """Восхождение — лестница несогласия
Curious (1-3)
1. Understand → Help me understand the thinking there.
2. Walk → Walk me through how you got to that number.
3. Read → I read the situation differently.
Cautious (4-5)
4. Outlier → That feels like an outlier to me.
5. Straight → Let me be straight with you.
Мнемо-текст: Ты хочешь UNDERSTAND гору, поэтому WALK к тропе и READ карту. На пике одинокий OUTLIER, и ты отвечаешь STRAIGHT.
"""


def _stub_synth(text, voice=None, model=None, speed=None, fmt=None, instructions=None):
    s = get_settings()
    p = s.audio_dir / "phrases" / f"stub_{abs(hash(text)) % 10**8}.wav"
    with wave.open(str(p), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(24000)
        w.writeframes(b"\x00\x00" * int(24000 * 0.15))
    return p, 0.15


def main():
    # 1) deterministic parse
    res = importer.parse(SAMPLE)
    b = res.batch
    print(f"[parse] parser={res.parser} phrases={len(b.phrases)} zones={len(b.zones)} "
          f"spans={len(b.mnemo.spans)} warnings={res.warnings}")
    assert len(b.phrases) == 5, "expected 5 phrases"
    assert len(b.mnemo.spans) == 5, f"expected 5 spans, got {len(b.mnemo.spans)}"
    assert b.phrases[0].anchor == "Understand"
    assert b.phrases[3].zone == "Cautious"
    # verify span actually points at the anchor text
    sp = b.mnemo.spans[0]
    assert b.mnemo.story_ru[sp.start:sp.end].lower() == "understand"
    print("[parse] OK — spans align with story positions")

    # 2) audio render (stubbed TTS)
    tts.synth = _stub_synth
    audio.tts.synth = _stub_synth
    from app.models import Setting
    st = Setting(id=1)
    from app.routers.sessions import _build_segments, _order_phrases

    class P:  # lightweight phrase stand-in
        def __init__(self, o, en, ru="", zid=None):
            self.order_index = o; self.phrase_en = en; self.gloss_ru = ru; self.zone_id = zid
    phrases = [P(i + 1, ph.phrase_en) for i, ph in enumerate(b.phrases)]
    segs = _build_segments("recall", phrases, st)
    path, dur, plan = audio.render_session(segs, "smoke.wav")
    print(f"[audio] rendered {path.name} dur={dur}s segments={len(plan)} "
          f"first={plan[0]['role']}@{plan[0]['start']} last_end={plan[-1]['end']}")
    assert Path(path).exists() and dur > 0
    assert plan[-1]["end"] == dur
    print("[audio] OK — gapless WAV with per-segment timecodes")

    # 3) API: commit + get via TestClient
    from fastapi.testclient import TestClient
    from app.db import init_db
    from app.main import app
    init_db()
    client = TestClient(app)
    assert client.get("/api/health").json() == {"ok": True}
    # The API is auth-gated (multi-tenant). The first account in this fresh temp
    # DB bootstraps as admin on the "ai" plan, which has the `import` entitlement;
    # TestClient carries the eng_auth cookie to the calls below.
    reg = client.post("/api/auth/register",
                      json={"email": "smoke@example.com", "password": "smoke-pass-123"})
    assert reg.status_code == 200, reg.text
    print(f"[auth] registered smoke user admin={reg.json()['is_admin']} plan={reg.json()['plan']}")
    r = client.post("/api/imports/commit", json=b.model_dump())
    assert r.status_code == 200, r.text
    bid = r.json()["id"]
    detail = client.get(f"/api/batches/{bid}").json()
    print(f"[api] committed batch id={bid} phrases={len(detail['phrases'])} "
          f"mnemo_spans={len(detail['mnemo']['spans'])} status={detail['status']}")
    assert len(detail["phrases"]) == 5
    lst = client.get("/api/batches").json()
    assert any(x["id"] == bid for x in lst)
    # SRS via the swipe path (the legacy /batches/reviews endpoint is removed)
    pid = detail["phrases"][0]["id"]
    rv = client.post("/api/training/swipe",
                     json={"session_id": "smoke", "phrase_id": pid,
                           "swipe_direction": "right"}).json()
    print(f"[api] swipe right -> self_ewma={rv['self_ewma']}")
    assert rv["ok"] is True
    print("\nALL SMOKE CHECKS PASSED")


if __name__ == "__main__":
    main()
