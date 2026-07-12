# TZ — Privacy & Legal Compliance (US / California + EU/UK + worldwide)

> **Status:** research + plan (consilium: substance-gated panel → debate). NOT yet built.
> **⚠️ Not legal advice.** This scopes the engineering/product build and prioritises a
> lawyer's time. A qualified privacy lawyer (US + EU/UK) must review the final policy,
> the voice/Art-9 call, and the DPIA before public launch. Items needing counsel are
> marked **[LAWYER]**.

Produced by a 4-lens research panel (US CCPA/CPRA, EU/UK GDPR, Apple App Store, privacy
engineering) + a 2-counsel debate (pragmatic vs risk-averse). The two counsel **converged**
on the launch-blockers and on where NOT to over-build.

---

## 0. The one-paragraph verdict

The app is closer to compliant than most (paid, **no ads/analytics/tracking**, account
deletion already shipped). Exposure is concentrated in a few concrete places. The two
**genuinely dangerous** items are: **(a)** voice **transcripts stored forever** with no
purge, and **(b)** a code path (`ENGLISH_LLM_PROVIDER=auto` → "Meridian") that can route
**customer content through a personal Anthropic Max subscription** (no DPA, consumer terms
may train on it). Everything else is disclosure + a consent screen + signing free vendor
DPAs. Ship on **one global GDPR-grade policy + a short US/California section** — do **not**
build a region-detection engine, double-consent, or pay for EU reps yet.

---

## 1. Data inventory (verified against the code)

| Data | Where | Sent to | Stored? |
|---|---|---|---|
| Email, hashed password, name, UI lang, plan, **Apple IAP tx id**, signup date | `User` | Resend (email verify), Apple (IAP) | Yes (DB, Germany) |
| Learning/SRS stats, batch progress, timestamps | `UserPhraseStat`, `BatchProgress`, `ReviewEvent` | — | Yes |
| **Raw audio** (spoken answers) | in-request only | OpenAI (STT) | **No — transient** ✅ |
| **Voice transcripts** | `PhraseAttempt.transcript`, `SequenceAttempt.transcript`, `TrainingEvent.transcript` | OpenAI (scoring, **every answer**), Anthropic (coaching paths) | **Yes — indefinitely (no purge)** ⚠️ |
| AI coaching text | `TrainingEvent.ai_feedback` | — | Yes |
| Profile photo | device `localStorage` only | — | Not server-side (today) |
| User-pasted import content (AI tier) | `llm.chat` (parse) | **`auto`→Meridian (personal Max) / OpenAI** | becomes a batch |

- **Hosting:** single server in **Germany** (Hetzner), SQLite. US users' data resting in
  the EU is fine (GDPR restricts transfers *out*, not *in*).
- **Subprocessors:** OpenAI (STT + scoring + coaching), Anthropic (coaching/import),
  Resend (email), Hetzner (hosting), Apple (IAP — *independent controller*, no DPA needed).
- **Account deletion** already wipes all per-user tables incl. all 3 transcript tables. ✅
- **No analytics/ads/tracking SDKs, no IDFA, no precise gelocation, no social login.** ✅

---

## 2. Findings by regime (condensed)

### US — CCPA/CPRA + multistate
- **Thresholds:** almost certainly **below** CCPA ($25M rev / 100k CA consumers) and the
  VCDPA-family (100k) at current scale; Texas TDPSA exempts SBA "small businesses". So
  **not legally in scope today** — but Apple + GDPR + growth mean build now. **[LAWYER]** re-check at each milestone.
- **"Sale"/"Sharing":** you **don't** sell (no consideration to you) or "share" (no
  cross-context ads). OpenAI/Anthropic/Resend are **service providers** → **no opt-out / no
  "Do Not Sell or Share" link / no GPC plumbing needed** — *provided DPAs are signed*.
- **Voice "biometric"?** Most likely **NO** as used (STT for content, no voiceprint, audio
  discarded). Keep it that way (architectural ban on voiceprinting). **[LAWYER]**.
- Must **state** "we do not sell or share", a Notice-at-Collection, sensitive-PI statement,
  retention periods, and the CCPA rights list.

### EU/UK — GDPR
- **Applies** (Art 3(2): offering services to EU/UK users; data in Germany).
- **Lawful basis:** account/lessons/voice-scoring = **Art 6(1)(b) contract**; notifications
  = consent; security logs = legitimate interest.
- **Art 9 (special category):** contentious — free-form transcripts can *incidentally*
  contain health/religion/etc. **Safer posture:** explicit first-use voice consent (which
  Apple forces anyway) + short retention + a lightweight DPIA. **[LAWYER]** owns the final call.
- **Transfers:** rely on each vendor's **SCCs / UK IDTA** (DPF as secondary, it's under
  CJEU appeal). Keep short TIA memos.
- **Processors (Art 28):** accept DPAs for OpenAI, Anthropic (commercial), Resend, Hetzner.
  Keep a one-page **RoPA** (Art 30).
- **Art 27 EU/UK reps:** **defer** until material EU traction (both counsel agree it's not a
  launch blocker at this volume). **[LAWYER]** confirm + revisit on scale. **DPO:** not needed at this scale.

### Apple App Store (these are enforced at review — hard blockers)
- **§5.1.2(i):** must **disclose + get explicit in-app consent before sending voice/transcripts
  to third-party AI**. Currently **absent** → rejection. **#1 fix.**
- **§3.1.2:** paywall must show **Privacy + Terms/EULA links + auto-renew disclosure**.
  Currently **absent** → rejection. (Use Apple's Standard EULA to avoid writing one.)
- **§5.1.1(i):** privacy policy linked **in App Store Connect AND in-app**, enumerating all
  subprocessors/retention/deletion. **App Privacy "nutrition label"** must match (all data
  **Linked to You**; **Tracking = NONE**; **do NOT add an ATT prompt**).
- **§5.1.1(v) account deletion:** ✅ already compliant (real in-app hard delete).
- **Mic purpose string:** strengthen `NSMicrophoneUsageDescription` to say audio is
  transcribed by an AI service.

---

## 3. Debate resolution — decisions (what we WILL and WON'T do)

| Question | Decision |
|---|---|
| Region handling | **ONE global GDPR-grade policy + a short "US/California residents" section.** No geo-detection engine, no per-region policy files for v1. (Over-compliance is the safe direction.) |
| Voice consent | **One contextual first-voice-use consent gate** (names OpenAI/Anthropic, transcription, storage). Doubles as Apple §5.1.2(i) consent **and** the GDPR Art-9 cover. |
| Signup consent | **Notice, not consent** — visible Privacy/Terms links under the button. **No blocking checkbox** (core processing is contract-based; bundled consent is weaker + kills activation). |
| Special category / DPIA | Treat persisted transcripts as **highest-sensitivity**; write a **lightweight 2-page DPIA** (cheap insurance). Hard architectural ban: **no voiceprinting, no raw-audio retention.** **[LAWYER]** final Art-9 call. |
| "Do Not Sell/Share" link, GPC | **Not built** — you don't sell/share. State it in the policy instead. |
| EU/UK Art 27 reps | **Deferred** (trigger: sustained EU traction or a B2B ask). |
| Data export (DSAR) | **Fast-follow** (cheap — inverse of the existing delete). Manual email acceptable at current scale. |
| Retention | **Build a transcript purge** (null transcript free-text after N days, keep numeric scores). **Non-negotiable.** |

---

## 4. 🔴 Fix-now (launch-blockers / live risk) — small, high-value

1. **Pin the LLM provider away from Meridian in prod.** Today `ENGLISH_LLM_PROVIDER=auto`
   → prefers the personal Anthropic-Max proxy; AI-tier **import parsing of user-pasted
   content** can flow through a consumer subscription with no DPA. **Set
   `ENGLISH_LLM_PROVIDER=openai` (or commercial `anthropic`) in `/root/english/.env` +
   restart.** Also add a code guard so any function handling a `transcript`/user content
   **cannot** fall back to Meridian (fail loud). *(One-line config + a small guard.)*
2. **First-voice-use consent screen** (Apple §5.1.2(i) + GDPR). Plain language; names
   OpenAI/Anthropic; shown once before the first recording; revocable.
3. **Paywall legal links + auto-renew text** (`Subscribe.tsx`) + Standard Apple EULA in
   App Store Connect + Privacy URL in metadata.
4. **Rewrite `/privacy` to match reality**: name OpenAI, **Anthropic**, Resend, Hetzner,
   Apple; voice→STT (audio not stored) + transcript storage; US transfers + SCCs;
   retention; "we do not sell or share"; rights + how to exercise. Link it in-app + ASC.
   Fill the **App Privacy nutrition label** to match (Tracking = none).
5. **Transcript retention purge** — scheduled job nulling transcript free-text older than N
   days (keep scores). Biggest substantive data-minimisation win.
6. **Sign/enable vendor DPAs** (you must do this — I can't): **OpenAI DPA + request Zero-
   Data-Retention**, **Anthropic commercial DPA**, **Resend DPA**, **Hetzner AV/DPA**.
   These are what make "service provider / no opt-out needed" actually true.

---

## 5. Phased build plan (each phase independently shippable)

- **Phase 0 — submission-ready (smallest, do first):** items 1–4 above + add `/terms`
  (`static/terms.html`) + strengthen mic purpose string. *No schema change.* Clears the
  Apple blockers and makes disclosures truthful.
- **Phase 1 — consent + US section:** first-voice-use consent gate; `ConsentRecord` table
  (append-only audit: user, kind, policy_version, jurisdiction, timestamp); signup
  notice-links; `User.jurisdiction` column (self-declared, default `rest`) **only** to tailor
  the policy anchor — not a detection engine; US/California policy section; `policy.py`
  version constants + `GET /api/policy/versions`.
- **Phase 2 — rights + retention:** shared `_user_owned_rows()` helper powering **both**
  delete and a new `GET /api/account/export` (JSON; access + portability); `DeletionLog`
  (non-PII audit); `retention.py` purge via a startup interval task +
  `ENGLISH_TRANSCRIPT_RETENTION_DAYS`.
- **Phase 3 — hardening:** `subprocessors.html` page; OpenAI ZDR enabled + documented;
  2-page DPIA; RoPA; TIA memos; breach runbook. **[LAWYER]** review of final policy.

---

## 6. What the founder must do (not codeable by me)
1. Sign/enable **DPAs**: OpenAI (+ ZDR), Anthropic commercial, Resend, Hetzner.
2. Set the **Standard Apple EULA** + Privacy URL in App Store Connect; fill the privacy
   nutrition label.
3. Decide the **transcript retention window** (e.g. 90–365 days). **[LAWYER]**.
4. Engage **counsel** for: final policy text, the Art-9/voice classification, the DPIA,
   whether Art 27 reps are needed, and confirming scoring isn't Art-22 automated decision-making.
5. Decide a support/privacy **contact email** for rights requests (about page uses
   `support@executive-english.net` — confirm it's monitored).

## 7. [LAWYER] checklist (the high-leverage hour)
Final Art-9 classification of voice/transcripts · sign-off on the DPIA · whether EU+UK Art 27
reps are required now · confirm scoring is not Art-22 ADM · bless the privacy policy + the
US/California section + a TIA template.
