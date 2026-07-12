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

from .config import get_secrets, get_settings

# Models are config-driven (ENGLISH_MODEL_SCORE / _SEQUENCE / _COACH in config.py).
# Defaults there: phrase drill = gpt-4.1-nano (cheap, high-frequency, has the local
# gate); sequence exam + coach = gpt-4.1-mini (the hard gate, needs reasoning).

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

# Practice "Answer Check" — the SAME score rubric as _PHRASE_SYSTEM (so the SRS
# signal doesn't drift), PLUS an honest coaching layer in one call: did the said
# phrase fit the TASK at all, how natural it sounded, and one plain RU note (incl.
# "не расслышал" when the transcript is STT garbage). SRS still keys off `score`.
_ANSWER_SYSTEM = (
    "Ты — строгий, но справедливый экзаменатор устного recall английских деловых "
    "фраз и одновременно коуч по executive-присутствию. Учащемуся дана ЗАДАЧА "
    "(task_ru) в СИТУАЦИИ (situation_ru); он пытается вспомнить и произнести уместную "
    "фразу. Тебе дают эталон (correct_phrase) и распознанную речь (user_said) — это "
    "вывод STT, в нём возможны ошибки распознавания.\n"
    "\n"
    "score (0..10) — СМЫСЛОВОЕ совпадение user_said с correct_phrase; смысл важнее "
    "дословности. Сжатая своя формулировка, сохраняющая суть и ключевой глагол/действие, "
    "— это 9-10, даже если опущены вводные/усилители (right now, actually, just). Снижай "
    "ТОЛЬКО за потерю смыслонесущего слова, не за краткость.\n"
    "  10 = семантически эквивалентно (валидный перефраз/синоним/сжатая форма).\n"
    "  8-9 = суть и ключевое действие верны, опущены лишь второстепенные слова.\n"
    "  6-7 = основной смысл есть, но пропущено ключевое слово ИЛИ ошибка времени.\n"
    "  4-5 = частично: тема узнаётся, фраза искажена.\n"
    "  2-3 = далеко, лишь отдельные общие слова.\n"
    "  0-1 = пусто / не по теме / мусор распознавания.\n"
    "\n"
    "fits_task (bool) — уместна ли САМА сказанная фраза для ЭТОЙ задачи по смыслу и "
    "интенции, ДАЖЕ если это не дословно эталон: валидный ответ в том же диапазоне "
    "(верный коммуникативный ход) = true; мимо задачи = false.\n"
    "natural (0..10) — насколько естественно и идиоматично звучит user_said для "
    "уверенного носителя-руководителя (калька/грамматически ломано = низко).\n"
    "note — ОДНА короткая строка по-русски, по делу: попал ли в задачу и что усилить. "
    "Если user_said похоже на МУСОР РАСПОЗНАВАНИЯ (обрывки, смесь языков, бессмыслица) — "
    "напиши ровно «Не расслышал — повтори чётче», и тогда fits_task=false, natural=0.\n"
    "\n"
    "Примеры (для формата):\n"
    "  correct='Let me push back on that.' said='let me push back a little' -> "
    "{\"score\":9,\"fits_task\":true,\"natural\":8,\"note\":\"Возражение уместно и звучит уверенно.\"}\n"
    "  correct=\"Let's take it down a notch.\" said='летний пушбек литл' -> "
    "{\"score\":0,\"fits_task\":false,\"natural\":0,\"note\":\"Не расслышал — повтори чётче.\"}\n"
    "Верни СТРОГО JSON без markdown: {\"score\": <int 0..10>, \"fits_task\": <bool>, "
    "\"natural\": <int 0..10>, \"note\": \"<str>\"}."
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

_COACH_SYSTEM = (
    "Ты — персональный коуч по executive-английскому (тон взрослый, не школьный). "
    "Контекст: собеседник сказал реплику (stimulus); учащийся должен был ответить "
    "уверенной фразой; эталон — target_phrase; распознанная речь — user_said; балл 0..10. "
    "Дай короткий практичный разбор про ПРИСУТСТВИЕ и ТОН (не про грамматику). "
    "Верни СТРОГО JSON без markdown: {"
    "\"feedback\": \"<1-2 предложения по-русски: как прозвучал ответ и что усилить>\", "
    "\"better\": \"<одна сильная английская фраза — как сказал бы уверенный руководитель здесь>\", "
    "\"tone\": \"<2-4 слова по-русски про тон, напр. 'спокойно и прямо'>\"}."
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
                 model: str | None = None) -> dict:
    if model is None:
        model = get_settings().model_score
    api_key = get_secrets().openai_api_key
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY not set — cannot score.")
    body = {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "response_format": {"type": "json_object"},
    }
    # GPT-5 / o-series are reasoning models: they reject `max_tokens` + a custom
    # `temperature`, and spend hidden reasoning tokens, so they need
    # `max_completion_tokens` with a budget large enough to leave room for the JSON
    # after the reasoning. Classic chat models keep the cheap, deterministic shape.
    # This is what makes ENGLISH_MODEL_* env-swaps work across model families.
    if model.startswith(("gpt-5", "o1", "o3", "o4")):
        body["max_completion_tokens"] = max(max_tokens, 2000)
    else:
        body["temperature"] = 0
        body["max_tokens"] = max_tokens
    r = httpx.post(
        "https://api.openai.com/v1/chat/completions",
        headers={"Authorization": f"Bearer {api_key}", "content-type": "application/json"},
        json=body,
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
    s = get_settings()
    try:
        data = _openai_json(_PHRASE_SYSTEM, user_payload, max_tokens=40, model=s.model_score)
        score = _clamp(data.get("score"))
        via = "llm"
        # Cascade: the cheap model is trusted at the extremes (clear pass/fail); only
        # its ambiguous-band verdict gets re-scored on the stronger model, which is the
        # only place the two disagree. Falls back to the cheap score if escalation errors.
        if (s.cascade_score_enabled and s.model_sequence != s.model_score
                and s.cascade_score_low <= score <= s.cascade_score_high):
            try:
                data2 = _openai_json(_PHRASE_SYSTEM, user_payload, max_tokens=40,
                                     model=s.model_sequence)
                score = _clamp(data2.get("score"))
                via = "llm:escalated"
            except Exception:
                pass  # keep the cheap-model score
    except Exception:
        # Graceful fallback: derive a coarse score from string similarity so a
        # transient LLM/network failure never hard-blocks the drill.
        ratio = SequenceMatcher(None, _normalize(correct_phrase), nu).ratio()
        score = _clamp(round(ratio * 10))
        via = "fallback"
    out = {"score": score, "correct_phrase": correct_phrase, "via": via}
    if via in ("llm", "llm:escalated"):
        _cache[ck] = {"score": score, "correct_phrase": correct_phrase}
    return out


def score_answer(anchor: str, correct_phrase: str, user_said: str,
                 task_ru: str = "", situation_ru: str = "") -> dict:
    """Practice Answer Check. One LLM call returns the SRS score (meaning-match to the
    card's phrase — SAME rubric as score_phrase, so the SRS signal doesn't drift) PLUS
    honest coaching: fits_task, natural, and a short RU note (incl. 'не расслышал' on
    STT garbage). Returns {score, fits_task, natural, note, correct_phrase, via}."""
    nu = _normalize(user_said)
    ck = ("answer", correct_phrase, nu)
    if ck in _cache:
        return {**_cache[ck], "via": "cache"}

    # Local gate: obvious verbatim hit or too-few-tokens — no LLM, but still return
    # the honest-feedback fields so the client shape is stable.
    gated = local_gate(correct_phrase, user_said)
    if gated is not None:
        if gated >= 10:
            out = {"score": 10, "fits_task": True, "natural": 9, "note": "",
                   "correct_phrase": correct_phrase}
        else:  # silence / not caught
            out = {"score": 0, "fits_task": False, "natural": 0,
                   "note": "Не расслышал — повтори чётче.", "correct_phrase": correct_phrase}
        _cache[ck] = out
        return {**out, "via": "gate"}

    user_payload = json.dumps(
        {"anchor": anchor, "correct_phrase": correct_phrase, "user_said": user_said,
         "task_ru": task_ru, "situation_ru": situation_ru},
        ensure_ascii=False,
    )
    s = get_settings()
    try:
        data = _openai_json(_ANSWER_SYSTEM, user_payload, max_tokens=160, model=s.model_score)
        score = _clamp(data.get("score"))
        via = "llm"
        # Same cascade as score_phrase: re-score the ambiguous band on the stronger
        # model (its full JSON wins). Falls back to the cheap verdict on error.
        if (s.cascade_score_enabled and s.model_sequence != s.model_score
                and s.cascade_score_low <= score <= s.cascade_score_high):
            try:
                data = _openai_json(_ANSWER_SYSTEM, user_payload, max_tokens=160,
                                    model=s.model_sequence)
                score = _clamp(data.get("score"))
                via = "llm:escalated"
            except Exception:
                pass
        out = {
            "score": score,
            "fits_task": bool(data.get("fits_task", score >= 6)),
            "natural": _clamp(data.get("natural")),
            "note": str(data.get("note", "") or "")[:200],
            "correct_phrase": correct_phrase,
        }
    except Exception:
        # Graceful fallback: coarse string-similarity score, no coaching claims.
        ratio = SequenceMatcher(None, _normalize(correct_phrase), nu).ratio()
        out = {"score": _clamp(round(ratio * 10)), "fits_task": False, "natural": 0,
               "note": "", "correct_phrase": correct_phrase}
        via = "fallback"
    if via in ("llm", "llm:escalated"):
        _cache[ck] = dict(out)
    return {**out, "via": via}


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


def coach_feedback(stimulus: str, target_phrase: str, user_said: str, score: int) -> dict:
    """AI Coach (paid): a short executive-coaching breakdown of the answer —
    {feedback, better, tone, via}. Falls back to a score-band note if the LLM is
    unavailable, so the feature degrades gracefully."""
    payload = json.dumps(
        {"stimulus": stimulus, "target_phrase": target_phrase,
         "user_said": user_said, "score": score}, ensure_ascii=False)
    try:
        data = _openai_json(_COACH_SYSTEM, payload, max_tokens=240,
                            model=get_settings().model_coach)
        return {
            "feedback": str(data.get("feedback", "")).strip(),
            "better": str(data.get("better", "")).strip() or target_phrase,
            "tone": str(data.get("tone", "")).strip(),
            "via": "llm",
        }
    except Exception:
        if score >= 8:
            note = "Сильно — звучит уверенно и по делу."
        elif score >= 5:
            note = "Узнаваемо, но смазано — добавь чёткости и убери лишнее."
        else:
            note = "Пока далеко от цели — вернись к эталону и скажи короче."
        return {"feedback": note, "better": target_phrase, "tone": "спокойно и прямо", "via": "fallback"}


_ANALYZE_SYSTEM = """You are an executive English coach for advanced non-native
professionals. You get notes or a rough transcript of a real work call/meeting the
user took part in. Find up to 5 places where the phrasing is correct but below
native executive register, and give the native-league upgrade. Rules:
- Only pick REAL fragments from the text (quote them as `original`).
- `native` is what a sharp native executive would say in that moment — idiomatic,
  concise, register-appropriate. A usable line, not a translation exercise.
- `note` is ONE short sentence (Russian) on why the upgrade lands better.
- Skip greetings/filler; prefer moments of stakes: pushback, deadlines, asks, repair.
- If the text has fewer than 5 upgradable moments, return fewer. Never invent.
Return JSON: {"upgrades":[{"original":"...","native":"...","note":"..."}]}"""


def analyze_call(text: str) -> dict:
    """Call Analyzer (AI plan): mine a real-meeting transcript/notes for
    native-league phrasing upgrades. Returns {upgrades: [{original, native, note}], via}."""
    try:
        data = _openai_json(_ANALYZE_SYSTEM, text, max_tokens=700,
                            model=get_settings().model_coach)
        ups = []
        for u in (data.get("upgrades") or [])[:5]:
            native = str(u.get("native", "")).strip()
            if not native:
                continue
            ups.append({"original": str(u.get("original", "")).strip(),
                        "native": native,
                        "note": str(u.get("note", "")).strip()})
        return {"upgrades": ups, "via": "llm"}
    except Exception:
        return {"upgrades": [], "via": "fallback"}


_BATTLE_SYSTEM = """Ты — суфлёр Executive English. Пользователь ПРЯМО СЕЙЧАС в живом
разговоре и коротко описал момент: с кем говорит и что происходит. Дан нумерованный
список английских фраз, которые он реально тренировал.

Ходы (фиксированные ключи — верни ТОЛЬКО их):
__MOVES__

1) intents: до 5 ходов, уместных в этот момент, лучший — первым.
2) picks: до 3 фраз под ПЕРВЫЙ ход, лучшая — первой. Суди по конверсационному ходу,
а не по совпадению слов. Ничего по-настоящему не подходит — верни пустой picks, не
притягивай за уши.

Верни СТРОГО JSON без markdown:
{"intents":["<ключ>",…],"picks":[{"n":<номер>}]}"""

_BATTLE_FORCED = """

Пользователь УЖЕ выбрал ход: {key} ({label}). Верни intents=["{key}"] и подбери
picks именно под этот ход."""


def battle_pick(situation: str, items: list[dict], intent: str | None = None) -> dict:
    """Battle/Live (AI plan): a live-conversation moment → ranked conversational
    MOVES (intents, the relevance axis) + the best lines for the top move.
    `items` = [{n, anchor, phrase_en, gloss_ru}] (n is the 1-based number the
    model answers with); `intent` forces a user-chosen move (one-tap override).
    One fast call, small output — this runs mid-conversation. Returns
    {picks: [{n, note}], intents: [key,…], via}; via="fallback" lets the client
    degrade to its local keyword search. `note` is tolerated for older stubs but
    no longer requested — the card shows just the line + gloss."""
    from .intents import INTENTS
    moves = "\n".join(f"- {k} = {gloss}" for k, gloss in INTENTS.items())
    system = _BATTLE_SYSTEM.replace("__MOVES__", moves)
    if intent and intent in INTENTS:
        system += _BATTLE_FORCED.format(key=intent, label=INTENTS[intent])
    listing = "\n".join(
        f"{i['n']}. {i['phrase_en']} — {i.get('gloss_ru') or i.get('anchor', '')}"
        for i in items)
    payload = f"Момент: {situation}\n\nФразы:\n{listing}"
    try:
        data = _openai_json(system, payload, max_tokens=120,
                            model=get_settings().model_coach)
        picks = []
        for p in (data.get("picks") or [])[:3]:
            n = p.get("n")
            if isinstance(n, bool) or not isinstance(n, int):
                continue
            picks.append({"n": n, "note": str(p.get("note", "")).strip()})
        if intent and intent in INTENTS:
            ranked = [intent]
        else:
            ranked = [k for k in (data.get("intents") or [])
                      if isinstance(k, str) and k in INTENTS][:5]
        return {"picks": picks, "intents": ranked, "via": "llm"}
    except Exception:
        return {"picks": [], "intents": [], "via": "fallback"}


_SCENARIO_SYSTEM = """Ты — методист приложения Executive English (деловой/светский
английский для носителей русского). Даны 3 целевые английские фразы с их смыслом.
Напиши СВЯЗНУЮ мини-сцену на русском — одна локация, один собеседник, деловой или
светский контекст с реальными ставками — которая разворачивается в 3 такта, по
одному на каждую фразу В ЗАДАННОМ ПОРЯДКЕ. Для каждого такта: situation_ru (1–2
живых предложения, продолжающих ОДНУ историю; на «ты») и task_ru (одно
повелительное предложение — что ты хочешь сделать репликой). Правила: сцена
должна естественно подводить к каждой целевой фразе; НЕ переводи фразы и НЕ
используй их слова; не раскрывай ответ. Верни СТРОГО JSON
{"title_ru": str, "beats": [{"situation_ru": str, "task_ru": str}, ×3]} без markdown."""


def weave_scenario(items: list[dict]) -> dict:
    """Arena: weave 3 learned phrases into ONE fresh coherent scene (the Langua
    pattern — reviews return "in battle", not on flashcards). `items` =
    [{anchor, phrase_en, gloss_ru}]. Returns {title_ru, beats, via}; beats align
    with `items` by index. Falls back to via="fallback" so the router can serve
    each phrase's own authored situation instead."""
    payload = json.dumps(
        [{"anchor": i.get("anchor", ""), "phrase_en": i.get("phrase_en", ""),
          "meaning_ru": i.get("gloss_ru", "")} for i in items], ensure_ascii=False)
    try:
        data = _openai_json(_SCENARIO_SYSTEM, payload, max_tokens=500,
                            model=get_settings().model_coach)
        beats = [{"situation_ru": str(b.get("situation_ru", "")).strip(),
                  "task_ru": str(b.get("task_ru", "")).strip()}
                 for b in (data.get("beats") or [])]
        if len(beats) != len(items) or not all(b["situation_ru"] for b in beats):
            raise ValueError("beat shape mismatch")
        return {"title_ru": str(data.get("title_ru", "")).strip(), "beats": beats,
                "via": "llm"}
    except Exception:
        return {"title_ru": "", "beats": [], "via": "fallback"}


_LEAGUE_SYSTEM = """You are the examiner of the "English League" placement test in
Executive English (RU-native professionals, B1+). For each work situation the user
answered in their OWN English words (typed, or a voice transcript — ignore
punctuation/casing artifacts of speech recognition).

Score every answer 0-10 as the sum of four explicit criteria:
- IDIOM (0-3): sounds like a living native executive, not a textbook. 3 = natural
  native-league phrasing; 2 = fluent but slightly bookish; 1 = correct learner
  English; 0 = broken or not an answer.
- REGISTER (0-3): tone fits the situation — direct without rudeness, no
  bureaucratese, no over-apologising, no servility.
- ECONOMY (0-2): compact and weighted; no filler chains, hedging or rambling.
- MOVE (0-2): the line performs the RIGHT conversational move for that moment
  (pushes back, lands a decision, protects the relationship — what the situation
  actually needs), not just a grammatical sentence nearby.
Hard rules: grammar mistakes that obscure meaning cap IDIOM at 1. An empty,
non-English or off-situation answer scores 0 total. Judge the move, not opinions.

For every answer also return:
- "better": ONE short native-league line a sharp executive would say there. If the
  user's answer already IS native-league (9-10), return their line lightly polished.
- "note_ru": ONE short Russian sentence — what exactly to upgrade (for 9-10: what
  made the line strong).
Return STRICT JSON: {"results":[{"id":"...","score":N,"better":"...","note_ru":"..."}]}"""


def league_score(answers: list[dict]) -> dict:
    """League placement, production answers: the user speaks/types their own line
    for each situation; one LLM call grades ALL answers against the explicit
    4-criteria rubric above. `answers` = [{id, situation, text}]. Returns
    {results: [{id, score, better, note_ru}], via} aligned by id; via="fallback"
    when the LLM is unavailable (the client then offers the legacy choice quiz)."""
    payload = json.dumps(
        [{"id": a.get("id", ""), "situation": a.get("situation", ""),
          "answer": a.get("text", "")} for a in answers], ensure_ascii=False)
    try:
        data = _openai_json(_LEAGUE_SYSTEM, payload, max_tokens=1000,
                            model=get_settings().model_coach)
        by_id = {str(r.get("id", "")): r for r in (data.get("results") or [])}
        results = []
        for a in answers:
            r = by_id.get(str(a.get("id", ""))) or {}
            results.append({
                "id": a.get("id", ""),
                "score": _clamp(r.get("score", 0)),
                "better": str(r.get("better", "")).strip(),
                "note_ru": str(r.get("note_ru", "")).strip(),
            })
        return {"results": results, "via": "llm"}
    except Exception:
        return {"results": [], "via": "fallback"}


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
                            model=get_settings().model_sequence)
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
