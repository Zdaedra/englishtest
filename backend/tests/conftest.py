"""Shared pytest fixtures for the backend suite.

Isolation strategy:
- A single throwaway SQLite DB under a temp ENGLISH_DATA_DIR, set BEFORE any
  `app.*` import (the engine is built at import time from cached settings, so
  the env var must win first — same trick tests/smoke.py uses).
- `fresh_db` (autouse) drops+recreates all tables between tests, so every test
  starts from an empty DB. Consequence: the first user registered in each test
  bootstraps as admin on the "ai" plan (see app/routers/auth.py).
- `stub_network` (autouse) replaces every paid/network boundary (TTS, STT, the
  AI scorers, cover art, LLM) so the whole suite runs offline with zero spend.
"""
import os
import tempfile
import wave
from pathlib import Path

# ── must run before importing app: pin data dir + disable network knobs ──────
_TMP = tempfile.mkdtemp(prefix="eng_pytest_")
os.environ["ENGLISH_DATA_DIR"] = _TMP
os.environ["ENGLISH_AUTO_COVER"] = "false"          # no cover gen during commit
os.environ["ENGLISH_LLM_PROVIDER"] = "openai"       # avoid the meridian auto-probe
os.environ.setdefault("OPENAI_API_KEY", "")
os.environ.setdefault("ANTHROPIC_API_KEY", "")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlmodel import Session, SQLModel  # noqa: E402

from app import importer, models  # noqa: E402
from app.config import get_settings  # noqa: E402
from app.db import engine, init_db  # noqa: E402
from app.main import app  # noqa: E402

# A minimal, deterministically-parseable import (5 phrases, 2 zones, 5 spans).
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


def _tiny_wav(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(24000)
        w.writeframes(b"\x00\x00" * int(24000 * 0.15))


@pytest.fixture(autouse=True)
def fresh_db():
    """Empty DB per test (tables dropped + recreated + Setting id=1 reseeded)."""
    eng = engine()
    SQLModel.metadata.drop_all(eng)
    init_db()
    yield


@pytest.fixture(autouse=True)
def stub_network(monkeypatch):
    """Replace every paid/network call. Routers import the *module* (``from ..
    import tts``) and call ``tts.synth`` etc., so patching the attribute on the
    real module reaches every call site."""
    s = get_settings()

    def _synth(text, voice=None, model=None, speed=None, fmt=None, instructions=None):
        p = s.audio_dir / "phrases" / f"stub_{abs(hash(text)) % 10**8}.wav"
        _tiny_wav(p)
        return p, 0.15

    monkeypatch.setattr("app.tts.synth", _synth)
    monkeypatch.setattr(
        "app.stt.transcribe",
        lambda raw, filename="clip.webm", language=None: "stub transcript",
    )
    monkeypatch.setattr(
        "app.scoring.score_phrase",
        lambda anchor, correct_phrase, user_said: {
            "score": 9, "correct_phrase": correct_phrase, "via": "gate"},
    )
    monkeypatch.setattr(
        "app.scoring.score_answer",
        lambda anchor, correct_phrase, user_said, task_ru="", situation_ru="": {
            "score": 9, "fits_task": True, "natural": 8, "note": "стаб",
            "correct_phrase": correct_phrase, "via": "gate"},
    )
    monkeypatch.setattr(
        "app.scoring.score_anchor",
        lambda anchor, user_said: {"score": 10, "correct_anchor": anchor, "via": "gate"},
    )
    monkeypatch.setattr(
        "app.scoring.score_sequence",
        lambda anchors, story, user_said: {
            "score": 8, "missed_anchors": [], "order_ok": True, "via": "llm"},
    )
    monkeypatch.setattr(
        "app.scoring.coach_feedback",
        lambda stimulus, target, user_said, score: {
            "feedback": "fb", "better": "better", "tone": "warm",
            "correct_phrase": target, "via": "llm"},
    )
    monkeypatch.setattr(
        "app.scoring.analyze_call",
        lambda text: {"upgrades": [{"original": "I think this is not good",
                                    "native": "Let me push back on that",
                                    "note": "короче и весомее"}], "via": "llm"},
    )
    monkeypatch.setattr(
        "app.scoring.weave_scenario",
        lambda items: {"title_ru": "Сцена", "via": "llm",
                       "beats": [{"situation_ru": f"Ситуация {i + 1}",
                                  "task_ru": f"Задача {i + 1}"}
                                 for i in range(len(items))]},
    )
    monkeypatch.setattr(
        "app.scoring.battle_pick",
        lambda situation, items, intent=None: {
            "via": "llm",
            "intents": [intent] if intent else
                       ["pushback", "hold", "ask", "warm", "clarify"],
            "picks": [{"n": 1, "note": "коротко и сразу"}] if items else []},
    )
    monkeypatch.setattr(
        "app.scoring.league_score",
        lambda answers: {"via": "llm", "results": [
            {"id": a["id"], "score": 7 if (a.get("text") or "").strip() else 0,
             "better": "Native line.", "note_ru": "заметка"} for a in answers]},
    )
    monkeypatch.setattr("app.cover.generate_cover", lambda *a, **k: "/covers/stub.png")
    monkeypatch.setattr("app.llm.parse_batch", lambda raw: {"phrases": []})
    monkeypatch.setattr("app.llm.chat", lambda system, user, temperature=None: "{}")
    # Embeddings: no network. embed_query -> None keeps battle on its
    # deterministic keyword/learned-first fallback; tests of the semantic path
    # install their own fakes on top of these. embed_texts returns a unit
    # vector of the configured dim per text so seed() runs offline.
    import struct as _struct
    _dim = s.embed_dim
    _unit = _struct.pack(f"<{_dim}f", 1.0, *([0.0] * (_dim - 1)))
    monkeypatch.setattr("app.embeddings.embed_query", lambda text: None)
    monkeypatch.setattr("app.embeddings.embed_texts",
                        lambda texts: [_unit for _ in texts])


@pytest.fixture
def client():
    """Unauthenticated client."""
    return TestClient(app)


@pytest.fixture
def make_user():
    """Factory: register a user and return an authenticated TestClient.

    The first user created in a fresh DB is forced to admin/"ai" by the
    register handler; pass plan/is_admin to override the row directly so tests
    can assert tier-specific behaviour deterministically.
    """
    counter = {"n": 0}

    def _make(email=None, password="password123", plan=None, is_admin=None,
              plan_expires_at=None, verified=True):
        counter["n"] += 1
        email = email or f"user{counter['n']}@example.com"
        c = TestClient(app)
        r = c.post("/api/auth/register",
                   json={"email": email, "password": password})
        assert r.status_code == 200, r.text
        data = r.json()
        # Email verification is mandatory and a fresh non-owner signup is
        # unverified — but most tests aren't about that gate, so verify by default
        # (pass verified=False to exercise the gate explicitly).
        with Session(engine()) as s:
            u = s.get(models.User, data["id"])
            u.email_verified = verified
            if plan is not None:
                u.plan = plan
            if is_admin is not None:
                u.is_admin = is_admin
            if plan_expires_at is not None:
                u.plan_expires_at = plan_expires_at
            s.add(u)
            s.commit()
            data["plan"] = u.plan
            data["is_admin"] = u.is_admin
            data["email_verified"] = u.email_verified
        c.headers.update({"Authorization": f"Bearer {data['token']}"})
        c.user = data  # type: ignore[attr-defined]
        return c

    return _make


def commit_sample_batch(client, *, as_admin_catalog=True):
    """Commit the SAMPLE import through the API. Admin → shared catalog
    (owner_id NULL, visible to all); non-admin → that user's private import.
    Returns the new batch id."""
    batch = importer.parse(SAMPLE).batch
    r = client.post("/api/imports/commit", json=batch.model_dump())
    assert r.status_code == 200, r.text
    return r.json()["id"]


def phrase_ids(client, batch_id):
    detail = client.get(f"/api/batches/{batch_id}").json()
    return [p["id"] for p in detail["phrases"]]


def pytest_collection_modifyitems(config, items):
    """Tag the whole collection with the project codename "smoketest3" so it can
    be run as a named group: `pytest -m smoketest3` selects exactly this suite."""
    mark = pytest.mark.smoketest3
    for item in items:
        item.add_marker(mark)
