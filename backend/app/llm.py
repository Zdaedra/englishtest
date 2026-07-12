"""LLM provider abstraction: Meridian (Hetzner) / Anthropic-direct / OpenAI.

Used as a one-time importer fallback and for context generation. The canonical
source of truth is the stored JSON — the LLM never re-parses approved batches.
"""
import json
from typing import Optional

import httpx

from .config import get_secrets, get_settings

_PROMPT_VERSION = "parse-v1"

_PARSE_SYSTEM = (
    "Ты парсер учебных батчей Executive English. На вход — сырой текст. "
    "Верни СТРОГО JSON по схеме без markdown-обёртки:\n"
    '{"title": str, "theme": str, "zones": [{"title": str, "order_index": int, '
    '"intensity_label": str, "range_start": int|null, "range_end": int|null}], '
    '"phrases": [{"order_index": int, "anchor": str, "phrase_en": str, '
    '"gloss_ru": str, "intensity_score": float, "zone": str|null}], '
    '"mnemo": {"story_ru": str}}\n'
    "anchor = ключевое слово-якорь (обычно глагол). phrases в порядке нарастания. "
    "Если зон нет — пустой список. Только валидный JSON."
)


def _strip_json(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        text = text.split("```", 2)[1]
        if text.startswith("json"):
            text = text[4:]
    return text.strip()


def _anthropic_call(base_url: str, api_key: Optional[str], system: str, user: str,
                    temperature: Optional[float] = None, max_tokens: int = 4096) -> str:
    headers = {"anthropic-version": "2023-06-01", "content-type": "application/json"}
    if api_key:
        headers["x-api-key"] = api_key
    body = {
        "model": get_settings().model_import_anthropic,
        "max_tokens": max_tokens,
        "system": system,
        "messages": [{"role": "user", "content": user}],
    }
    if temperature is not None:
        body["temperature"] = temperature
    r = httpx.post(f"{base_url.rstrip('/')}/v1/messages", json=body, headers=headers, timeout=120)
    r.raise_for_status()
    data = r.json()
    return "".join(part.get("text", "") for part in data.get("content", []))


def _openai_call(api_key: str, system: str, user: str,
                 temperature: Optional[float] = None) -> str:
    headers = {"Authorization": f"Bearer {api_key}", "content-type": "application/json"}
    body = {
        "model": get_settings().model_import,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    }
    if temperature is not None:
        body["temperature"] = temperature
    r = httpx.post("https://api.openai.com/v1/chat/completions", json=body, headers=headers, timeout=120)
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"]


def _resolve_provider() -> str:
    s = get_settings()
    if s.llm_provider != "auto":
        return s.llm_provider
    # auto: prefer a COMMERCIAL API (covered by a signed DPA, no training on inputs)
    # for any real/user data. The Meridian dev proxy is a personal Anthropic Max
    # subscription (consumer terms, no DPA) and must NEVER be the production default —
    # so it is the LAST resort, only when no commercial key is configured (pure dev).
    sec = get_secrets()
    if sec.anthropic_api_key:
        return "anthropic"
    if sec.openai_api_key:
        return "openai"
    try:
        httpx.get(s.meridian_url, timeout=1.5)
        return "meridian"
    except Exception:
        pass
    raise RuntimeError("No LLM provider available (no API keys, meridian unreachable).")


def chat(system: str, user: str, temperature: Optional[float] = None) -> str:
    provider = _resolve_provider()
    s = get_settings()
    sec = get_secrets()
    if provider == "meridian":
        return _anthropic_call(s.meridian_url, None, system, user, temperature)
    if provider == "anthropic":
        return _anthropic_call(sec.anthropic_base_url, sec.anthropic_api_key, system, user, temperature)
    if provider == "openai":
        return _openai_call(sec.openai_api_key, system, user, temperature)
    raise RuntimeError(f"Unknown LLM provider: {provider}")


def parse_batch(raw_text: str) -> dict:
    """LLM fallback for messy input. Returns a BatchIn-compatible dict (no spans)."""
    out = chat(_PARSE_SYSTEM, raw_text)
    return json.loads(_strip_json(out))
