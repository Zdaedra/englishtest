<!-- Pedagogy audit — research/theory phase, NO code changes implied.
Produced by a 5-lens expert consilium (cognitive-science / SLA / behavioral-product /
assessment / competitive) → adversarial feasibility pass → synthesis, grounded on a
code-audit of the actual learning system. Every recommendation is tagged by lever:
A) content-only (no code) · B) training-flow (needs code) · C) product. -->

# Executive English — Final Pedagogy Audit

**For:** Founder
**Scope:** Learning design only (positioning, content model, learner journey, scoring, memory/scheduling). Theory phase — no code changes implied; every recommendation is tagged by lever.
**Date:** 2026-06-18

---

## 1. Executive summary

Executive English is built on the right spine: it is a **retrieval-practice machine for formulaic chunks**, and almost everything a learner does is *generative production under a meaning-first grader* — the single strongest memory lever known, paired with the lexical-chunk unit that actually produces fluent speech. The mnemonic-story encoding (one Russian narrative chaining all 9 anchors, karaoke-lit) is a genuinely differentiated primitive no competitor has, and the register/intensity ladder is the one axis that matters for *presence* rather than vocabulary. Three things hold it back, and they compound. **First, there is no real spaced repetition** — the "SRS" is a label machine that is never even written, has no `next_review`/interval/decay, and treats a phrase mastered yesterday identically to one mastered six weeks ago; the product can manufacture the *aha* of learning but cannot deliver the *retention* it is selling. **Second, the retrieval cue trains translation, not situational selection** — the learner practices "see anchor word → recite string," which is exactly the decontextualized route that yields high in-app scores and zero transfer to a real negotiation; the dormant `CheckPhrase` table that would fix this is wired and empty. **Third, the entire mastery/memory state is invisible** — no due-count, no competence map, no reminder loop — so even the strong machinery that exists only fires for a learner who spontaneously returns. The good news: the highest-ROI fix (situational cues) is **pure content**, ships today, and needs no code.

---

## 2. What to keep

These are real strengths. Do not refactor them away in the name of any recommendation below.

- **Production-first, meaning-over-verbatim scoring.** Every gate is *spoken* (L1 retell, L2 cued recall, L3 oral exam, swipe, Practice), and the grader rewards valid paraphrase/compression (9–10) rather than verbatim parroting. This is the **testing effect** (Roediger & Karpicke) executed correctly *and* **Swain's Output Hypothesis** — the learner is forced from semantic into syntactic processing, which app-based learning almost never does (most apps are recognition/tapping). This is the load-bearing decision; protect it.

- **The lexical-chunk unit.** The thing learned is the whole prefabricated phrase ("Help me understand the thinking there."), not words or grammar rules. This is **Lewis/Nattinger's Lexical Approach** — multi-word units are the engine of native-like fluency. It is also why the app can teach *presence* at all: presence lives in formulaic moves, not declension tables.

- **Mnemonic-story encoding (keyword mnemonic + narrative chaining + dual coding).** The ~70-word Russian narrative with all 9 anchors woven in order, narrated as continuous audio, is **Atkinson's keyword method fused with dual coding (Paivio)** — strong episodic hooks for otherwise arbitrary chunks. You just rewrote all 76 stories as scene-metaphors (commit `59c1987`); the *distinctiveness* of an unrelated peg is what makes them stick. Keep it.

- **Register/intensity as a first-class axis.** Zones escalate tone (Curious → Cautious → Direct; Warm → Backbone → Weight) and carry `intensity_score`. Pragmatic gradation is the **single most-neglected dimension** in L2 instruction and the actual definition of executive presence. It is structurally present in every batch — most competitors teach phrases flat.

- **L3's bidirectional, gated exam.** Three orthogonal retrieval routes (full retell, paused cued production, **reverse EN→RU**), each gated at 80% over 2 rounds. Reverse recall is a genuine **desirable difficulty (Bjork)** that forces a second route through the same trace — robust, flexibly-accessible memory requires exactly this, and the gate gives it teeth.

- **The measurement instinct is sound.** Per-phrase EWMA (`avg_score`, α=0.3), the swipe self-grade kept on a *separate* channel (`self_ewma`) so subjective grades never contaminate the objective recall estimate, attempt-aware confidence (`_conf` shrinks a high score earned on one attempt), and a cost-disciplined grader (local string gate → nano/mini, process-cached, graceful string fallback, daily caps that degrade to self-graded rather than hard-blocking). This is the right *foundation* for a scheduler — it's just not driving one yet.

- **Adult-respectful structure.** WIP-limited sprints (3–7 active batches, server-enforced), goal-based path shaping that reorders to your domains, ungated low-stakes L1/L2 before the one real exam, and "closed batches never re-lock." This is **SDT autonomy + competence** done for professionals who resent a kid's tree.

---

## 3. The core gaps, ranked

### P1 — No true spaced repetition; the "SRS" is a dead label machine

**What's wrong.** `srs_status` (`new|shaky|familiar|automatic`) is declared in `models.py` and written **only** by the legacy `/reviews` endpoint (`batches.py:372`) — grep finds *zero* assignments in any active path, so every phrase is permanently `new`. There is no `next_review_at`, no interval, no ease, no forgetting-curve decay. "Due" is a crude batch-level heuristic (avg < 7 OR untouched 14 days); within a session the only spacing primitive is a flat **90-second** anti-repeat cooldown (`_COOLDOWN`).

**Why it matters pedagogically.** The spacing effect is the most replicated finding in the science of memory and the *entire premise* of an SRS. `avg_score` has no decay, so the scheduler cannot tell a six-week-old phrase from a yesterday phrase — it cannot do the one thing spacing promises: surface each item *just before* it would be forgotten. For a paid retention product aimed at execs who train in metro bursts, this is the central scientific deficiency.

**Evidence.** `models.py` `UserPhraseStat` has no `next_review/interval/ease`; `batches.py` `_SRS_NEXT` is a pure (state, score)→state map; `training.py` `_COOLDOWN = 90s`; deck `weight()` reads only `avg_score/last_failed_at/last_seen_at`.

### P1 — The retrieval cue trains translation, not situational selection

**What's wrong.** L2 cues with the bare **English anchor word** (`Lesson2.tsx: current.anchor`); Training falls back to `gloss_ru`/anchor because `CheckPhrase` is empty (`training.py:343`). The learner practices "see keyword → retrieve memorized string."

**Why it matters pedagogically.** This is precisely the **decontextualized, translation-mediated route Krashen/Nation warn produces inert knowledge** — phrases that score 10/10 in-app but won't deploy when a real CFO pushes back. Executive presence is a *pragmatic selection* skill (the right move under social pressure), and the cue mechanism trains the opposite of it. The app's most distinctive promise is undermined by its most frequent interaction.

**Evidence.** `Lesson2.tsx` stimulus = `current.anchor`; `training.py:325–343` reads `CheckPhrase` first but it's unfed; `ContextExample` (`scenario_type/register_tone/speaker_role/listener_role`) exists and has zero references anywhere.

### P1 — Mastery and "due" state are completely invisible to the learner

**What's wrong.** `srs_status`, `avg_score`, attempts, and the "due" flag never reach the UI. The home screen shows three raw numbers (total / in-progress / streak) and a "Current Focus" hero that points only *forward*. There is no due-count, no competence map, **no reminder of any kind** — zero notification code in the repo despite Capacitor already shipping.

**Why it matters pedagogically.** Spacing is worthless if the learner never returns at the scheduled moment — engineering that return is *the reason schedulers exist*. And **competence visibility is one of the two strongest retention levers (SDT)**, currently dark: the learner has no felt sense of getting better and no rooted reason to come back tomorrow. The strong retrieval machinery has no entry point and no timing.

**Evidence.** `Library.tsx:259–316` (forward-only metrics + hero); `UserPhraseStat.srs_status/avg_score` never rendered; repo-wide grep finds no `LocalNotifications`/push/cron.

### P2 — `ContextExample` is dormant; no pragmatics layer reaches the learner

The fields that hold *exactly* what SLA says matters most for adult professional speech — register, speaker/listener role, scenario — are built and switched off. Pragmatic failure (right words, wrong register) is the **#1 way fluent non-natives sabotage presence**, especially in flirt/composure where a phrase tips from confident to aggressive. The framework exists; the learner never sees "this lands warm to a peer, careful to your boss."

### P2 — Latency is captured everywhere and used nowhere

`latency_ms`/`response_time_ms` is written in 7 places (`training.py` 102/127/162/388/405/412, `practice.py:138`) and read by nothing. **Time-to-respond is the canonical proxy for automaticity** (ACT-R) — the exact gap between "I can translate it" and "it comes out under pressure" that presence requires, and the data needed to legitimately *write* the dead `srs_status` field. The richest free signal the app already pays to store is inert.

### P2 — The calibration gap is invisible

`self_ewma` (swipe "I know this") and `avg_score` (actually produced it) sit in the same row and are never compared. The **most actionable self-study insight for execs is the gap** — phrases they *feel* fluent in but cannot produce when scored. That over-confidence is exactly where adult self-learners plateau, and detecting it costs a diff of two existing columns.

### P3 — No initial-encoding gate; latent thresholds; no exposure floor

L1/L2 are ungated, so weakly-encoded items reach the (timeless) review pool with no compensating mechanism. There is a **latent** threshold inconsistency (`score_sequence` returns `passed` at ≥7; `Lesson3` gates at `PASS_AVG=8`) — worth tidying, but verified *not* a live gating bug (L3 computes its own mean). And weighted-random deck sampling can statistically *starve* a weak phrase for days (the 90s cooldown is the only brake). And no pronunciation/prosody signal — real, but see Avoid for why it's a trap on this audience.

---

## 4. Recommendations by lever

### A) Content-only (no code) — *available today*

1. **Populate `CheckPhrase` with situational cues.** Author 1–3 cues per phrase into the empty-but-wired table (`training.py:325–334` reads it first; `Training.tsx` renders it). Replace "see *Understand*" with *"Your CFO just defended a number you doubt — you want the reasoning, not a fight. Say it."* Trains **situated retrieval (Nation) + TBLT (Ellis)** instead of translation — the highest-leverage single change for transfer, zero code. **Do NOT** copy Duolingo's word-bank translation prompts; that *is* the cue we're removing.

2. **Author real Practice tasks with an outcome.** `questions/*.json` are `stub:true` and `_FRAMES` are content-free ("react in the Curious register"). Write genuine **TBLT** task cards: named interlocutor, concrete goal, success condition (*"Cut a circular debate without losing the room — you have one move."*). The scorer already accepts any batch phrase. **Do NOT** drift into loosely-graded free roleplay — keep answers constrained to the activated repertoire.

3. **Add a register/role pragmatic note per phrase** (author the dormant `ContextExample` fields, surface on the L2/Training reveal). The **interlanguage-pragmatics (Kasper & Rose)** layer that protects presence from register failure — flag where flirt/composure phrases tip confident→aggressive. **Do NOT** ship a generic formal/informal toggle; make it relationship- and stakes-specific. (Content-only *only if* rendered in the existing reveal slot.)

4. **Recurring anchor "callbacks" in later stories.** When generating a section-N story, inject 1–2 anchors from already-learned batches as natural callbacks (a gravitas story re-uses *understand* from the disagreement ladder). **Distributed practice + contextual variation (Bjork)** at encoding time, zero code. Cap at 1–2, handle order-dependence (don't "call back" to a batch the learner hasn't reached). **Do NOT** treat this as a substitute for real SRS — re-exposure follows the *path's* schedule, not the forgetting curve's.

5. **Turn each phrase into a 2-line adjacency pair** (author an English "their line" before each `phrase_en`, rendered in the existing stimulus slot). Encodes the **trigger condition (Conversation Analysis)** — *when* do I reach for this move. **Do NOT** also write a separate situational cue for the same phrase — one or the other, they're redundant. **Do NOT** build branching dialogue trees; one eliciting turn.

### B) Training-flow (needs code) — ordered by impact

1. **Real per-phrase spaced repetition — SM-2-lite, seeded from EWMA.** Add `next_review_at` + interval (and actually *write* `srs_status`), advanced on each scored attempt: ≥8 expands, a miss resets short; seed ease from existing `avg_score` so no cold start. `/deck` and the review rail prioritize `next_review_at <= now` instead of the 90s cooldown. This is the consensus #1 fix. Drawn from **SM-2/Anki**. **Do NOT** build full FSRS half-life regression now — the 9-phrase-batch, sprint-limited corpus won't yield fittable history for months. **Do NOT** expose ease/interval numbers (Anki's failure mode for non-power-users).

2. **Use the latency you already store → automaticity + a `fast & automatic` state.** Fold median latency into `_conf`: a phrase is `automatic` only when `avg_score` is high *and* median latency < a per-length threshold over the last N attempts. This legitimately *writes* `srs_status` from real data and keeps the deck drilling known-but-slow phrases. Drawn from **ACT-R automaticity**. Calibrate per-phrase-length, use medians/last-N (client latency is dirty — network, mic warm-up, re-reading the cue); keep any badge sober.

3. **Surface the calibration gap.** Compute per-phrase `self_ewma` high / `avg_score` low-or-absent and build one section: *"Проверка уверенности — 7 фраз, которые вы отметили как знакомые, но не произнесли вслух."* Cheap (diff of two columns), high-value, on-brand. Drawn from **metacognitive-calibration research**. Frame as "the app catches a blind spot a mirror can't," never "gotcha." Don't punish the swipe or you lose the free `self_ewma` signal.

4. **Inline "why it landed" tone coaching on every miss < ~8** (free, cached, cheap model): one line — *"прозвучало с хеджем — убери just/maybe, скажи короче"* + one model phrasing. For a register product the *why* is the lesson; it's currently paywalled (`training.py:519`). Drawn from **Duolingo Max "Explain My Answer."** **Do NOT** make it grammar-school correction — TONE/presence only. Pricing call required: keep the *deep* multi-turn coach paid, give away the one-liner.

5. **Within-session expanding-interval recall for new phrases** (`attempts==0` → re-test at ~30s/2m/5m, interleaved) — **Pimsleur graduated-interval**, best in a dedicated audio/Drive Mode session, not the short 12-card deck.

6. **Interleave the intensity ladder inside L2** (pair Curious immediately with the matching Direct) — **Rohrer & Taylor** discrimination of confusable items. Low cost, modest gain (partly present via `zone_random`). Keep L1/L3 chained.

7. **Graduated soft checkpoints in L1/L2** (L2 "ready" needs cued-recall mean ≥6 + every phrase ≥1 attempt; L1 a "ready/not yet" nudge) — **Bloom mastery learning**, removes the zero-gate→80%-wall cliff. Reconcile the latent ≥7/≥8 threshold while here. **Do NOT** make them hard retries-to-pass — soft "recommended ready" only.

8. **Due-driven maintenance weighting** (replace the flat 0.12 factor with a weight that rises as a closed batch approaches `next_review_at`; cap maintenance share at 30–40%). *Fold this into the scheduler work* — it's a tuning of `weight()`, not a separate project.

### C) Product

1. **A calm daily "due / at-risk" set on the home screen** — *"Освежить: 7 фраз на грани,"* above Current Focus, opening straight into the deck; a maintenance session type that draws only from due items. This is the habit lever **compatible with the anti-gamification rule** (no points/streaks/lives, just respectful review debt). Cap the due-set share so review debt never walls off new-domain progress. *Strictly downstream of the scheduler.*

2. **One respectful daily local notification** via `@capacitor/local-notifications` (already shipped, no backend push), at a user-picked time, framed as rehearsal — *"Пять минут на голос перед сегодняшними переговорами"* — and **skipped entirely when the due-set is empty.** Premium adults churn on nagging; *substance-gating is mandatory* (hence scheduler-dependent). **Do NOT** copy Duo's owl-guilt, multi-ping cadence, or loss-aversion dark patterns.

3. **A per-domain "presence" competence map** — a mastery ring per active domain (Charisma, Negotiation, Composure…) filled by share at `familiar/automatic`, plus a "shaky" count linking into review; the SLA variant shows the **register matrix** (can I be direct *and* warm?), which is what presence actually is. Drawn from **CEFR can-do descriptors + Apple Fitness rings**. *Depends on `srs_status`/automaticity being populated first* — a ring on a dead field reads all-zero. **Do NOT** make it a game HUD; sober skills profile.

4. **Engineer the onboarding "aha": a 60-second guided first story** before the library — play one mnemonic story for a chosen-domain batch, light anchors karaoke-style, then soft cued-recall on 3 of 9, end on *"это и есть метод."* Front-loads the most persuasive moment (**Superhuman onboarding-aha**). Keep it ONE story, skippable; verify path-shaping picks a strong, *goal-relevant* opener (a mismatched demo does the opposite).

**Deferred (Later / low-confidence):** multi-turn "Pressure Room" AI roleplay (scope-creep magnet, defer until the SRS spine is solid, keep answers constrained); Pimsleur "Drive Mode" audio review (needs due-list; Web Speech unreliable hands-free); weekly "presence review" digest; FSRS-lite half-life model (data-hungry, only after SM-2-lite has run long enough to fit).

---

## 5. The no-code path — what we can do *right now*

The only lever available today is the content pipeline. It also happens to contain the **single highest-ROI fix in the entire audit** (situational cues), so this is not a consolation prize — it's the correct first move regardless.

**Ship now, in priority order:**

1. **Situational cues into `CheckPhrase`** (P1 fix, zero code). The table is wired and read first by the deck; filling it converts every drill from "translate this word" to "produce the right move for *this moment*." This is the app's actual promise, currently unfulfilled.
2. **Pragmatic register/role notes** on the reveal side (closes the dormant-`ContextExample` P2 gap as far as content can).
3. **Real Practice task cards** replacing the stubs.
4. **Deliberate anchor callbacks** in new stories (the only spacing we can get without code — partial, path-scheduled, but free).
5. **2-line adjacency pairs** for phrases where a cue alone doesn't supply the trigger.

**Two hard constraints on all of the above:**
- **Every cue must be expert-authored and gated on the existing `approved` status. Do NOT bulk-generate unreviewed.** A wrong-register or off-situation cue is *worse than the bare anchor* — it actively mis-trains the one skill (pragmatic selection) the app exists to fix. Author quality, not feasibility, is the entire risk here.
- **Because scoring is meaning-based, a cue must not imply a specific phrasing the grader doesn't reward** — or you manufacture frustration.

Do **not** attempt to fix spacing through content alone. Callbacks help at encoding time but re-expose on the *path's* schedule, not the forgetting curve's — real SRS is unavoidably a code change.

---

## 6. Phased roadmap

### Now (content-only + cheapest code)
- **Author situational `CheckPhrase` cues** for the highest-traffic domains first (P1, no code).
- **Pragmatic register notes** + **real Practice tasks** + **anchor callbacks** (content).
- **Latency → automaticity / write `srs_status`** (P2, pure backend, data already exists).
- **Calibration-gap section** (low-effort, high-value, two existing columns).
- **Inline free tone-coaching one-liner** (low-effort; needs a pricing decision).

### Next (the retention spine)
- **SM-2-lite scheduler** (`next_review_at` + interval, seeded from EWMA) — the consensus #1, but sequenced *after* the no-code wins because it's the highest-effort, highest-risk-to-over-build item.
- **Calm "due / at-risk" home surface** (depends on scheduler).
- **Per-domain competence map** (depends on `srs_status` being live).
- **One substance-gated daily notification** (depends on due-set).
- **Onboarding "aha" first-story.**
- Tidy the latent ≥7/≥8 threshold; soft L1/L2 readiness nudges; due-driven maintenance weighting (folded into scheduler).

### Later (only once the above is proven)
- **FSRS-lite half-life model** — only after SM-2-lite has generated fittable history.
- **Multi-turn "Pressure Room" roleplay** (activate `ContextExample`), voice-only, constrained answers.
- **Pimsleur "Drive Mode"** audio review; weekly presence digest; varied-accent interlocutor input.
- **Pronunciation/Delivery sub-score** — *only* as pace/hesitation/one-tell on stage/gravitas batches, never accent-conformity (see Avoid).

### Avoid (explicit)
- **ELSA-style per-phoneme IPA accent scoring.** For premium RU-L1 execs a native-conformity heatmap reads as immigrant speech-therapy — the exact insult they're paying to avoid. If you score delivery at all: pace/hesitation/one tell, on stage-gravitas batches only.
- **Rewriting the mnemo stories from distinctive pegs into realistic boardroom scenes app-wide.** Distinctiveness is what makes 76 stories stick; realism risks context interference, and you *just* rewrote all 76 (`59c1987`). A/B on L3 transfer before touching, never bulk-replace.
- **Full FSRS half-life regression now.** Data-hungry; the corpus won't yield fittable history for months. SM-2-lite first.
- **Duolingo-style streak-panic / leaderboards / paid streak-repair / multi-ping nags.** Directly contradicts the anti-gamification, premium positioning. (Re: the current streak — it's buggy: `recordVisit()` fires on *home-open*, localStorage-only, no freeze. Lean toward **killing it** in favor of the due-count + competence map rather than dignifying a Duolingo mechanic execs are fleeing. If kept: server-side, work-based, free silent freeze, no panic UI.)
- **Bulk auto-generating any cues/notes unreviewed** — gate on `approved`, expert author, every time.
- **Hard retry-to-pass gates on L1/L2** — converts a deliberate premium-adult strength into a kid-game redo loop. Soft nudges only.
- **Multiple-choice "noticing" primes and passive nightly playback as core bets** — both import recognition/passive mechanics that dilute the production-first testing-effect thesis that is the app's actual edge. Late, optional, or not at all.
- **A standalone Leitner box *and* a full scheduler** — two competing schedulers. Pick one (Leitner = cheap version, FSRS-lite = real one); the SM-2-lite path already absorbs the "weak phrase starvation" concern via due-prioritization.

---

**The one-line takeaway:** the encoding and retrieval halves are excellent; the *scheduling* and *contextualization* halves are missing — and the cheapest of those two (situational cues, no code) is also the most valuable, so start there today while the SM-2-lite spine is built next.

---

## Appendix — full consensus master list (32 items)
_Raw output of the feasibility editor: every deduped proposal with lever, impact/effort, evidence strength, the lenses that raised it (consensus signal), and the skeptic's caveat._

### Populate the dormant CheckPhrase table with situational cues (retrieve from a moment, not a translation)
- **Lever:** content-only · **Impact:** high · **Effort:** medium · **Evidence:** strong · **Raised by:** sla, behavioral-product, assessment
- Author 1-3 situational cues per phrase into the EXISTING CheckPhrase table — already read first by the deck stimulus path (training.py:325-334, 533) and rendered by Training.tsx, currently empty. Replace 'see anchor word → recite string' with 'Your CFO just defended a number you doubt — you want the reasoning, not a fight. Say it.' This trains situational selection (the app's actual promise) instead of decontextualized translation, with zero schema/app-code work. Author register variants so the cue varies across sessions.
- ⚠️ _Skeptic:_ Genuinely content-only and verified-wired (CheckPhrase is the highest-ROI dormant asset). The risk is authoring quality, not feasibility: a generic or off-register cue is worse than the bare anchor because it mis-trains the trigger condition. These must be written/reviewed by someone fluent in the executive register, gated on the existing approved status — do NOT bulk-generate unreviewed. Scoring is meaning-based, so a cue that implies a specific phrasing the grader doesn't reward will frustrate users.

### Multi-turn 'Pressure Room' AI roleplay (activate dormant ContextExample)
- **Lever:** product · **Impact:** high · **Effort:** high · **Evidence:** moderate · **Raised by:** sla, competitive
- ContextExample (scenario_type/register_tone/speaker_role/listener_role) exists and is unused. Wire a streaming endpoint where an LLM plays the counterpart (hostile board member, cooling investor) for 4-6 turns; the learner must HOLD a target register across the exchange, scored on register consistency and recovery, not single phrases. Seed scenarios from each batch's theme. The missing top-of-funnel between drill and real life; the entire 2024-26 category (Duolingo Max, Speak, Praktika) lives here.
- ⚠️ _Skeptic:_ Biggest scope-creep magnet and a different product surface from the focused chunk-drill thesis. Free-conversation scoring is exactly the loose grading the app deliberately avoids — keep answers constrained to the activated repertoire or risk a vague chatbot. Real cost/latency exposure with streaming. Defer until the retention spine (SRS) is solid; voice-only, no avatar, tense and specific — not generic small talk.

### Engineer the onboarding 'aha': a 60-second guided first story before the library
- **Lever:** product · **Impact:** high · **Effort:** medium · **Evidence:** moderate · **Raised by:** behavioral-product
- After the goal pick, run one mnemonic story end-to-end in onboarding for a chosen-domain batch — play it, light anchors karaoke-style, then a soft cued-recall on 3 of 9 so the learner feels themselves recall executive phrases they didn't know 60s ago. End on 'это и есть метод' before the library. Front-loads the product's most persuasive moment.
- ⚠️ _Skeptic:_ High potential but easy to overdo into a long scripted tutorial that execs skip — keep it ONE real story, learner-driven, skippable. The 'aha' only fires if the very first auto-selected batch is genuinely relevant to the goal they just picked; a mismatched demo batch produces the opposite impression. Verify the path-shaping picks a strong opener for each domain.

### Real per-phrase spaced repetition (next_review + interval/stability), seeded from existing EWMA
- **Lever:** training-flow · **Impact:** high · **Effort:** high · **Evidence:** strong · **Raised by:** cognitive-science, behavioral-product, assessment, competitive
- Add next_review_at + interval/stability (and actually WRITE srs_status) to UserPhraseStat, advanced on each scored attempt: score>=8 expands the interval, a miss resets it short. Seed from the existing avg_score EWMA for zero cold-start. The /deck and review rail then prioritize phrases where next_review_at<=now instead of the timeless 90s cooldown. This is the consensus #1 fix: the documented '4-state SRS' is currently a dead label machine (srs_status written only by the legacy /reviews endpoint at batches.py:372, never read by any scheduler; deck reads only avg_score/last_failed_at/last_seen_at). FSRS-style stability is the preferred math over raw SM-2 ease.
- ⚠️ _Skeptic:_ Highest-value but also highest-risk to over-build. FSRS needs review-history volume to fit per-item half-lives; with a 9-phrase-batch, sprint-limited corpus and modest DAU, you'll be running on priors for months — so ship SM-2-lite first, not a half-life regression. Do NOT expose ease/interval numbers; for premium adults the value is an invisible 'ready to review' set, not Anki knobs. Also verify: avg_score has no decay, so before scheduling exists a 6-week-old and a yesterday phrase look identical — that's exactly why this matters, but it also means the seed is noisy.

### Surface a calm daily 'due / at-risk' review set on the home screen
- **Lever:** training-flow · **Impact:** high · **Effort:** medium · **Evidence:** strong · **Raised by:** cognitive-science, behavioral-product, competitive
- Compute due-now items from next_review_at (closed-batch phrases past interval + currently-shaky) and surface a single curated set — 'Освежить: 7 фраз на грани' / 'Закрепить сегодня' — above 'Current Focus', opening straight into the existing deck. Add a maintenance session type drawing only from due items. This is the habit lever that's compatible with the stated anti-gamification rule (no points/streaks/lives, just respectful review debt).
- ⚠️ _Skeptic:_ Strictly downstream of the scheduler — useless until next_review exists, so it cannot ship first. Cap the due-set share so review debt never crowds out new-domain progress (40% max), or busy execs who skip days will return to an all-review wall and bounce. The number must never read as a guilt-meter; 'на грани' framing is right, a red badge count is wrong.

### Pronunciation/delivery sub-score (Meaning vs Delivery) for stage/gravitas/composure batches
- **Lever:** training-flow · **Impact:** high · **Effort:** high · **Evidence:** moderate · **Raised by:** assessment, competitive
- Keep meaning scoring as-is; add a Delivery bar from cheap signals: word-timestamped STT (gpt-4o-transcribe/Whisper) → WPM, longest pause, hesitation count; plus an LLM/forced-alignment check on the 3-4 phonemes RU-L1 speakers systematically miss (th, w/v, final-consonant voicing, schwa). Show 'Meaning 9 / Delivery 6 — слишком много пауз'. This is the one dimension 'executive presence' lives on and where the app currently scores a flat-intonation, heavily-accented 10/10 as perfect.
- ⚠️ _Skeptic:_ Most likely to backfire on this exact audience. A prosody/accent score that fires on RU-L1 features can read as a 'speech-therapy for foreigners' verdict — the precise insult a premium executive is paying to avoid. Do NOT do ELSA's per-phoneme IPA heatmap. Restrict to 2-3 presence cues (pace, hesitation, ONE accent tell), and only on stage/gravitas batches where delivery is the literal skill. STT timing reliability on short utterances over phone mics is unproven; a noisy Delivery score that contradicts a 10 on Meaning will feel arbitrary and erode trust in the whole grader.

### Use the already-captured latency to set automaticity + a 'fast & automatic' state
- **Lever:** training-flow · **Impact:** high · **Effort:** medium · **Evidence:** moderate · **Raised by:** assessment, competitive
- latency_ms/response_time_ms is written in 7 places (training.py 102/127/162/388/405/412, practice.py 138) and read nowhere. Fold it into the confidence calc: a phrase is 'automatic' only when avg_score is high AND median latency is below a per-length threshold (e.g. <250ms/word over last 3 attempts). This finally lets you legitimately write srs_status (new→shaky→familiar→automatic) from real data, and lets the deck keep drilling known-but-slow phrases — exactly the gap between 'I can translate it' and 'it comes out under pressure'. Pure backend, data already exists.
- ⚠️ _Skeptic:_ Cheap and elegant, but client-reported latency_ms is dirty: it conflates think-time, network, mic warm-up, STT round-trip, and the user re-reading the cue. Without isolating actual speech-onset, 'slow' may just mean 'bad connection on the metro'. Calibrate per-phrase-length and use medians/last-N, never a single attempt. Keep any visible 'automatic' badge sober — not a dopamine ping.

### Within-session expanding-interval recall for brand-new phrases (Pimsleur engine)
- **Lever:** training-flow · **Impact:** high · **Effort:** medium · **Evidence:** strong · **Raised by:** cognitive-science, competitive
- When a phrase is first introduced (attempts==0), re-test it at expanding gaps in the SAME session (~30s, ~2min, ~5min), interleaved with other items, instead of the flat 90s anti-repeat cooldown. Implement as a per-session in-memory queue in the deck/drill layer. Cheapest evidence-backed way to harden a day-1 encoding; uniquely suited to this audio-first app since the learner is already listening continuously.
- ⚠️ _Skeptic:_ Strong principle, but a 12-card swipe session or a 9-phrase batch may be too short to fit expanding gaps without feeling repetitive — the very repetition adults find childish. Works best in a dedicated audio/'Drive Mode' session, less so in the existing finite deck. Keep the chained mnemo story as the encoding asset; only the drill expands.

### Surface a per-domain 'presence' competence map (mastery rings, strong-vs-shaky)
- **Lever:** training-flow · **Impact:** high · **Effort:** medium · **Evidence:** moderate · **Raised by:** sla, behavioral-product
- Replace the three raw home metrics with a per-section progress identity: a ring per active domain (Charisma, Negotiation, Composure…) filled by share of phrases at familiar/automatic, plus a 'shaky' count linking into review. Renders the rich-but-hidden UserPhraseStat as felt competence — the SDT competence loop and an executive-skills profile, not a game HUD. SLA variant: show the register MATRIX (can I be direct AND warm?), not a single fluency %.
- ⚠️ _Skeptic:_ Depends on srs_status/automaticity actually being populated first (currently every phrase is permanently 'new'), so it's downstream of the latency/scheduler work — a ring built on a dead field shows all-zero. Risk of crown-grind/ring-close dopamine spam clashing with premium positioning; keep it a sober skills profile. A map that exposes how little is 'automatic' early on can demotivate rather than motivate.

### Surface the calibration gap: 'you marked these known but can't say them yet'
- **Lever:** training-flow · **Impact:** high · **Effort:** low · **Evidence:** moderate · **Raised by:** assessment
- self_ewma (swipe) and avg_score (spoken) sit in the same UserPhraseStat row and are never compared. Compute the per-phrase gap (self_ewma high, avg_score low/never-spoken) and build one section targeting exactly those: 'Проверка уверенности — 7 фраз, которые вы отметили как знакомые, но не произнесли вслух'. The most defensible self-study feature for execs who over-rate themselves; costs a diff of two existing columns.
- ⚠️ _Skeptic:_ Cheap and on-brand IF framed as 'the app catches a blind spot a mirror can't', not as 'gotcha, you were wrong'. The signal is only meaningful once a phrase has BOTH a swipe and a spoken attempt — many won't, so the eligible set may be small early. Don't punish the swipe or discourage self-grading, or you lose the cheap self_ewma signal entirely.

### Inline 'why it landed' tone coaching on everyday misses (free, not paywalled)
- **Lever:** training-flow · **Impact:** high · **Effort:** low · **Evidence:** moderate · **Raised by:** competitive
- Run the existing coach_feedback (tone + a stronger phrasing) on every drill miss below ~8, cached, on the cheap model, returning a one-line note: 'прозвучало с хеджем — убери just/maybe, скажи короче' + one model phrasing. For a register-focused product the WHY is the lesson; it's currently gated to the AI plan (training.py:519) and invisible elsewhere. Keep deep multi-turn coaching paid; the single-line tone note should be free.
- ⚠️ _Skeptic:_ Tension with monetization: coaching is currently a paid differentiator, so giving the one-liner away free needs a deliberate pricing call (the deeper coach stays paid). Cost: even on nano, firing on every sub-8 miss adds per-attempt LLM cost against the daily caps — cache hard and only on genuine misses. Must be about TONE/presence (hedging, pace, status), never grammar-school correction, or it infantilizes the audience.

### Pimsleur-style eyes-free 'Drive Mode' audio review of the user's weak set
- **Lever:** training-flow · **Impact:** high · **Effort:** medium · **Evidence:** moderate · **Raised by:** competitive
- Compose a single gapless WAV (the render pipeline already does this) pulling from the due-list across batches at EXPANDING intervals — a missed phrase reappears after 3, then 7, then 12 items, anticipation-drill style, scored by Web Speech to stay free. The one mode a metro/commute exec will actually do daily, pairing true anticipation intervals with executive content (no competitor does). 3-5 min, phrase-dense, from the user's own weak set.
- ⚠️ _Skeptic:_ Depends on the due-list (so post-scheduler). Web Speech recognition is unreliable hands-free in a noisy car/metro — the scoring half may silently fail, degrading it to passive listening (still useful, but undersells 'recall'). Don't copy Pimsleur's slow 30-min scripted lessons; keep it short and dense.

### Recurring anchor 'callbacks' woven into later stories (content-only distributed practice)
- **Lever:** content-only · **Impact:** medium · **Effort:** medium · **Evidence:** moderate · **Raised by:** cognitive-science
- Anchors already recur across batches in the corpus. Make it deliberate: when generating a new batch's mnemo story (mnemo.py), inject 1-2 anchors from already-learned batches as natural callbacks (a gravitas story re-uses 'understand' from the disagreement ladder). Forces spaced re-exposure at story-encoding time with zero app code, and adds varied-context encoding (same item, new scene = stronger trace).
- ⚠️ _Skeptic:_ Feasible and brand-safe, but it is NOT a substitute for true cross-day SRS — the re-exposure happens only when the user reaches the later batch, on the path's schedule, not the forgetting curve's. Risk: callbacks constrain the story generator's narrative freedom and can make the 70-word stories feel contrived if forced. Cap at 1-2 callbacks and only where they fit naturally. Also: a learner who hasn't yet done the source batch gets a 'callback' to nothing — order-dependence needs handling.

### Turn each phrase into a 2-line adjacency pair (interlocutor turn → your move)
- **Lever:** content-only · **Impact:** medium · **Effort:** medium · **Evidence:** moderate · **Raised by:** sla
- Author an English 'their line' immediately before each phrase_en so the deck shows the prior turn and the learner produces the response ('The numbers speak for themselves.' → 'Run me through how you got to that number.'). Encodes the trigger condition (when do I reach for this?) that isolated-monologue drilling misses — the conversational-competence half of fluency.
- ⚠️ _Skeptic:_ 'Content-only' only holds if the eliciting turn renders in an EXISTING slot (e.g. as a CheckPhrase stimulus). If it needs a new card face or its own audio render, it becomes training-flow + asset work — don't undersell the lift. Overlaps heavily with the situational-cue proposal; a good situational cue may already supply the trigger, so do one or the other per phrase, not both (redundant).

### Add a register/role pragmatic note to each phrase ('to a peer warm; to your boss, careful')
- **Lever:** content-only · **Impact:** medium · **Effort:** medium · **Evidence:** moderate · **Raised by:** sla
- Author the dormant ContextExample register_tone/speaker_role/listener_role per phrase and show a one-line pragmatic note on the reveal side of L2 cards / Training backs — flagging where flirt/composure phrases tip from confident to aggressive. The pragmatics layer that protects 'executive presence' from register failure; the differentiator no beginner app offers.
- ⚠️ _Skeptic:_ Content-only ONLY if rendered in the existing reveal slot; a dedicated card face tips it to training-flow (the lens admits this). Authoring risk is high — a wrong register call actively mis-teaches pragmatics, the one thing this is meant to fix. Must be relationship/stakes-specific, not a generic formal/informal toggle. Needs an expert author, gated on approved status.

### Make the mnemo story carry the real scene (not a random peg) for ≥1 anchor per zone
- **Lever:** content-only · **Impact:** medium · **Effort:** medium · **Evidence:** speculative · **Raised by:** sla
- Evolve the story generator so the narrative scene is a plausible version of the ACTUAL scenario (a tense boardroom, a charged dinner) rather than a mountain/fishing metaphor, with anchors landing on real conversational beats — so the most-replayed audio also teaches WHEN the phrase is used. Keep the keyword-mnemonic chaining mechanics. Pure prompt/content change.
- ⚠️ _Skeptic:_ This trades AWAY a validated strength for an unproven one. The bizarre/unrelated peg (mountain, fly-fishing) is what makes 76 stories memorable via the keyword-mnemonic mechanism; a realistic boardroom scene risks interference (the scene resembles the target context, reducing the distinctiveness that aids recall). The team just rewrote all 76 mnemos as scene-metaphors (commit 59c1987) — reversing that is costly. A/B against current peg stories on L3 transfer before any rollout; do not assume realism beats distinctiveness.

### Author real Practice tasks with an outcome (replace the stub frames)
- **Lever:** content-only · **Impact:** medium · **Effort:** medium · **Evidence:** moderate · **Raised by:** sla
- questions/*.json are stub:true and practice.py _FRAMES are content-free shells ('react in the Curious register'). Write genuine task cards per batch: named interlocutor, concrete goal, success condition ('Cut a circular debate without losing the room — you have one move.'). The Practice scorer already accepts any batch phrase; richer prompts make it a real TBLT task. Pure content into existing files.
- ⚠️ _Skeptic:_ Genuinely content-only and clearly better than the current stubs. But Practice is a lower-traffic surface than the core drills/SRS — high authoring effort per batch for a screen fewer users reach. Keep the constraint that answers come from the activated repertoire (don't drift into loosely-graded free roleplay). Sequence after the higher-traffic CheckPhrase cues.

### Per-phrase intrinsic-difficulty tags + graded check variants to seed cold-start adaptivity
- **Lever:** content-only · **Impact:** medium · **Effort:** medium · **Evidence:** speculative · **Raised by:** assessment
- Populate CheckPhrase with easy/medium/hard register variants AND tag each phrase's intrinsic difficulty (length, idiomaticity, RU-L1 false-friend risk) so the deck can match cue difficulty to the learner's avg_score and so a new phrase's cold-start weight reflects how hard IT is, not a flat new_boost. The deck already joins CheckPhrase; it just gets richer data (gate on approved).
- ⚠️ _Skeptic:_ IRT-style difficulty calibration is overkill for 9-phrase batches and the variant-matching needs the deck to actually select by difficulty (may be training-flow, not pure content). Lower priority than just getting baseline situational cues into CheckPhrase first; do the simple version before the graded one.

### Native-delivery reference clips for a curated set of status-defining power lines
- **Lever:** content-only · **Impact:** medium · **Effort:** medium · **Evidence:** speculative · **Raised by:** competitive
- For a few dozen high-leverage, prosody-carrying lines ('Give me the green light' — clipped, downward, unbothered), commission/generate short real-voice reference deliveries with a register tag, stored as an audio variant the player can A/B against the learner's attempt. Curate quality over coverage. The player already handles per-phrase audio.
- ⚠️ _Skeptic:_ 'Content-only' is generous — it implies new human-voice asset production (a pipeline/cost the team doesn't currently run) and a player A/B UI is arguably training-flow. Without a delivery score (separate proposal) to act on, hearing a native model is passive and may not transfer. Only worth it paired with delivery scoring; otherwise it's premium polish, not learning.

### Register-variant phrase generation (same intent across Warm/Spine/Weight)
- **Lever:** content-only · **Impact:** medium · **Effort:** medium · **Evidence:** speculative · **Raised by:** competitive
- Extend content generation so each anchor optionally ships 2-3 register variants of the same intent (soften / hold / dominate), reusing the existing register dial. The drill can then ask 'say this so it reads as Weight, not Warm' — training the room-reading skill that is the product's thesis. Phrase data + a gloss tag; composes with the 9-phrase batch.
- ⚠️ _Skeptic:_ The drill prompt 'say it as Weight not Warm' is a new training-flow interaction, so the end-to-end feature is NOT content-only even if the variant data is. Generating 3x the phrases risks diluting the curated, tight 9-per-batch structure that is a strength. Heavy authoring/QA; the existing zone-escalation already delivers much of the register-gradation value.

### Respectful single daily local notification framed as rehearsal, not guilt
- **Lever:** product · **Impact:** medium · **Effort:** medium · **Evidence:** moderate · **Raised by:** behavioral-product
- Use @capacitor/local-notifications (Capacitor already shipped; no backend push) to schedule ONE daily reminder at a user-picked time, copy framed as executive rehearsal ('Пять минут на голос перед сегодняшними переговорами'), and SKIP entirely on days the due-set is empty/cleared so it never nags without substance. Lands directly in a finite review.
- ⚠️ _Skeptic:_ Premium adults churn fastest on nagging — a notification is net-negative if it ever fires without substance, so it MUST be gated on a non-empty due-set (hence dependent on the scheduler). Opt-in, single ping, dismissible, no multi-ping cadence, no owl-guilt. iOS notification-permission prompt timing matters; don't ask on first launch.

### Weekly 'presence review' digest assembled from existing data
- **Lever:** product · **Impact:** medium · **Effort:** medium · **Evidence:** speculative · **Raised by:** behavioral-product
- Once a week assemble a short, executive-coach-voiced in-app (optionally notified) review from completed_at, per-section closes, and EWMA gains: 'На этой неделе ты закрепил 11 фраз в Negotiation и Composure; самая прочная — "Help me understand the thinking there."; на следующей освежим 6'. A low-frequency, high-dignity identity hook distinct from the daily ritual.
- ⚠️ _Skeptic:_ Nice-to-have identity layer, but it's a new product surface competing for build time against the retention spine. Don't copy Wrapped hype or Duo year-in-review cartoonishness. Impact is real but soft and hard to measure; sequence late.

### Passive 'Presence Playback' nightly audio program of the weak set
- **Lever:** product · **Impact:** medium · **Effort:** medium · **Evidence:** speculative · **Raised by:** competitive
- Auto-compile a nightly ~6-min gapless program of the learner's weak phrases (phrase + one-line situational gloss + model delivery), Apple Fitness+ in tone — passive exposure for moments the user won't do active recall, strengthening the same phrases the scheduler flags. Uses the render pipeline + due-list.
- ⚠️ _Skeptic:_ Passive listening is the weakest memory lever in the deck (the whole app is correctly built on active production) — this partly contradicts the testing-effect thesis. Depends on the due-list. Pleasant premium framing but low retention ROI per build-hour; treat as a late differentiator, not core.

### Interleave the intensity ladder inside L2 drilling (break within-batch blocking)
- **Lever:** training-flow · **Impact:** medium · **Effort:** low · **Evidence:** strong · **Raised by:** cognitive-science
- Drill L2 cued-recall ACROSS zones in a shuffled, contrast-maximizing order — pair a 'Curious' phrase immediately with the matching 'Direct' one so the learner discriminates register/intensity rather than reciting a chain. The canonical interleaving win (highly similar, confusable items). Keep the story's ordered chain for L1 encoding and the L3 exam; only L2 interleaves.
- ⚠️ _Skeptic:_ Solid and low-cost, but the gain is modest and partly already present (sessions.py supports zone_random / 'listen shuffle'). Do NOT interleave L1 first-encounter or the L3 narrative retell — the chaining is the encoding asset there. Net effect may be small relative to the SRS gap.

### Graduated mastery checkpoints in L1/L2 to remove the L3 cliff
- **Lever:** training-flow · **Impact:** medium · **Effort:** medium · **Evidence:** moderate · **Raised by:** cognitive-science, sla, assessment
- Make L2 'complete' require the cued-recall mean over the last full pass to clear a low bar (~6/10) AND every phrase to have ≥1 scored attempt; keep L1's retell informational but feed a 'ready / not yet' nudge. Spreads assessment off the expensive mini sequence exam and removes the demotivating jump from zero gates to an 80% wall (Bloom mastery learning). Also reconcile the latent threshold inconsistency (backend returns passed at score>=7 in training.py:166 while Lesson3 gates at PASS_AVG=8).
- ⚠️ _Skeptic:_ Direct friction added to the deliberately low-stakes, ungated practice phase that adults like — a soft gate that feels like a hard one will read as a kids' game. Keep these 'recommended ready' nudges, never retries-to-pass. Note the >=7/>=8 discrepancy is latent, NOT a live gating bug: L3 computes its own mean and doesn't consume the backend 'passed' flag — still worth aligning, but don't bill it as breakage.

### Server-side, work-based streak with a quiet weekly freeze
- **Lever:** training-flow · **Impact:** medium · **Effort:** medium · **Evidence:** moderate · **Raised by:** behavioral-product
- Move the streak off localStorage (ee-streak, fires on home OPEN) onto the account, incrementing only on real work (a swipe session, an L-stage, a cleared due-set). Add one auto-applied weekly freeze so a single missed day doesn't wipe weeks, shown as a calm rhythm ('14 дней практики'), not a flaming combo.
- ⚠️ _Skeptic:_ Tension with the explicit anti-gamification positioning — any streak, however calm, can read as the Duolingo mechanic execs are fleeing. The current bug (rewards app-opening) is real and worth fixing, but consider whether the right move is to KILL the streak in favor of the due-count + weekly review rather than dignify it. If kept: free silent freeze only, no leaderboards, no paid repair, no streak-panic UI.

### Per-item Leitner-box exposure control so weak phrases get a guaranteed spaced burst
- **Lever:** training-flow · **Impact:** medium · **Effort:** medium · **Evidence:** moderate · **Raised by:** assessment
- Layer a light Leitner promotion on the weighted-random deck: a failed phrase enters a 'priority box' guaranteeing it appears in the next 1-2 sessions (not merely statistically up-weighted, which can miss it for days), promoted out only after 2 spaced clean+fast recalls. Cap any single strong phrase's per-session exposure so maintenance can't starve new/weak items. Box numbers stay internal.
- ⚠️ _Skeptic:_ Overlaps with the FSRS-lite scheduler — if you build proper next_review, a separate Leitner box is partly redundant and risks two competing schedulers. Treat as either a cheaper ALTERNATIVE to full FSRS or a thin guarantee layer on top, not both. The genuine gap it fixes (weighted-random can starve a weak item) is real but narrow.

### Break the L3 sequence exam's single number into its already-computed structured verdict
- **Lever:** training-flow · **Impact:** medium · **Effort:** low · **Evidence:** moderate · **Raised by:** assessment
- score_sequence already returns missed_anchors and order_ok, then discards them into one mean. Drive the L3 stage verdict + debrief off that structure: 'Gist solid, but you dropped anchors 4 & 7 and inverted the escalation order.' For an escalation ladder, order_ok is itself a presence skill — weight it explicitly. Cheap; the signal exists.
- ⚠️ _Skeptic:_ Low cost, but L3 is a once-per-batch terminal event — improving its debrief touches a low-frequency surface, so impact is bounded. Don't turn the exam screen into a rubric dashboard; one or two trait lines max. Order-weighting must match the pedagogy (only ladder batches care about order; non-escalation batches shouldn't be penalized for sequence).

### Due-driven maintenance weighting in the cross-batch deck (replace flat 0.12 factor)
- **Lever:** training-flow · **Impact:** medium · **Effort:** low · **Evidence:** moderate · **Raised by:** cognitive-science
- The swipe deck already pulls across active + maintenance batches, but maintenance is a flat 0.12 factor unrelated to time. Replace it with a due-driven weight that rises as a completed batch's items approach next_review_at, so one deck naturally interleaves fresh items with old items genuinely about to be forgotten. Cap maintenance share (30-40%) so new learning never stalls.
- ⚠️ _Skeptic:_ Pure downstream of the scheduler — meaningless without next_review. Essentially a tuning of the existing weight() once intervals exist, so fold it into the scheduler work rather than tracking as a separate item.

### Soft 'noticing' multiple-choice prime before L2 cued recall
- **Lever:** training-flow · **Impact:** medium · **Effort:** medium · **Evidence:** speculative · **Raised by:** sla
- Before the L2 drill, insert a tiny receptive step: show the situation + 2-3 candidate phrases (one right, distractors from adjacent zones), learner picks the register/stakes fit. Forces conscious attention to form-meaning-register mapping (Schmidt noticing) and primes correct retrieval. Reuses existing phrases as distractors; not a hard gate.
- ⚠️ _Skeptic:_ Adds a recognition/multiple-choice step to a deliberately production-first app — the exact tapping-not-speaking mechanic the app's differentiation rejects. Risk of importing Duolingo tedium. Keep it a fast optional prime, never a gate; or skip entirely if it slows the production loop.

### Per-phrase memory half-life model (FSRS-lite) once intervals + history exist
- **Lever:** training-flow · **Impact:** medium · **Effort:** high · **Evidence:** moderate · **Raised by:** cognitive-science
- After next_review ships and history accumulates, fit a lightweight retrievability model estimating per-item stability from (gap, outcome) history, scheduling the next review where predicted recall hits ~85-90% (the desirable-difficulty sweet spot). Duolingo half-life regression on the already-logged attempts. The ceiling-raiser: per-item, per-learner forgetting curves.
- ⚠️ _Skeptic:_ Explicitly downstream of basic intervals (P3 in its own lens) and data-hungry — premature for current scale. Target ~85% retrievability, NOT 100% (over-easy review wastes the spacing budget). Do not build until SM-2-lite has run long enough to generate fittable history; otherwise you're regressing on noise.

### Vary interlocutor voice/accent on completed batches for comprehension robustness
- **Lever:** training-flow · **Impact:** low · **Effort:** low · **Evidence:** speculative · **Raised by:** sla
- For maintenance-pool batches, render the eliciting interlocutor turn in 2-3 different TTS voices/accents so the learner recognizes the same trigger spoken differently — comprehension robustness for multi-accent executive audiences. Vary ONLY the interlocutor input, never the learner's target phrase (keep one clear American model). Uses existing TTS cache.
- ⚠️ _Skeptic:_ Depends on the adjacency-pair 'their line' existing first, and production (not listening) is explicitly the app's core — so this addresses a non-core dimension. Lowest impact in the set; defer indefinitely.

---

### Feasibility editor's picks

**Do first:**
- Populate the dormant CheckPhrase table with situational cues (retrieve from a moment, not a translation)
- Real per-phrase spaced repetition (next_review + interval/stability), seeded from existing EWMA
- Surface a calm daily 'due / at-risk' review set on the home screen
- Use the already-captured latency to set automaticity + a 'fast & automatic' state
- Surface the calibration gap: 'you marked these known but can't say them yet'
- Inline 'why it landed' tone coaching on everyday misses (free, not paywalled)

**Content-only quick wins (no code):**
- Populate the dormant CheckPhrase table with situational cues (retrieve from a moment, not a translation)
- Author real Practice tasks with an outcome (replace the stub frames)
- Recurring anchor 'callbacks' woven into later stories (content-only distributed practice)
- Turn each phrase into a 2-line adjacency pair (interlocutor turn → your move)
- Add a register/role pragmatic note to each phrase ('to a peer warm; to your boss, careful')

**Avoid:**
- ELSA-style per-phoneme IPA accent scoring — for premium RU-L1 execs a heatmap of native-conformity errors reads as immigrant speech-therapy, the exact insult they're paying to avoid; if you score delivery, score pace/hesitation/ONE tell, not accent.
- Rewriting the mnemo stories from distinctive pegs (mountain/fishing) into realistic boardroom scenes app-wide — distinctiveness is what makes 76 stories stick; realism risks context interference, and the team just rewrote all 76 (commit 59c1987). A/B first, never bulk-replace.
- Building full FSRS half-life regression now — it's data-hungry and the 9-phrase-batch, sprint-limited corpus won't yield fittable history for months; ship SM-2-lite seeded from EWMA instead.
- Duolingo-style streak-panic / leaderboards / paid streak-repair / multi-ping notifications — directly contradicts the stated anti-gamification, premium-adult positioning; any nag without substance churns this audience.
- Bulk auto-generating CheckPhrase/ContextExample/register notes unreviewed — a wrong-register or off-situation cue actively mis-trains the one skill (pragmatic selection) the app exists to fix; gate every cue on the existing approved status with an expert author.
- Adding hard retry-to-pass gates to L1/L2 — the ungated low-stakes practice phase is a deliberate premium-adult strength; convert to soft 'recommended ready' nudges only, never kid-game redo loops.
- Treating the >=7 (backend) vs >=8 (Lesson3) thresholds as a live gating bug — verified that L3 computes its own mean and doesn't consume the backend 'passed' flag, so it's a latent inconsistency to tidy, not breakage to firefight.
- A standalone Leitner box AND a full next_review scheduler — two competing schedulers; pick one (Leitner as the cheap version, or FSRS-lite as the real one).
- Multiple-choice 'noticing' primes and passive nightly playback as core bets — both import recognition/passive mechanics that dilute the production-first testing-effect thesis that is the app's actual edge; at best late, optional extras.