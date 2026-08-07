# Phrase replacement — WAVE 2 (expert Douglass Hatcher)

> Provisional review artifact. Nothing applied to prod yet. Source of new phrases = expert's **`Suggested Phrase`** column (81 rows). Verdicts computed against that text; if we curate the source (GPT alt / keep-original), affected verdicts shift.


**Scope:** 81 phrases · 32 batches (of 90).

- **20 phrases — TEXT-ONLY**: the old anchor word survives in the new phrase → replace text, **story untouched**.

- **61 phrases — drop their anchor** → their batch story must change. At batch level = **29 stories to regenerate** (restory), because restory is per-batch.

- Borrowing a sibling phrase's anchor word is **not** viable (every English word in a story already *is* some phrase's anchor → collision). So text-only is the only zero-story-cost path.

- **Every** replacement (trivial included) still needs the phrase chain: `rephrase` → re-author cues (rephrase deletes them) → `intents` → `gen_context` → `i18n --refill` → `embeddings` → `doctor CLEAN`. Trivial ones simply **skip `restory`**.


## Quality gate ⚠️ (2 auto-flagged; realistically more)

Several expert rewrites are grammatically broken or drift into corporate-verbose and lose the original's punch. Decide the SOURCE policy before applying.


| batch#slot | OLD (ours) | expert NEW | flag | GPT alt (col6) |
|---|---|---|---|---|
| charisma-4#7 | Come on, that's the safe answer — give me the honest one. | Polished and safe answers won't get us to where we need to go. I need some unvarnished perspective. | — | That's the safe answer. What's your honest read? |
| charisma-9#2 | We're all just going to agree that was charming, right? | I think we can all agree that on the surface, that sounds good but I sense there's more to it. | — | I'm choosing to call that charming. |
| charisma-9#7 | See, now you trust me — nobody this awkward is hiding anything. | We've established a level of trust which is the foundation for the work ahead. | — | Well, at least you know I'm not overly rehearsed. |
| charisma-10#7 | When you two build something, I want it on record I started it. | When you two build something, please has a strong metric in place and benchmark the current situation. | garbled,garbled,garbled | When you two build something together, I'll be glad I made the introduction. |
| charisma-4#3 | Let's go around — I want everyone's one-liner on this. | I want to hear from everyone. Let's go around the table. Each person share your point of view but in just one sentence. | verbose,much-longer |  |

## A. TEXT-ONLY — story stays (20)

Old anchor still present in the new phrase. Safe once the phrase-chain runs; no restory.


| batch#slot | anchor | OLD | NEW |
|---|---|---|---|
| batch-3#7 | `elephant` | Feels like there's an elephant in the room nobody's naming — what is it? | What's the elephant in the room? |
| charisma-4#3 | `around` | Let's go around — I want everyone's one-liner on this. | I want to hear from everyone. Let's go around the table. Each person share your point of view but in just one sentence. |
| charisma-4#4 | `park` | Let's park that — it deserves its own conversation. | Let's park that and come back to it. |
| charisma-4#5 | `loop` | Hang on — we never looped back to what Dave started. | Let's take a pause and loop back to David's point. |
| charisma-8#4 | `calendar` | Let's get something on the calendar before we both pretend we will and don't. | Let's get something on the calendar to lock this in. |
| charisma-8#8 | `Next` | Next time, I want the question you were too polite to ask me. | Next time, let's take a deeper dive. |
| charisma-9#6 | `formal` | Good — the formal part's officially over. Now we can actually talk. | With formal lines of communication officially opened, let's roll up our sleeves and dig in a little deeper. |
| charisma-9#7 | `trust` | See, now you trust me — nobody this awkward is hiding anything. | We've established a level of trust which is the foundation for the work ahead. |
| composure-11#8 | `handle` | How I handle this will say more about me than the loss itself. | how we handle this will reveal more about our character than the loss itself. |
| composure-3#3 | `directly` | If there's feedback, give it to me directly — not theatrically. | If there's feedback, give it to me directly. |
| leadership-2#2 | `lead` | I need you to lead on this. | I need you to *take* the lead on this. |
| leadership-2#3 | `call` | It's your call from here. | It's your call. |
| negotiation-1#2 | `map` | Let me map out what a good deal looks like for me. | Let's map out what a good deal looks like |
| negotiation-1#6 | `bottom` | That's my bottom line — I won't go under it. | That's my bottom line. |
| pitch-1#0 | `fire` | Picture this: Monday morning, and the whole thing's on fire before your first coffee. | Imagine, it's Monday morning and your day starts with a fire drill. |
| pitch-3#3 | `ask` | So here's the ask, plainly. | So, here's the ask. |
| pitch-3#6 | `skin` | I've got skin in the game — I'm taking the same risk I'm asking you to take. | I've got skin in the game. |
| repair-1#1 | `overstepped` | I overstepped, and I know it. | I overstepped. |
| stage-11#5 | `deck` | I don't need the deck — the argument lives in my head. | I don't need the deck but I do need notes to be at my best. |
| stage-11#6 | `safety` | No safety net today — that's when it gets good. | No safety net today? Let's see how I do and then assess. |

## B. RESTORY needed — by batch (29 stories)

For each batch: phrases whose anchor is dropped (need a new anchor woven into a regenerated story) + trivial carry-overs the new story must still preserve.


### `charisma-4` — 4 new anchor(s), 3 carry-over

| slot | old anchor → NEW | OLD phrase | NEW phrase |
|---|---|---|---|
| #0 | `Quiet` → `situation` | Hey, the quiet end of the table — I want in on whatever you're discussing. | We haven't heard from you yet? What's your take on the situation? |
| #2 | `Hog` → `talked` | Okay, I've been hogging this — someone take it from me. | I've talked enough. I want to hear other points of view. |
| #6 | `Drop` → `surface` | Let's drop the charm for a minute and actually talk. | We've hit some surface issues. Let's take a deeper dive. |
| #7 | `Honest` → `unvarnished` | Come on, that's the safe answer — give me the honest one. | Polished and safe answers won't get us to where we need to go. I need some unvarnished perspective. |
| #3 | `around` (kept) | Let's go around — I want everyone's one-liner on this. | I want to hear from everyone. Let's go around the table. Each person share your point of view but in just one sentence. |
| #4 | `park` (kept) | Let's park that — it deserves its own conversation. | Let's park that and come back to it. |
| #5 | `loop` (kept) | Hang on — we never looped back to what Dave started. | Let's take a pause and loop back to David's point. |

### `charisma-9` — 5 new anchor(s), 2 carry-over

| slot | old anchor → NEW | OLD phrase | NEW phrase |
|---|---|---|---|
| #0 | `Head` → `anticipate` | Well — that landed better in my head. | I didn't anticipate that response. |
| #1 | `Heard` → `covered` | Well, everyone heard that one. Moving on. | We've covered that ground already. What's next? |
| #2 | `Charming` → `surface` | We're all just going to agree that was charming, right? | I think we can all agree that on the surface, that sounds good but I sense there's more to it. |
| #3 | `Dignity` → `circle` | We'll circle back to my dignity later — you were saying? | Let's circle back on that. You were saying? |
| #4 | `Pretend` → `reset` | Okay, let's pretend the last ten seconds didn't happen. | Let's reset and start fresh. |
| #6 | `formal` (kept) | Good — the formal part's officially over. Now we can actually talk. | With formal lines of communication officially opened, let's roll up our sleeves and dig in a little deeper. |
| #7 | `trust` (kept) | See, now you trust me — nobody this awkward is hiding anything. | We've established a level of trust which is the foundation for the work ahead. |

### `charisma-6` — 6 new anchor(s)

| slot | old anchor → NEW | OLD phrase | NEW phrase |
|---|---|---|---|
| #1 | `Generous` → `everyone` | That's generous — most people wait ten minutes before diagnosing me. | You read people well. That's skill not everyone has. |
| #2 | `Rehearse` → `prepared` | Not bad — did you rehearse that in the car? | Nicely done. You've come prepared. |
| #3 | `Careful` → `sense` | Careful — you're dangerously close to being funny. | You've got a good sense of humor. |
| #4 | `Laugh` → `going` | If I laugh, you'll just keep going. | Don't mind me. Keep going. |
| #5 | `Landing` → `opening` | Bold opening — let's see if you can stick the landing. | Bold opening. I'm ready to hear the rest. |
| #6 | `Hand` → `saved` | Give him a hand, folks — he's been saving that one all night. | Good for you. You saved the best for last. |

### `repair-1` — 5 new anchor(s), 1 carry-over

| slot | old anchor → NEW | OLD phrase | NEW phrase |
|---|---|---|---|
| #2 | `Fault` → `accountability` | This is my fault here. | I take accountability for that. |
| #5 | `Watch` → `brought` | Don't take my word for it — just watch. | My team brought a demo I think you'll love. |
| #6 | `Trust` → `reset` | I want to earn back your trust. | Let's reset. |
| #7 | `Slate` → `reset` | Can we wipe the slate clean? | Let's reset. |
| #8 | `Track` → `alignment` | Let's get back on track. | Let's make sure we're in alignment. |
| #1 | `overstepped` (kept) | I overstepped, and I know it. | I overstepped. |

### `charisma-5` — 5 new anchor(s)

| slot | old anchor → NEW | OLD phrase | NEW phrase |
|---|---|---|---|
| #0 | `Stop` → `repeating` | Stop me if I've told you this one — actually, don't, it's too good. | I'm going to risk repeating myself but the learning is too important. |
| #1 | `Badly` → `instructive` | You'll like this — it starts badly. | This story is instructive despite the difficult beginning. |
| #2 | `Picture` → `perspective` | Picture me at 2 a.m., completely lost — that's where this starts. | I'll set the scene. It's late at night. I'm at a loss for an answer. That's how this change of perspective began. |
| #3 | `Mind` → `thought` | Keep that one detail in mind — it matters in a minute. | Keep that thought. We'll come back to it in a minute. |
| #8 | `Anyway` → `topic` | Anyway. Pass the wine. | Ok. New topic. |

### `batch-3` — 3 new anchor(s), 1 carry-over

| slot | old anchor → NEW | OLD phrase | NEW phrase |
|---|---|---|---|
| #4 | `Off` → `through` | Something's off here — help me figure out what it is. | Something's not lining up - take me through your thought process |
| #5 | `Agenda` → `probably` | You probably think I've got my own agenda here. | You probably think I've got my mind made up. |
| #6 | `Kill` → `inclination` | Honestly, I'd kill the whole thing myself — talk me out of it. | My inclination is to punt the whole thing. Tell me why I shouldn't. |
| #7 | `elephant` (kept) | Feels like there's an elephant in the room nobody's naming — what is it? | What's the elephant in the room? |

### `charisma-8` — 2 new anchor(s), 2 carry-over

| slot | old anchor → NEW | OLD phrase | NEW phrase |
|---|---|---|---|
| #1 | `Night` → `tomorrow` | I could talk to you all night — which is exactly why I should go. | It's getting late and I've got a full day tomorrow. |
| #6 | `Trouble` → `together` | You and I are going to be trouble together — I can already tell. | Looking forward to working together. |
| #4 | `calendar` (kept) | Let's get something on the calendar before we both pretend we will and don't. | Let's get something on the calendar to lock this in. |
| #8 | `Next` (kept) | Next time, I want the question you were too polite to ask me. | Next time, let's take a deeper dive. |

### `leadership-2` — 2 new anchor(s), 2 carry-over

| slot | old anchor → NEW | OLD phrase | NEW phrase |
|---|---|---|---|
| #0 | `Reins` → `taking` | I'm handing you the reins. | You're taking the lead now. |
| #1 | `Charge` → `accountable` | You're in charge of this now. | You're accountable for this now. |
| #2 | `lead` (kept) | I need you to lead on this. | I need you to *take* the lead on this. |
| #3 | `call` (kept) | It's your call from here. | It's your call. |

### `stage-11` — 2 new anchor(s), 2 carry-over

| slot | old anchor → NEW | OLD phrase | NEW phrase |
|---|---|---|---|
| #7 | `luck` → `rehearsal` | No rehearsal for this one — wish me luck. | No rehearsal for this one is not the way to go. Let's put in the time. |
| #8 | `cold` → `something` | No script? Fine — I know this stuff cold. | No script? Let's talk it through and get something down. |
| #5 | `deck` (kept) | I don't need the deck — the argument lives in my head. | I don't need the deck but I do need notes to be at my best. |
| #6 | `safety` (kept) | No safety net today — that's when it gets good. | No safety net today? Let's see how I do and then assess. |

### `charisma-3` — 3 new anchor(s)

| slot | old anchor → NEW | OLD phrase | NEW phrase |
|---|---|---|---|
| #0 | `Fired` → `right` | What's got you genuinely fired up lately? | What's top of mind for you right now? |
| #2 | `Obsessed` → `attention` | What are you a little obsessed with right now? | Where are you focusing your attention right now? |
| #8 | `Ahead` → `missing` | What are you seeing that the rest of us are still catching up to? | What are you seeing that the rest of us are missing? |

### `pitch-1` — 2 new anchor(s), 1 carry-over

| slot | old anchor → NEW | OLD phrase | NEW phrase |
|---|---|---|---|
| #1 | `Quick` → `process` | Give me thirty seconds — quick one. | I'll need a moment to process this. |
| #5 | `Bet` → `hunch` | I'd bet money you've felt this exact thing. | My hunch is you know what that feels like. |
| #0 | `fire` (kept) | Picture this: Monday morning, and the whole thing's on fire before your first coffee. | Imagine, it's Monday morning and your day starts with a fire drill. |

### `pitch-3` — 1 new anchor(s), 2 carry-over

| slot | old anchor → NEW | OLD phrase | NEW phrase |
|---|---|---|---|
| #7 | `Shake` → `aligned` | If we're aligned, let's shake on it and get moving. | Great that we're aligned...and extend you hand. |
| #3 | `ask` (kept) | So here's the ask, plainly. | So, here's the ask. |
| #6 | `skin` (kept) | I've got skin in the game — I'm taking the same risk I'm asking you to take. | I've got skin in the game. |

### `batch` — 2 new anchor(s)

| slot | old anchor → NEW | OLD phrase | NEW phrase |
|---|---|---|---|
| #1 | `Run` → `through` | Run me through how you got to that number. | Take me through how you got to that number. |
| #2 | `Angle` → `perspective` | Can I offer a different angle? | I'd like to offer a different perspective. |

### `charisma-11` — 2 new anchor(s)

| slot | old anchor → NEW | OLD phrase | NEW phrase |
|---|---|---|---|
| #0 | `Smiled` → `positive` | Your name came up last night and I smiled like an idiot. | Your name came up last night in a positive light. |
| #4 | `Free` → `accepted` | Skip the apologies — when are you free? | Apology accepted. Now, let's focus on a good time to regroup. |

### `charisma-2` — 2 new anchor(s)

| slot | old anchor → NEW | OLD phrase | NEW phrase |
|---|---|---|---|
| #2 | `Crash` → `looks` | You looked like the most fun in the room — mind if I crash? | This looks like this is the place to be. Mind if I join? |
| #7 | `Forget` → `agenda` | Forget small talk — what's actually worth talking about tonight? | What's on our agenda? |

### `requests-1` — 2 new anchor(s)

| slot | old anchor → NEW | OLD phrase | NEW phrase |
|---|---|---|---|
| #0 | `Heads` → `blindsided` | Heads up — we've got a problem. | I don't want you to be blindsided. We've got a problem. |
| #5 | `Buck` → `accountable` | The buck stops with me on this. | I'm accountable |

### `charisma-1` — 1 new anchor(s)

| slot | old anchor → NEW | OLD phrase | NEW phrase |
|---|---|---|---|
| #7 | `Dancing` → `elephant` | Can I say the thing we're all dancing around? | Can we talk about the elephant in the room? |

### `charisma-10` — 1 new anchor(s)

| slot | old anchor → NEW | OLD phrase | NEW phrase |
|---|---|---|---|
| #7 | `Record` → `something` | When you two build something, I want it on record I started it. | When you two build something, please has a strong metric in place and benchmark the current situation. |

### `composure-1` — 1 new anchor(s)

| slot | old anchor → NEW | OLD phrase | NEW phrase |
|---|---|---|---|
| #0 | `Bait` → `appreciate` | I see the bait — and I admire the presentation. | I'm know what you're doing and appreciate it. |

### `composure-10` — 1 new anchor(s)

| slot | old anchor → NEW | OLD phrase | NEW phrase |
|---|---|---|---|
| #1 | `Comfortable` → `sure` | I'm not sure — and I'm comfortable saying that out loud. | I'm not sure. |

### `flirt-9` — 1 new anchor(s)

| slot | old anchor → NEW | OLD phrase | NEW phrase |
|---|---|---|---|
| #0 | `Cliffhanger` → `things` | Some things are better left as a cliffhanger. | Some things are better left unsaid. |

### `gravitas-6` — 1 new anchor(s)

| slot | old anchor → NEW | OLD phrase | NEW phrase |
|---|---|---|---|
| #8 | `Outrank` → `speak` | You outrank me — that doesn't make you right. | Part of my job is to speak truth to power. That's what I'm doing right now. |

### `leadership-1` — 1 new anchor(s)

| slot | old anchor → NEW | OLD phrase | NEW phrase |
|---|---|---|---|
| #2 | `Wrong` → `unclear` | Don't take this the wrong way. | Please let me know if any of this is unclear. |

### `negotiation-2` — 1 new anchor(s)

| slot | old anchor → NEW | OLD phrase | NEW phrase |
|---|---|---|---|
| #6 | `Dotted` → `aligned` | Ready to sign on the dotted line? | Are we aligned? |

### `pitch-2` — 1 new anchor(s)

| slot | old anchor → NEW | OLD phrase | NEW phrase |
|---|---|---|---|
| #1 | `Hole` → `approaching` | There's a hole in how everyone does this today. | There's a disparity in how the market is approaching this today. |

### `pressure-1` — 1 new anchor(s)

| slot | old anchor → NEW | OLD phrase | NEW phrase |
|---|---|---|---|
| #1 | `Feet` → `thinking` | I'm thinking on my feet here. | I'm thinking out loud. |

### `stage-4` — 1 new anchor(s)

| slot | old anchor → NEW | OLD phrase | NEW phrase |
|---|---|---|---|
| #8 | `present` → `perfection` | I don't have to be perfect up here. I have to be present. | We're not seeking perfection here. Instead, we're sitting with a problem, together. |

### `stage-6` — 1 new anchor(s)

| slot | old anchor → NEW | OLD phrase | NEW phrase |
|---|---|---|---|
| #5 | `derailed` → `remember` | So — where was I before I derailed myself? | help me remember where we left off. |

### `stage-9` — 1 new anchor(s)

| slot | old anchor → NEW | OLD phrase | NEW phrase |
|---|---|---|---|
| #5 | `sentence` → `reframe` | Here it is in one sentence you can run as-is. | Good reframe/bridge |