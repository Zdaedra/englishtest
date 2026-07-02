# TZ — AI Cost & Model Strategy (STT + LLM routing / "bridges")

> Research (4-lens consilium: STT · LLM-cascade · API-economics · implementation) + synthesis.
> Goal: cheapest-but-effective models, a cheap→strong cascade, and config-driven "bridges"
> so traffic can be routed to the right model/provider per task.

## 0. Bottom line
- **There is NO flat "app subscription"** for these APIs — billing is usage-based (per token / per minute). The real levers are: **pick a cheap-tier model · prompt caching (~90% off) · Batch API (50% off, offline only) · run STT on-device (free).**
- **Margins are already excellent.** Even today (unoptimized) AI cost is ≈ **$0.06–0.26 / active AI-user / month** against a **$12.99/mo** (≈$6.67/mo annual) price → **~98–99% gross margin**. AI cost is NOT a margin risk at this scale; the risk is a single abuser → keep per-day caps (already there).
- **No multi-provider router (OpenRouter/LiteLLM) yet** — it adds 5–7% overhead + a dependency for ~zero benefit. The app is ~100× below the ~$5k/mo spend where volume discounts matter. Stay 1–2 providers, wired direct.
- The current design is already smart: **free local gate → cheap model → (escalate)**. The work is to make models/providers **config-swappable** and add the missing levers.

## 1. Current stack (verified)
| Task | Today | Notes |
|---|---|---|
| STT (native iOS) | OpenAI `gpt-4o-mini-transcribe` ($0.003/min) | Web already uses free on-device Web Speech first |
| Phrase scoring (Test B, high-freq) | free local gate → `gpt-4.1-nano` (cached, in-process) | gate absorbs verbatim/empty |
| Sequence exam (Test A, once/batch) | `gpt-4.1-mini` | needs reasoning (nano fails on RU/EN) |
| AI Coach (paid) | `gpt-4.1-mini` | |
| Import parse / context gen | `gpt-4o-mini` / `claude-sonnet-4-6` | admin/offline |
| TTS | `tts-1` | |

## 2. Recommended strategy

### STT — biggest structural win = on-device on iOS
- **Phrase drill (English-only, ~90% of volume): on-device** `SFSpeechRecognizer` (free, private, offline, low-latency), biased with the **expected phrase as `contextualStrings`**. Plugin exists (`@capacitor-community/speech-recognition`) — no native code needed. iOS 26 `SpeechAnalyzer` is a later polish (no permission dialog, paid plugin/native shim).
- **Sequence exam (mixed RU+EN): keep cloud** `gpt-4o-mini-transcribe` (auto-detect) — on-device recognizers are **single-locale** and mangle code-switching.
- **Fallback:** cloud STT when on-device is unavailable/empty. Net STT cost ≈ −75–90%; bigger wins are latency + "audio never leaves the phone".
- Avoid `whisper-1` (1-min file minimum) and Google (15s rounding) for 2–5s clips.

### LLM — keep the cascade, modernise the models (env-flip after a quick A/B)
- Phrase scoring: **`gpt-4.1-nano` → `gpt-5-nano`** (≈2× cheaper input, better) — *A/B first (watch 40-tok truncation on a reasoning model).*
- Exam/coach: keep mini-class; **`gpt-4.1-mini` → `gpt-5-mini`** optional.
- Import/context: drop `gpt-4o-mini` → `gpt-5-nano`, and route through **Batch API (50%)** (offline).
- **Add an escalation tier** (ship OFF, env-gated): cheap model → re-run on the strong model only when the cheap score is **borderline [5–7]** or low-confidence. Tag `via` so the escalation rate is measurable.

### Other levers
- **Prompt caching** (OpenAI auto ≥1024-token stable prefix; Anthropic explicit `cache_control`): keep the system prompt the leading, byte-stable block. *Measure prompt size — short prompts may not cross the 1024 floor.*
- **Batch API** for import/context only (never the live drill).
- **Persistent scoring cache** (curriculum targets are finite → high hit rate). ⚠️ **Privacy:** key it on `(target, hash(normalized_spoken))` — store a hash, not the raw utterance — to stay consistent with the transcript-retention work. (Deferred for that reason; in-process cache stays for now.)
- **Fair-use:** keep per-day scored-answer caps; add a monthly STT-minute ceiling only if any cloud-STT path remains.

## 3. Cost model (per active AI-user / month, assumption-driven)
| | STT | LLM | Total | Margin on $12.99 |
|---|---|---|---|---|
| Today | ~$0.18–0.24 | ~$0.05 | **~$0.23–0.29** | ~98% |
| Optimized (on-device STT + gpt-5-nano + caching) | ~$0.00–0.04 | ~$0.04 | **~$0.04–0.08** | ~99.5% |

Numbers are assumption-driven (≈60 scored answers/day, ≈40–50 STT min/mo). The app already logs `via` (`gate|llm|cache|...`) on attempts — derive the **real** gate/cache/LLM split from production before flipping models.

## 4. The "bridges" — implementation (phased, minimal-diff)
1. **Config-driven models** ✅ (this turn): model names move to env-overridable Settings (`ENGLISH_MODEL_*`), defaults = current values → zero behaviour change; any model swaps with an env change + restart (`get_settings()` is lru-cached).
2. **Provider bridge** (`providers.py`): normalise JSON-mode across OpenAI / Gemini / Anthropic and STT across OpenAI / Deepgram; per-task provider env knob; keep the existing graceful-fallback envelope (the bridge raises, callers degrade). Needs the user's Gemini/Deepgram keys to actually use non-OpenAI.
3. **Observability**: log `{task, provider, model, via, tokens, cost_est, latency}` (enrich `via` + a `usage.py`) — *before* turning on the cascade, so savings are measured.
4. **Cascade** (ship OFF): borderline-band escalation, env-gated.
5. **On-device iOS STT**: Capacitor plugin + a 3-tier ladder in `Training.tsx` (web speech → native on-device → server STT); server path untouched; Test A stays server-side. *(Needs the device to test.)*
6. **Caching/Batch**: ensure cacheable prompt ordering; `--batch` flag on `gen_context`.

## 5. What needs the founder (consolidated)
1. **API keys** for any non-OpenAI provider you want to enable: **Gemini** (cheapest proprietary scoring) and/or **Deepgram** (cheap STT). Without these we stay OpenAI-only (fine).
2. **A/B sign-off** to flip the scoring default `gpt-4.1-nano → gpt-5-nano` (or Gemini Flash-Lite) once validated on real answers.
3. **Device online** to build/test the on-device iOS STT path.
4. Decide whether to add a **monthly STT-minute fair-use cap** (or rely on on-device).

Everything below #1 is buildable by me; #1–#3 are where you'd unblock the bigger savings.
