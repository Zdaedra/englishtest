"""Fuzzy semantic scoring for spoken-recall training (0..10).

Two tests:
  - score_phrase   (Test B): learner says one English phrase back -> score vs the
                   correct phrase keyed to an anchor.
  - score_sequence (Test A): learner retells the whole mnemonic story -> score the
                   gist + presence/order of anchors.

Cost discipline (per consilium): a local "gate" resolves the obvious cases
(verbatim hit -> 10, empty -> 0) WITHOUT an LLM call. Only the ambiguous middle
hits an LLM (JSON mode, temperature 0). An in-process cache de-dupes identical
(target, normalized-spoken) pairs so repeats are free and never drift.

Model split: the high-frequency phrase drill uses the cheap nano (it has the
local gate to absorb verbatim hits). The sequence exam is the HARD GATE, runs
once per batch, and must reason over a mixed RU+EN retelling with phonetic
transliterations (e.g. "ленд" -> land) — nano fails that badly, so it uses the
stronger mini. Verified: on a real retelling nano scored 4/10 marking present
anchors as missed, while mini scored 9/10 correctly.
"""
import json
import re
from difflib import SequenceMatcher

import httpx

from .config import get_secrets

SCORING_MODEL = "gpt-4.1-nano"       # phrase drill (Test B) — cheap, high-frequency
SEQUENCE_MODEL = "gpt-4.1-mini"      # sequence exam (Test A) — the hard gate, needs reasoning

# Local-gate thresholds: above these the spoken answer is "essentially the target"
# and we award 10 without spending an LLM call.
_GATE_RATIO = 0.92      # SequenceMatcher ratio on normalized strings
_GATE_JACCARD = 0.90    # token-set overlap (catches re-ordering)
_MIN_TOKENS = 2         # fewer than this => treat as empty/garbage -> 0

_PHRASE_SYSTEM = (
    "Ты — строгий, но справедливый экзаменатор устного recall английских фраз. "
    "Учащийся пытается вспомнить и произнести правильную фразу; тебе дают эталон "
    "(correct_phrase) и распознанную речь (user_said). Оцени СМЫСЛОВОЕ совпадение "
    "по целочисленной шкале 0..10 — смысл важнее дословности.\n"
    "ВАЖНО: учащемуся разрешено отвечать КОРОТКО и своими словами. Сжатая/укороченная "
    "версия, сохраняющая суть и ключевой глагол/действие, — это 9-10, даже если опущены "
    "вводные слова, усилители или детали (right now, actually, for this, just, you know). "
    "Снижай до 6-7 ТОЛЬКО если потеряно смыслонесущее слово, без которого сам запрос звучит "
    "иначе, — не за краткость саму по себе.\n"
    "10 = семантически эквивалентно (включая валидный перефраз/синоним/сжатую форму).\n"
    "8-9 = суть и ключевое действие верны, опущены лишь второстепенные слова или мелочь "
    "(артикль, время глагола без потери смысла).\n"
    "6-7 = основной смысл есть, но пропущено ключевое слово ИЛИ ошибка времени, меняющая нюанс.\n"
    "4-5 = частично: тема узнаётся, фраза искажена.\n"
    "2-3 = далеко, лишь отдельные общие слова.\n"
    "0-1 = пусто / не по теме / мусор распознавания.\n"
    "Примеры (correct -> said -> score):\n"
    "  'Let me cut to it.' -> 'let me cut to it' -> 10\n"
    "  'The window for this is open right now.' -> 'the window is open' -> 9\n"
    "  'Walk me through how you got to that number.' -> 'walk me through how you reached that number' -> 9\n"
    "  'Here is what is actually at stake.' -> 'here is what is at stake' -> 9\n"
    "  'Walk me through how you got to that number.' -> 'walk me through it' -> 6\n"
    "  'I'd bet money you've felt this.' -> 'i think you felt something' -> 3\n"
    "  'Give me the green light.' -> 'what time is it' -> 0\n"
    "Верни СТРОГО JSON без markdown: {\"score\": <int 0..10>}."
)

_SEQUENCE_SYSTEM = (
    "Ты — экзаменатор по запоминанию мнемонической истории. Учащийся ПЕРЕСКАЗЫВАЕТ "
    "своими словами суть истории (story_ru) и должен воспроизвести цепочку якорей "
    "(anchors_in_order) В ПРАВИЛЬНОМ ПОРЯДКЕ. Оценивай не дословность, а: (а) передан "
    "ли смысл истории, (б) названы ли якоря, (в) сохранён ли их порядок.\n"
    "Шкала score 0..10: 10 = вся суть и все якоря по порядку; 7-9 = почти всё, "
    "1-2 мелких пропуска/перестановки; 4-6 = половина якорей или заметно нарушен "
    "порядок; 1-3 = вспомнил мало; 0 = пусто/не по теме.\n"
    "missed_anchors = якоря из anchors_in_order, которых НЕТ в пересказе (по смыслу). "
    "order_ok = true, если упомянутые якоря идут в правильном относительном порядке.\n"
    "Верни СТРОГО JSON без markdown: "
    "{\"score\": <int 0..10>, \"missed_anchors\": [<str>...], \"order_ok\": <bool>}."
)

# Process-level cache: (kind, target, normalized_spoken) -> result dict.
_cache: dict[tuple, dict] = {}


def _normalize(text: str) -> str:
    text = re.sub(r"[^\w\s]", " ", text or "", flags=re.UNICODE)
    return re.sub(r"\s+", " ", text).strip().lower()


def _tokens(norm: str) -> list[str]:
    return norm.split() if norm else []


def local_gate(correct: str, user_said: str) -> int | None:
    """Resolve obvious cases without an LLM. Returns a score, or None if the
    answer is in the ambiguous middle and needs the model."""
    nc, nu = _normalize(correct), _normalize(user_said)
    tu = _tokens(nu)
    if len(tu) < _MIN_TOKENS:
        return 0
    if SequenceMatcher(None, nc, nu).ratio() >= _GATE_RATIO:
        return 10
    sc, su = set(_tokens(nc)), set(tu)
    if sc:
        jacc = len(sc & su) / len(sc | su)
        if jacc >= _GATE_JACCARD:
            return 10
    return None


def _openai_json(system: str, user: str, max_tokens: int = 80,
                 model: str = SCORING_MODEL) -> dict:
    api_key = get_secrets().openai_api_key
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY not set — cannot score.")
    r = httpx.post(
        "https://api.openai.com/v1/chat/completions",
        headers={"Authorization": f"Bearer {api_key}", "content-type": "application/json"},
        json={
            "model": model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": 0,
            "max_tokens": max_tokens,
            "response_format": {"type": "json_object"},
        },
        timeout=60,
    )
    r.raise_for_status()
    return json.loads(r.json()["choices"][0]["message"]["content"])


def _clamp(v, lo=0, hi=10) -> int:
    try:
        return max(lo, min(hi, int(round(float(v)))))
    except (TypeError, ValueError):
        return 0


def score_phrase(anchor: str, correct_phrase: str, user_said: str) -> dict:
    """Test B. Returns {score, correct_phrase, via}."""
    nu = _normalize(user_said)
    ck = ("phrase", correct_phrase, nu)
    if ck in _cache:
        return {**_cache[ck], "via": "cache"}

    gated = local_gate(correct_phrase, user_said)
    if gated is not None:
        out = {"score": gated, "correct_phrase": correct_phrase, "via": "gate"}
        _cache[ck] = {"score": gated, "correct_phrase": correct_phrase}
        return out

    user_payload = json.dumps(
        {"anchor": anchor, "correct_phrase": correct_phrase, "user_said": user_said},
        ensure_ascii=False,
    )
    try:
        data = _openai_json(_PHRASE_SYSTEM, user_payload, max_tokens=40)
        score = _clamp(data.get("score"))
        via = "llm"
    except Exception:
        # Graceful fallback: derive a coarse score from string similarity so a
        # transient LLM/network failure never hard-blocks the drill.
        ratio = SequenceMatcher(None, _normalize(correct_phrase), nu).ratio()
        score = _clamp(round(ratio * 10))
        via = "fallback"
    out = {"score": score, "correct_phrase": correct_phrase, "via": via}
    if via == "llm":
        _cache[ck] = {"score": score, "correct_phrase": correct_phrase}
    return out


def score_anchor(anchor: str, user_said: str) -> dict:
    """Test C (anchor recall): the learner hears a phrase and must name its single
    anchor keyword. The target is ONE word, so we score by string similarity (no
    LLM) — an exact/near match is full credit, partial overlap is partial. The
    phrase gate's 2-token minimum deliberately does NOT apply here: one word is
    the whole answer."""
    na = _normalize(anchor)
    nu = _normalize(user_said)
    if not na or not nu:
        return {"score": 0, "correct_anchor": anchor, "via": "gate"}
    # Credit the best-matching spoken token (so "uh, read" still matches 'read'),
    # and also the whole utterance in case the anchor itself is multi-word.
    said = _tokens(nu)
    best_tok = max((SequenceMatcher(None, na, t).ratio() for t in said), default=0.0)
    whole = SequenceMatcher(None, na, nu).ratio()
    ratio = max(best_tok, whole)
    score = 10 if ratio >= 0.85 else _clamp(round(ratio * 10))
    return {"score": score, "correct_anchor": anchor, "via": "gate"}


def score_sequence(anchors_in_order: list[str], story_ru: str, user_said: str) -> dict:
    """Test A. Returns {score, missed_anchors, order_ok, via}."""
    if len(_tokens(_normalize(user_said))) < _MIN_TOKENS:
        return {"score": 0, "missed_anchors": list(anchors_in_order),
                "order_ok": False, "via": "gate"}
    user_payload = json.dumps(
        {"anchors_in_order": anchors_in_order, "story_ru": story_ru, "user_said": user_said},
        ensure_ascii=False,
    )
    try:
        data = _openai_json(_SEQUENCE_SYSTEM, user_payload, max_tokens=160,
                            model=SEQUENCE_MODEL)
        missed = data.get("missed_anchors") or []
        if not isinstance(missed, list):
            missed = []
        return {"score": _clamp(data.get("score")),
                "missed_anchors": [str(m) for m in missed][:len(anchors_in_order)],
                "order_ok": bool(data.get("order_ok", False)), "via": "llm"}
    except Exception:
        # Fallback: which anchors literally surfaced in the retelling.
        nu = _normalize(user_said)
        missed = [a for a in anchors_in_order if _normalize(a) not in nu]
        present = len(anchors_in_order) - len(missed)
        score = _clamp(round(present / max(1, len(anchors_in_order)) * 10))
        return {"score": score, "missed_anchors": missed, "order_ok": True, "via": "fallback"}
