# Отсев «искусственных» фраз — 811 фраз, 90 батчей, вердикт по НИЖНЕМУ баллу + оценка замен

**Дата:** 2026-07-06 · Судьи: **GPT-5.5** (ChatGPT web) и **Claude Fable 5** (личная вычитка фраз И замен). Итог фразы = **минимум из двух оценок**. Замены предложены GPT (есть у фраз, где GPT сам ставил ≤6); каждую замену Fable оценил по той же шкале; **Δ = балл замены − нижний балл оригинала**.

## Итого

- Фраз: **811**. Слабых по нижнему баллу (min ≤6): **340** (42%)
- Распределение нижнего балла: 2: 1 · 3: 11 · 4: 48 · 5: 105 · 6: 175 · 7: 196 · 8: 204 · 9: 71
- Замен от GPT: **121**. Средний балл замены (Fable): **7.00**, средняя Δ: **+2.23**
- Замен уровня «живая» (≥7): **85** — можно брать как есть. Замен, которые сами слабые (≤6): **36** — нужен новый вариант. Замен хуже/не лучше оригинала (Δ≤0): **12**
- У 219 слабых фраз замены нет вовсе (GPT ставил >6, слабой посчитал только Fable) — генерировать отдельно

## ГЛАВНАЯ ТАБЛИЦА: слабые фразы, худшие сверху

Колонки: Мин = вердикт (нижний из двух баллов) · Замена (GPT) · **F(зам)** = оценка замены от Fable · **Δ** = F(зам) − Мин.

| Мин | GPT | Fable | Батч | Якорь | Фраза сейчас | Замена (GPT) | F(зам) | Δ |
|---|---|---|---|---|---|---|---|---|
| **2** | 2 | 3 | `stage-1` | Here | The room is mine — not because I took it, but because I'm already here. | I’m here, you’re here, so let’s make this worth the room. | 5 | +3 |
| **3** | 3 | 3 | `pitch-1` | Knife | Here's where the knife comes down — what actually matters. | Here’s the part that really matters. | 8 | +5 |
| **3** | 3 | 3 | `stage-2` | Air | I don't fill the air to feel in control — the space is already mine. | I don’t need to fill every second. Some points need space. | 7 | +4 |
| **3** | 3 | 3 | `stage-2` | Wait | I'm in no rush to fill it — watch the room wait for me. | I’m going to give that a second before we move on. | 8 | +5 |
| **3** | 3 | 3 | `stage-8` | pad | No thank-yous to pad it. Just the line — and the door. | No filler. Just this: the next move is yours. | 7 | +4 |
| **3** | 4 | 3 | `intimacy-12` | Presence | My desire for you comes from presence — not from needing you to complete me. | I want you because I’m here with you, not because I need you to fix something in me. | 6 | +3 |
| **3** | 4 | 3 | `composure-9` | Sweet | My choice stays mine — even when the room gets sweet. | My choice is still mine, even when the pitch is warm. | 4 | +1 |
| **3** | 4 | 3 | `gravitas-6` | Over | Bigger than me doesn't mean over me — not in this room. | You may have more authority here, but I still need to say what I see. | 8 | +5 |
| **3** | 5 | 3 | `composure-6` | Composure | I won't spend my composure on a conversation that's lost its center. | I’m not going to keep spending energy on a conversation that’s lost the point. | 7 | +4 |
| **3** | 3 | 5 | `gravitas-2` | Inside | Whatever's shaking inside stays inside — what you get from me is steady. | I may feel the pressure, but I’m going to stay steady for the room. | 6 | +3 |
| **3** | 5 | 3 | `stage-3` | stiffen | A lens doesn't make me stiffen. I breathe, I slow, I stay me. | The lens is just a person on the other side. I breathe, slow down, and stay myself. | 5 | +2 |
| **3** | 6 | 3 | `composure-9` | Bought | Good feeling isn't how my judgment gets bought. | A good feeling doesn’t change my judgment here. | 6 | +3 |
| **4** | 4 | 4 | `pitch-1` | Grab | This is the line that should grab you. | This is the part that should make you lean in. | 6 | +2 |
| **4** | 4 | 4 | `pitch-3` | Bridge | So here's the bridge from where we are to where this goes. | So here’s how we get from here to there. | 7 | +3 |
| **4** | 4 | 4 | `pitch-3` | Door | I'm opening one door — you decide if you walk through it. | I’m putting a real option in front of you. You can decide if it’s worth pursuing. | 7 | +3 |
| **4** | 4 | 4 | `pitch-3` | Room | I want to be the obvious person you back in this room. | I want to be the person you’re comfortable backing in this room. | 6 | +2 |
| **4** | 4 | 4 | `intimacy-7` | Crack | This isn't a crack in me — it's a choice. | This isn’t me falling apart. It’s me choosing to be honest with you. | 7 | +3 |
| **4** | 4 | 4 | `lead-11` | Up | I'm calling you up — not bending you down. There's a difference, and you'll feel it. | I’m asking more of you because I know you’re capable of more. | 9 | +5 |
| **4** | 4 | 4 | `composure-1` | Lever | My reaction is my choice — never your lever. | My reaction is mine to choose. I’m not handing it over. | 5 | +1 |
| **4** | 4 | 4 | `composure-3` | Tall | This isn't landing the way you hoped — I'm still standing exactly as tall. | That didn’t land the way you hoped. Let’s get back to the point. | 7 | +3 |
| **4** | 4 | 4 | `gravitas-2` | Voice | The room can shake — my voice will not. | Things may be moving fast, but I’m going to stay steady. | 7 | +3 |
| **4** | 4 | 4 | `gravitas-4` | Count | Ask in any order — I'll answer in the order that makes this count. | Ask in any order. I’ll answer in the order that makes the most sense. | 7 | +3 |
| **4** | 4 | 4 | `gravitas-6` | Fold | I don't fold for power, and I don't fight it — I just hold. | I’m not here to fight power. I’m here to stay with the facts. | 6 | +2 |
| **4** | 4 | 4 | `gravitas-9` | Calm | The loudest thing in this room is calm. Let it do the work. | Let’s bring the energy down so we can actually think. | 8 | +4 |
| **4** | 4 | 4 | `stage-1` | Singular | Let me talk to you — singular — not to a room. | I want to talk to one person in this room, not to a crowd. | 7 | +3 |
| **4** | 4 | 5 | `charisma-2` | Deal | Here's my deal: ninety seconds, and you'll be glad you stopped. | Give me ninety seconds. If I’m boring, I’ll let you escape. | 8 | +4 |
| **4** | 5 | 4 | `flirt-10` | Carry | Let's carry this into a night that can hold it. | Let’s continue this somewhere that gives it a little more room. | 7 | +3 |
| **4** | 5 | 4 | `intimacy-8` | Sift | I'll sift it — take what lands, leave what doesn't. Calmly. | I’ll sit with it and take in the part that’s true. | 7 | +3 |
| **4** | 5 | 4 | `lead-1` | Gather | Let's gather this for a second — so we're not all carrying it separately. | Let’s pull this together for a second so we’re all working from the same picture. | 8 | +4 |
| **4** | 5 | 4 | `composure-2` | Beside | I'll let that land beside me — not on me. | I’m going to let that pass without taking it on. | 7 | +3 |
| **4** | 5 | 4 | `composure-3` | Shrink | You can't shrink me by trying to — that's just not how I work. | Trying to put me down isn’t going to move the conversation forward. | 7 | +3 |
| **4** | 5 | 4 | `composure-9` | Anchor | I can enjoy the charm and still keep my anchor. | I can appreciate the charm and still keep my position. | 7 | +3 |
| **4** | 5 | 4 | `stage-8` | trail | I'm not going to trail off — I'm landing this, right here. | I’m going to land this plainly. | 5 | +1 |
| **4** | 6 | 4 | `intimacy-10` | Freedom | I won't make my fear the manager of your freedom. | I won’t let my fear turn into control. | 7 | +3 |
| **4** | 6 | 4 | `lead-8` | Fact | Give me the fact — then what you need from it. | Give me the fact first, then tell me what you need. | 6 | +2 |
| **4** | 6 | 4 | `lead-8` | Frame | I'll just hold the frame until you actually hear each other. | I’ll hold the structure for a minute so you can actually hear each other. | 5 | +1 |
| **4** | 6 | 4 | `lead-10` | Taller | When we name excellence accurately, everyone stands taller. | When we give credit accurately, the whole team gets stronger. | 6 | +2 |
| **4** | 6 | 4 | `composure-7` | Hesitation | My pause isn't hesitation — it's the weight of doing this right. | I’m pausing because I want to get this right, not because I’m unsure. | 8 | +4 |
| **4** | 6 | 4 | `gravitas-2` | Deliberate | I'm speaking deliberately — the moment needs it. | I’m going to slow down because this needs to be precise. | 8 | +4 |
| **4** | 6 | 4 | `gravitas-3` | Fog | We're deciding in fog — not in failure. | We’re making this call with incomplete information, not because we’ve failed. | 7 | +3 |
| **4** | 6 | 4 | `gravitas-7` | Become | We can't choose how this ends — only who we become getting there. | We can’t control exactly how this ends. We can control how we handle it. | 8 | +4 |
| **4** | 6 | 4 | `gravitas-8` | Unwind | Bring it back to the consequence we can't unwind. | Bring it back to the consequence we can’t undo. | 6 | +2 |
| **4** | 6 | 4 | `gravitas-9` | Lower | I'll speak lower — because the stakes are high. | I’m going to lower my voice because this needs clarity, not volume. | 7 | +3 |
| **4** | 6 | 4 | `stage-3` | fillers | I'll land each sentence — no fillers, no drift. | I’m going to keep this tight: no filler, no wandering. | 7 | +3 |
| **4** | 6 | 4 | `stage-6` | stumble | One stumble does not get to own the room. | One stumble doesn’t get the whole room. Let’s keep going. | 4 | 0 |
| **4** | 4 | 6 | `stage-6` | forgettable | Flawless would've been forgettable. This, you'll remember. | Well, that made it memorable. Now back to the point. | 8 | +4 |
| **4** | 7 | 4 | `charisma-9` | Microphone | We're all human — that one just got a microphone. | — | — | — |
| **4** | 7 | 4 | `intimacy-10` | Tightened | Something tightened in me tonight — and that one's mine to look at. | — | — | — |
| **4** | 7 | 4 | `intimacy-10` | Loud | I'm not accusing you — I'm naming the part of me that got loud. | — | — | — |
| **4** | 7 | 4 | `composure-7` | Clock | I'm not letting the clock outrank my judgment. | — | — | — |
| **4** | 7 | 4 | `composure-10` | Limited | What I can say now is limited — what I'll bring back is clear. | — | — | — |
| **4** | 7 | 4 | `composure-11` | Reduce | This result doesn't reduce me — it gives me information. | — | — | — |
| **4** | 7 | 4 | `gravitas-8` | Wear | I'll wear the pause — be mad at me later. | — | — | — |
| **4** | 7 | 4 | `gravitas-9` | Down | Let's bring the room down — nobody loses power by listening. | — | — | — |
| **4** | 7 | 4 | `stage-1` | Command | I'll speak slowly — because speed isn't the same as command. | — | — | — |
| **4** | 7 | 4 | `stage-5` | nerve | Thank you for the question with some nerve in it. Let's take it seriously. | — | — | — |
| **4** | 7 | 4 | `stage-7` | image | Hold that image. That's the lesson before I name it. | — | — | — |
| **4** | 8 | 4 | `charisma-6` | Clap | I'd clap, but you'd only encourage yourself. | — | — | — |
| **4** | 8 | 4 | `gravitas-8` | Permanent | We don't make permanent damage out of temporary heat. | — | — | — |
| **4** | 8 | 4 | `gravitas-10` | Lesson | The lesson isn't the pain — the lesson is what we change because of it. | — | — | — |
| **5** | 5 | 5 | `pitch-3` | Fit | The reason I'm bringing this to you specifically — it's a fit. | I’m bringing this to you specifically because I think it’s a strong fit. | 8 | +3 |
| **5** | 5 | 5 | `pitch-3` | Handshake | Let's not overthink it — handshake and we're moving. | Let’s not overthink it. If we’re aligned, let’s shake on it and move. | 8 | +3 |
| **5** | 5 | 5 | `charisma-1` | Momentum | Don't stop on my account — I love walking into momentum. | Don’t stop on my account. I like walking into a room with energy. | 7 | +2 |
| **5** | 5 | 5 | `flirt-8` | Smile | I caught that smile — I'm going to take it gently. | I caught that smile. I’m not going to overread it, but I noticed. | 7 | +2 |
| **5** | 5 | 5 | `intimacy-7` | Collapsing | I can say this without collapsing: I need you. | This is hard for me to say, but I need you. | 9 | +4 |
| **5** | 5 | 5 | `intimacy-7` | Steady | I'm telling you the truth because I'm steady enough to stand in it. | I’m telling you the truth because I feel steady enough to say it. | 6 | +1 |
| **5** | 5 | 5 | `intimacy-8` | Shatter | This doesn't shatter me — I can hear it and stay with you. | This is hard to hear, but I can hear it and stay with you. | 6 | +1 |
| **5** | 5 | 5 | `lead-11` | Waste | I'd rather expect a lot and mean it than flatter you and waste you. | I’d rather hold you to a high standard than pretend this is your best work. | 8 | +3 |
| **5** | 5 | 5 | `composure-1` | Button | My calm isn't a button you get to press. | You can try to push that button. I’m not going to give you the reaction. | 7 | +2 |
| **5** | 5 | 5 | `composure-2` | Inch | I know exactly who I am — that didn't move it an inch. | I know who I am. That didn’t change anything. | 8 | +3 |
| **5** | 5 | 5 | `composure-3` | Ounce | I don't lose an ounce of standing because you raised your voice. | Raising your voice doesn’t make your point stronger. | 8 | +3 |
| **5** | 5 | 5 | `gravitas-5` | Helm | I take the hit and I keep the helm. Both. Here's where we start. | I’m taking responsibility, and I’m staying in the seat to fix it. | 7 | +2 |
| **5** | 5 | 5 | `gravitas-7` | Upright | Whatever comes, we meet it upright. That part I guarantee. | Whatever happens, we’ll meet it honestly and stay steady. | 6 | +1 |
| **5** | 5 | 5 | `stage-3` | reads | I'm not acting for you — and that's exactly what reads. | I’m not going to perform at you. I’m just going to talk to you. | 8 | +3 |
| **5** | 5 | 5 | `stage-11` | thought | I don't need a plan. I've got a thought — and that's plenty. | I don’t need the original plan. The main idea still holds. | 7 | +2 |
| **5** | 6 | 5 | `pitch-1` | Catch | Most people miss this, and that's the whole catch. | Most people miss this, and that’s where the opportunity is. | 8 | +3 |
| **5** | 6 | 5 | `pitch-1` | Lean | Lean in — this is the part nobody talks about. | Here’s the part most people don’t talk about. | 8 | +3 |
| **5** | 5 | 6 | `charisma-2` | Watching | I've been watching the room — you're the only one not working it. | I noticed you’re the only one here who doesn’t seem to be working the room. | 7 | +2 |
| **5** | 6 | 5 | `charisma-10` | Casually | I don't make introductions casually — this one has range. | I don’t make introductions casually. I think this one could go somewhere. | 8 | +3 |
| **5** | 6 | 5 | `charisma-11` | Date | No backlog, no apologies — just give me a date. | No big apology, no long catch-up preface — just tell me when I can see you. | 6 | +1 |
| **5** | 6 | 5 | `flirt-3` | Smaller | I'm not going to make this smaller by explaining it. | I don’t want to over-explain it and ruin it. | 8 | +3 |
| **5** | 5 | 6 | `flirt-6` | Errand | I'm not offering you an errand — I'm offering you a night you'll remember. | I’m not asking you to squeeze me in. I’m asking you out properly. | 8 | +3 |
| **5** | 6 | 5 | `intimacy-2` | Dignity | I can hold my dignity and still stay close to you. | I don’t want to lose myself here, but I also don’t want to pull away from you. | 6 | +1 |
| **5** | 6 | 5 | `intimacy-9` | Desire | I want you in my future from desire — not from fear. | I want you in my future because I choose you, not because I’m afraid to be without you. | 7 | +2 |
| **5** | 6 | 5 | `lead-3` | Steady | Stay with me. We move steady from here. | Stay with me. We move steadily from here. | 5 | 0 |
| **5** | 6 | 5 | `lead-4` | Expensive | I'd rather be uncomfortable now than quiet and expensive later. | I’d rather have the uncomfortable conversation now than pay for the silence later. | 8 | +3 |
| **5** | 5 | 6 | `lead-5` | Landed | Here's the fact: you committed to this, and it didn't land. What happened? | Here’s the fact: you committed to this, and it didn’t happen. What got in the way? | 8 | +3 |
| **5** | 6 | 5 | `lead-5` | Dignity | I'm going to protect the standard without taking away your dignity. | I want to keep the standard high without making this personal. | 8 | +3 |
| **5** | 6 | 5 | `lead-10` | Light | I don't need to stand in someone else's light to be seen. | Giving someone else credit doesn’t take anything away from me. | 7 | +2 |
| **5** | 6 | 5 | `lead-11` | Invitation | This isn't pressure — it's an invitation to be who you already are at your best. | This isn’t pressure. It’s an invitation to do the level of work I know you can do. | 6 | +1 |
| **5** | 5 | 6 | `composure-1` | Strings | Pull all the strings you want — they're not attached to anything. | You can keep pulling on that. I’m not going with it. | 5 | 0 |
| **5** | 6 | 5 | `composure-2` | Worth | Your words don't get to define my worth. | That doesn’t define me, and I’m not going to treat it like it does. | 6 | +1 |
| **5** | 6 | 5 | `composure-4` | Own | A small miss doesn't get to own the room. | Small miss. Let’s not give it the whole room. | 4 | -1 |
| **5** | 6 | 5 | `composure-6` | Kindly | I'm going to step away kindly — not angrily. | I’m going to step away from this without anger. | 5 | 0 |
| **5** | 6 | 5 | `composure-9` | Lovely | Lovely words — I'm keeping them and my position both. | That’s kind of you to say. My position is still the same. | 8 | +3 |
| **5** | 6 | 5 | `stage-2` | Hang | I'll let that line hang. The silence is on my side. | I’ll let that line hang for a second. | 7 | +2 |
| **5** | 6 | 5 | `stage-4` | fuel | This isn't fear — it's fuel. Same chemistry, my label on it. | I’m going to use the nerves as fuel and keep going. | 7 | +2 |
| **5** | 5 | 6 | `stage-6` | fall | It's not the fall — it's how I get up. Watch. | The recovery is the point. Let’s keep going. | 6 | +1 |
| **5** | 6 | 5 | `stage-7` | wait | And here's the turn. [pause] Wait for it. | And here’s the turn. Pause with me for a second. | 5 | 0 |
| **5** | 6 | 5 | `stage-8` | believe | You walked in as a crowd. You're leaving as people I believe in. | You walked in as a crowd. I hope you leave feeling personally responsible for what happens next. | 6 | +1 |
| **5** | 6 | 5 | `stage-9` | armor | I don't want to put on armor and call it transparency. | I don’t want to hide behind corporate language and call it transparency. | 8 | +3 |
| **5** | 7 | 5 | `charisma-1` | Name | Let me name the thing the room's been circling. | — | — | — |
| **5** | 5 | 7 | `charisma-4` | Changed | Going around: one thing you've changed your mind about this year — I'll start. | Let’s go around: what’s one thing you’ve changed your mind about this year? I’ll start. | 8 | +3 |
| **5** | 5 | 7 | `flirt-3` | Away | This is the part where someone usually looks away — I won't. | This is the part where people usually look away. I kind of don’t want to. | 7 | +2 |
| **5** | 7 | 5 | `flirt-8` | Space | No ego in it — if you want space, it's yours, no story attached. | — | — | — |
| **5** | 7 | 5 | `flirt-9` | Linger | I'd rather leave you wanting than overstay — let it linger. | — | — | — |
| **5** | 7 | 5 | `intimacy-5` | Line | I'm staying connected — and I'm not moving the line. | — | — | — |
| **5** | 7 | 5 | `intimacy-9` | Imagine | I'd love space to imagine what we're building — not just what we're managing. | — | — | — |
| **5** | 7 | 5 | `intimacy-10` | Crime | This is my fear to hold — not your crime to answer for. | — | — | — |
| **5** | 7 | 5 | `intimacy-12` | Ordinary | You make ordinary moments feel chosen. | — | — | — |
| **5** | 7 | 5 | `lead-1` | Got | I've got us for now. Let's move. | — | — | — |
| **5** | 5 | 7 | `lead-8` | Crown | I'm not here to crown a winner — I'm here to get you hearing each other. | I’m not here to pick a winner. I’m here to get us to a workable answer. | 8 | +3 |
| **5** | 7 | 5 | `lead-9` | Heavy | This is heavy — and I want to meet it with you honestly. | — | — | — |
| **5** | 7 | 5 | `lead-10` | Smaller | Lifting them doesn't make me smaller. | — | — | — |
| **5** | 7 | 5 | `lead-11` | Ceiling | I can see the ceiling you're capable of — and we're nowhere near it yet. | — | — | — |
| **5** | 7 | 5 | `composure-1` | Role | I'm not going to take the role you're offering me. | — | — | — |
| **5** | 7 | 5 | `composure-1` | Fishing | I won't perform the reaction you're fishing for. | — | — | — |
| **5** | 7 | 5 | `composure-4` | Public | I can be human in public and still be clear. | — | — | — |
| **5** | 7 | 5 | `gravitas-2` | Clear | Clear voices, clean facts, no extra noise. | — | — | — |
| **5** | 7 | 5 | `gravitas-4` | Directly | I'll answer that directly: yes, that one sits with us. | — | — | — |
| **5** | 7 | 5 | `gravitas-5` | Theater | No one here needs theater — we need steadiness and truth. | — | — | — |
| **5** | 7 | 5 | `gravitas-6` | Threat | A threat may change the temperature — it won't change my read. | — | — | — |
| **5** | 7 | 5 | `gravitas-7` | Presence | What I can give you right now is honesty, steadiness, and presence. | — | — | — |
| **5** | 7 | 5 | `gravitas-7` | Promise | I won't promise the result — I promise the way we meet it. | — | — | — |
| **5** | 7 | 5 | `gravitas-10` | Exit | This crisis won't define us — our exit from it will. | — | — | — |
| **5** | 7 | 5 | `stage-1` | Settle | Let the room settle — I'm not rushing the first sentence. | — | — | — |
| **5** | 7 | 5 | `stage-3` | lens | I'm looking right at you — one person — not a lens. | — | — | — |
| **5** | 7 | 5 | `stage-3` | performance | The camera doesn't need a performance. It needs presence. | — | — | — |
| **5** | 7 | 5 | `stage-5` | steady | The question was sharp. The answer will be steady. | — | — | — |
| **5** | 7 | 5 | `stage-6` | blank | Total blank just now. Happens to the best of me. | — | — | — |
| **5** | 7 | 5 | `stage-7` | sit | [long pause] ...I'll let that sit. Some things land harder in silence. | — | — | — |
| **5** | 7 | 5 | `stage-9` | chopped | Let me give you that in one line they can't chop up. | — | — | — |
| **5** | 7 | 5 | `stage-9` | spotlight | The spotlight doesn't change my answer. It only raises the standard for it. | — | — | — |
| **5** | 8 | 5 | `charisma-7` | Risk | You caught the risk before the room had language for it. | — | — | — |
| **5** | 8 | 5 | `intimacy-9` | Disappear | I'm willing to build something real — but I won't disappear from myself to keep it. | — | — | — |
| **5** | 8 | 5 | `intimacy-11` | Adults | I want us to meet as adults — not as old roles. | — | — | — |
| **5** | 8 | 5 | `composure-1` | Table | I'm going to leave that one on the table. | — | — | — |
| **5** | 8 | 5 | `composure-2` | Unsaid | I'll give you the chance to leave that one unsaid. | — | — | — |
| **5** | 8 | 5 | `composure-2` | Dig | Say the real thing, not the dig — I'll happily take the real thing. | — | — | — |
| **5** | 8 | 5 | `composure-3` | Substance | Give me the substance — and I'll stand right here and take it. | — | — | — |
| **5** | 8 | 5 | `composure-5` | Respect | I can give you respect without giving you more reasons. | — | — | — |
| **5** | 8 | 5 | `composure-5` | Selling | I'm not selling you my boundaries — I'm stating them. | — | — | — |
| **5** | 8 | 5 | `composure-8` | Condition | Respect is the condition for this conversation — not the reward. | — | — | — |
| **5** | 8 | 5 | `composure-9` | Warmth | I appreciate the warmth — and I'd like to keep the question clean. | — | — | — |
| **5** | 8 | 5 | `gravitas-1` | Ground | Get your feet on the ground — I've got the room. | — | — | — |
| **5** | 8 | 5 | `gravitas-1` | Alone | Nobody handles this alone — stay visible. | — | — | — |
| **5** | 8 | 5 | `gravitas-1` | Count | Move on my count — not on panic. | — | — | — |
| **5** | 8 | 5 | `gravitas-2` | Slow | Let's slow the room down — we do the next right thing first. | — | — | — |
| **5** | 8 | 5 | `gravitas-7` | Unknown | Honest version: it's unknown. Also honest: you're not facing it alone. | — | — | — |
| **5** | 8 | 5 | `gravitas-8` | Hold | Hold on one second — let's bring the room down before we move. | — | — | — |
| **5** | 8 | 5 | `gravitas-9` | Quieter | Stay with me — we'll get further together if we get quieter. | — | — | — |
| **5** | 8 | 5 | `gravitas-9` | Signal | Stop adding noise — give me the signal. | — | — | — |
| **5** | 8 | 5 | `gravitas-10` | Sharpest | Take a breath — we got through the sharpest part together. | — | — | — |
| **5** | 8 | 5 | `stage-3` | glass | There's glass between us, but I don't want this to feel distant. | — | — | — |
| **5** | 8 | 5 | `stage-4` | floor | Feet flat on the floor. One slow breath. Begin. | — | — | — |
| **5** | 8 | 5 | `stage-4` | ready | I don't wait to feel ready — I start, and ready catches up. | — | — | — |
| **5** | 8 | 5 | `stage-6` | where | Here's where we were before the room took that little detour. | — | — | — |
| **5** | 8 | 5 | `stage-8` | test | This is the end of the talk. It is the start of the test. | — | — | — |
| **5** | 8 | 5 | `stage-8` | sentence | I'll stop here. The next sentence is yours. | — | — | — |
| **5** | 8 | 5 | `stage-10` | spectacle | One real moment beats any amount of spectacle. | — | — | — |
| **5** | 8 | 5 | `stage-11` | live | Good. We get to make this live instead of polished. | — | — | — |
| **5** | 9 | 5 | `composure-4` | Cleanly | Let me correct that cleanly — before I make the real point. | — | — | — |
| **5** | 9 | 5 | `stage-2` | Slow | I'm going to slow this down — it deserves precision. | — | — | — |
| **5** | 9 | 5 | `stage-5` | premise | I'd challenge the premise — but the question under it is fair, so here it is. | — | — | — |
| **5** | 9 | 5 | `stage-11` | core | Let me cut to the core — there's really just one idea here. | — | — | — |
| **6** | 6 | 6 | `batch-3` | Underneath | Help me see what's really going on underneath. | Help me understand what’s really driving this. | 9 | +3 |
| **6** | 6 | 6 | `pitch-1` | Picture | Picture this — it's Monday morning and the whole thing already broke. | Picture this: it’s Monday morning, and the whole thing is already on fire. | 8 | +2 |
| **6** | 6 | 6 | `pitch-2` | Tide | The tide just turned — and here's why now. | The tide just turned, and here’s why that matters now. | 6 | 0 |
| **6** | 6 | 6 | `pitch-3` | Skin | I've got skin in this — I'm not asking you to go where I won't. | I’ve got skin in the game. I’m not asking you to take a risk I’m not taking myself. | 9 | +3 |
| **6** | 6 | 6 | `charisma-2` | Read | You look like you've got the real read on this room. | You look like you’ve got the best read on this room. | 7 | +1 |
| **6** | 6 | 6 | `flirt-5` | Charge | I'm enjoying the charge here — I don't want to pretend it's casual. | I’m enjoying the chemistry here, and I don’t really want to pretend it’s casual. | 7 | +1 |
| **6** | 6 | 6 | `flirt-7` | Dent | A no doesn't dent me — and it shouldn't cost you a thing. | A no is totally fine. I don’t want it to make things weird for you. | 9 | +3 |
| **6** | 6 | 6 | `flirt-8` | Pace | I like your pace — it makes me want to match it. | I like your pace. I’m happy to follow it. | 7 | +1 |
| **6** | 6 | 6 | `flirt-9` | Read | This is where I leave before I become too easy to read. | This is where I leave before I give away too much. | 7 | +1 |
| **6** | 6 | 6 | `flirt-10` | Almosts | Before this becomes one of those great almosts — let's put a plan on it. | Before this turns into one of those almosts, let’s put an actual plan on the calendar. | 6 | 0 |
| **6** | 6 | 6 | `flirt-10` | Electricity | Give me your number — I'll make sure the next time has the same electricity. | Give me your number. I’ll make sure the next time feels just as good. | 7 | +1 |
| **6** | 6 | 6 | `intimacy-1` | Close | I want to talk about something — because I want us close, not because I want us hurt. | I want to talk about something because I want us to feel close, not hurt each other. | 7 | +1 |
| **6** | 6 | 6 | `intimacy-3` | Reach | I'm reaching out first, on purpose. Take my hand. | I’m reaching out first because I don’t want this distance between us. | 8 | +2 |
| **6** | 6 | 6 | `intimacy-8` | Grow | I don't need to defend my way out of this — I'd rather just grow. | I don’t want to defend my way out of this. I want to learn from it. | 7 | +1 |
| **6** | 6 | 6 | `lead-1` | Steer | Someone's got to steer this — so I will. Call it the moment you disagree. | Someone needs to steer this, so I’ll do it for now. Stop me if you disagree. | 8 | +2 |
| **6** | 6 | 6 | `lead-2` | Yours | The part that excites me most is the piece that's so clearly yours. | The part that excites me most is the piece only you can really own. | 6 | 0 |
| **6** | 6 | 6 | `composure-2` | Describes | What you just said describes you, not me. | That says more about the tone of this conversation than it does about me. | 7 | +1 |
| **6** | 6 | 6 | `composure-6` | Afraid | I'm not leaving because I'm afraid — I'm leaving because this deserves better. | I’m not walking away from the issue. I’m walking away from the way we’re talking about it. | 8 | +2 |
| **6** | 6 | 6 | `stage-4` | run | Fear doesn't run this room. I do. | The nerves don’t get to run this room. I do. | 6 | 0 |
| **6** | 6 | 6 | `stage-10` | tell | Some of you are feeling it right now — I can tell. That's exactly the point. | Some of you are feeling it right now. That’s exactly the point. | 7 | +1 |
| **6** | 7 | 6 | `pitch-2` | Crack | There's a crack in how everyone does this today. | — | — | — |
| **6** | 7 | 6 | `pitch-3` | Seal | Give me the green light and I'll seal it by Friday. | — | — | — |
| **6** | 6 | 7 | `repair-1` | Better | I'll do better from here. | I’ll do better going forward. | 8 | +2 |
| **6** | 6 | 7 | `charisma-3` | Light | You lit up when you said that — what's underneath it? | You lit up when you said that. What’s behind it? | 8 | +2 |
| **6** | 7 | 6 | `charisma-4` | Truth | We've got enough charm at this table — let's add a little truth. | — | — | — |
| **6** | 7 | 6 | `charisma-4` | Safe | Let's not waste a good table on safe answers. | — | — | — |
| **6** | 7 | 6 | `charisma-7` | Level | You didn't just answer it — you changed the level of the conversation. | — | — | — |
| **6** | 7 | 6 | `charisma-7` | Authority | That's a rare kind of authority — quiet, clean, and earned. | — | — | — |
| **6** | 7 | 6 | `charisma-7` | Remember | Remember I called it — you're going to be the one they all reference. | — | — | — |
| **6** | 6 | 7 | `charisma-11` | List | I keep a very short list of people worth keeping — you never came off it. | There are very few people I’d go out of my way to keep in my life — you’re one of them. | 8 | +2 |
| **6** | 6 | 7 | `flirt-1` | Lightly | I don't give my attention lightly — and you have it. | I don’t get pulled in that easily, but you’ve got my attention. | 8 | +2 |
| **6** | 6 | 7 | `flirt-1` | Easy | I've said my piece — where it goes is up to you, and I'm easy either way. | I’ve said my piece. Where it goes is up to you, and I’m good either way. | 8 | +2 |
| **6** | 7 | 6 | `flirt-3` | Pause | I like this little pause between us. | — | — | — |
| **6** | 6 | 7 | `flirt-3` | Comfortable | I'm comfortable right here — the question is whether you are. | I’m comfortable with this. Are you? | 8 | +2 |
| **6** | 6 | 7 | `flirt-4` | Full | You've got my full attention — that's rarer than it sounds. | You’ve got my full attention, which doesn’t happen that often. | 8 | +2 |
| **6** | 7 | 6 | `flirt-5` | Tempted | I'm tempted to give this conversation a little more room. | — | — | — |
| **6** | 7 | 6 | `flirt-6` | Coffee | Give me one evening — and I promise it won't be a coffee. | — | — | — |
| **6** | 6 | 7 | `flirt-6` | Boring | I don't do boring — say yes and find out exactly what I mean. | I don’t do boring dates. Say yes and I’ll prove it. | 8 | +2 |
| **6** | 7 | 6 | `flirt-7` | Safe | Your no is safe with me — no awkwardness. | — | — | — |
| **6** | 7 | 6 | `flirt-7` | Clarity | I can take a clear no — I'd rather have clarity than performance. | — | — | — |
| **6** | 7 | 6 | `flirt-8` | Force | I don't need to force the moment — I'd rather follow what's actually here. | — | — | — |
| **6** | 7 | 6 | `flirt-8` | Signal | I'll follow the signal you give me — not the one I want. | — | — | — |
| **6** | 7 | 6 | `flirt-9` | Explained | Not everything good needs to be explained on the first pass. | — | — | — |
| **6** | 6 | 7 | `intimacy-1` | Survive | Whatever gets said, we're still us when it's over. We survive this. | Whatever gets said, I want us to stay connected through it. | 6 | 0 |
| **6** | 7 | 6 | `intimacy-2` | Tender | That landed somewhere tender. I'm not angry — I just want you to know. | — | — | — |
| **6** | 7 | 6 | `intimacy-2` | Gentle | We can be hurt and still be gentle. And I'm choosing gentle. | — | — | — |
| **6** | 7 | 6 | `intimacy-7` | Weak | I'm telling you because it matters — not because I'm weak. | — | — | — |
| **6** | 7 | 6 | `intimacy-8` | Truth | There's truth in that — and I want the rest of it, not less. | — | — | — |
| **6** | 7 | 6 | `intimacy-9` | Dream | Can we dream out loud together for a bit? No pressure — just us. | — | — | — |
| **6** | 7 | 6 | `intimacy-11` | Concern | I hear the concern underneath it — let's not fight over the form. | — | — | — |
| **6** | 7 | 6 | `intimacy-12` | Want | I want you — and I like that I can say it without making it cheap. | — | — | — |
| **6** | 7 | 6 | `intimacy-12` | Pull | There's still a pull in me every time you look at me like that. | — | — | — |
| **6** | 7 | 6 | `intimacy-12` | Whole | I choose you with my eyes open — the tender parts and the difficult ones. | — | — | — |
| **6** | 7 | 6 | `lead-2` | Hope | I've thought this through — it's not a hope, it's a path. | — | — | — |
| **6** | 7 | 6 | `lead-3` | Ground | Let's get our feet back on the ground — together. | — | — | — |
| **6** | 7 | 6 | `lead-4` | Risk | I don't see it the same way — and here's the risk I'm carrying. | — | — | — |
| **6** | 7 | 6 | `lead-6` | Hit | I'll take the hit — and we'll move with the lesson. | — | — | — |
| **6** | 7 | 6 | `lead-7` | Alone | You're right to expect better — and I'm not leaving them alone with that. | — | — | — |
| **6** | 7 | 6 | `lead-9` | Through | I'm staying with you through the hard part — not just the announcement. | — | — | — |
| **6** | 7 | 6 | `lead-11` | Bar | Here's the bar: not 'fine,' but the thing people remember. | — | — | — |
| **6** | 7 | 6 | `composure-4` | Flustered | I don't get flustered over a slip. Onward. | — | — | — |
| **6** | 7 | 6 | `composure-7` | Mull | Let me mull this for a moment. | — | — | — |
| **6** | 7 | 6 | `composure-7` | Stopwatch | Good decisions don't get made on a stopwatch. | — | — | — |
| **6** | 7 | 6 | `composure-8` | Lower | I won't lower myself to answer that in kind. | — | — | — |
| **6** | 7 | 6 | `composure-8` | Level | I'm not coming down to that level — meet me at this one, and we'll talk. | — | — | — |
| **6** | 7 | 6 | `gravitas-5` | Serious | Yes, it's serious — that's exactly why I'm not letting go of the wheel. | — | — | — |
| **6** | 7 | 6 | `gravitas-9` | Outshout | I'm not going to outshout the room — I'm going to steady it. | — | — | — |
| **6** | 7 | 6 | `gravitas-10` | Discipline | We held the line — now we build the discipline that keeps it from breaking again. | — | — | — |
| **6** | 7 | 6 | `stage-3` | kitchen | Picture us in your kitchen, not on a screen. | — | — | — |
| **6** | 7 | 6 | `stage-4` | momentum | Just land the first line. Momentum takes it from there. | — | — | — |
| **6** | 7 | 6 | `stage-5` | gift | A tough question is a gift — it lets me clear this up for everyone. | — | — | — |
| **6** | 7 | 6 | `stage-9` | cycle | I set the tone of this conversation, not the news cycle. | — | — | — |
| **6** | 7 | 6 | `stage-10` | whisper | I could shout this — but a whisper in a room this size hits harder. | — | — | — |
| **6** | 7 | 6 | `stage-10` | seen | My job is not to fill the room. It's to make each of you feel seen. | — | — | — |
| **6** | 6 | 7 | `stage-11` | raw | Unscripted and raw beats polished and dead. Lucky you. | Unscripted beats polished when the room is right. Lucky us. | 6 | 0 |
| **6** | 8 | 6 | `negotiation-1` | Line | That's my line — I won't go below it. | — | — | — |
| **6** | 8 | 6 | `charisma-2` | Usual | Before the usual small talk — what's actually worth knowing here? | — | — | — |
| **6** | 8 | 6 | `charisma-3` | Pattern | What I'm hearing is, you saw the pattern early. | — | — | — |
| **6** | 8 | 6 | `charisma-3` | Bet | When you're eighty, which of these will you be glad you bet on? | — | — | — |
| **6** | 8 | 6 | `charisma-4` | Corner | Let's bring the quiet corner in — I want that side of the table. | — | — | — |
| **6** | 8 | 6 | `charisma-6` | Proud | My mother would be so proud you finally noticed. | — | — | — |
| **6** | 6 | 8 | `charisma-7` | Lightly | I don't say this lightly — | I don’t say this lightly: that was excellent. | 8 | +2 |
| **6** | 8 | 6 | `charisma-8` | Selfish | I'd keep you all night if I weren't trying to be less selfish about it. | — | — | — |
| **6** | 8 | 6 | `charisma-8` | Mystery | Let's leave a little mystery for the next one. | — | — | — |
| **6** | 8 | 6 | `charisma-9` | Reset | Let's give that a clean reset. | — | — | — |
| **6** | 8 | 6 | `charisma-9` | Dwell | I'm not going to dwell on it — and I'd advise you not to either. | — | — | — |
| **6** | 8 | 6 | `charisma-11` | Properly | No long preface — I'd like to reconnect properly. | — | — | — |
| **6** | 8 | 6 | `flirt-7` | Grown-ups | Let's be the two people who handled this like grown-ups. | — | — | — |
| **6** | 8 | 6 | `flirt-8` | Reading | I'm reading interest — but I'd rather check than assume. | — | — | — |
| **6** | 8 | 6 | `flirt-10` | Disappear | I don't want this to disappear into the night — give me a way to continue it. | — | — | — |
| **6** | 8 | 6 | `intimacy-1` | Softly | Can we go into this softly? It matters to me — and so do you. | — | — | — |
| **6** | 8 | 6 | `intimacy-1` | Name | I need to name something between us without turning it into blame. | — | — | — |
| **6** | 8 | 6 | `intimacy-2` | Differently | Can you say that again differently? That version I can't quite hear. | — | — | — |
| **6** | 8 | 6 | `intimacy-5` | Protecting | I'm not pulling away from you — I'm protecting something I need. | — | — | — |
| **6** | 8 | 6 | `intimacy-5` | Limit | This is about my limit — not about you as a person. | — | — | — |
| **6** | 8 | 6 | `intimacy-5` | Explain | I'm not available for that — and I'm not going to over-explain it. | — | — | — |
| **6** | 8 | 6 | `intimacy-7` | Closeness | What I need right now is closeness — not a solution. | — | — | — |
| **6** | 8 | 6 | `intimacy-10` | Trust | I can feel jealous and still choose trust. | — | — | — |
| **6** | 8 | 6 | `intimacy-11` | Court | I'm not going to defend my life like a case in court. | — | — | — |
| **6** | 8 | 6 | `intimacy-12` | Closer | Come closer — I've been wanting less room between us. | — | — | — |
| **6** | 8 | 6 | `intimacy-12` | Stay | After all this time, I still want to stay curious about you. | — | — | — |
| **6** | 8 | 6 | `lead-1` | Tie | Let me tie a few of these threads together for us. | — | — | — |
| **6** | 8 | 6 | `lead-2` | Direction | The direction is clear: smaller, sharper, and useful enough to matter. | — | — | — |
| **6** | 8 | 6 | `lead-2` | Believe | I believe in this enough to put my name on the first step. | — | — | — |
| **6** | 8 | 6 | `lead-3` | Calm | I'm going to stay calm enough for all of us to think. | — | — | — |
| **6** | 8 | 6 | `lead-4` | Owe | You own the call — I owe you the cleanest version of what I see. | — | — | — |
| **6** | 8 | 6 | `lead-5` | Broke | Help me see where the chain broke. | — | — | — |
| **6** | 8 | 6 | `lead-6` | Guessing | Let me name it plainly — so no one's left guessing. | — | — | — |
| **6** | 8 | 6 | `lead-6` | Missed | I moved too fast and missed the part that should've slowed me down. | — | — | — |
| **6** | 8 | 6 | `lead-7` | Through | My team, my responsibility — you come through me. | — | — | — |
| **6** | 8 | 6 | `lead-8` | Closer | I hear both of you — and we're closer to the same concern than it sounds. | — | — | — |
| **6** | 8 | 6 | `lead-8` | Outcome | You both want the same outcome — that's the part to stand on. | — | — | — |
| **6** | 8 | 6 | `lead-10` | Visible | I want to make that contribution visible — it changed the outcome. | — | — | — |
| **6** | 8 | 6 | `lead-10` | Belongs | Credit belongs there — that was her judgment call, not mine. | — | — | — |
| **6** | 8 | 6 | `lead-10` | Carried | If we're naming the win, let's name who carried it. | — | — | — |
| **6** | 8 | 6 | `lead-11` | Costing | 'Good enough' is costing us the thing we actually care about. | — | — | — |
| **6** | 8 | 6 | `composure-1` | Designed | That was designed to get a reaction — I noticed, and I'll pass. | — | — | — |
| **6** | 8 | 6 | `composure-3` | Volume | No need to raise the volume — I hear you fine. | — | — | — |
| **6** | 8 | 6 | `composure-5` | Standing | I've given you the decision I'm comfortable standing behind. | — | — | — |
| **6** | 8 | 6 | `composure-5` | Reasons | Adding more reasons would only make this less clear. | — | — | — |
| **6** | 8 | 6 | `composure-5` | Argument | My 'no' doesn't need a closing argument. | — | — | — |
| **6** | 8 | 6 | `composure-6` | Damage | I don't want this to do more damage than it solves. | — | — | — |
| **6** | 8 | 6 | `composure-6` | Attacks | I'm open to the issue — not the attacks around it. | — | — | — |
| **6** | 8 | 6 | `composure-7` | Sloppy | I hear the urgency — a moment now saves you a sloppy answer. | — | — | — |
| **6** | 8 | 6 | `composure-7` | Speed | I'm not making a call this size on speed alone. | — | — | — |
| **6** | 8 | 6 | `composure-8` | Again | Say that again in a way I can actually work with. | — | — | — |
| **6** | 8 | 6 | `composure-8` | Ways | Here's how it works with me: respect runs both ways. | — | — | — |
| **6** | 8 | 6 | `composure-9` | Guilt | That's the guilt angle — I see it, and it doesn't change the question. | — | — | — |
| **6** | 8 | 6 | `composure-10` | Trouble | Not knowing that doesn't trouble me — pretending to would. | — | — | — |
| **6** | 8 | 6 | `composure-11` | Sharpen | Fair outcome — what should I sharpen for next time? | — | — | — |
| **6** | 8 | 6 | `gravitas-2` | Breath | Stay with me. One breath — then the next step. | — | — | — |
| **6** | 8 | 6 | `gravitas-2` | Frightening | This is frightening — and we can still think clearly. | — | — | — |
| **6** | 8 | 6 | `gravitas-3` | Downside | I'm choosing the option that limits the downside we can't recover from. | — | — | — |
| **6** | 8 | 6 | `gravitas-3` | Call | This is my call — and I'll carry the consequence. | — | — | — |
| **6** | 8 | 6 | `gravitas-4` | Heat | I understand the heat in the room — let's make it useful. | — | — | — |
| **6** | 8 | 6 | `gravitas-4` | Rushed | I won't be rushed into a weaker answer because the room is loud. | — | — | — |
| **6** | 8 | 6 | `gravitas-5` | Affected | To everyone affected: I see what this did, and I'm not looking away. | — | — | — |
| **6** | 8 | 6 | `gravitas-5` | Recovery | The damage is real — and so is the recovery. It begins right now. | — | — | — |
| **6** | 8 | 6 | `gravitas-6` | Diminish | I'm not here to diminish anyone's position — I'm here to solve the problem. | — | — | — |
| **6** | 8 | 6 | `gravitas-6` | Rank | Rank won't settle this — facts and consequences will. | — | — | — |
| **6** | 8 | 6 | `gravitas-6` | Title | Your title doesn't make you right — and it doesn't make me small. | — | — | — |
| **6** | 8 | 6 | `gravitas-7` | Measure | We measure ourselves by how we show up — not by what we can't control. | — | — | — |
| **6** | 8 | 6 | `gravitas-8` | Adrenaline | We're not crossing an irreversible line on adrenaline. | — | — | — |
| **6** | 8 | 6 | `gravitas-10` | Closed | The emergency phase is closed — we're moving into recovery. | — | — | — |
| **6** | 8 | 6 | `stage-1` | Back | I can see the back row — hi, you count too. | — | — | — |
| **6** | 8 | 6 | `stage-2` | Lean | Lean in with me for this next part. | — | — | — |
| **6** | 8 | 6 | `stage-2` | Soak | Let that soak for a second before we move on. | — | — | — |
| **6** | 8 | 6 | `stage-3` | crisp | Three things. Crisp. Then I'm done. | — | — | — |
| **6** | 8 | 6 | `stage-3` | thread | Here's the thread I want you to follow. | — | — | — |
| **6** | 8 | 6 | `stage-4` | heart | I'll be honest — my heart's going. Bear with me; I care about this. | — | — | — |
| **6** | 8 | 6 | `stage-5` | heat | Let me take the heat out of the question and keep the concern. | — | — | — |
| **6** | 8 | 6 | `stage-5` | audience | I'm not here to fight the questioner. I'm here to serve the audience. | — | — | — |
| **6** | 8 | 6 | `stage-6` | resume | No big apology — let's just resume. | — | — | — |
| **6** | 8 | 6 | `stage-6` | rails | Let me get back on the rails — here's the real point. | — | — | — |
| **6** | 8 | 6 | `stage-7` | stakes | The stakes were simple: if we got this wrong, the whole thing changed. | — | — | — |
| **6** | 8 | 6 | `stage-10` | between | Let me drop my voice. This next part's just between us. | — | — | — |
| **6** | 8 | 6 | `stage-10` | person | Bring to mind one person this is really about. Hold them there. | — | — | — |
| **6** | 8 | 6 | `stage-11` | prepped | You're not quite the room I prepped for — so let's make this about you. | — | — | — |
| **6** | 8 | 6 | `stage-11` | shape | Here's the new shape: one story, one lesson, one decision. | — | — | — |
| **6** | 8 | 6 | `stage-11` | net | No net today — and that's when I'm actually at my best. | — | — | — |
| **6** | 9 | 6 | `intimacy-6` | Smaller | You don't have to make your pain smaller so I can handle it. | — | — | — |
| **6** | 9 | 6 | `intimacy-8` | Defend | I can feel myself wanting to defend — but I want to hear you first. | — | — | — |
| **6** | 9 | 6 | `intimacy-10` | Reassurance | I don't need to police you — I need reassurance, and I can just ask for it. | — | — | — |
| **6** | 9 | 6 | `lead-9` | News | Here's the news, plainly: the plan has changed, and the impact is real. | — | — | — |
| **6** | 9 | 6 | `composure-3` | Concern | I can hear the concern without accepting the tone. | — | — | — |
| **6** | 9 | 6 | `composure-5` | Brief | I'm going to keep this kind and brief. | — | — | — |
| **6** | 9 | 6 | `composure-5` | Silence | I can let the silence sit — I don't need to fill it. | — | — | — |
| **6** | 9 | 6 | `composure-10` | Bluff | I won't bluff my way through an answer just to fill the room. | — | — | — |
| **6** | 9 | 6 | `gravitas-1` | Eyes | Eyes on me. We breathe — then we move. | — | — | — |
| **6** | 9 | 6 | `gravitas-4` | Tone | I'm not answering the tone — I'm answering the substance. | — | — | — |
| **6** | 9 | 6 | `gravitas-7` | Step | The whole road isn't visible — but the next step is. | — | — | — |
| **6** | 9 | 6 | `gravitas-8` | Escalation | This is escalation — not decision-making. | — | — | — |
| **6** | 9 | 6 | `gravitas-9` | Point | One point at a time — the first one is safety. | — | — | — |
| **6** | 9 | 6 | `gravitas-9` | Pause | We pause. We hear the facts. Then we decide. | — | — | — |
| **6** | 9 | 6 | `stage-5` | bait | I'm not taking the bait on the framing — but the substance, I'll answer. | — | — | — |

## Замены, которые сами не годятся (балл замены ≤6) — нужен новый вариант

| Батч | Якорь | Мин ориг. | Замена (GPT) | F(зам) | Δ |
|---|---|---|---|---|---|
| `composure-4` | Own | 5 | Small miss. Let’s not give it the whole room. | 4 | -1 |
| `composure-9` | Sweet | 3 | My choice is still mine, even when the pitch is warm. | 4 | +1 |
| `stage-6` | stumble | 4 | One stumble doesn’t get the whole room. Let’s keep going. | 4 | 0 |
| `lead-3` | Steady | 5 | Stay with me. We move steadily from here. | 5 | 0 |
| `lead-8` | Frame | 4 | I’ll hold the structure for a minute so you can actually hear each other. | 5 | +1 |
| `composure-1` | Strings | 5 | You can keep pulling on that. I’m not going with it. | 5 | 0 |
| `composure-1` | Lever | 4 | My reaction is mine to choose. I’m not handing it over. | 5 | +1 |
| `composure-6` | Kindly | 5 | I’m going to step away from this without anger. | 5 | 0 |
| `stage-1` | Here | 2 | I’m here, you’re here, so let’s make this worth the room. | 5 | +3 |
| `stage-3` | stiffen | 3 | The lens is just a person on the other side. I breathe, slow down, and stay myself. | 5 | +2 |
| `stage-7` | wait | 5 | And here’s the turn. Pause with me for a second. | 5 | 0 |
| `stage-8` | trail | 4 | I’m going to land this plainly. | 5 | +1 |
| `pitch-1` | Grab | 4 | This is the part that should make you lean in. | 6 | +2 |
| `pitch-2` | Tide | 6 | The tide just turned, and here’s why that matters now. | 6 | 0 |
| `pitch-3` | Room | 4 | I want to be the person you’re comfortable backing in this room. | 6 | +2 |
| `charisma-11` | Date | 5 | No big apology, no long catch-up preface — just tell me when I can see you. | 6 | +1 |
| `flirt-10` | Almosts | 6 | Before this turns into one of those almosts, let’s put an actual plan on the calendar. | 6 | 0 |
| `intimacy-1` | Survive | 6 | Whatever gets said, I want us to stay connected through it. | 6 | 0 |
| `intimacy-2` | Dignity | 5 | I don’t want to lose myself here, but I also don’t want to pull away from you. | 6 | +1 |
| `intimacy-7` | Steady | 5 | I’m telling you the truth because I feel steady enough to say it. | 6 | +1 |
| `intimacy-8` | Shatter | 5 | This is hard to hear, but I can hear it and stay with you. | 6 | +1 |
| `intimacy-12` | Presence | 3 | I want you because I’m here with you, not because I need you to fix something in me. | 6 | +3 |
| `lead-2` | Yours | 6 | The part that excites me most is the piece only you can really own. | 6 | 0 |
| `lead-8` | Fact | 4 | Give me the fact first, then tell me what you need. | 6 | +2 |
| `lead-10` | Taller | 4 | When we give credit accurately, the whole team gets stronger. | 6 | +2 |
| `lead-11` | Invitation | 5 | This isn’t pressure. It’s an invitation to do the level of work I know you can do. | 6 | +1 |
| `composure-2` | Worth | 5 | That doesn’t define me, and I’m not going to treat it like it does. | 6 | +1 |
| `composure-9` | Bought | 3 | A good feeling doesn’t change my judgment here. | 6 | +3 |
| `gravitas-2` | Inside | 3 | I may feel the pressure, but I’m going to stay steady for the room. | 6 | +3 |
| `gravitas-6` | Fold | 4 | I’m not here to fight power. I’m here to stay with the facts. | 6 | +2 |
| `gravitas-7` | Upright | 5 | Whatever happens, we’ll meet it honestly and stay steady. | 6 | +1 |
| `gravitas-8` | Unwind | 4 | Bring it back to the consequence we can’t undo. | 6 | +2 |
| `stage-4` | run | 6 | The nerves don’t get to run this room. I do. | 6 | 0 |
| `stage-6` | fall | 5 | The recovery is the point. Let’s keep going. | 6 | +1 |
| `stage-8` | believe | 5 | You walked in as a crowd. I hope you leave feeling personally responsible for what happens next. | 6 | +1 |
| `stage-11` | raw | 6 | Unscripted beats polished when the room is right. Lucky us. | 6 | 0 |

## Рейтинг батчей по среднему нижнему баллу (худшие сверху)

| # | Батч | Название | Ср. мин | Слабых ≤6 |
|---|---|---|---|---|
| 1 | `stage-3` | Держаться на камеру / в записи | 5.00 | 9/9 |
| 2 | `composure-9` | Остаться собой под лестью/манипуляцией | 5.22 | 6/9 |
| 3 | `gravitas-2` | Говорить с весом, когда внутри страшно | 5.22 | 7/9 |
| 4 | `gravitas-9` | Командовать через спокойствие и экономию слов | 5.22 | 8/9 |
| 5 | `pitch-3` | Прямая просьба | 5.44 | 7/9 |
| 6 | `stage-1` | Открыть выступление, схватить зал | 5.44 | 5/9 |
| 7 | `composure-1` | Не дать себя спровоцировать | 5.56 | 7/9 |
| 8 | `gravitas-7` | Дать уверенность, когда исход неизвестен | 5.56 | 7/9 |
| 9 | `gravitas-8` | Остановить опасную эскалацию словом | 5.56 | 6/9 |
| 10 | `gravitas-6` | Держать рамку против ранга/угрозы/силы | 5.67 | 6/9 |
| 11 | `stage-6` | Восстановиться после провала на сцене | 5.67 | 7/9 |
| 12 | `intimacy-10` | Ревность без обвинения | 5.78 | 6/9 |
| 13 | `stage-2` | Командовать сценой (тело/голос/пауза) | 5.78 | 6/9 |
| 14 | `stage-5` | Враждебные вопросы из зала | 5.78 | 7/9 |
| 15 | `stage-8` | Закрыть мощно, дать унести | 5.78 | 5/9 |
| 16 | `pitch-1` | Крючок | 5.89 | 5/9 |
| 17 | `intimacy-12` | Желание и тепло без клише | 5.89 | 7/9 |
| 18 | `lead-11` | Задать планку / позвать к лучшему | 5.89 | 6/9 |
| 19 | `composure-3` | Держаться, когда унижают публично | 5.89 | 6/9 |
| 20 | `stage-11` | Импровизировать, когда план рухнул | 5.89 | 7/9 |
| 21 | `composure-2` | Принять оскорбление с достоинством | 6.00 | 6/9 |
| 22 | `intimacy-7` | Назвать уязвимость как силу | 6.11 | 5/9 |
| 23 | `lead-8` | Разрулить чужой конфликт | 6.11 | 5/9 |
| 24 | `composure-5` | Не оправдываться под давлением | 6.11 | 7/9 |
| 25 | `composure-6` | Уйти из токсичного разговора с достоинством | 6.11 | 5/9 |
| 26 | `composure-7` | Держать паузу под напором | 6.11 | 6/9 |
| 27 | `gravitas-10` | Завершить кризис, посадить самолёт | 6.11 | 5/9 |
| 28 | `stage-4` | Совладать со сценическим страхом вживую | 6.11 | 6/9 |
| 29 | `flirt-8` | Читать и отвечать на сигналы | 6.22 | 6/9 |
| 30 | `lead-10` | Отдать признание, поднять других | 6.22 | 6/9 |
| 31 | `gravitas-1` | Взять командование, когда всё горит | 6.33 | 4/9 |
| 32 | `gravitas-4` | Не дрогнуть под шквалом враждебных вопросов | 6.33 | 5/9 |
| 33 | `stage-7` | История, которая держит зал | 6.33 | 4/9 |
| 34 | `charisma-2` | Открыть разговор с незнакомцем | 6.44 | 4/9 |
| 35 | `flirt-3` | Удержать заряженный момент | 6.44 | 4/9 |
| 36 | `intimacy-8` | Принять критику не защищаясь | 6.44 | 5/9 |
| 37 | `lead-1` | Взять комнату без мандата | 6.44 | 4/9 |
| 38 | `composure-8` | Ответить на неуважение, не опускаясь | 6.44 | 5/9 |
| 39 | `gravitas-5` | Признать катастрофу, не теряя командования | 6.44 | 5/9 |
| 40 | `stage-10` | Сделать момент личным с большой аудиторией | 6.44 | 6/9 |
| 41 | `stage-9` | Под софитами / вниманием прессы | 6.56 | 4/9 |
| 42 | `flirt-6` | Пригласить с зарядом | 6.67 | 3/9 |
| 43 | `intimacy-2` | Не сорваться, когда задели | 6.67 | 4/9 |
| 44 | `intimacy-9` | Разговор об ожиданиях и будущем | 6.67 | 4/9 |
| 45 | `gravitas-3` | Сделать необратимый звонок под неопределённостью | 6.67 | 3/9 |
| 46 | `charisma-7` | Комплимент со статусом | 6.78 | 5/9 |
| 47 | `flirt-7` | Принять или дать отказ изящно | 6.78 | 4/9 |
| 48 | `intimacy-1` | Поднять трудную тему | 6.78 | 4/9 |
| 49 | `intimacy-5` | Поставить границу с близким | 6.78 | 4/9 |
| 50 | `lead-2` | Повести за идеей | 6.78 | 4/9 |
| 51 | `lead-5` | Призвать к ответственности без молотка | 6.78 | 3/9 |
| 52 | `composure-4` | Сохранить лицо после ошибки | 6.78 | 4/9 |
| 53 | `charisma-4` | Держать стол | 6.89 | 4/9 |
| 54 | `flirt-10` | Перевести флирт в свидание | 6.89 | 4/9 |
| 55 | `intimacy-11` | Заряженный разговор с семьёй | 6.89 | 3/9 |
| 56 | `composure-10` | Сказать «не знаю» без потери лица | 6.89 | 3/9 |
| 57 | `lead-3` | Стать спокойствием в кризисе | 7.00 | 3/9 |
| 58 | `lead-4` | Возразить старшему без бунта | 7.00 | 3/9 |
| 59 | `lead-6` | Признать промах, не теряя авторитета | 7.00 | 3/9 |
| 60 | `lead-7` | Заступиться за своего, принять удар | 7.00 | 2/9 |
| 61 | `charisma-3` | Сделать собеседника главным | 7.11 | 3/9 |
| 62 | `flirt-5` | Поднять накал, не форсируя | 7.11 | 2/9 |
| 63 | `flirt-9` | Держать загадку | 7.11 | 3/9 |
| 64 | `composure-11` | Держать достоинство в проигрыше/отказе | 7.11 | 2/9 |
| 65 | `charisma-6` | Остроумие и подколка | 7.22 | 2/9 |
| 66 | `charisma-9` | Спасти неловкий момент | 7.22 | 3/9 |
| 67 | `charisma-11` | Возобновить связь после молчания | 7.22 | 3/9 |
| 68 | `flirt-4` | Сделать так, чтобы почувствовала себя единственной | 7.22 | 1/9 |
| 69 | `lead-9` | Сообщить плохую новость команде | 7.22 | 3/9 |
| 70 | `intimacy-4` | Извиниться по-настоящему | 7.33 | 0/9 |
| 71 | `intimacy-6` | Быть рядом в чужой боли | 7.33 | 1/9 |
| 72 | `pitch-2` | Заострить проблему | 7.44 | 2/9 |
| 73 | `charisma-1` | Войти в комнату | 7.44 | 2/9 |
| 74 | `flirt-1` | Обозначить интерес | 7.44 | 2/9 |
| 75 | `intimacy-3` | Починить после ссоры | 7.44 | 1/9 |
| 76 | `charisma-8` | Красивый выход из разговора | 7.56 | 2/9 |
| 77 | `charisma-10` | Представить людей | 7.56 | 1/9 |
| 78 | `batch-3` | Эмпатия → присутствие | 7.78 | 1/9 |
| 79 | `negotiation-1` | Торг | 7.78 | 1/9 |
| 80 | `leadership-1` | Обратная связь | 7.78 | 0/9 |
| 81 | `negotiation-2` | Закрыть сделку | 7.89 | 0/9 |
| 82 | `repair-1` | Помириться | 8.00 | 1/9 |
| 83 | `flirt-2` | Заряженная пикировка | 8.00 | 0/9 |
| 84 | `pressure-1` | Под давлением | 8.11 | 0/9 |
| 85 | `charisma-5` | Рассказать историю | 8.11 | 0/9 |
| 86 | `leadership-2` | Делегировать | 8.33 | 0/9 |
| 87 | `batch` | Несогласие | 8.44 | 0/9 |
| 88 | `requests-1` | Плохие новости | 8.44 | 0/9 |
| 89 | `batch-2` | Узнать мнение | 8.78 | 0/9 |
| 90 | `close-meeting` | Финал встречи | 8.80 | 0/10 |

## Батчи, где отсеивать нечего (11)

`close-meeting`, `batch-2`, `batch`, `requests-1`, `leadership-2`, `pressure-1`, `charisma-5`, `flirt-2`, `negotiation-2`, `leadership-1`, `intimacy-4`
