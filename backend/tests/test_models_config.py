"""Config-driven model routing (the "bridges"). Locks the env contract per the
testing rule: defaults must equal today's production models (so an unset env is a
no-op), and ENGLISH_MODEL_* env overrides must flow through to the call sites."""
from types import SimpleNamespace

from app.config import Settings
# Captured at import — before the autouse stub_network fixture replaces the module
# attribute — so the cascade tests exercise the real scoring logic.
from app.scoring import score_phrase as _real_score_phrase


def test_model_defaults_match_production():
    """Unset env => byte-identical to the pre-config hardcoded models."""
    s = Settings()
    assert s.model_stt == "gpt-4o-mini-transcribe"
    assert s.model_score == "gpt-4.1-nano"
    assert s.model_sequence == "gpt-4.1-mini"
    assert s.model_coach == "gpt-4.1-mini"
    assert s.model_import == "gpt-4o-mini"
    assert s.model_import_anthropic == "claude-sonnet-4-6"


def test_env_overrides_model(monkeypatch):
    """A model swaps with an env change (no code deploy)."""
    monkeypatch.setenv("ENGLISH_MODEL_SCORE", "gpt-5-nano")
    monkeypatch.setenv("ENGLISH_MODEL_STT", "deepgram-nova-3")
    s = Settings()
    assert s.model_score == "gpt-5-nano"
    assert s.model_stt == "deepgram-nova-3"


def test_scoring_reads_model_from_settings(monkeypatch):
    """scoring._openai_json (the shared OpenAI caller) resolves its default model
    from config, not a hardcoded constant. Tested at this level because the autouse
    stub_network fixture replaces the higher-level score_phrase wrapper."""
    from app import scoring

    captured = {}

    def fake_post(url, headers=None, json=None, timeout=None):
        captured["model"] = json["model"]

        class _R:
            def raise_for_status(self): ...
            def json(self):
                return {"choices": [{"message": {"content": '{"score": 7}'}}]}
        return _R()

    monkeypatch.setattr(scoring.httpx, "post", fake_post)
    monkeypatch.setattr(scoring, "get_secrets", lambda: SimpleNamespace(openai_api_key="sk-test"))
    scoring._openai_json("sys", "usr", max_tokens=40)  # model=None => config default
    assert captured["model"] == Settings().model_score


def _capture_body(monkeypatch):
    from app import scoring
    body = {}

    def fake_post(url, headers=None, json=None, timeout=None):
        body.update(json)

        class _R:
            def raise_for_status(self): ...
            def json(self):
                return {"choices": [{"message": {"content": '{"score": 7}'}}]}
        return _R()

    monkeypatch.setattr(scoring.httpx, "post", fake_post)
    monkeypatch.setattr(scoring, "get_secrets", lambda: SimpleNamespace(openai_api_key="sk-test"))
    return body


def test_classic_model_request_shape(monkeypatch):
    """Classic chat models keep temperature + max_tokens."""
    from app import scoring
    body = _capture_body(monkeypatch)
    scoring._openai_json("sys", "usr", max_tokens=40, model="gpt-4.1-nano")
    assert body["max_tokens"] == 40 and body["temperature"] == 0
    assert "max_completion_tokens" not in body


def test_reasoning_model_request_shape(monkeypatch):
    """GPT-5/o-series use max_completion_tokens and drop the rejected params, so an
    ENGLISH_MODEL_* swap to a reasoning model doesn't 400."""
    from app import scoring
    body = _capture_body(monkeypatch)
    scoring._openai_json("sys", "usr", max_tokens=40, model="gpt-5-nano")
    assert "max_completion_tokens" in body and body["max_completion_tokens"] >= 2000
    assert "max_tokens" not in body and "temperature" not in body


def _patch_scoring(monkeypatch, cheap_score, strong_score, settings):
    """Wire scoring so the cheap model returns cheap_score and the strong model
    returns strong_score; force the LLM branch (gate returns None). Returns the
    list that records which models were called."""
    from app import scoring
    calls = []

    def fake_json(system, user, max_tokens=80, model=None):
        calls.append(model)
        return {"score": strong_score if model == settings.model_sequence else cheap_score}

    monkeypatch.setattr(scoring, "_openai_json", fake_json)
    monkeypatch.setattr(scoring, "local_gate", lambda c, u: None)
    monkeypatch.setattr(scoring, "get_settings", lambda: settings)
    scoring._cache.clear()
    return calls


def test_cascade_escalates_borderline(monkeypatch):
    """A cheap-model score in the ambiguous band is re-scored on the strong model,
    and the strong verdict wins."""
    s = Settings(cascade_score_enabled=True, cascade_score_low=4, cascade_score_high=7)
    calls = _patch_scoring(monkeypatch, cheap_score=6, strong_score=9, settings=s)
    r = _real_score_phrase("a", "the correct target phrase", "an ambiguous answer")
    assert r["score"] == 9
    assert r["via"] == "llm:escalated"
    assert s.model_score in calls and s.model_sequence in calls  # both tiers ran


def test_cascade_skips_clearcut(monkeypatch):
    """A clear pass from the cheap model is trusted — no escalation, no second call."""
    s = Settings(cascade_score_enabled=True, cascade_score_low=4, cascade_score_high=7)
    calls = _patch_scoring(monkeypatch, cheap_score=9, strong_score=2, settings=s)
    r = _real_score_phrase("a", "target", "answer")
    assert r["score"] == 9
    assert r["via"] == "llm"
    assert s.model_sequence not in calls  # strong model never touched


def test_cascade_disabled_never_escalates(monkeypatch):
    """With the cascade off, even a borderline cheap score is taken as final."""
    s = Settings(cascade_score_enabled=False)
    calls = _patch_scoring(monkeypatch, cheap_score=6, strong_score=9, settings=s)
    r = _real_score_phrase("a", "target", "answer")
    assert r["score"] == 6
    assert r["via"] == "llm"
    assert s.model_sequence not in calls
