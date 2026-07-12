"""Hybrid practice scoring (F5): score_answer returns the SRS score PLUS honest
coaching (fits_task, natural, note) in one call. The autouse stub_network patches
`scoring.score_answer` for endpoint tests, so we capture the REAL function at module
import (before any fixture runs) and exercise it with only `_openai_json` stubbed."""
from app import scoring

_REAL = scoring.score_answer  # real impl, captured before autouse stub replaces it


def test_gate_verbatim_hit_is_10_and_fits(monkeypatch):
    monkeypatch.setattr("app.scoring._cache", {})
    out = _REAL("Push", "Let me push back.", "let me push back")
    assert out["score"] == 10
    assert out["fits_task"] is True
    assert out["natural"] == 9
    assert out["note"] == ""
    assert out["via"] == "gate"


def test_gate_too_few_tokens_says_repeat(monkeypatch):
    monkeypatch.setattr("app.scoring._cache", {})
    out = _REAL("Push", "Let me push back on that.", "ok")  # 1 token < _MIN_TOKENS
    assert out["score"] == 0
    assert out["fits_task"] is False
    assert out["natural"] == 0
    assert "расслыш" in out["note"].lower()
    assert out["via"] == "gate"


def test_llm_passthrough_of_honest_fields(monkeypatch):
    monkeypatch.setattr("app.scoring._cache", {})
    monkeypatch.setattr(
        "app.scoring._openai_json",
        lambda system, user, max_tokens=160, model=None: {
            "score": 3, "fits_task": True, "natural": 6,
            "note": "Возражение уместно, но звучит калькой."},
    )
    out = _REAL("Push", "Let's take it down a notch.",
                "we should calm this down a little", task_ru="Осадить, не обостряя")
    assert out["score"] == 3
    assert out["fits_task"] is True           # valid move for the task, even if not the target
    assert out["natural"] == 6
    assert "калькой" in out["note"]
    assert out["via"] in ("llm", "llm:escalated")


def test_llm_error_falls_back_without_coaching_claims(monkeypatch):
    monkeypatch.setattr("app.scoring._cache", {})

    def boom(*a, **k):
        raise RuntimeError("no api key")

    monkeypatch.setattr("app.scoring._openai_json", boom)
    out = _REAL("Push", "Let me push back on that.", "let me push back on it firmly")
    assert out["via"] == "fallback"
    assert isinstance(out["score"], int)
    assert out["fits_task"] is False          # no confident claim when the model failed
    assert out["natural"] == 0
    assert out["correct_phrase"] == "Let me push back on that."
